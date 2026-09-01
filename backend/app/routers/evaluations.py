from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.question import Question
from app.models.answer import Answer
from app.schemas.answer import AnswerCreate, AnswerResponse

router = APIRouter(prefix="/answers", tags=["Answers & Evaluations"])


@router.post("", response_model=AnswerResponse, status_code=status.HTTP_201_CREATED)
def submit_answer(answer_in: AnswerCreate, db: Session = Depends(get_db)):
    """
    Submit a candidate's answer for a question.
    """
    question = db.query(Question).filter(Question.id == answer_in.question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    answer = Answer(
        question_id=answer_in.question_id,
        answer_text=answer_in.answer_text,
        evaluation={"status": "pending_evaluation"}
    )
    db.add(answer)
    db.commit()
    db.refresh(answer)
    return answer


@router.get("/{answer_id}", response_model=AnswerResponse)
def get_answer(answer_id: str, db: Session = Depends(get_db)):
    """
    Get answer and its evaluation details.
    """
    answer = db.query(Answer).filter(Answer.id == answer_id).first()
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")
    return answer
