from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class SessionBase(BaseModel):
    candidate_id: str = Field(..., description="Foreign key to Candidate ID")
    role: str = Field(..., description="Screening role")
    status: str = Field(default="pending", description="Session state (pending, in_progress, completed, failed)")


class SessionCreate(SessionBase):
    pass


class SessionUpdate(BaseModel):
    status: Optional[str] = None
    role: Optional[str] = None


class SessionResponse(SessionBase):
    id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
