from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class AnswerBase(BaseModel):
    question_id: str = Field(..., description="Foreign key to Question ID")
    answer_text: str = Field(..., description="Candidate's submitted response")
    evaluation: Optional[Dict[str, Any]] = Field(default=None, description="AI Evaluation payload")


class AnswerCreate(BaseModel):
    question_id: str = Field(..., description="Foreign key to Question ID")
    answer_text: str = Field(..., description="Candidate's submitted response")


class AnswerResponse(AnswerBase):
    id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
