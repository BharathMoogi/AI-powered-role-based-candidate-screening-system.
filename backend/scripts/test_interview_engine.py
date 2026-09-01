#!/usr/bin/env python3
"""
Prompt-Engineering Test Harness for Interview Engine

Demonstrates and evaluates the end-to-end question generation pipeline:
1. Ingests sample domain knowledge chunks (Machine Learning / Backend Systems) into ChromaDB
2. Parses sample candidate resume (Senior Machine Learning & Backend Engineer)
3. Builds 5-8 dynamic conceptual queries bridging candidate skills to textbook principles
4. Retrieves and deduplicates top-k grounded chunks from ChromaDB
5. Generates 5 applied, scenario-based interview questions with traceable source chunk IDs
"""

import sys
from pathlib import Path

# Add backend directory to path
CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent if CURRENT_DIR.name == "scripts" else CURRENT_DIR
ROOT_DIR = BACKEND_DIR.parent

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.vector_db import get_or_create_collection
from app.services.ingestion import EmbeddingGenerator
from app.services.resume import parse_resume, ParsedResume
from app.services.query_builder import build_retrieval_queries
from app.services.interview_engine import (
    retrieve_context,
    generate_question,
    RetrievedChunk,
    GeneratedQuestion
)

SAMPLE_RESUME = """
Elena Rostova
Senior Machine Learning & Distributed Systems Engineer
Email: elena.rostova@tech.io | GitHub: github.com/erostova

SUMMARY:
Senior Engineer with 7+ years specializing in distributed deep learning training infrastructure,
high-throughput asynchronous inference microservices, and reliable database architectures.

CORE SKILLS & TECHNOLOGIES:
• Languages & Frameworks: Python, PyTorch, TensorFlow, FastAPI, C++
• Infrastructure & Data: Docker, Kubernetes, PostgreSQL, Redis, Apache Kafka
• Domain Areas: Natural Language Processing, Distributed Consensus, Computer Vision, High Concurrency

NOTABLE EXPERIENCE:
Staff Infrastructure Engineer | CoreAI Systems (2021 - Present)
• Architected a distributed transformer training pipeline on 128 NVIDIA H100 GPUs using PyTorch FSDP and CUDA kernels.
• Mitigated severe gradient synchronization bottlenecks, reducing multi-node communication overhead by 40%.
• Built high-concurrency FastAPI gateway processing 100k requests/sec with Redis cluster caching and async connection pooling.

Senior Backend & ML Engineer | DataStream Tech (2017 - 2021)
• Engineered transactional financial data service backed by PostgreSQL with strict serializable isolation and custom partitioning.
• Designed Kafka streaming pipeline handling 2TB daily log telemetry with zero message loss.
"""

SAMPLE_DOMAIN_KNOWLEDGE_CHUNKS = [
    {
        "id": "ml_eng_tom_mitchell_c0001_p12",
        "text": (
            "Chapter 4: Gradient Descent and Backpropagation in Deep Networks.\n"
            "Backpropagation computes the gradient of the loss function with respect to each weight by the chain rule, "
            "computing the gradient one layer at a time, iterating backward from the output layer. In deep architectures "
            "with many non-linear activation layers, repeated multiplication of weight matrices can lead to exponential decay "
            "(vanishing gradients) or exponential growth (exploding gradients). Techniques such as residual connections, "
            "layer normalization, proper weight initialization (He/Xavier), and gradient clipping are essential to maintain "
            "gradient norm stability during distributed backward passes."
        ),
        "metadata": {
            "role": "Machine Learning Engineer",
            "source_book": "Machine Learning Foundations (Mitchell)",
            "page_number": 12,
            "chunk_index": 1,
            "token_count": 120
        }
    },
    {
        "id": "ml_eng_distributed_training_c0002_p45",
        "text": (
            "Chapter 9: Distributed Training Paradigms: Data Parallelism and Pipeline Parallelism.\n"
            "In Fully Sharded Data Parallelism (FSDP) and ZeRO-3, model parameters, gradients, and optimizer states are "
            "partitioned across all worker GPUs. During forward computation, each GPU executes an all-gather to reconstruct "
            "the layer parameters temporarily and frees them immediately after computation. Inter-node network latency and "
            "NCCL collective communication bottlenecks (All-Reduce / All-Gather) represent the primary limiting factor for linear scaling."
        ),
        "metadata": {
            "role": "Machine Learning Engineer",
            "source_book": "Distributed Deep Learning Systems",
            "page_number": 45,
            "chunk_index": 2,
            "token_count": 115
        }
    },
    {
        "id": "ml_eng_async_systems_c0003_p78",
        "text": (
            "Chapter 6: Asynchronous Event Loops and Concurrency in Modern ASGI Frameworks.\n"
            "The asynchronous event loop manages execution by scheduling cooperative coroutines on a single OS thread. "
            "If a coroutine executes a synchronous blocking call (such as synchronous database drivers, heavy CPU serialization, "
            "or file disk I/O), the entire event loop is halted, preventing other concurrent tasks from progressing. Solutions "
            "require offloading CPU-bound tasks to separate process/thread pools, adopting non-blocking async drivers, and configuring "
            "bounded concurrency semaphores to prevent memory exhaustion under sudden traffic spikes."
        ),
        "metadata": {
            "role": "Machine Learning Engineer",
            "source_book": "High Performance Asynchronous Architectures",
            "page_number": 78,
            "chunk_index": 3,
            "token_count": 130
        }
    },
    {
        "id": "ml_eng_db_transactions_c0004_p105",
        "text": (
            "Chapter 7: Relational Storage Internals, ACID Guarantees, and Indexing.\n"
            "PostgreSQL implements Multi-Version Concurrency Control (MVCC) to ensure read transactions do not block write transactions. "
            "Under Read Committed and Repeatable Read isolation levels, anomalies such as write skew and lost updates can still manifest. "
            "Serializable isolation employs Serializable Snapshot Isolation (SSI) to detect dependency cycles (siREAD locks) and abort "
            "conflicting transactions. Write-Ahead Logging (WAL) ensures durability by writing sequential delta records before dirty buffer "
            "pages are flushed to persistent disk."
        ),
        "metadata": {
            "role": "Machine Learning Engineer",
            "source_book": "Database System Concepts & Internals",
            "page_number": 105,
            "chunk_index": 4,
            "token_count": 125
        }
    },
    {
        "id": "ml_eng_docker_k8s_c0005_p140",
        "text": (
            "Chapter 11: Container Virtualization and Kubernetes Orchestration.\n"
            "Linux containers rely on kernel namespaces (PID, NET, MNT, IPC, UTS) for process isolation and Control Groups (cgroups v2) "
            "for enforcing memory, CPU, and I/O resource ceilings. When container memory exceeds cgroup limits, the Linux kernel Out-Of-Memory "
            "(OOM) killer terminates the process. In Kubernetes, kube-scheduler and controller manager use declarative reconciliation loops "
            "and etcd Raft consensus to maintain desired state across distributed nodes."
        ),
        "metadata": {
            "role": "Machine Learning Engineer",
            "source_book": "Cloud Native Infrastructure & Distributed Orchestration",
            "page_number": 140,
            "chunk_index": 5,
            "token_count": 118
        }
    }
]


def seed_test_knowledge_base():
    """Seeds ChromaDB with sample domain chunks for the test harness."""
    collection = get_or_create_collection("role_knowledge_base")
    embedder = EmbeddingGenerator()

    ids = [c["id"] for c in SAMPLE_DOMAIN_KNOWLEDGE_CHUNKS]
    docs = [c["text"] for c in SAMPLE_DOMAIN_KNOWLEDGE_CHUNKS]
    metas = [c["metadata"] for c in SAMPLE_DOMAIN_KNOWLEDGE_CHUNKS]
    embeddings = embedder.generate_embeddings(docs)

    collection.upsert(
        ids=ids,
        documents=docs,
        embeddings=embeddings,
        metadatas=metas
    )
    print(f"[HARNESS] Seeded {len(ids)} domain knowledge chunks into ChromaDB.")


def run_test_harness():
    print("=" * 80)
    print("  INTERVIEW ENGINE: PROMPT ENGINEERING TEST HARNESS")
    print("=" * 80)

    # 1. Seed Knowledge Base
    seed_test_knowledge_base()

    role = "Machine Learning Engineer"

    # 2. Parse Resume
    print("\n" + "-" * 80)
    print(" 1. RESUME EXTRACTION")
    print("-" * 80)
    parsed: ParsedResume = parse_resume(SAMPLE_RESUME)
    print(f"Candidate:        {parsed.candidate_name or 'Elena Rostova'}")
    print(f"Experience Level: {parsed.apparent_experience_level.upper()}")
    print(f"Skills:           {parsed.skills}")
    print(f"Technologies:     {parsed.technologies}")

    # 3. Dynamic Query Construction
    print("\n" + "-" * 80)
    print(" 2. DYNAMIC CONCEPTUAL RETRIEVAL QUERIES (Bridge Skills -> Concepts)")
    print("-" * 80)
    queries = build_retrieval_queries(resume=parsed, role=role)
    for i, q in enumerate(queries, 1):
        print(f" [{i}] Source Skill: {q.source_skill}")
        print(f"     Query:        \"{q.query}\"")
        print(f"     Rationale:    {q.rationale}")

    # 4. Grounded Context Retrieval
    print("\n" + "-" * 80)
    print(" 3. ROLE-FILTERED CONTEXT RETRIEVAL & DEDUPLICATION (k=3)")
    print("-" * 80)
    chunks = retrieve_context(queries=queries, role=role, top_k=3)
    print(f"Retrieved {len(chunks)} unique deduplicated chunks from ChromaDB.\n")
    for i, c in enumerate(chunks, 1):
        src = c.source_metadata.get("source_book", "Unknown")
        pg = c.source_metadata.get("page_number", "N/A")
        print(f"  * Chunk #{i} [{c.chunk_id}] (Source: {src}, Page {pg})")
        print(f"    Matched: {c.matched_query[:70]}...")

    # 5. Generate Grounded Scenario Interview Questions
    print("\n" + "=" * 80)
    print(" 4. GENERATED APPLIED INTERVIEW QUESTIONS (5 Questions)")
    print("=" * 80)

    for i in range(min(5, len(queries))):
        q_item = queries[i]
        
        # Match chunks for this query
        matching_chunks = [
            c for c in chunks
            if q_item.source_skill.lower() in c.matched_query.lower() or q_item.query.lower() in c.matched_query.lower()
        ]
        if not matching_chunks:
            matching_chunks = [chunks[i % len(chunks)]] if chunks else []

        question: GeneratedQuestion = generate_question(
            chunk_context=matching_chunks,
            resume_data=parsed,
            query_item=q_item,
            difficulty="hard" if parsed.apparent_experience_level == "senior" else "medium"
        )

        print("\n" + "+" + "-" * 78 + "+")
        print(f"| QUESTION #{i+1} | TOPIC: {question.topic.upper()} | DIFFICULTY: {question.difficulty.upper()}")
        print("+" + "-" * 78 + "+")
        print(f"| Targeted Candidate Skill: {q_item.source_skill}")
        print(f"| Query Rationale:          {q_item.rationale}")
        print(f"| Source Chunk IDs Cited:   {question.source_chunk_ids}")
        print("+" + "-" * 78 + "+")
        print(f"| SCENARIO QUESTION:")
        print(f"| \"{question.question_text}\"")
        if question.expected_key_concepts:
            print("|")
            print("| EXPECTED KEY EVALUATION CONCEPTS:")
            for concept in question.expected_key_concepts:
                print(f"|  [+] {concept}")
        print("+" + "-" * 78 + "+")

    print("\n[SUCCESS] Test harness completed successfully. Quality check ready.\n")


if __name__ == "__main__":
    run_test_harness()
