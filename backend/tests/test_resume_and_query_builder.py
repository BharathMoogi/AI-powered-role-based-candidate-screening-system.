"""
Unit and Integration Tests for Resume Parser and Dynamic Query Builder.
"""

import sys
import unittest
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.resume import (
    parse_resume,
    ResumeParserService,
    ParsedResume,
    ProjectDetail,
    extract_text_from_input
)
from app.services.query_builder import (
    build_retrieval_queries,
    DynamicQueryBuilder,
    RetrievalQueryItem
)

SAMPLE_RESUME_TEXT = """
Alex Mercer
Senior Machine Learning Engineer
Email: alex.mercer@example.com | GitHub: github.com/alexmercer

PROFESSIONAL SUMMARY
Senior Machine Learning Engineer with 6+ years of experience designing and deploying scalable deep learning pipelines,
distributed training workflows, and high-throughput real-time inference microservices.

TECHNICAL SKILLS
• Programming & Frameworks: Python, PyTorch, TensorFlow, Scikit-Learn, C++
• Backend & Infrastructure: FastAPI, Docker, Kubernetes, PostgreSQL, Redis, Kafka
• Core Competencies: Natural Language Processing, Computer Vision, Distributed Systems, Asynchronous Programming, CI/CD

EXPERIENCE
Lead ML Engineer | QuantAI Systems (2021 - Present)
• Architected a real-time transformer inference service handling 50M daily requests using FastAPI, Redis caching, and Triton Inference Server.
• Reduced model latency by 45% using PyTorch quantization, TensorRT acceleration, and custom CUDA kernels.
• Designed and orchestrated distributed training jobs on a 64-GPU Kubernetes cluster with automated checkpointing and fault tolerance.

Machine Learning Engineer | DataVision Labs (2018 - 2021)
• Developed convolutional neural network models for defect detection in manufacturing, achieving 99.2% recall.
• Built automated ETL and data ingestion pipelines in PostgreSQL and Kafka for terabyte-scale image datasets.

EDUCATION
B.S. in Computer Science | University of Washington (2014 - 2018)
"""


class TestResumeParser(unittest.TestCase):

    def setUp(self):
        self.parser = ResumeParserService()

    def test_extract_text_from_string(self):
        extracted = extract_text_from_input(SAMPLE_RESUME_TEXT)
        self.assertIn("Alex Mercer", extracted)
        self.assertIn("PyTorch", extracted)

    def test_parse_sample_resume_text(self):
        parsed: ParsedResume = parse_resume(SAMPLE_RESUME_TEXT)

        # Validate Schema and Fields
        self.assertIsInstance(parsed, ParsedResume)
        self.assertIn(parsed.apparent_experience_level, ["junior", "mid", "senior"])
        self.assertEqual(parsed.apparent_experience_level, "senior")  # 6+ years noted
        
        # Verify skills and technologies
        tech_set = {t.lower() for t in parsed.technologies}
        self.assertTrue(any("python" in t for t in tech_set))
        self.assertTrue(any("pytorch" in t for t in tech_set))
        
        self.assertGreater(len(parsed.skills), 0)
        self.assertGreater(len(parsed.domains), 0)
        self.assertGreater(len(parsed.notable_projects), 0)

        print(f"\n[TEST SUCCESS] Parsed Resume Summary:")
        print(f"  • Level: {parsed.apparent_experience_level}")
        print(f"  • Skills: {parsed.skills}")
        print(f"  • Technologies: {parsed.technologies}")
        print(f"  • Domains: {parsed.domains}")

    def test_retry_on_invalid_json(self):
        # Test clean json helper
        raw_markdown_json = '```json\n{"candidate_name": "Test", "summary": "Dev", "skills": ["Python"], "technologies": ["Docker"], "domains": ["Cloud"], "apparent_experience_level": "mid", "notable_projects": []}\n```'
        cleaned = self.parser._clean_json_string(raw_markdown_json)
        self.assertTrue(cleaned.startswith("{") and cleaned.endswith("}"))
        parsed = ParsedResume.model_validate_json(cleaned)
        self.assertEqual(parsed.apparent_experience_level, "mid")


class TestDynamicQueryBuilder(unittest.TestCase):

    def setUp(self):
        self.builder = DynamicQueryBuilder()
        self.sample_parsed_resume = ParsedResume(
            candidate_name="Alex Mercer",
            summary="Senior Machine Learning Engineer",
            skills=["Distributed Systems", "Natural Language Processing", "Asynchronous Programming"],
            technologies=["PyTorch", "FastAPI", "PostgreSQL", "Docker", "Kubernetes"],
            domains=["Machine Learning", "Cloud Infrastructure"],
            apparent_experience_level="senior",
            notable_projects=[
                ProjectDetail(
                    name="Real-time Transformer Inference",
                    description="High throughput microservice handling 50M daily requests.",
                    technologies=["PyTorch", "FastAPI", "Redis"],
                    highlights="45% latency reduction"
                )
            ]
        )

    def test_build_queries_count_and_schema(self):
        role = "Machine Learning Engineer"
        queries: list[RetrievalQueryItem] = build_retrieval_queries(
            resume=self.sample_parsed_resume,
            role=role
        )

        # Must generate 5 to 8 queries
        self.assertGreaterEqual(len(queries), 5, "Queries must be at least 5")
        self.assertLessEqual(len(queries), 8, "Queries must be at most 8")

        print(f"\n[TEST SUCCESS] Generated {len(queries)} Conceptual Queries for Role: '{role}':")
        for i, q in enumerate(queries, 1):
            self.assertIsInstance(q, RetrievalQueryItem)
            self.assertTrue(len(q.query.strip()) > 10, "Query string must be descriptive")
            self.assertTrue(len(q.source_skill.strip()) > 0, "Source skill must be populated")
            self.assertTrue(len(q.rationale.strip()) > 10, "Rationale must be explanatory")
            print(f"  {i}. [{q.source_skill}] -> Query: \"{q.query}\"")
            print(f"     Rationale: {q.rationale}\n")

    def test_query_conceptual_bridging_not_just_echoing(self):
        role = "Senior Backend & ML Engineer"
        queries = build_retrieval_queries(
            resume=self.sample_parsed_resume,
            role=role
        )

        # Verify that queries probe deeper conceptual topics (e.g. gradients/graphs, ACID, async/event loop)
        query_texts = " ".join([q.query.lower() for q in queries])
        
        # Check for conceptual terms rather than just simple keywords
        has_deep_concepts = any(term in query_texts for term in [
            "gradient", "differentiation", "concurrency", "event loop",
            "acid", "isolation", "consensus", "computational", "partition",
            "complexity", "tradeoffs"
        ])
        self.assertTrue(has_deep_concepts, "Queries should bridge tools to deep foundational concepts.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
