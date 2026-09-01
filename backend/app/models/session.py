import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, List, Optional
from sqlalchemy import DateTime, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.candidate import Candidate
    from app.models.question import Question


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    candidate_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    role: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        index=True,
        comment="Specific role being screened for during this session"
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        nullable=False,
        index=True,
        comment="Session status: pending, in_progress, completed, failed, evaluated"
    )
    summary: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Structured session summary and evaluation report"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    candidate: Mapped["Candidate"] = relationship(
        "Candidate",
        back_populates="sessions"
    )
    questions: Mapped[List["Question"]] = relationship(
        "Question",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Question.order_index"
    )

    def __repr__(self) -> str:
        return f"<Session(id='{self.id}', candidate_id='{self.candidate_id}', role='{self.role}', status='{self.status}')>"
