from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.candidate import Candidate
from app.schemas.candidate import CandidateCreate, CandidateResponse

router = APIRouter(prefix="/candidates", tags=["Candidates"])


@router.post("", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
def create_candidate(candidate_in: CandidateCreate, db: Session = Depends(get_db)):
    """
    Create a new candidate profile with resume text and extracted skills.
    """
    candidate = Candidate(
        target_role=candidate_in.target_role,
        resume_text=candidate_in.resume_text,
        extracted_skills=candidate_in.extracted_skills
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


@router.get("", response_model=List[CandidateResponse])
def list_candidates(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """
    List all candidates.
    """
    return db.query(Candidate).offset(skip).limit(limit).all()


@router.get("/{candidate_id}", response_model=CandidateResponse)
def get_candidate(candidate_id: str, db: Session = Depends(get_db)):
    """
    Retrieve candidate profile by ID.
    """
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate
