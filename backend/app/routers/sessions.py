from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.candidate import Candidate
from app.models.session import Session as ScreeningSession
from app.schemas.session import SessionCreate, SessionResponse

router = APIRouter(prefix="/sessions", tags=["Screening Sessions"])


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(session_in: SessionCreate, db: Session = Depends(get_db)):
    """
    Start a screening session for a candidate.
    """
    candidate = db.query(Candidate).filter(Candidate.id == session_in.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    new_session = ScreeningSession(
        candidate_id=session_in.candidate_id,
        role=session_in.role,
        status=session_in.status
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session


@router.get("", response_model=List[SessionResponse])
def list_sessions(candidate_id: str = None, skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """
    List screening sessions optionally filtered by candidate_id.
    """
    query = db.query(ScreeningSession)
    if candidate_id:
        query = query.filter(ScreeningSession.candidate_id == candidate_id)
    return query.offset(skip).limit(limit).all()


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, db: Session = Depends(get_db)):
    """
    Get session details by ID.
    """
    session = db.query(ScreeningSession).filter(ScreeningSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
