"""
Unit tests for Session Summary Service
"""

import sys
import unittest
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.candidate import Candidate
from app.models.session import Session as ScreeningSession
from app.models.question import Question
from app.models.answer import Answer
from app.services.summary import generate_session_summary, StructuredSessionSummary


class TestSessionSummary(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.engine = engine
        Base.metadata.create_all(bind=engine)
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def setUp(self):
        self.db = self.SessionLocal()

        # Seed candidate
        self.candidate = Candidate(
            target_role="Senior Machine Learning Engineer",
            resume_text="Senior ML Engineer with 7+ years in distributed PyTorch training.",
            extracted_skills={
                "skills": ["Distributed Systems", "Deep Learning", "Gradient Optimization"],
                "technologies": ["Python", "PyTorch", "FastAPI", "PostgreSQL"],
                "apparent_experience_level": "senior"
            }
        )
        self.db.add(self.candidate)
        self.db.commit()
        self.db.refresh(self.candidate)

        # Seed session
        self.session = ScreeningSession(
            candidate_id=self.candidate.id,
            role="Senior Machine Learning Engineer",
            status="in_progress"
        )
        self.db.add(self.session)
        self.db.commit()
        self.db.refresh(self.session)

        # Seed Q1 and Answer
        q1 = Question(
            session_id=self.session.id,
            question_text="How would you diagnose vanishing gradients during distributed backward propagation?",
            topic="Deep Learning Optimization & Gradient Backpropagation",
            difficulty="hard",
            order_index=0
        )
        self.db.add(q1)
        self.db.commit()
        self.db.refresh(q1)

        ans1 = Answer(
            question_id=q1.id,
            answer_text="I would monitor per-layer gradient norms using PyTorch hooks, apply gradient clipping at norm 1.0, and use layer normalization.",
            evaluation={
                "rating": "strong",
                "score": 92,
                "rationale": "Clear theoretical understanding of backward gradient mechanics and practical mitigation steps.",
                "next_difficulty": "hard"
            }
        )
        self.db.add(ans1)

        # Seed Q2 and Answer
        q2 = Question(
            session_id=self.session.id,
            question_text="In a FastAPI service under 15,000 RPS burst, worker coroutines stall on the ASGI event loop. How do you resolve it?",
            topic="Asynchronous Concurrency & Event Loop Optimization",
            difficulty="hard",
            order_index=1
        )
        self.db.add(q2)
        self.db.commit()
        self.db.refresh(q2)

        ans2 = Answer(
            question_id=q2.id,
            answer_text="Offload CPU-bound and synchronous blocking operations to threadpools using anyio.to_thread, adopt non-blocking async drivers, and tune worker pool limits.",
            evaluation={
                "rating": "strong",
                "score": 90,
                "rationale": "Accurately diagnosed event loop thread starvation and applied proper asynchronous delegation patterns.",
                "next_difficulty": "hard"
            }
        )
        self.db.add(ans2)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_generate_session_summary_and_db_persistence(self):
        summary: StructuredSessionSummary = generate_session_summary(
            session_id=self.session.id,
            db=self.db
        )

        # Validate Schema
        self.assertIsInstance(summary, StructuredSessionSummary)
        self.assertEqual(summary.session_id, self.session.id)
        self.assertEqual(summary.candidate_id, self.candidate.id)
        
        # Validate Natural Narrative Assessment
        self.assertGreater(len(summary.overall_assessment), 100)
        self.assertFalse(summary.overall_assessment.startswith("- "), "Overall assessment must be a cohesive prose paragraph, not a bullet list.")
        self.assertFalse(summary.overall_assessment.startswith("* "), "Overall assessment must be a cohesive prose paragraph, not a bullet list.")

        # Validate 0-10 Score & Justification
        self.assertGreaterEqual(summary.approximate_score_out_of_10, 0.0)
        self.assertLessEqual(summary.approximate_score_out_of_10, 10.0)
        self.assertGreater(len(summary.score_justification), 20)

        # Validate 2-3 Concrete Improvements
        self.assertGreaterEqual(len(summary.concrete_improvements), 2)
        self.assertLessEqual(len(summary.concrete_improvements), 3)

        # Validate Topic Breakdown
        self.assertGreaterEqual(len(summary.topic_breakdown), 1)
        for t in summary.topic_breakdown:
            self.assertGreater(len(t.topic), 3)
            self.assertIn(t.rating, ["weak", "adequate", "strong"])
            self.assertGreaterEqual(t.score_out_of_10, 0.0)

        # Validate Hiring Recommendation
        self.assertIn(summary.hiring_recommendation, ["strong_hire", "hire", "lean_hire", "lean_no_hire", "no_hire"])

        # Validate Database Persistence
        refreshed_session = self.db.query(ScreeningSession).filter(ScreeningSession.id == self.session.id).first()
        self.assertEqual(refreshed_session.status, "completed")
        self.assertIsNotNone(refreshed_session.summary)
        self.assertEqual(refreshed_session.summary["session_id"], self.session.id)
        self.assertIn("overall_assessment", refreshed_session.summary)

        print(f"\n[SUMMARY TEST PASSED]")
        print(f"  * Overall Score: {summary.approximate_score_out_of_10}/10 | Rec: {summary.hiring_recommendation.upper()}")
        print(f"  * Overall Assessment Narrative:\n    \"{summary.overall_assessment}\"")
        print(f"  * Score Justification: {summary.score_justification}")
        print(f"  * Concrete Improvements:")
        for imp in summary.concrete_improvements:
            print(f"    - {imp}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
