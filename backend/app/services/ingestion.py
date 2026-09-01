"""
Knowledge Ingestion Pipeline Service

This module handles:
1. Extracting text page-by-page from role-specific PDF textbooks and rubrics.
2. Recursive character/token chunking (~600 tokens with 15% overlap).
3. Vector embedding generation (OpenAI text-embedding-3-small with fallback support).
4. Idempotent storage into ChromaDB with rich metadata (role, source_book, chunk_index, page_number).
"""

import os
import re
import uuid
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pypdf
from app.config import settings
from app.services.vector_db import get_or_create_collection

logger = logging.getLogger("ingestion_service")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


# ============================================================================
# Tokenizer & Splitting Helpers
# ============================================================================

try:
    import tiktoken
    _TIKTOKEN_AVAILABLE = True
    _ENCODER = tiktoken.get_encoding("cl100k_base")
except Exception:
    _TIKTOKEN_AVAILABLE = False
    _ENCODER = None


def count_tokens(text: str) -> int:
    """
    Counts tokens accurately using tiktoken cl100k_base, with ~4 chars/token fallback.
    """
    if _TIKTOKEN_AVAILABLE and _ENCODER:
        return len(_ENCODER.encode(text, disallowed_special=()))
    return max(1, len(text) // 4)


class RecursiveTokenChunker:
    """
    Recursive chunker that breaks down text using natural language boundaries
    until each chunk satisfies the target token limit with specified overlap.

    ============================================================================
    CHOICE OF 600 TOKENS PER CHUNK WITH ~15% OVERLAP:
    ============================================================================
    1. Semantic Density:
       Technical domain literature (such as machine learning textbooks, system
       design docs, and interview rubrics) requires sufficient context to capture
       full algorithms, mathematical formulas, or conceptual explanations.
       600 tokens (~2400 characters / 400-450 words) is the optimal window to
       preserve a complete concept without diluting vector focus.
    2. Embedding Retrieval Accuracy:
       Smaller chunks (e.g. 150-200 tokens) fragment complex concepts across
       multiple embeddings, leading to incomplete RAG context retrieval.
       Larger chunks (e.g. 1200+ tokens) reduce embedding specificity, lowering
       cosine similarity for targeted interview question generation.
    3. Boundary Preservation (15% Overlap / ~90 tokens):
       ~15% overlap ensures definitions, code snippets, or proof steps spanning
       chunk boundaries are not truncated or lost during retrieval.
    ============================================================================
    """

    def __init__(
        self,
        chunk_size_tokens: int = 600,
        chunk_overlap_tokens: int = 90, # ~15% of 600
        separators: Optional[List[str]] = None
    ):
        self.chunk_size_tokens = chunk_size_tokens
        self.chunk_overlap_tokens = chunk_overlap_tokens
        self.separators = separators or ["\n\n", "\n", ". ", "? ", "! ", "; ", " ", ""]

    def _split_text(self, text: str, separators: List[str]) -> List[str]:
        """Recursively splits text using the highest-level valid separator."""
        final_chunks: List[str] = []
        separator = separators[-1]
        new_separators = []

        for i, sep in enumerate(separators):
            if sep == "":
                separator = ""
                break
            if sep in text:
                separator = sep
                new_separators = separators[i + 1:]
                break

        splits = text.split(separator) if separator else list(text)

        good_splits: List[str] = []
        for s in splits:
            if not s:
                continue
            if separator and separator != "":
                piece = s + separator
            else:
                piece = s

            if count_tokens(piece) <= self.chunk_size_tokens:
                good_splits.append(piece)
            else:
                if new_separators:
                    other_splits = self._split_text(piece, new_separators)
                    good_splits.extend(other_splits)
                else:
                    good_splits.append(piece)

        # Merge small splits up to chunk_size_tokens with overlap
        merged_chunks: List[str] = []
        current_chunk: List[str] = []
        current_tokens = 0

        for piece in good_splits:
            piece_tokens = count_tokens(piece)
            if current_tokens + piece_tokens <= self.chunk_size_tokens:
                current_chunk.append(piece)
                current_tokens += piece_tokens
            else:
                if current_chunk:
                    chunk_text = "".join(current_chunk).strip()
                    if chunk_text:
                        merged_chunks.append(chunk_text)
                    
                    # Create overlap buffer from previous chunks
                    overlap_buffer: List[str] = []
                    overlap_tokens = 0
                    for prev_piece in reversed(current_chunk):
                        prev_tokens = count_tokens(prev_piece)
                        if overlap_tokens + prev_tokens <= self.chunk_overlap_tokens:
                            overlap_buffer.insert(0, prev_piece)
                            overlap_tokens += prev_tokens
                        else:
                            break
                    current_chunk = overlap_buffer + [piece]
                    current_tokens = sum(count_tokens(p) for p in current_chunk)
                else:
                    current_chunk = [piece]
                    current_tokens = piece_tokens

        if current_chunk:
            chunk_text = "".join(current_chunk).strip()
            if chunk_text:
                merged_chunks.append(chunk_text)

        return merged_chunks

    def chunk_document_pages(self, pages: List[Tuple[int, str]]) -> List[Dict[str, Any]]:
        """
        Splits a list of (page_number, text) tuples into chunks while tracking the originating page.
        """
        chunks_with_metadata: List[Dict[str, Any]] = []
        chunk_idx = 0

        for page_num, page_text in pages:
            cleaned_text = page_text.strip()
            if not cleaned_text:
                continue

            page_chunks = self._split_text(cleaned_text, self.separators)
            for text_chunk in page_chunks:
                if len(text_chunk.strip()) < 20:  # Skip trivial/empty whitespace chunks
                    continue
                chunks_with_metadata.append({
                    "chunk_index": chunk_idx,
                    "page_number": page_num,
                    "text": text_chunk.strip(),
                    "token_count": count_tokens(text_chunk)
                })
                chunk_idx += 1

        return chunks_with_metadata


# ============================================================================
# Embedding Generator
# ============================================================================

class EmbeddingGenerator:
    """
    Generates dense embeddings for chunks.
    
    CHOICE OF OPENAI text-embedding-3-small:
    - Superior MTEB multilingual & technical retrieval benchmarks.
    - Low dimensionality (1536) and latency, with exceptional cost efficiency ($0.02/1M tokens).
    - If no API key is set, falls back to Gemini text-embedding-004 or local deterministic embeddings for test environments.
    """

    def __init__(self):
        self.openai_api_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", "")
        self.gemini_api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
        self._openai_client = None

        if self.openai_api_key:
            try:
                from openai import OpenAI
                self._openai_client = OpenAI(api_key=self.openai_api_key)
            except Exception as e:
                logger.warning(f"OpenAI client initialization failed: {e}")

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generates vector embeddings for a list of text strings in batches.
        """
        if not texts:
            return []

        # 1. Try OpenAI text-embedding-3-small
        if self._openai_client:
            try:
                # Process in batches of 100 to avoid request size limits
                batch_size = 100
                all_embeddings: List[List[float]] = []
                for i in range(0, len(texts), batch_size):
                    batch = texts[i:i + batch_size]
                    response = self._openai_client.embeddings.create(
                        model="text-embedding-3-small",
                        input=batch
                    )
                    batch_embeddings = [item.embedding for item in response.data]
                    all_embeddings.extend(batch_embeddings)
                return all_embeddings
            except Exception as e:
                logger.warning(f"OpenAI embedding generation failed, trying fallback: {e}")

        # 2. Try Gemini text-embedding-004 if Gemini key available
        if self.gemini_api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_api_key)
                embeddings = []
                for text in texts:
                    res = genai.embed_content(
                        model="models/text-embedding-004",
                        content=text,
                        task_type="retrieval_document"
                    )
                    embeddings.append(res['embedding'])
                return embeddings
            except Exception as e:
                logger.warning(f"Gemini embedding generation failed: {e}")

        # 3. Deterministic normalized embedding fallback for development/testing without keys
        logger.info("Using built-in feature embedding generator for offline/development environment.")
        return [self._local_fallback_embedding(t) for t in texts]

    def _local_fallback_embedding(self, text: str, dim: int = 1536) -> List[float]:
        """
        Generates a deterministic normalized pseudo-embedding based on text hashing,
        allowing the entire pipeline and ChromaDB integration tests to run offline.
        """
        import hashlib
        import math

        vector = [0.0] * dim
        words = re.findall(r"\w+", text.lower())
        if not words:
            return vector

        for word in words:
            h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
            idx = h % dim
            vector[idx] += 1.0

        # L2 normalize
        norm = math.sqrt(sum(x * x for x in vector))
        if norm > 0:
            vector = [x / norm for x in vector]
        return vector


# ============================================================================
# PDF Extractor
# ============================================================================

class PDFExtractor:
    """Extracts raw text per page from PDF files."""

    @staticmethod
    def extract_pages(pdf_path: str) -> List[Tuple[int, str]]:
        """
        Reads a PDF file and returns a list of (page_number, text) tuples.
        Page numbers are 1-indexed.
        """
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        reader = pypdf.PdfReader(str(path))
        pages: List[Tuple[int, str]] = []

        for idx, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            pages.append((idx, text))

        return pages


# ============================================================================
# Main Knowledge Ingestion Pipeline Service
# ============================================================================

class KnowledgeIngestionService:
    """
    Ingestion service that coordinates PDF parsing, chunking, embedding,
    and idempotent insertion into ChromaDB.
    """

    def __init__(self, collection_name: str = "role_knowledge_base"):
        self.collection_name = collection_name
        self.chunker = RecursiveTokenChunker(chunk_size_tokens=600, chunk_overlap_tokens=90)
        self.embedder = EmbeddingGenerator()

    def check_existing(self, role: str, source_book: str) -> int:
        """
        Checks how many chunks are already indexed for the given role and source book.
        Used for idempotency.
        """
        collection = get_or_create_collection(self.collection_name)
        try:
            results = collection.get(
                where={"$and": [{"role": {"$eq": role}}, {"source_book": {"$eq": source_book}}]},
                include=["metadatas"]
            )
            return len(results.get("ids", []))
        except Exception:
            # Fallback for simple where syntax
            try:
                results = collection.get(
                    where={"role": role},
                    include=["metadatas"]
                )
                matching = [
                    m for m in (results.get("metadatas") or [])
                    if m.get("source_book") == source_book
                ]
                return len(matching)
            except Exception as e:
                logger.warning(f"Error checking existing documents: {e}")
                return 0

    def delete_existing(self, role: str, source_book: str) -> int:
        """
        Deletes existing chunks for a role and source book before re-ingestion.
        """
        collection = get_or_create_collection(self.collection_name)
        try:
            results = collection.get(
                where={"$and": [{"role": {"$eq": role}}, {"source_book": {"$eq": source_book}}]}
            )
            ids_to_delete = results.get("ids", [])
            if ids_to_delete:
                collection.delete(ids=ids_to_delete)
                logger.info(f"Deleted {len(ids_to_delete)} existing chunks for '{source_book}' ({role}).")
            return len(ids_to_delete)
        except Exception as e:
            logger.warning(f"Error deleting existing chunks: {e}")
            return 0

    def ingest_pdf(
        self,
        pdf_path: str,
        role: str,
        source_book: Optional[str] = None,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Main entrypoint for ingesting a PDF.

        Args:
            pdf_path: Path to the PDF document.
            role: Target candidate role (e.g. 'Machine Learning Engineer', 'Backend Engineer').
            source_book: Name of the textbook or document (defaults to filename).
            force: If True, overwrite and re-ingest if already present.

        Returns:
            Dictionary containing ingestion statistics.
        """
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            raise FileNotFoundError(f"PDF file not found at: {pdf_path}")

        if not source_book:
            source_book = pdf_file.stem.replace("_", " ").replace("-", " ").title()

        logger.info(f"Starting ingestion: Book='{source_book}' | Role='{role}' | File='{pdf_file.name}'")

        # 1. Idempotency Check
        existing_count = self.check_existing(role=role, source_book=source_book)
        if existing_count > 0 and not force:
            logger.info(f"Document '{source_book}' for role '{role}' is already ingested ({existing_count} chunks). Skipping.")
            return {
                "status": "skipped",
                "reason": "already_ingested",
                "role": role,
                "source_book": source_book,
                "chunks_count": existing_count,
                "force": False
            }

        if existing_count > 0 and force:
            self.delete_existing(role=role, source_book=source_book)

        # 2. Extract PDF text per page
        pages = PDFExtractor.extract_pages(str(pdf_file))
        logger.info(f"Extracted {len(pages)} pages from {pdf_file.name}")

        # 3. Recursive chunking (~600 tokens with ~15% overlap)
        chunks = self.chunker.chunk_document_pages(pages)
        if not chunks:
            logger.warning("No valid text content extracted from document.")
            return {
                "status": "empty",
                "role": role,
                "source_book": source_book,
                "chunks_count": 0
            }

        logger.info(f"Generated {len(chunks)} chunks (~600 tokens/chunk, 15% overlap)")

        # 4. Generate Embeddings
        chunk_texts = [c["text"] for c in chunks]
        embeddings = self.embedder.generate_embeddings(chunk_texts)

        # 5. Prepare ChromaDB records
        # Slugify identifiers for deterministic, unique chunk IDs
        source_slug = re.sub(r"[^a-zA-Z0-9]+", "_", source_book.lower()).strip("_")
        role_slug = re.sub(r"[^a-zA-Z0-9]+", "_", role.lower()).strip("_")

        ids: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        documents: List[str] = []

        for chunk in chunks:
            chunk_id = f"{role_slug}_{source_slug}_c{chunk['chunk_index']:04d}_p{chunk['page_number']}"
            ids.append(chunk_id)
            documents.append(chunk["text"])
            metadatas.append({
                "role": role,
                "source_book": source_book,
                "chunk_index": chunk["chunk_index"],
                "page_number": chunk["page_number"],
                "token_count": chunk["token_count"]
            })

        # 6. Upsert into ChromaDB in batches
        collection = get_or_create_collection(self.collection_name)
        batch_size = 200
        for i in range(0, len(ids), batch_size):
            collection.upsert(
                ids=ids[i:i + batch_size],
                embeddings=embeddings[i:i + batch_size],
                documents=documents[i:i + batch_size],
                metadatas=metadatas[i:i + batch_size]
            )

        logger.info(f"Successfully ingested {len(ids)} chunks for '{source_book}' ({role}) into ChromaDB collection '{self.collection_name}'.")

        return {
            "status": "success",
            "role": role,
            "source_book": source_book,
            "pages_count": len(pages),
            "chunks_count": len(ids),
            "collection": self.collection_name,
            "sample_chunk_id": ids[0] if ids else None
        }


# Module-level convenience function
def ingest_pdf(
    pdf_path: str,
    role: str,
    source_book: Optional[str] = None,
    force: bool = False
) -> Dict[str, Any]:
    """
    Convenience function to run the PDF knowledge ingestion pipeline.
    """
    service = KnowledgeIngestionService()
    return service.ingest_pdf(
        pdf_path=pdf_path,
        role=role,
        source_book=source_book,
        force=force
    )
