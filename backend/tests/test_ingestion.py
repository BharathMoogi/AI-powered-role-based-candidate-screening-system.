"""
Unit and integration test for the Knowledge Ingestion Pipeline.
"""

import os
import sys
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pypdf
from app.services.ingestion import (
    RecursiveTokenChunker,
    EmbeddingGenerator,
    KnowledgeIngestionService,
    ingest_pdf,
    count_tokens
)
from app.services.vector_db import get_or_create_collection


def create_sample_pdf(filepath: Path):
    """Generates a small multi-page test PDF for verification."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    
    page1_text = """Chapter 1: Supervised Learning Foundations
Machine learning is a subset of artificial intelligence that focuses on building applications that learn from data.
In supervised learning, algorithms are trained using labeled examples, such as an input where the desired output label is known.
Decision Tree learning is one of the most widely used inductive inference algorithms. It approximates discrete-valued target functions
in which the learned function is represented by a decision tree. Trees can also be re-represented as sets of if-then rules to improve
human readability. The algorithm searches a completely expressive hypothesis space, using heuristics such as Information Gain and
Entropy to guide greedy top-down recursive partitioning."""

    page2_text = """Chapter 4: Artificial Neural Networks
Artificial neural networks (ANNs) provide a general, practical method for learning real-valued, discrete-valued, and vector-valued
functions from examples. Algorithms such as Gradient Descent and Backpropagation dynamically adjust the connection weights
to minimize the squared error between the network output values and the target values for these outputs.
Feedforward networks with hidden units can represent nonlinear decision surfaces of arbitrary complexity. Regularization methods
such as weight decay, dropout, and early stopping are essential to prevent overfitting on complex training sets."""

    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R 4 0 R]/Count 2>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 5 0 R/Resources<</Font<</F1 7 0 R>>>>>>endobj\n"
        b"4 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 6 0 R/Resources<</Font<</F1 7 0 R>>>>>>endobj\n"
        b"5 0 obj<</Length " + str(len(page1_text) + 50).encode() + b">>stream\nBT\n/F1 12 Tf\n50 700 Td\n(" + page1_text.replace('\n', ' ').encode('latin-1') + b") Tj\nET\nendstream\nendobj\n"
        b"6 0 obj<</Length " + str(len(page2_text) + 50).encode() + b">>stream\nBT\n/F1 12 Tf\n50 700 Td\n(" + page2_text.replace('\n', ' ').encode('latin-1') + b") Tj\nET\nendstream\nendobj\n"
        b"7 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
        b"xref\n0 8\n0000000000 65535 f\n0000000009 00000 n\n0000000056 00000 n\n0000000111 00000 n\n0000000212 00000 n\n0000000313 00000 n\n0000000800 00000 n\n0000001200 00000 n\ntrailer<</Size 8/Root 1 0 R>>\nstartxref\n1300\n%%EOF\n"
    )

    filepath.write_bytes(pdf_content)


def test_chunker_logic():
    print("[TEST] Running Chunker tests...")
    chunker = RecursiveTokenChunker(chunk_size_tokens=50, chunk_overlap_tokens=10)
    pages = [
        (1, "Artificial intelligence and machine learning provide statistical learning models. Supervised models learn from labeled examples."),
        (2, "Neural networks learn representations through backpropagation and gradient descent optimization.")
    ]
    chunks = chunker.chunk_document_pages(pages)
    assert len(chunks) >= 2, f"Expected >= 2 chunks, got {len(chunks)}"
    assert chunks[0]["page_number"] == 1
    assert "token_count" in chunks[0]
    print(f"  Passed! Generated {len(chunks)} chunks with proper metadata.")


def test_ingestion_pipeline():
    print("[TEST] Running Ingestion Pipeline & Idempotency tests...")
    test_pdf_path = BACKEND_DIR / "tests" / "sample_ml_book.pdf"
    test_pdf_path.parent.mkdir(parents=True, exist_ok=True)
    create_sample_pdf(test_pdf_path)

    role = "Machine Learning Engineer"
    source_book = "Tom Mitchell ML Test"

    # Test Run 1: Ingest
    res1 = ingest_pdf(
        pdf_path=str(test_pdf_path),
        role=role,
        source_book=source_book,
        force=True
    )
    print(f"  Run 1 (Initial Ingest): status={res1.get('status')}, chunks={res1.get('chunks_count')}")
    assert res1.get("status") == "success"
    assert res1.get("chunks_count") > 0

    # Test Run 2: Idempotency check (should skip)
    res2 = ingest_pdf(
        pdf_path=str(test_pdf_path),
        role=role,
        source_book=source_book,
        force=False
    )
    print(f"  Run 2 (Idempotent Check): status={res2.get('status')}, reason={res2.get('reason')}")
    assert res2.get("status") == "skipped"

    # Test Run 3: Force Re-ingest
    res3 = ingest_pdf(
        pdf_path=str(test_pdf_path),
        role=role,
        source_book=source_book,
        force=True
    )
    print(f"  Run 3 (Force Re-ingest): status={res3.get('status')}, chunks={res3.get('chunks_count')}")
    assert res3.get("status") == "success"

    # Test ChromaDB query metadata for specific source_book
    collection = get_or_create_collection("role_knowledge_base")
    items = collection.get(
        where={"$and": [{"role": {"$eq": role}}, {"source_book": {"$eq": source_book}}]},
        include=["metadatas", "documents"]
    )
    assert len(items["ids"]) > 0, "Expected chunks for ingested source book"
    meta = items["metadatas"][0]
    print(f"  ChromaDB verified: found {len(items['ids'])} items with metadata {meta}")
    assert meta["role"] == role
    assert meta["source_book"] == source_book
    assert "page_number" in meta
    assert "chunk_index" in meta

    # Clean up test file
    if test_pdf_path.exists():
        test_pdf_path.unlink()

    print("[SUCCESS] All tests passed!")


if __name__ == "__main__":
    test_chunker_logic()
    test_ingestion_pipeline()
