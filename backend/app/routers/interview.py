"""
Interview Session & Screening API Router

Implements the end-to-end role-based candidate screening workflow:
- Candidate onboarding & automated resume skill extraction
- Session initialization with pre-generated grounded scenario questions
- Real-time answer evaluation & dynamic difficulty adaptation
- Automated session completion and comprehensive candidate hiring reports
"""

import json
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as DBSession

from app.db.session import get_db
from app.models.candidate import Candidate
from app.models.session import Session as ScreeningSession
from app.models.question import Question
from app.models.answer import Answer
from app.services.resume import parse_resume, ParsedResume
from app.services.query_builder import build_retrieval_queries
from app.services.interview_engine import retrieve_context, generate_question, GeneratedQuestion
from app.services.evaluator import evaluate_candidate_answer, synthesize_session_summary
from app.schemas.interview import (
    CandidateCreateJSON,
    CandidateUploadResponse,
    SessionStartRequest,
    SessionStartResponse,
    QuestionResponse,
    CurrentQuestionResponse,
    AnswerSubmissionRequest,
    AnswerSubmissionResponse,
    SessionSummaryResponse,
    QuestionSummaryItem,
)

logger = logging.getLogger("interview_router")
router = APIRouter(tags=["Interview & Screening Engine"])

MAX_QUESTIONS_PER_SESSION = 5


# ============================================================================
# 1. Candidate Upload & Extraction Endpoint
# ============================================================================

@router.post(
    "/candidates",
    response_model=CandidateUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Resume and Extract Structured Candidate Profile",
    description="""
Accepts either a PDF/text file upload (multipart/form-data) or a JSON payload (`{ target_role, resume_text }`).
Extracts structured skills, technologies, domains, experience level, and notable projects using LLM analysis with automated schema validation.
    """
)
async def create_candidate_profile(
    request: Request,
    db: DBSession = Depends(get_db)
):
    content_type = request.headers.get("content-type", "")
    target_role: Optional[str] = None
    resume_content: Any = None
    raw_resume_text: str = ""

    if "multipart/form-data" in content_type:
        form = await request.form()
        target_role = str(form.get("target_role", "")).strip() or None
        file_obj = form.get("file")
        if file_obj and hasattr(file_obj, "read"):
            resume_content = await file_obj.read()
            raw_resume_text = "Uploaded PDF Resume"
        else:
            resume_content = form.get("resume_text")
            raw_resume_text = str(resume_content or "")
    else:
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid JSON payload or content-type"
            )
        target_role = body.get("target_role")
        resume_content = body.get("resume_text")
        raw_resume_text = str(resume_content or "")

    if not target_role:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="target_role is required."
        )

    if not resume_content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Please provide a resume file or resume_text in request body."
        )

    try:
        parsed_resume: ParsedResume = parse_resume(resume_content)
    except Exception as e:
        logger.error(f"Resume parsing failure: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse resume into structured format: {str(e)}"
        )

    # Save to PostgreSQL
    candidate = Candidate(
        target_role=target_role,
        resume_text=parsed_resume.summary or raw_resume_text or "Extracted Resume",
        extracted_skills=parsed_resume.model_dump()
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    return CandidateUploadResponse(
        id=candidate.id,
        target_role=candidate.target_role,
        resume_summary=parsed_resume.summary,
        extracted_data=parsed_resume.model_dump(),
        created_at=candidate.created_at
    )


# ============================================================================
# 2. Start Session Endpoint
# ============================================================================

@router.post(
    "/sessions",
    response_model=SessionStartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start Screening Session and Pre-generate First Question",
    description="""
Initializes an interactive screening session for a candidate.
Queries the role-specific ChromaDB knowledge base based on the candidate's extracted profile and generates the first applied scenario question.
    """
)
def start_screening_session(
    request: SessionStartRequest,
    db: DBSession = Depends(get_db)
):
    candidate = db.query(Candidate).filter(Candidate.id == request.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    role = request.role or candidate.target_role
    extracted = candidate.extracted_skills or {}
    level = extracted.get("apparent_experience_level", "mid")

    # 1. Create Session
    session = ScreeningSession(
        candidate_id=candidate.id,
        role=role,
        status="in_progress"
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # 2. Build dynamic queries and retrieve grounded knowledge base context
    queries = build_retrieval_queries(resume=extracted, role=role)
    chunks = retrieve_context(queries=queries, role=role, top_k=3)

    projects = extracted.get("notable_projects", [])
    first_project = projects[0] if projects else None

    first_query = queries[0] if queries else None
    if first_project:
        for q in queries:
            if q.project_name == first_project.get("name") or any(t.lower() in q.source_skill.lower() for t in first_project.get("technologies", [])):
                first_query = q
                break

    matching_chunks = [
        c for c in chunks
        if (first_project and c.project_name == first_project.get("name"))
        or (first_query and (first_query.source_skill.lower() in c.matched_query.lower() or first_query.query.lower() in c.matched_query.lower()))
    ]
    if not matching_chunks:
        matching_chunks = chunks[:2] if chunks else []

    # Initial difficulty: hard for senior, medium for mid/junior
    init_diff = "hard" if level == "senior" else "medium"
    first_q: GeneratedQuestion = generate_question(
        chunk_context=matching_chunks,
        resume_data=extracted,
        source_skill=first_query.source_skill if first_query else None,
        query_item=first_query,
        project_name=first_project.get("name") if first_project else None,
        project_tech=first_project.get("technologies") if first_project else None,
        project_description=first_project.get("description") if first_project else None,
        difficulty=init_diff
    )

    # 3. Persist First Question
    db_question = Question(
        session_id=session.id,
        question_text=first_q.question_text,
        topic=first_q.topic,
        difficulty=first_q.difficulty,
        source_chunk_ids=first_q.source_chunk_ids,
        order_index=0
    )
    db.add(db_question)
    db.commit()
    db.refresh(db_question)

    return SessionStartResponse(
        session_id=session.id,
        candidate_id=candidate.id,
        role=session.role,
        status=session.status,
        first_question=QuestionResponse.model_validate(db_question)
    )


# ============================================================================
# 3. Get Current Question Endpoint
# ============================================================================

@router.get(
    "/sessions/{session_id}/current-question",
    response_model=CurrentQuestionResponse,
    summary="Get Current Active Question for Session",
    description="""
Retrieves the current active (unanswered) question in the screening session.
Returns `is_finished=True` if the candidate has answered all allocated session questions.
    """
)
def get_current_question(
    session_id: str,
    db: DBSession = Depends(get_db)
):
    session = db.query(ScreeningSession).filter(ScreeningSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    questions = db.query(Question).filter(Question.session_id == session_id).order_by(Question.order_index).all()
    if not questions:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No questions found for this session")

    # Find the first question without an answer
    unanswered_q = None
    answered_count = 0
    for q in questions:
        ans = db.query(Answer).filter(Answer.question_id == q.id).first()
        if not ans and unanswered_q is None:
            unanswered_q = q
        elif ans:
            answered_count += 1

    is_finished = (unanswered_q is None and answered_count >= len(questions)) or session.status in ["completed", "ready_for_completion"]

    return CurrentQuestionResponse(
        session_id=session.id,
        status=session.status,
        question=QuestionResponse.model_validate(unanswered_q) if unanswered_q else None,
        is_finished=is_finished,
        total_answered=answered_count
    )


# ============================================================================
# 4. Submit Answer & Adapt Difficulty Endpoint
# ============================================================================

@router.post(
    "/sessions/{session_id}/answer",
    response_model=AnswerSubmissionResponse,
    summary="Submit Candidate Answer, Evaluate, and Generate Next Question",
    description="""
Submits candidate's answer for evaluation.
1. Evaluates response quality against rubric criteria (weak/adequate/strong with rationale).
2. Adjusts difficulty dynamically for the next question.
3. Generates and stores the next grounded scenario question cycling across all projects.
    """
)
def submit_candidate_answer(
    session_id: str,
    request: AnswerSubmissionRequest,
    db: DBSession = Depends(get_db)
):
    session = db.query(ScreeningSession).filter(ScreeningSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if session.status == "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session is already completed")

    # Find the current unanswered question
    questions = db.query(Question).filter(Question.session_id == session_id).order_by(Question.order_index).all()
    current_q = None
    answered_count = 0
    for q in questions:
        ans = db.query(Answer).filter(Answer.question_id == q.id).first()
        if not ans and current_q is None:
            current_q = q
        elif ans:
            answered_count += 1

    if not current_q:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="All existing questions have already been answered")

    candidate = db.query(Candidate).filter(Candidate.id == session.candidate_id).first()
    level = candidate.extracted_skills.get("apparent_experience_level", "mid") if candidate and candidate.extracted_skills else "mid"

    # 1. Evaluate Candidate Answer
    eval_payload = evaluate_candidate_answer(
        question_text=current_q.question_text,
        topic=current_q.topic,
        difficulty=current_q.difficulty,
        answer_text=request.answer_text,
        candidate_level=level
    )

    # 2. Store Answer in Database
    db_answer = Answer(
        question_id=current_q.id,
        answer_text=request.answer_text,
        evaluation=eval_payload.model_dump()
    )
    db.add(db_answer)
    db.commit()
    db.refresh(db_answer)

    answered_count += 1
    next_question_response = None

    # 3. Generate Next Question cycling to the next distinct project
    if answered_count < MAX_QUESTIONS_PER_SESSION:
        queries = build_retrieval_queries(
            resume=candidate.extracted_skills or {},
            role=session.role
        )
        chunks = retrieve_context(queries=queries, role=session.role, top_k=3)

        next_idx = answered_count
        projects = (candidate.extracted_skills or {}).get("notable_projects", [])
        
        # Pick next project by rotating through projects
        target_project = projects[next_idx % len(projects)] if projects else None

        next_query = None
        if target_project:
            for q in queries:
                if q.project_name == target_project.get("name") or any(t.lower() in q.source_skill.lower() for t in target_project.get("technologies", [])):
                    next_query = q
                    break

        if not next_query:
            next_query = queries[next_idx % len(queries)] if queries else None

        # Filter chunks matching the target project / query
        matching_chunks = [
            c for c in chunks
            if (target_project and c.project_name == target_project.get("name"))
            or (next_query and (next_query.source_skill.lower() in c.matched_query.lower() or next_query.query.lower() in c.matched_query.lower()))
        ]
        if not matching_chunks:
            matching_chunks = chunks[next_idx % len(chunks):next_idx % len(chunks) + 2] if chunks else []

        new_q: GeneratedQuestion = generate_question(
            chunk_context=matching_chunks,
            resume_data=candidate.extracted_skills or {},
            source_skill=next_query.source_skill if next_query else None,
            query_item=next_query,
            project_name=target_project.get("name") if target_project else None,
            project_tech=target_project.get("technologies") if target_project else None,
            project_description=target_project.get("description") if target_project else None,
            difficulty=eval_payload.next_difficulty  # Adapted difficulty
        )

        db_next_q = Question(
            session_id=session.id,
            question_text=new_q.question_text,
            topic=new_q.topic,
            difficulty=new_q.difficulty,
            source_chunk_ids=new_q.source_chunk_ids,
            order_index=next_idx
        )
        db.add(db_next_q)
        db.commit()
        db.refresh(db_next_q)

        next_question_response = QuestionResponse.model_validate(db_next_q)
        session.status = "in_progress"
    else:
        session.status = "ready_for_completion"

    db.commit()


    return AnswerSubmissionResponse(
        answer_id=db_answer.id,
        question_id=current_q.id,
        evaluation=eval_payload,
        next_question=next_question_response,
        session_status=session.status
    )


# ============================================================================
# 5. Complete Session Endpoint
# ============================================================================

@router.post(
    "/sessions/{session_id}/complete",
    response_model=SessionSummaryResponse,
    summary="Complete Interview Session and Generate Performance Summary",
    description="""
Finalizes the interview screening session.
Pulls all question-answer pairs and evaluations to synthesize a comprehensive executive evaluation report with narrative assessment, score out of 10, topic breakdown, concrete improvements, and hiring recommendation.
Persists the structured summary on the session record.
    """
)
def complete_screening_session(
    session_id: str,
    db: DBSession = Depends(get_db)
):
    session = db.query(ScreeningSession).filter(ScreeningSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    from app.services.summary import generate_session_summary
    summary_obj = generate_session_summary(session_id=session.id, db=db)

    # Format question transcript items for response
    questions = db.query(Question).filter(Question.session_id == session_id).order_by(Question.order_index).all()
    question_summary_items: List[QuestionSummaryItem] = []
    for q in questions:
        ans = db.query(Answer).filter(Answer.question_id == q.id).first()
        if ans and ans.evaluation:
            eval_data = ans.evaluation
            question_summary_items.append(
                QuestionSummaryItem(
                    order_index=q.order_index,
                    topic=q.topic,
                    difficulty=q.difficulty,
                    question_text=q.question_text,
                    answer_text=ans.answer_text,
                    rating=eval_data.get("rating", "adequate"),
                    score=eval_data.get("score", 70),
                    rationale=eval_data.get("rationale", "")
                )
            )

    return SessionSummaryResponse(
        session_id=session.id,
        candidate_id=session.candidate_id,
        role=session.role,
        status=session.status,
        total_questions=len(question_summary_items),
        overall_assessment=summary_obj.overall_assessment,
        approximate_score_out_of_10=summary_obj.approximate_score_out_of_10,
        score_justification=summary_obj.score_justification,
        hiring_recommendation=summary_obj.hiring_recommendation,
        topic_breakdown=summary_obj.topic_breakdown,
        concrete_improvements=summary_obj.concrete_improvements,
        questions=question_summary_items
    )


# ============================================================================
# 6. Get Session Summary Endpoint
# ============================================================================

@router.get(
    "/sessions/{session_id}/summary",
    response_model=SessionSummaryResponse,
    summary="Get Structured Session Summary & Diagnostic Insights",
    description="""
Retrieves the comprehensive screening synthesis report including narrative assessment, score out of 10, topic breakdown, candidate improvement suggestions, and per-question evaluations.
    """
)
def get_session_summary(
    session_id: str,
    db: DBSession = Depends(get_db)
):
    session = db.query(ScreeningSession).filter(ScreeningSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    from app.services.summary import generate_session_summary
    if session.summary:
        from app.services.summary import StructuredSessionSummary
        try:
            summary_obj = StructuredSessionSummary.model_validate(session.summary)
        except Exception:
            summary_obj = generate_session_summary(session_id=session.id, db=db)
    else:
        summary_obj = generate_session_summary(session_id=session.id, db=db)

    # Format question transcript items
    questions = db.query(Question).filter(Question.session_id == session_id).order_by(Question.order_index).all()
    question_summary_items: List[QuestionSummaryItem] = []
    for q in questions:
        ans = db.query(Answer).filter(Answer.question_id == q.id).first()
        if ans and ans.evaluation:
            eval_data = ans.evaluation
            question_summary_items.append(
                QuestionSummaryItem(
                    order_index=q.order_index,
                    topic=q.topic,
                    difficulty=q.difficulty,
                    question_text=q.question_text,
                    answer_text=ans.answer_text,
                    rating=eval_data.get("rating", "adequate"),
                    score=eval_data.get("score", 70),
                    rationale=eval_data.get("rationale", "")
                )
            )

    return SessionSummaryResponse(
        session_id=session.id,
        candidate_id=session.candidate_id,
        role=session.role,
        status=session.status,
        total_questions=len(question_summary_items),
        overall_assessment=summary_obj.overall_assessment,
        approximate_score_out_of_10=summary_obj.approximate_score_out_of_10,
        score_justification=summary_obj.score_justification,
        hiring_recommendation=summary_obj.hiring_recommendation,
        topic_breakdown=summary_obj.topic_breakdown,
        concrete_improvements=summary_obj.concrete_improvements,
        questions=question_summary_items
    )

