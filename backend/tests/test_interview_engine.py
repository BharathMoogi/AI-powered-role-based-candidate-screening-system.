"""
Unit tests for Interview Engine Service
"""

import sys
import unittest
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.resume import ParsedResume, ProjectDetail
from app.services.query_builder import RetrievalQueryItem
from app.services.interview_engine import (
    retrieve_context,
    generate_question,
    generate_interview_session_questions,
    RetrievedChunk,
    GeneratedQuestion
)
from app.services.vector_db import get_or_create_collection
from app.services.ingestion import EmbeddingGenerator


class TestInterviewEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Seed test chunk into ChromaDB
        cls.collection = get_or_create_collection("role_knowledge_base")
        cls.role = "Backend Machine Learning Specialist"
        cls.chunk_id = "test_chunk_dl_001"
        
        embedder = EmbeddingGenerator()
        text = "Gradient descent with momentum accelerates SGD by dampening oscillations and navigating ravines."
        embeddings = embedder.generate_embeddings([text])
        
        cls.collection.upsert(
            ids=[cls.chunk_id],
            documents=[text],
            embeddings=embeddings,
            metadatas=[{
                "role": cls.role,
                "source_book": "Optimization Handbook",
                "page_number": 42,
                "chunk_index": 0
            }]
        )

    def setUp(self):
        self.sample_resume = ParsedResume(
            candidate_name="Test Candidate",
            summary="Machine Learning Practitioner",
            skills=["Machine Learning", "System Optimization"],
            technologies=["PyTorch", "FastAPI", "PostgreSQL"],
            domains=["Machine Learning"],
            apparent_experience_level="senior",
            notable_projects=[
                ProjectDetail(
                    name="Optimization Engine",
                    description="Tuned large-scale model training workflows.",
                    technologies=["PyTorch"],
                    highlights="Speedups achieved"
                )
            ]
        )

    def test_retrieve_context_and_deduplication(self):
        queries = [
            RetrievalQueryItem(
                query="gradient descent momentum and optimization oscillations",
                source_skill="PyTorch",
                rationale="Test optimization mechanics"
            ),
            RetrievalQueryItem(
                query="gradient descent momentum and optimization oscillations",
                source_skill="Machine Learning",
                rationale="Duplicate query test for deduplication"
            )
        ]
        chunks = retrieve_context(queries=queries, role=self.role, top_k=2)
        self.assertIsInstance(chunks, list)
        
        # Verify deduplication
        chunk_ids = [c.chunk_id for c in chunks]
        self.assertEqual(len(chunk_ids), len(set(chunk_ids)), "Retrieved chunks must be unique (deduplicated).")

    def test_resume_driven_question_divergence_between_profiles(self):
        ml_resume = ParsedResume(
            candidate_name="Jane Doe",
            summary="Senior ML Engineer specializing in Computer Vision and PyTorch",
            skills=["Deep Learning", "Computer Vision", "Convolutional Neural Networks"],
            technologies=["PyTorch", "CUDA", "Python"],
            domains=["Computer Vision", "Manufacturing AI"],
            apparent_experience_level="senior",
            notable_projects=[
                ProjectDetail(
                    name="Industrial Defect Detection",
                    description="Built CNN vision backbone for manufacturing defect classification.",
                    technologies=["PyTorch", "CUDA"],
                    highlights="Reduced false negative defect rate by 34%"
                )
            ]
        )

        backend_resume = ParsedResume(
            candidate_name="Alex Smith",
            summary="Senior Backend Architect specializing in high-throughput FastAPI and PostgreSQL",
            skills=["Asynchronous Concurrency", "Database Architecture", "Event Streaming"],
            technologies=["FastAPI", "PostgreSQL", "Kafka", "Redis"],
            domains=["Fintech", "Distributed Systems"],
            apparent_experience_level="senior",
            notable_projects=[
                ProjectDetail(
                    name="Payment Ledger Service",
                    description="Engineered transactional checkout backend handling 15,000 requests per second.",
                    technologies=["FastAPI", "PostgreSQL"],
                    highlights="Zero write-skew anomalies under peak concurrent load"
                )
            ]
        )

        role = "Senior Software Engineer"
        ml_questions = generate_interview_session_questions(resume=ml_resume, role=role, target_count=5)
        backend_questions = generate_interview_session_questions(resume=backend_resume, role=role, target_count=5)

        self.assertEqual(len(ml_questions), 5)
        self.assertEqual(len(backend_questions), 5)

        ml_q_texts = [q.question_text for q in ml_questions]
        backend_q_texts = [q.question_text for q in backend_questions]

        # Assert no overlap
        overlap = set(ml_q_texts).intersection(set(backend_q_texts))
        self.assertEqual(len(overlap), 0, "ML and Backend candidates must receive distinctly different questions.")

        # Assert ML questions reference ML projects/skills
        has_ml_content = any("defect" in q.lower() or "pytorch" in q.lower() or "vision" in q.lower() for q in ml_q_texts)
        self.assertTrue(has_ml_content, "ML candidate questions must reference resume ML project/skills.")

        # Assert Backend questions reference Backend projects/skills
        has_backend_content = any("fastapi" in q.lower() or "ledger" in q.lower() or "postgres" in q.lower() for q in backend_q_texts)
        self.assertTrue(has_backend_content, "Backend candidate questions must reference resume Backend project/skills.")

    def test_generate_question_grounding_and_schema(self):
        chunk = RetrievedChunk(
            chunk_id=self.chunk_id,
            chunk_text="Gradient descent with momentum accelerates SGD by dampening oscillations.",
            source_metadata={"source_book": "Optimization Handbook", "page_number": 42},
            matched_query="momentum optimization"
        )
        query_item = RetrievalQueryItem(
            query="gradient descent momentum",
            source_skill="PyTorch",
            rationale="Probe optimization fundamentals"
        )

        question: GeneratedQuestion = generate_question(
            chunk_context=[chunk],
            resume_data=self.sample_resume,
            query_item=query_item,
            difficulty="hard"
        )

        self.assertIsInstance(question, GeneratedQuestion)
        self.assertGreater(len(question.question_text), 30)
        self.assertGreater(len(question.topic), 3)
        self.assertIn(self.chunk_id, question.source_chunk_ids)
        self.assertFalse(question.question_text.lower().startswith("what is "), "Questions must not be generic recall questions.")

    def test_generate_interview_session_questions(self):
        questions = generate_interview_session_questions(
            resume=self.sample_resume,
            role=self.role,
            target_count=5,
            difficulty="hard"
        )
        self.assertEqual(len(questions), 5)
        for q in questions:
            self.assertIsInstance(q, GeneratedQuestion)
            self.assertGreater(len(q.source_chunk_ids), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
