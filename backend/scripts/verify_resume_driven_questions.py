"""
Verification Test Script for Resume-Driven Question Generation

Compares question generation for two distinctly different candidate resumes against the same role:
1. Candidate A: Machine Learning / Computer Vision Heavy (PyTorch, CNN defect detection, HuggingFace)
2. Candidate B: Backend / Distributed Systems Heavy (FastAPI, PostgreSQL transaction ledger, Kafka event streaming)

Confirms that generated questions are distinctly different and explicitly reference each candidate's
specific resume projects, technologies, and claimed background.
"""

import sys
import json
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.resume import extract_resume_data, parse_resume
from app.services.query_builder import build_retrieval_queries
from app.services.interview_engine import retrieve_chunks, generate_interview_session_questions, QuestionGenerator, RetrievedChunk

# ============================================================================
# Sample Resumes
# ============================================================================

ML_CANDIDATE_RESUME = """
Jane Doe - Senior Machine Learning Engineer
Email: jane.doe@ml-engineering.ai | GitHub: github.com/janedoe-ai

PROFESSIONAL SUMMARY
Senior ML Engineer with 6+ years specializing in deep learning, computer vision, and transformer optimization.
Led deployment of real-time computer vision defect inspection systems and multi-GPU distributed PyTorch training pipelines.

CORE SKILLS
- Deep Learning & Optimization: PyTorch, Convolutional Neural Networks (CNNs), CUDA, Automatic Differentiation
- Computer Vision: Feature Pyramid Networks (FPNs), Dilated Convolutions, Defect Detection Backbones
- NLP & LLMs: Hugging Face Transformers, LoRA Fine-Tuning, Semantic Embeddings
- Frameworks & Tools: Python, Scikit-Learn, Docker, Ray, Weights & Biases

NOTABLE PROJECTS
Project: Industrial Real-Time Vision Defect Classifier
- Architected custom CNN vision backbone with Dilated Convolutions for sub-millimeter manufacturing defect detection.
- Reduced false-negative defect rate by 34% while keeping GPU inference latency under 8ms per image.

Project: Distributed Transformer Pre-Training Pipeline
- Implemented PyTorch mixed-precision distributed training across 32 A100 GPUs using ZeRO memory optimization.
- Resolved numerical instability in gradient accumulation and eliminated NaN loss spikes during backward passes.
"""

BACKEND_CANDIDATE_RESUME = """
Alex Smith - Senior Backend & Distributed Systems Engineer
Email: alex.smith@distributed-systems.io | GitHub: github.com/alexsmith-dev

PROFESSIONAL SUMMARY
Backend Architect with 7+ years designing high-throughput distributed microservices, transactional payment ledgers, and event-driven data streaming pipelines.

CORE SKILLS
- Backend Systems: Python, FastAPI, Asynchronous Concurrency (ASGI), Non-blocking I/O
- Databases: PostgreSQL, ACID Transactions, Serializable Snapshot Isolation (SSI), Redis, B-Tree Indexing
- Distributed Messaging: Apache Kafka, Event-Driven Architecture, Exactly-Once Processing
- Infrastructure: Docker, Kubernetes, Prometheus, Distributed Tracing

NOTABLE PROJECTS
Project: High-Throughput Payment Ledger Service
- Built real-time transactional checkout backend using FastAPI and PostgreSQL handling 15,000 requests per second.
- Implemented strict Serializable transaction isolation and custom row-locking to prevent write-skew and double-spend anomalies.

Project: Distributed Event Streaming Pipeline
- Architected Kafka event streaming cluster processing 40 million financial events daily with idempotent consumer deduplication.
- Handled network partition failovers without message loss or consumer group rebalance storms.
"""


def run_pipeline_for_candidate(candidate_label: str, resume_text: str, role: str):
    print("=" * 80)
    print(f"PIPELINE RUN: {candidate_label.upper()} (Target Role: '{role}')")
    print("=" * 80)

    # 1. Extract Resume Data
    print("\n[Step 1: extract_resume_data]")
    resume_data = extract_resume_data(resume_text)
    print(f"  * Candidate: {resume_data.get('candidate_name')}")
    print(f"  * Experience Level: {resume_data.get('apparent_experience_level')}")
    print(f"  * Skills: {resume_data.get('skills')}")
    print(f"  * Technologies: {resume_data.get('technologies')}")
    print(f"  * Projects Extracted ({len(resume_data.get('notable_projects', []))}):")
    for p in resume_data.get('notable_projects', []):
        print(f"    - {p.get('name')}: {p.get('description')} (Tech: {p.get('technologies')})")

    # 2. Build Conceptual Queries
    print("\n[Step 2: build_queries]")
    queries = build_retrieval_queries(resume=resume_data, role=role)
    for i, q in enumerate(queries[:5], 1):
        print(f"  Q{i}: Query=\"{q.query}\"")
        print(f"      Source Skill/Project: {q.source_skill}")
        print(f"      Rationale: {q.rationale}")

    # 3. Retrieve Chunks
    print("\n[Step 3: retrieve_chunks]")
    chunks = retrieve_chunks(queries=queries, role=role, top_k=3)
    print(f"  * Retrieved {len(chunks)} chunks from ChromaDB with attached source_skills.")

    # 4. Generate 5 Questions
    print("\n[Step 4: generate_question - 5 Scenario Questions]")
    questions = generate_interview_session_questions(
        resume=resume_data,
        role=role,
        target_count=5,
        difficulty="hard"
    )

    for i, q in enumerate(questions, 1):
        print(f"\n  --- QUESTION #{i} ---")
        print(f"  Topic: {q.topic} (Difficulty: {q.difficulty})")
        print(f"  Question Text:\n    \"{q.question_text}\"")
        print(f"  Expected Key Concepts: {q.expected_key_concepts}")

    return resume_data, queries, questions


def main():
    target_role = "Senior Software Engineer"

    # Run Candidate 1 (ML-Heavy)
    ml_data, ml_queries, ml_questions = run_pipeline_for_candidate(
        "Candidate A: Machine Learning / Computer Vision",
        ML_CANDIDATE_RESUME,
        target_role
    )

    # Run Candidate 2 (Backend-Heavy)
    backend_data, backend_queries, backend_questions = run_pipeline_for_candidate(
        "Candidate B: Backend / Distributed Systems",
        BACKEND_CANDIDATE_RESUME,
        target_role
    )

    # Verification & Diff Analysis
    print("\n" + "=" * 80)
    print("VERIFICATION & COMPARISON ANALYSIS")
    print("=" * 80)

    ml_q_texts = [q.question_text for q in ml_questions]
    backend_q_texts = [q.question_text for q in backend_questions]

    # Verify that the two sets of questions are distinct
    overlap = set(ml_q_texts).intersection(set(backend_q_texts))
    print(f"\n* Question Overlap Count between ML and Backend candidates: {len(overlap)} (Expected: 0)")
    
    # Check for ML-specific keywords in Candidate A's questions
    ml_keywords_found = any(any(kw in q.lower() for kw in ["vision", "cnn", "pytorch", "defect", "receptive field", "gradient"]) for q in ml_q_texts)
    print(f"* ML Candidate questions reference ML/Vision/PyTorch/Defect projects: {ml_keywords_found}")

    # Check for Backend-specific keywords in Candidate B's questions
    backend_keywords_found = any(any(kw in q.lower() for kw in ["fastapi", "kafka", "ledger", "postgres", "concurrency", "event loop", "transaction", "isolation"]) for q in backend_q_texts)
    print(f"* Backend Candidate questions reference FastAPI/Postgres/Kafka/Ledger projects: {backend_keywords_found}")

    if len(overlap) == 0 and ml_keywords_found and backend_keywords_found:
        print("\n>>> SUCCESS: Both candidates received distinctly different, resume-grounded questions tailored to their respective projects and skills!")
    else:
        print("\n>>> WARNING: Questions did not meet divergence criteria. Dumping raw prompt...")
        chunk = RetrievedChunk(chunk_id="debug_01", chunk_text="Sample grounding reference.", matched_query="test", source_skill="PyTorch")
        gen = QuestionGenerator()
        print("Sample Prompt generated for ML candidate:")
        # Test prompt structure
        test_q = gen.generate(chunk_context=chunk, resume_data=ml_data, source_skill="PyTorch")
        print(f"Generated Q: {test_q.question_text}")


if __name__ == "__main__":
    main()
