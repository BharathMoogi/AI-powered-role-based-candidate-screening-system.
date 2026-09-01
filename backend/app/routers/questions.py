from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.session import Session as ScreeningSession
from app.models.question import Question
from app.schemas.question import QuestionCreate, QuestionResponse

router = APIRouter(prefix="/questions", tags=["Questions"])


@router.post("", response_model=QuestionResponse, status_code=status.HTTP_201_CREATED)
def create_question(question_in: QuestionCreate, db: Session = Depends(get_db)):
    """
    Create a new question attached to a session.
    """
    session = db.query(ScreeningSession).filter(ScreeningSession.id == question_in.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    question = Question(
        session_id=question_in.session_id,
        question_text=question_in.question_text,
        source_chunk_ids=question_in.source_chunk_ids,
        topic=question_in.topic,
        difficulty=question_in.difficulty,
        order_index=question_in.order_index
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


@router.get("", response_model=List[QuestionResponse])
def list_questions(session_id: str, db: Session = Depends(get_db)):
    """
    Get all questions for a given session.
    """
    return db.query(Question).filter(Question.session_id == session_id).order_by(Question.order_index).all()
