from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class QuestionBase(BaseModel):
    session_id: str = Field(..., description="Foreign key to Session ID")
    question_text: str = Field(..., description="Interview question text")
    source_chunk_ids: Optional[List[Any]] = Field(default_factory=list, description="Vector chunk IDs cited")
    topic: str = Field(..., description="Topic / competency domain")
    difficulty: str = Field(default="medium", description="Difficulty level")
    order_index: int = Field(default=0, description="Order sequence number")


class QuestionCreate(QuestionBase):
    pass


class QuestionResponse(QuestionBase):
    id: str

    model_config = ConfigDict(from_attributes=True)
