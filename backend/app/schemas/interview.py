"""
Interview & Screening API Schemas
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.services.resume import ParsedResume
from app.services.summary import TopicAssessment, StructuredSessionSummary


# ============================================================================
# Candidate Creation Schemas
# ============================================================================

class CandidateCreateJSON(BaseModel):
    target_role: str = Field(..., description="Target job role (e.g. 'Machine Learning Engineer', 'Backend Engineer')")
    resume_text: str = Field(..., description="Raw text of candidate resume")


class CandidateUploadResponse(BaseModel):
    id: str = Field(..., description="Unique candidate ID")
    target_role: str = Field(..., description="Screening target role")
    resume_summary: Optional[str] = Field(None, description="Brief candidate background summary")
    extracted_data: Dict[str, Any] = Field(..., description="Extracted skills, tech, domains, and experience level")
    created_at: datetime = Field(..., description="Timestamp of profile creation")

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Session Schemas
# ============================================================================

class SessionStartRequest(BaseModel):
    candidate_id: str = Field(..., description="Candidate ID to initiate screening session for")
    role: Optional[str] = Field(None, description="Optional override role; defaults to candidate target_role")


class QuestionResponse(BaseModel):
    id: str = Field(..., description="Question UUID")
    session_id: str = Field(..., description="Session UUID")
    question_text: str = Field(..., description="Scenario interview question text")
    topic: str = Field(..., description="Competency topic")
    difficulty: str = Field(..., description="Difficulty: easy, medium, hard")
    order_index: int = Field(..., description="Question number in session (0-indexed)")
    source_chunk_ids: Optional[List[Any]] = Field(default_factory=list, description="Cited ChromaDB chunk IDs")

    model_config = ConfigDict(from_attributes=True)


class SessionStartResponse(BaseModel):
    session_id: str = Field(..., description="Created session UUID")
    candidate_id: str = Field(..., description="Candidate UUID")
    role: str = Field(..., description="Screening role")
    status: str = Field(..., description="Session status (e.g. 'in_progress')")
    first_question: QuestionResponse = Field(..., description="Initial grounded scenario question")


class CurrentQuestionResponse(BaseModel):
    session_id: str
    status: str
    question: Optional[QuestionResponse] = Field(None, description="Current unanswered question or None if finished")
    is_finished: bool = Field(False, description="True if max questions answered and session is ready for completion")
    total_answered: int = Field(0, description="Count of answered questions in this session")


# ============================================================================
# Answer & Evaluation Schemas
# ============================================================================

class AnswerSubmissionRequest(BaseModel):
    answer_text: str = Field(..., min_length=5, description="Candidate's technical response text")


class AnswerEvaluationPayload(BaseModel):
    rating: Literal["weak", "adequate", "strong"] = Field(..., description="Evaluation grade")
    score: int = Field(..., ge=0, le=100, description="Numerical evaluation score (0-100)")
    rationale: str = Field(..., description="Detailed rationale explaining the grade")
    strengths: List[str] = Field(default_factory=list, description="Key technical points handled well")
    improvement_areas: List[str] = Field(default_factory=list, description="Missing trade-offs or inaccuracies")
    next_difficulty: str = Field(..., description="Adapted difficulty for following question")


class AnswerSubmissionResponse(BaseModel):
    answer_id: str = Field(..., description="Submitted answer UUID")
    question_id: str = Field(..., description="Evaluated question UUID")
    evaluation: AnswerEvaluationPayload = Field(..., description="Structured evaluation output")
    next_question: Optional[QuestionResponse] = Field(None, description="Next adaptive question, or null if completed")
    session_status: str = Field(..., description="Current session state (in_progress, ready_for_completion, completed)")


# ============================================================================
# Session Summary & Insights Schemas
# ============================================================================

class QuestionSummaryItem(BaseModel):
    order_index: int
    topic: str
    difficulty: str
    question_text: str
    answer_text: str
    rating: str
    score: int
    rationale: str


class SessionSummaryResponse(BaseModel):
    session_id: str
    candidate_id: str
    role: str
    status: str
    total_questions: int
    overall_assessment: str = Field(..., description="Cohesive natural narrative paragraph summarizing performance")
    approximate_score_out_of_10: float = Field(..., ge=0.0, le=10.0, description="Overall technical score out of 10")
    score_justification: str = Field(..., description="Concise justification supporting assigned score")
    hiring_recommendation: Literal["strong_hire", "hire", "lean_hire", "lean_no_hire", "no_hire"] = Field(
        ...,
        description="Final hiring recommendation"
    )
    topic_breakdown: List[TopicAssessment] = Field(default_factory=list, description="Topic-by-topic evaluation breakdown")
    concrete_improvements: List[str] = Field(default_factory=list, description="2-3 actionable technical recommendations")
    questions: List[QuestionSummaryItem] = Field(default_factory=list, description="Detailed per-question log")
