import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import DateTime, String, Text, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.session import Session


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    resume_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Full extracted raw text from the candidate resume"
    )
    extracted_skills: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Structured JSON of candidate skills, experience years, technologies"
    )
    target_role: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        index=True,
        comment="Target job role (e.g., Backend Engineer, Data Scientist)"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    sessions: Mapped[List["Session"]] = relationship(
        "Session",
        back_populates="candidate",
        cascade="all, delete-orphan",
        order_by="Session.created_at.desc()"
    )

    def __repr__(self) -> str:
        return f"<Candidate(id='{self.id}', role='{self.target_role}', created_at='{self.created_at}')>"
