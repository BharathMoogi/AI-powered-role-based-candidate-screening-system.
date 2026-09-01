"""
Answer Evaluation & Session Synthesis Service

Handles:
1. Multi-dimensional technical evaluation of candidate answers (rating: weak/adequate/strong, numerical score, rationale, strengths, gaps).
2. Dynamic difficulty adaptation for consecutive interview questions.
3. Final session synthesis and candidate performance reporting.
"""

import json
import os
import re
import logging
from typing import Any, Dict, List, Optional

from app.config import settings
from app.schemas.interview import AnswerEvaluationPayload

logger = logging.getLogger("evaluator_service")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


EVALUATOR_SYSTEM_PROMPT = """You are an expert Technical Interview Evaluator and Principal Hiring Bar Raiser.
Your task is to critically evaluate a candidate's answer to an applied technical interview question.

EVALUATION CRITERIA:
1. Technical Accuracy & Depth: Did the candidate identify the correct root cause, mechanism, or architecture?
2. Practical Reasoning: Did they account for real-world constraints (concurrency, memory ceilings, network partitions, race conditions)?
3. Nuance & Trade-offs: Did they explain WHY their chosen solution is preferable over naive alternatives?

RATING SCALE:
- "strong": Highly accurate, addresses foundational mechanics, identifies subtle failure modes, clear trade-off analysis (Score: 85-100).
- "adequate": Correct high-level approach, functional understanding, but misses subtle edge cases, architectural trade-offs, or precision (Score: 60-84).
- "weak": Inaccurate, superficial, demonstrates misconceptions, or fails to address core question scenario (Score: 0-59).

DIFFICULTY ADAPTATION LOGIC:
- If current difficulty is "easy" and rating is "strong" -> next_difficulty = "medium"
- If current difficulty is "medium" and rating is "strong" -> next_difficulty = "hard"
- If current difficulty is "hard" and rating is "strong" -> next_difficulty = "hard"
- If rating is "adequate" -> keep same difficulty
- If current difficulty is "hard" and rating is "weak" -> next_difficulty = "medium"
- If current difficulty is "medium" and rating is "weak" -> next_difficulty = "easy"
- If current difficulty is "easy" and rating is "weak" -> next_difficulty = "easy"

Return ONLY valid JSON matching this schema:
{
  "rating": "weak" | "adequate" | "strong",
  "score": 0 to 100,
  "rationale": "2-4 sentence diagnostic explanation of the grade",
  "strengths": ["Key technical strengths demonstrated"],
  "improvement_areas": ["Key omissions or inaccuracies"],
  "next_difficulty": "easy" | "medium" | "hard"
}
"""


SUMMARY_SYSTEM_PROMPT = """You are a Lead Hiring Committee Chair.
Synthesize the provided interview session transcript (questions, candidate answers, and individual evaluations) into a concise, executive hiring evaluation report.

Return ONLY valid JSON matching this schema:
{
  "overall_rating": "not_recommended" | "needs_review" | "recommended" | "strongly_recommended",
  "executive_summary": "3-5 sentence comprehensive synthesis of the candidate's technical depth, problem-solving maturity, and fit",
  "top_strengths": ["3-5 prominent technical strengths observed"],
  "growth_areas": ["2-3 specific technical gaps to monitor"]
}
"""


class AnswerEvaluatorService:
    """Evaluates candidate answers and synthesizes session outcomes."""

    def __init__(self):
        self.openai_api_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", "")
        self.gemini_api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")

    def _call_llm(self, user_prompt: str, system_prompt: str = EVALUATOR_SYSTEM_PROMPT) -> str:
        if self.openai_api_key:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=self.openai_api_key)
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2
                )
                return response.choices[0].message.content or "{}"
            except Exception as e:
                logger.warning(f"OpenAI evaluation failed: {e}")

        if self.gemini_api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_api_key)
                model = genai.GenerativeModel(
                    model_name="gemini-1.5-flash",
                    generation_config={"response_mime_type": "application/json"}
                )
                response = model.generate_content(f"{system_prompt}\n\n{user_prompt}")
                return response.text or "{}"
            except Exception as e:
                logger.warning(f"Gemini evaluation failed: {e}")

        return self._heuristic_evaluation_fallback(user_prompt)

    def _calculate_next_difficulty(self, current_difficulty: str, rating: str) -> str:
        current = current_difficulty.lower().strip()
        if rating == "strong":
            if current == "easy":
                return "medium"
            return "hard"
        elif rating == "weak":
            if current == "hard":
                return "medium"
            return "easy"
        else:
            return current if current in ["easy", "medium", "hard"] else "medium"

    def _heuristic_evaluation_fallback(self, user_prompt: str) -> str:
        """Deterministic evaluation fallback for testing without API keys."""
        prompt_lower = user_prompt.lower()
        
        # Check current difficulty in prompt
        curr_diff = "medium"
        if "difficulty: hard" in prompt_lower:
            curr_diff = "hard"
        elif "difficulty: easy" in prompt_lower:
            curr_diff = "easy"

        # Check depth of answer length & keywords
        answer_section = prompt_lower.split("candidate answer:")[-1] if "candidate answer:" in prompt_lower else prompt_lower
        words = len(answer_section.split())

        has_technical_depth = any(term in answer_section for term in [
            "gradient", "synchronous", "asynchronous", "isolation", "serializable",
            "cgroup", "wal", "event loop", "all-gather", "checkpointing", "receptive field",
            "trade-off", "bottleneck", "concurrency", "mitigation", "profile", "decompose"
        ])

        if words > 40 and has_technical_depth:
            rating = "strong"
            score = 92
            rationale = "Candidate provided a comprehensive response addressing core mechanical bottlenecks and practical mitigations."
            strengths = ["Identified underlying theoretical root cause", "Provided structured architectural mitigations"]
            improvements = ["Could further quantify memory vs latency trade-offs"]
        elif words > 15:
            rating = "adequate"
            score = 74
            rationale = "Candidate demonstrated valid high-level understanding of the concept but omitted specific lower-level execution details."
            strengths = ["Correct overall troubleshooting direction"]
            improvements = ["Lacked depth on edge cases and synchronization nuances"]
        else:
            rating = "weak"
            score = 42
            rationale = "Response was too brief and lacked concrete technical substance or problem analysis."
            strengths = ["Basic familiarity with terminology"]
            improvements = ["Did not address the failure scenario or provide technical justification"]

        next_diff = self._calculate_next_difficulty(curr_diff, rating)

        return json.dumps({
            "rating": rating,
            "score": score,
            "rationale": rationale,
            "strengths": strengths,
            "improvement_areas": improvements,
            "next_difficulty": next_diff
        })

    def evaluate_answer(
        self,
        question_text: str,
        topic: str,
        difficulty: str,
        answer_text: str,
        candidate_level: str = "mid"
    ) -> AnswerEvaluationPayload:
        """
        Evaluates a single answer and computes adapted next difficulty.
        """
        user_prompt = (
            f"Candidate Stated Experience Level: {candidate_level.upper()}\n"
            f"Question Topic: {topic}\n"
            f"Question Current Difficulty: {difficulty.upper()}\n\n"
            f"Scenario Question:\n\"{question_text}\"\n\n"
            f"Candidate Answer:\n\"{answer_text}\"\n\n"
            f"Please evaluate this response."
        )

        response_str = self._call_llm(user_prompt, system_prompt=EVALUATOR_SYSTEM_PROMPT)

        try:
            cleaned = self._clean_json(response_str)
            data = json.loads(cleaned)
            # Ensure next difficulty is populated accurately
            if "next_difficulty" not in data or not data["next_difficulty"]:
                data["next_difficulty"] = self._calculate_next_difficulty(difficulty, data.get("rating", "adequate"))
            return AnswerEvaluationPayload.model_validate(data)
        except Exception as e:
            logger.warning(f"Failed to parse LLM evaluation ({e}), using fallback.")
            fallback_json = self._heuristic_evaluation_fallback(user_prompt)
            data = json.loads(fallback_json)
            return AnswerEvaluationPayload.model_validate(data)

    def generate_session_summary(
        self,
        session_id: str,
        candidate_role: str,
        questions_log: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Synthesizes the entire session into an executive hiring summary.
        """
        if not questions_log:
            return {
                "overall_score": 0,
                "overall_rating": "needs_review",
                "executive_summary": "Session ended with no questions answered.",
                "topic_breakdown": {},
                "top_strengths": [],
                "growth_areas": []
            }

        scores = [q.get("score", 70) for q in questions_log]
        avg_score = int(sum(scores) / max(1, len(scores)))

        # Compute topic breakdown
        topic_scores: Dict[str, List[int]] = {}
        for q in questions_log:
            t = q.get("topic", "General Engineering")
            s = q.get("score", 70)
            topic_scores.setdefault(t, []).append(s)

        topic_breakdown = {t: int(sum(s_list) / len(s_list)) for t, s_list in topic_scores.items()}

        # Build transcript prompt for LLM summary
        transcript_lines = []
        for i, q in enumerate(questions_log, 1):
            transcript_lines.append(
                f"Q{i} [{q.get('topic', 'N/A')}] (Difficulty: {q.get('difficulty', 'N/A')}, Score: {q.get('score', 0)}/100, Rating: {q.get('rating', 'N/A')}):\n"
                f"Question: {q.get('question_text', '')}\n"
                f"Answer: {q.get('answer_text', '')}\n"
                f"Evaluation Rationale: {q.get('rationale', '')}\n"
            )

        transcript_str = "\n".join(transcript_lines)
        user_prompt = (
            f"Target Role: {candidate_role}\n"
            f"Overall Average Score: {avg_score}/100\n\n"
            f"Interview Transcript & Evaluations:\n{transcript_str}"
        )

        llm_response = self._call_llm(user_prompt, system_prompt=SUMMARY_SYSTEM_PROMPT)

        try:
            cleaned = self._clean_json(llm_response)
            data = json.loads(cleaned)
        except Exception:
            # Fallback heuristic summary
            rating = "recommended" if avg_score >= 75 else ("needs_review" if avg_score >= 60 else "not_recommended")
            if avg_score >= 90:
                rating = "strongly_recommended"
            data = {
                "overall_rating": rating,
                "executive_summary": f"Candidate demonstrated solid technical grounding for the {candidate_role} position with an average competency score of {avg_score}/100.",
                "top_strengths": ["Applied system reasoning", "Solid grasp of core architectural concepts"],
                "growth_areas": ["Fine-tuning edge case analysis under extreme scale"]
            }

        data["overall_score"] = avg_score
        data["topic_breakdown"] = topic_breakdown
        return data

    def _clean_json(self, text: str) -> str:
        text = text.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()
        return text


# Module-level convenience functions

def evaluate_candidate_answer(
    question_text: str,
    topic: str,
    difficulty: str,
    answer_text: str,
    candidate_level: str = "mid",
) -> AnswerEvaluationPayload:
    """
    Evaluate a single candidate answer against the technical rubric.

    Calls the LLM (OpenAI → Gemini → deterministic fallback) to produce a
    ``weak`` / ``adequate`` / ``strong`` rating, a 0–100 numerical score,
    a diagnostic rationale, and the adapted difficulty for the next question.

    Args:
        question_text: The full text of the scenario question that was posed.
        topic: The competency domain being assessed (e.g. "Gradient Optimization").
        difficulty: Current question difficulty (``"easy"``, ``"medium"``, or ``"hard"``).
        answer_text: The raw text of the candidate's submitted answer.
        candidate_level: Stated seniority level (``"junior"``, ``"mid"``, ``"senior"``).

    Returns:
        A validated :class:`AnswerEvaluationPayload` with rating, score, rationale,
        strengths, improvement areas, and ``next_difficulty``.
    """
    service = AnswerEvaluatorService()
    return service.evaluate_answer(
        question_text=question_text,
        topic=topic,
        difficulty=difficulty,
        answer_text=answer_text,
        candidate_level=candidate_level,
    )


def synthesize_session_summary(
    session_id: str,
    candidate_role: str,
    questions_log: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Legacy session synthesis helper used by the evaluator's own summariser.

    .. deprecated::
        The primary session summary path now runs through
        :func:`app.services.summary.generate_session_summary`, which produces a
        richer :class:`StructuredSessionSummary` schema with narrative prose and
        per-topic breakdowns persisted to the ``Session`` database record.
        This function is retained for backwards compatibility with any tooling
        that calls the evaluator layer directly.

    Args:
        session_id: UUID of the session (used as metadata in the response dict).
        candidate_role: Target role label for the session.
        questions_log: List of dicts containing ``topic``, ``difficulty``,
            ``question_text``, ``answer_text``, ``score``, ``rating``,
            and ``rationale`` for each evaluated question.

    Returns:
        A dict with keys ``overall_score``, ``overall_rating``,
        ``executive_summary``, ``topic_breakdown``, ``top_strengths``,
        and ``growth_areas``.
    """
    service = AnswerEvaluatorService()
    return service.generate_session_summary(
        session_id=session_id,
        candidate_role=candidate_role,
        questions_log=questions_log,
    )

