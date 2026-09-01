from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class CandidateBase(BaseModel):
    target_role: str = Field(..., description="Target job role")
    resume_text: str = Field(..., description="Raw text extracted from resume")
    extracted_skills: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Parsed skills JSON")


class CandidateCreate(CandidateBase):
    pass


class CandidateUpdate(BaseModel):
    target_role: Optional[str] = None
    resume_text: Optional[str] = None
    extracted_skills: Optional[Dict[str, Any]] = None


class CandidateResponse(CandidateBase):
    id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
