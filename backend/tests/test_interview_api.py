"""
Integration tests for Interview Session API Router
"""

import sys
import unittest
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.base import Base
from app.db.session import get_db

# Create in-memory SQLite database for fast isolated testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


class TestInterviewAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=engine)

    def test_complete_interview_lifecycle(self):
        # 1. POST /candidates — create candidate profile
        sample_resume = (
            "Senior Backend and Machine Learning Engineer with 6+ years experience. "
            "Skilled in Python, PyTorch, FastAPI, PostgreSQL, Docker, and Distributed Systems. "
            "Architected high throughput real-time streaming services handling millions of transactions."
        )
        cand_resp = self.client.post(
            "/api/v1/candidates",
            json={
                "target_role": "Machine Learning Engineer",
                "resume_text": sample_resume
            }
        )
        self.assertEqual(cand_resp.status_code, 201, f"Candidate creation failed: {cand_resp.text}")
        cand_data = cand_resp.json()
        candidate_id = cand_data["id"]
        self.assertIsNotNone(candidate_id)
        self.assertEqual(cand_data["target_role"], "Machine Learning Engineer")
        self.assertIn("extracted_data", cand_data)
        print(f"\n[API TEST] Candidate Created: ID={candidate_id}")

        # 2. POST /sessions — start session and pre-generate 1st question
        session_resp = self.client.post(
            "/api/v1/sessions",
            json={
                "candidate_id": candidate_id,
                "role": "Machine Learning Engineer"
            }
        )
        self.assertEqual(session_resp.status_code, 201, f"Session start failed: {session_resp.text}")
        session_data = session_resp.json()
        session_id = session_data["session_id"]
        self.assertEqual(session_data["status"], "in_progress")
        first_q = session_data["first_question"]
        self.assertIsNotNone(first_q["id"])
        self.assertEqual(first_q["order_index"], 0)
        self.assertGreater(len(first_q["question_text"]), 20)
        print(f"[API TEST] Session Started: ID={session_id} | Q1 Topic: {first_q['topic']}")

        # 3. GET /sessions/{id}/current-question
        curr_q_resp = self.client.get(f"/api/v1/sessions/{session_id}/current-question")
        self.assertEqual(curr_q_resp.status_code, 200)
        curr_q_data = curr_q_resp.json()
        self.assertFalse(curr_q_data["is_finished"])
        self.assertEqual(curr_q_data["question"]["id"], first_q["id"])

        # 4. POST /sessions/{id}/answer — submit answer, verify evaluation and next question
        answer_text = (
            "To diagnose vanishing gradients during distributed backward propagation, I would inspect gradient norms "
            "per layer using automatic differentiation hooks. We should implement gradient clipping (norm ceiling 1.0), "
            "transition activation layers to Swish/GELU with layer normalization, and ensure fp32 master weight accumulation."
        )
        ans_resp = self.client.post(
            f"/api/v1/sessions/{session_id}/answer",
            json={"answer_text": answer_text}
        )
        self.assertEqual(ans_resp.status_code, 200, f"Answer submission failed: {ans_resp.text}")
        ans_data = ans_resp.json()
        
        # Verify evaluation payload
        eval_payload = ans_data["evaluation"]
        self.assertIn(eval_payload["rating"], ["weak", "adequate", "strong"])
        self.assertGreaterEqual(eval_payload["score"], 0)
        self.assertIn(eval_payload["next_difficulty"], ["easy", "medium", "hard"])
        self.assertIsNotNone(ans_data["next_question"])
        self.assertEqual(ans_data["next_question"]["order_index"], 1)
        print(f"[API TEST] Answer Evaluated: Rating={eval_payload['rating']} | Score={eval_payload['score']} | Next Diff={eval_payload['next_difficulty']}")

        # 5. POST /sessions/{id}/complete — complete session
        comp_resp = self.client.post(f"/api/v1/sessions/{session_id}/complete")
        self.assertEqual(comp_resp.status_code, 200, f"Complete session failed: {comp_resp.text}")
        comp_data = comp_resp.json()
        self.assertEqual(comp_data["status"], "completed")
        self.assertGreater(comp_data["approximate_score_out_of_10"], 0.0)
        self.assertIn(comp_data["hiring_recommendation"], ["strong_hire", "hire", "lean_hire", "lean_no_hire", "no_hire"])
        self.assertGreater(len(comp_data["overall_assessment"]), 50)
        self.assertGreaterEqual(len(comp_data["concrete_improvements"]), 2)
        print(f"[API TEST] Session Completed: Final Rating={comp_data['hiring_recommendation']} | Score={comp_data['approximate_score_out_of_10']}/10")

        # 6. GET /sessions/{id}/summary — retrieve structured summary
        summary_resp = self.client.get(f"/api/v1/sessions/{session_id}/summary")
        self.assertEqual(summary_resp.status_code, 200)
        summary_data = summary_resp.json()
        self.assertEqual(summary_data["session_id"], session_id)
        self.assertGreaterEqual(len(summary_data["questions"]), 1)
        self.assertIn("topic_breakdown", summary_data)
        print(f"[API TEST] Session Summary verified with {len(summary_data['questions'])} evaluated questions.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
