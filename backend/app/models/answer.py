import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import DateTime, ForeignKey, String, Text, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.question import Question


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    question_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    answer_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Candidate's submitted response text"
    )
    evaluation: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="AI Evaluation output (score, rubric checks, strengths, weaknesses, followups)"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    question: Mapped["Question"] = relationship(
        "Question",
        back_populates="answers"
    )

    def __repr__(self) -> str:
        return f"<Answer(id='{self.id}', question_id='{self.question_id}', created_at='{self.created_at}')>"
