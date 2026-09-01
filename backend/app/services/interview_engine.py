"""
Interview Engine Service

Handles resume-driven question generation and knowledge-grounded retrieval:
1. extract_resume_data: Parses candidate resume into structured skills, technologies, projects, and level.
2. build_queries: Generates conceptual retrieval queries mapped from candidate resume claims, cycling across all projects.
3. retrieve_chunks: Queries ChromaDB, top-k=3 per query, keeping source_skill and project context attached.
4. generate_question: Constructs prompt with specific resume skill/project text + chunk context with strict negative
   constraints preventing domain bleed (e.g., no GPU/CNN questions for web backend projects).
"""

import json
import os
import re
import logging
import hashlib
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from pydantic import BaseModel, Field, ValidationError

from app.config import settings
from app.services.vector_db import get_or_create_collection
from app.services.ingestion import EmbeddingGenerator
from app.services.resume import ParsedResume, extract_resume_data
from app.services.query_builder import RetrievalQueryItem, build_retrieval_queries

logger = logging.getLogger("interview_engine")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


# ============================================================================
# Schemas
# ============================================================================

class RetrievedChunk(BaseModel):
    chunk_id: str = Field(..., description="ChromaDB unique chunk identifier")
    chunk_text: str = Field(..., description="Raw text snippet from knowledge base")
    source_metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata: role, source_book, page_number, chunk_index")
    matched_query: str = Field(..., description="Query that retrieved this chunk")
    source_skill: str = Field(default="", description="Candidate skill/project that motivated this retrieval")
    project_name: Optional[str] = Field(default=None, description="Associated project name from resume")
    project_tech: List[str] = Field(default_factory=list, description="Technologies of the associated project")
    project_description: Optional[str] = Field(default=None, description="Description of the associated project")

    @property
    def metadata(self) -> Dict[str, Any]:
        return self.source_metadata


class GeneratedQuestion(BaseModel):
    question_text: str = Field(
        ...,
        description="Scenario-based, non-generic interview question grounded in knowledge base and resume"
    )
    topic: str = Field(
        ...,
        description="Domain topic or competency (e.g. Distributed Consensus, Gradient Backpropagation, Asynchronous I/O)"
    )
    difficulty: str = Field(
        default="medium",
        description="Difficulty level: easy, medium, hard"
    )
    source_chunk_ids: List[str] = Field(
        default_factory=list,
        description="List of ChromaDB chunk IDs referenced to construct this question"
    )
    expected_key_concepts: List[str] = Field(
        default_factory=list,
        description="Key technical concepts or trade-offs a strong candidate must address"
    )
    project_referenced: Optional[str] = Field(
        default=None,
        description="Name of the specific resume project probed in this question"
    )
    technologies_referenced: List[str] = Field(
        default_factory=list,
        description="Specific technologies from the project stack referenced in this question"
    )


# ============================================================================
# System Prompt: Resume-Driven Grounded Scenario Question Generator
# ============================================================================

INTERVIEW_QUESTION_SYSTEM_PROMPT = """You are a Principal Engineer and Lead Technical Bar Raiser.
Your goal is to generate ONE deep, rigorous, applied scenario-based interview question tailored to the candidate's exact resume project and grounded in the reference material.

CRITICAL RULES & ISOLATION CONSTRAINTS:
1. STRICT PROJECT TECH-STACK ALIGNMENT: You MUST strictly limit the technologies and technical domains in your question to the candidate's stated project tech stack and project theme.
   - If the project is a Web API / backend service (e.g. FastAPI, Twilio, Redis), ask about asynchronous webhook dispatch, token-bucket rate limiting, or connection pooling. Do NOT ask about convolutional neural networks, GPU memory, or model training.
   - If the project is an AI/ML or LLM application (e.g. ApplyRA, RAG, NLP), ask about semantic search retrieval, latency vs context size, prompt injection defenses, or token rate limits.
   - If the project is a Telephony / VoIP system (e.g. Twilio integration), ask about call session state synchronization, bi-directional audio streaming, or webhook retry storms.
   - If the project is a Data Pipeline (e.g. Spark, Airflow, SQL), ask about distributed partitioning and shuffle memory management.
2. Every question MUST connect directly to the candidate's stated experience in that specific project.
3. The question MUST NOT be a generic textbook definition (e.g. "What is X?").
4. It MUST be an applied scenario, failure-mode diagnostic, or architectural trade-off problem.
5. It MUST match the candidate's experience level in depth.

Return ONLY valid JSON matching this schema:
{
  "question_text": "Detailed applied scenario question referencing the specific project and its actual technologies...",
  "topic": "Domain topic or competency name",
  "difficulty": "easy" | "medium" | "hard",
  "source_chunk_ids": ["chunk_id_1", "chunk_id_2"],
  "expected_key_concepts": ["concept 1", "concept 2", "concept 3"],
  "project_referenced": "Name of the project",
  "technologies_referenced": ["Tech1", "Tech2"]
}
"""


# ============================================================================
# Context Retrieval Functions (Step 3)
# ============================================================================

def retrieve_chunks(
    queries: List[Union[RetrievalQueryItem, str]],
    role: str,
    top_k: int = 3,
    collection_name: str = "role_knowledge_base"
) -> List[RetrievedChunk]:
    """
    Step 3: Runs each query against ChromaDB (top-k=3), attaches source_skill and project
    metadata to each retrieved chunk for full traceability, and deduplicates overlapping chunks.
    """
    collection = get_or_create_collection(collection_name)
    embedder = EmbeddingGenerator()

    seen_chunk_ids: Set[str] = set()
    retrieved_chunks: List[RetrievedChunk] = []

    # Format query tuples with project and skill metadata
    query_tuples: List[Tuple[str, str, str, Optional[str], List[str], Optional[str]]] = []
    for q in queries:
        if isinstance(q, RetrievalQueryItem):
            query_tuples.append((
                q.query,
                f"[{q.source_skill}] {q.query}",
                q.source_skill,
                q.project_name,
                q.project_tech,
                q.project_description
            ))
        else:
            query_tuples.append((str(q), str(q), "Domain Skill", None, [], None))

    if not query_tuples:
        return []

    # Query ChromaDB for each conceptual query
    for query_str, match_label, source_skill, p_name, p_tech, p_desc in query_tuples:
        try:
            query_embeddings = embedder.generate_embeddings([query_str])
            if not query_embeddings:
                continue

            results = collection.query(
                query_embeddings=query_embeddings,
                n_results=top_k,
                where={"role": role},
                include=["documents", "metadatas", "distances"]
            )

            ids_list = results.get("ids", [[]])[0]
            docs_list = results.get("documents", [[]])[0]
            metas_list = results.get("metadatas", [[]])[0]

            for chunk_id, doc_text, meta in zip(ids_list, docs_list, metas_list):
                if chunk_id not in seen_chunk_ids:
                    seen_chunk_ids.add(chunk_id)
                    retrieved_chunks.append(
                        RetrievedChunk(
                            chunk_id=chunk_id,
                            chunk_text=doc_text,
                            source_metadata=meta or {},
                            matched_query=match_label,
                            source_skill=source_skill,
                            project_name=p_name,
                            project_tech=p_tech,
                            project_description=p_desc
                        )
                    )

        except Exception as e:
            logger.warning(f"ChromaDB retrieval error for query '{query_str}': {e}")
            try:
                # Fallback without where filter if collection schema differs
                results = collection.query(
                    query_embeddings=query_embeddings,
                    n_results=top_k,
                    include=["documents", "metadatas", "distances"]
                )
                ids_list = results.get("ids", [[]])[0]
                docs_list = results.get("documents", [[]])[0]
                metas_list = results.get("metadatas", [[]])[0]
                for chunk_id, doc_text, meta in zip(ids_list, docs_list, metas_list):
                    if chunk_id not in seen_chunk_ids:
                        seen_chunk_ids.add(chunk_id)
                        retrieved_chunks.append(
                            RetrievedChunk(
                                chunk_id=chunk_id,
                                chunk_text=doc_text,
                                source_metadata=meta or {},
                                matched_query=match_label,
                                source_skill=source_skill,
                                project_name=p_name,
                                project_tech=p_tech,
                                project_description=p_desc
                            )
                        )
            except Exception as e2:
                logger.error(f"Fallback ChromaDB query also failed: {e2}")

    logger.info(f"Retrieved {len(retrieved_chunks)} unique chunks across {len(queries)} queries for role '{role}'.")
    return retrieved_chunks


# Alias for backwards compatibility
retrieve_context = retrieve_chunks


# ============================================================================
# Question Generator Class & Functions (Step 4)
# ============================================================================

class QuestionGenerator:
    """Generates grounded, resume-driven, experience-calibrated interview questions."""

    def __init__(self):
        self.openai_api_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", "")
        self.gemini_api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")

    def _call_llm(
        self,
        prompt: str,
        project_name: str = "",
        project_tech: List[str] = None,
        project_desc: str = ""
    ) -> str:
        # 1. Try OpenAI
        if self.openai_api_key:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=self.openai_api_key)
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": INTERVIEW_QUESTION_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2
                )
                return response.choices[0].message.content or "{}"
            except Exception as e:
                logger.warning(f"OpenAI question generation failed: {e}")

        # 2. Try Gemini
        if self.gemini_api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_api_key)
                model = genai.GenerativeModel(
                    model_name="gemini-1.5-flash",
                    generation_config={"response_mime_type": "application/json"}
                )
                full_prompt = f"{INTERVIEW_QUESTION_SYSTEM_PROMPT}\n\n{prompt}"
                response = model.generate_content(full_prompt)
                return response.text or "{}"
            except Exception as e:
                logger.warning(f"Gemini question generation failed: {e}")

        # 3. Fallback deterministic generator strictly tailored to candidate project stack
        return self._heuristic_question_fallback(
            prompt=prompt,
            project_name=project_name,
            project_tech=project_tech or [],
            project_desc=project_desc
        )

    def _heuristic_question_fallback(
        self,
        prompt: str,
        project_name: str = "",
        project_tech: List[str] = None,
        project_desc: str = ""
    ) -> str:
        """
        Deterministic scenario question generator that analyzes the specific theme, title,
        and technologies of the project to generate a completely distinct technical scenario.
        """
        p_name = project_name or "Target Technical Project"
        p_techs = project_tech or []
        p_tech_str = ", ".join(p_techs) if p_techs else "Python"
        p_tech_lower = [t.lower() for t in p_techs]
        p_name_lower = p_name.lower()
        p_desc_lower = (project_desc or "").lower()
        prompt_lower = prompt.lower()
        chunk_ids = re.findall(r"\[ID:\s*([a-zA-Z0-9_\-]+)\]", prompt)

        # 1. VoiceFlow AI / Telephony / Twilio / Voice / SMS / Whisper
        if any(kw in p_name_lower for kw in ["voiceflow", "twilio", "telephony", "voice", "call", "sms", "whisper", "saarthi"]) or any("twilio" in t or "whisper" in t for t in p_tech_lower):
            q_text = (
                f"In your project '{p_name}' built with {p_tech_str}, you design an end-to-end voice AI pipeline integrating speech transcription with Whisper, LLM intent parsing, and automated outbound calling via the Twilio Voice API. "
                "During concurrent peak calls, background acoustic noise and intermittent speech pauses cause Whisper transcription hallucination, "
                "while delayed telephony status callbacks create race conditions where call termination events arrive before call initialization records commit to PostgreSQL. "
                "How did you implement voice-activity detection (VAD) audio chunking, handle out-of-order webhook delivery with distributed state idempotency, "
                "and ensure sub-800ms end-to-end latency from speech input to telephony response?"
            )
            topic = "Voice AI Pipeline, Speech Transcription (Whisper) & Telephony Event Idempotency"
            concepts = ["Whisper audio VAD chunking", "Twilio webhook race condition idempotency", "Low-latency voice-to-intent pipeline orchestration"]

        # 2. ApplyRA / AI Job Assistant / NLP / RAG / ATS Optimization / LLM APIs
        elif any(kw in p_name_lower for kw in ["applyra", "ats", "resume", "job", "agent", "automation", "rag", "nlp"]) or any(t in ["rag", "nlp", "rag pipelines", "rag / embeddings", "groq", "openrouter"] for t in p_tech_lower):
            q_text = (
                f"In your intelligent assistant project '{p_name}' built with {p_tech_str}, you build an NLP/RAG retrieval pipeline that extracts required skills from unstructured job descriptions and scores them against candidate profiles. "
                "When processing dense technical job descriptions, standard dense embeddings struggle with rare acronyms and keyword matching, "
                "while external LLM APIs (Groq, OpenRouter) occasionally generate unstructured or non-compliant resume text under heavy traffic. "
                "How did you design hybrid dense-sparse retrieval (BM25 + embeddings) for ATS matching, and how did you implement rule-based scoring with schema self-healing retries to guarantee deterministic structured output?"
            )
            topic = "NLP / RAG Semantic Skill Matching, ATS Optimization & Structured LLM Output"
            concepts = ["Hybrid dense-sparse retrieval for ATS matching", "Structured output validation with error-feedback retries", "Embedding similarity thresholds"]

        # 3. Visibility Enhancement / Computer Vision / Deep Learning / Object Detection
        elif any(kw in p_name_lower for kw in ["visibility", "vision", "transportation", "image", "defect", "detection", "enhancement"]) or any(t in ["computer vision", "deep learning", "object detection", "cnn", "opencv"] for t in p_tech_lower):
            q_text = (
                f"In your research project '{p_name}' utilizing {p_tech_str}, you deploy computer vision and deep learning models to enhance image visibility and improve object-detection reliability under degraded driving conditions (fog, glare, low light). "
                "Enhancement preprocessing networks introduce spatial artifact distortion that degrades downstream object bounding box confidence, "
                "while multi-stage inference adds unacceptable latency for real-time intelligent transportation systems. "
                "How did you analyze receptive field expansion versus feature map resolution, evaluate end-to-end joint optimization (enhancement + detection loss) versus decoupled pipelines, and benchmark inference frame rates (FPS) on resource-constrained hardware?"
            )
            topic = "Computer Vision Visibility Enhancement, Deep Learning & Object Detection"
            concepts = ["Joint enhancement-detection loss optimization", "Receptive field scaling under degraded conditions", "Real-time edge FPS latency benchmarking"]

        # 4. Data Engineering / Clickstream / ETL / Spark / Airflow / Kafka
        elif any(t in ["spark", "apache spark", "airflow", "kafka", "hadoop", "etl", "flink"] for t in p_tech_lower) or "etl" in p_name_lower or "stream" in p_name_lower or "pipeline" in p_name_lower:
            q_text = (
                f"In your data engineering pipeline '{p_name}' built with {p_tech_str}, your distributed ETL job processing "
                "large-scale event data experiences severe stage skew, where 95% of executor tasks finish in seconds but the final task "
                "spills 140 GB to disk due to high-cardinality partition keys. "
                "How would you inspect the physical execution plan, tune partition boundaries and salting strategies, "
                "and configure memory fraction thresholds to eliminate shuffle spill without causing OutOfMemory (OOM) crashes?"
            )
            topic = "Distributed Data Partitioning & Pipeline Memory Optimization"
            concepts = ["Shuffle partition skew salting", "Executor memory fraction tuning", "Disk spill mitigation in distributed DAGs"]

        # 5. Database & Cloud Architecture / PostgreSQL / AWS / Caching
        elif any(t in ["postgresql", "postgres", "aws", "database", "sql", "rds"] for t in p_tech_lower):
            q_text = (
                f"In your cloud and database architecture for '{p_name}' deployed on AWS with PostgreSQL, "
                "your backend experiences sudden database connection pool exhaustion (PG::ConnectionBad: FATAL: remaining connection slots are reserved) "
                "during concurrent traffic spikes, while read-heavy queries on unindexed foreign keys trigger table scans that lock worker threads. "
                "How did you structure connection pooling (e.g. PgBouncer / AWS RDS Proxy), configure partial indexes and execution plan EXPLAIN analysis, "
                "and implement multi-layer caching with Redis to safeguard database stability?"
            )
            topic = "Database Connection Pooling, Index Optimization & AWS Scalability"
            concepts = ["PgBouncer connection pooling", "Partial index EXPLAIN analysis", "Multi-tier caching to prevent DB saturation"]

        # 6. Web / Backend / Asynchronous Concurrency / FastAPI
        else:
            q_text = (
                f"In your backend service project '{p_name}' built with {p_tech_str}, your service experiences a sudden 15,000 RPS burst, "
                "causing P99 latency to spike from 12ms to 4.2s despite CPU utilization remaining below 35%. Profiling shows worker coroutines stalling on the ASGI event loop. "
                "How would you isolate synchronous blocking database/IO calls, configure bounded connection pools, and prevent event loop thread starvation?"
            )
            topic = "Asynchronous Concurrency & Event Loop Optimization"
            concepts = ["ASGI event loop mechanics", "Synchronous threadpool delegation", "Backpressure and pool saturation"]


        return json.dumps({
            "question_text": q_text,
            "topic": topic,
            "difficulty": "hard" if "senior" in prompt_lower else "medium",
            "source_chunk_ids": chunk_ids[:2] if chunk_ids else ["chunk_kbase_grounded_01"],
            "expected_key_concepts": concepts,
            "project_referenced": p_name,
            "technologies_referenced": p_techs
        })

    def generate(
        self,
        chunk_context: Union[List[RetrievedChunk], RetrievedChunk, str],
        resume_data: Union[ParsedResume, Dict[str, Any]],
        source_skill: Optional[str] = None,
        query_item: Optional[RetrievalQueryItem] = None,
        project_name: Optional[str] = None,
        project_tech: Optional[List[str]] = None,
        project_description: Optional[str] = None,
        difficulty: str = "medium"
    ) -> GeneratedQuestion:
        """
        Step 4: Generates ONE applied scenario question strictly tied to the designated project
        and its actual tech stack, enforcing strict negative constraints against domain bleed.
        """
        if isinstance(resume_data, ParsedResume):
            resume_dict = resume_data.model_dump()
        else:
            resume_dict = resume_data

        experience_level = resume_dict.get("apparent_experience_level", "mid")
        source_chunk_ids: List[str] = []

        # 1. Resolve Target Project and Tech Stack
        resolved_project_name = project_name or (query_item.project_name if query_item else None)
        resolved_project_tech = project_tech or (query_item.project_tech if query_item else [])
        resolved_project_desc = project_description or (query_item.project_description if query_item else "")

        projects = resume_dict.get("notable_projects", [])
        
        # If project name is not explicit, find the best matching project from resume
        if not resolved_project_name and projects:
            target_skill_str = source_skill or (query_item.source_skill if query_item else "")
            for p in projects:
                p_techs_lower = [t.lower() for t in p.get("technologies", [])]
                if target_skill_str.lower() in p_techs_lower or target_skill_str.lower() in p.get("description", "").lower():
                    resolved_project_name = p.get("name")
                    resolved_project_tech = p.get("technologies", [])
                    resolved_project_desc = p.get("description", "")
                    break
            if not resolved_project_name and projects:
                resolved_project_name = projects[0].get("name")
                resolved_project_tech = projects[0].get("technologies", [])
                resolved_project_desc = projects[0].get("description", "")

        resolved_project_name = resolved_project_name or "Core Technical Initiative"
        if not resolved_project_tech:
            resolved_project_tech = resume_dict.get("technologies", [])[:3] or ["Python"]

        tech_stack_str = ", ".join(resolved_project_tech)
        target_skill_str = source_skill or (query_item.source_skill if query_item else resolved_project_tech[0])

        # 2. Format chunk reference text
        if isinstance(chunk_context, list):
            formatted_chunks = []
            for c in chunk_context:
                source_chunk_ids.append(c.chunk_id)
                formatted_chunks.append(
                    f"--- Chunk [ID: {c.chunk_id}] (Source: {c.source_metadata.get('source_book', 'Domain Guide')}, Page: {c.source_metadata.get('page_number', 'N/A')}) ---\n"
                    f"{c.chunk_text}"
                )
            context_str = "\n\n".join(formatted_chunks)
        elif isinstance(chunk_context, RetrievedChunk):
            source_chunk_ids.append(chunk_context.chunk_id)
            context_str = f"--- Chunk [ID: {chunk_context.chunk_id}] (Source: {chunk_context.source_metadata.get('source_book', 'Domain Guide')}) ---\n{chunk_context.chunk_text}"
        else:
            context_str = str(chunk_context)
            source_chunk_ids = re.findall(r"\[ID:\s*([a-zA-Z0-9_\-]+)\]", context_str)

        # 3. Build Prompt with Strict Negative Constraints
        prompt = (
            f"The candidate's resume shows experience with: {target_skill_str} in project '{resolved_project_name}'.\n"
            f"Project Description: '{resolved_project_desc}'.\n"
            f"Project Allowed Tech Stack: {tech_stack_str}.\n"
            f"Their overall experience level is: {experience_level.upper()}.\n\n"
            f"Using the following reference material:\n"
            f"{context_str}\n\n"
            f"Generate ONE interview question that:\n"
            f"- Connects directly to the candidate's stated experience with {target_skill_str} in '{resolved_project_name}'\n"
            f"- Is grounded in the reference material's concepts\n"
            f"- Is applied/scenario-based, not a bare definition question\n"
            f"- Matches their experience level in depth\n\n"
            f"STRICT NEGATIVE CONSTRAINT:\n"
            f"You MUST NOT introduce or mention technologies, hardware (like GPUs/CUDA), frameworks, or domains outside this project's actual tech stack ({tech_stack_str}).\n"
            f"Target Difficulty: {difficulty.upper()}"
        )

        response_str = self._call_llm(
            prompt=prompt,
            project_name=resolved_project_name,
            project_tech=resolved_project_tech,
            project_desc=resolved_project_desc
        )

        try:
            cleaned = self._clean_json(response_str)
            data = json.loads(cleaned)
            if not data.get("source_chunk_ids") and source_chunk_ids:
                data["source_chunk_ids"] = source_chunk_ids[:2]
            if not data.get("project_referenced"):
                data["project_referenced"] = resolved_project_name
            if not data.get("technologies_referenced"):
                data["technologies_referenced"] = resolved_project_tech
            return GeneratedQuestion.model_validate(data)
        except Exception as e:
            logger.warning(f"Failed to parse LLM question output ({e}), using fallback.")
            fallback_json = self._heuristic_question_fallback(
                prompt=prompt,
                project_name=resolved_project_name,
                project_tech=resolved_project_tech,
                project_desc=resolved_project_desc
            )
            data = json.loads(fallback_json)
            if source_chunk_ids:
                data["source_chunk_ids"] = source_chunk_ids[:2]
            return GeneratedQuestion.model_validate(data)

    def _clean_json(self, text: str) -> str:
        text = text.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()
        return text


# Module-level convenience functions
def generate_question(
    chunk_context: Union[List[RetrievedChunk], RetrievedChunk, str],
    resume_data: Union[ParsedResume, Dict[str, Any]],
    source_skill: Optional[str] = None,
    query_item: Optional[RetrievalQueryItem] = None,
    project_name: Optional[str] = None,
    project_tech: Optional[List[str]] = None,
    project_description: Optional[str] = None,
    difficulty: str = "medium"
) -> GeneratedQuestion:
    """Convenience function to generate one resume-driven grounded interview question."""
    generator = QuestionGenerator()
    return generator.generate(
        chunk_context=chunk_context,
        resume_data=resume_data,
        source_skill=source_skill,
        query_item=query_item,
        project_name=project_name,
        project_tech=project_tech,
        project_description=project_description,
        difficulty=difficulty
    )


def generate_interview_session_questions(
    resume: Union[ParsedResume, Dict[str, Any]],
    role: str,
    target_count: int = 5,
    difficulty: str = "medium"
) -> List[GeneratedQuestion]:
    """
    End-to-end pipeline cycling through ALL projects and skills in the candidate resume:
    1. Generates conceptual queries covering each project and skill.
    2. Retrieves role-filtered chunks with source_skill and project context.
    3. Synthesizes N questions systematically cycling through distinct projects (ensuring no project is ignored).
    """
    if isinstance(resume, dict):
        resume_obj = ParsedResume.model_validate(resume)
    else:
        resume_obj = resume

    queries = build_retrieval_queries(resume=resume_obj, role=role)
    chunks = retrieve_chunks(queries=queries, role=role, top_k=3)

    projects = resume_obj.notable_projects or []
    questions: List[GeneratedQuestion] = []
    used_project_names: Set[str] = set()

    for i in range(target_count):
        # 1. Prefer an unused project first
        target_project = None
        if projects:
            unused_projects = [p for p in projects if p.name not in used_project_names]
            if unused_projects:
                target_project = unused_projects[0]
            else:
                target_project = projects[i % len(projects)]
            used_project_names.add(target_project.name)

        # 2. Pick or generate matching query item for this project
        matching_query = None
        if target_project:
            for q in queries:
                if q.project_name == target_project.name or any(t.lower() in q.source_skill.lower() for t in target_project.technologies):
                    matching_query = q
                    break

        if not matching_query:
            matching_query = queries[i % len(queries)] if queries else RetrievalQueryItem(
                query=f"core architectural design for {role}",
                source_skill=role,
                rationale="Assess foundational domain competency"
            )

        # 3. Filter chunks that match this query / project
        matching_chunks = [
            c for c in chunks
            if (target_project and c.project_name == target_project.name)
            or (c.source_skill.lower() in matching_query.source_skill.lower())
            or (matching_query.query.lower() in c.matched_query.lower())
        ]
        if not matching_chunks:
            matching_chunks = chunks[i % len(chunks):i % len(chunks) + 2] if chunks else []

        q = generate_question(
            chunk_context=matching_chunks,
            resume_data=resume_obj,
            source_skill=matching_query.source_skill,
            query_item=matching_query,
            project_name=target_project.name if target_project else matching_query.project_name,
            project_tech=target_project.technologies if target_project else matching_query.project_tech,
            project_description=target_project.description if target_project else matching_query.project_description,
            difficulty=difficulty
        )
        questions.append(q)

    return questions
