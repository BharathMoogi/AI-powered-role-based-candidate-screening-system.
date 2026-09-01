import uuid
from typing import TYPE_CHECKING, Any, List, Optional
from sqlalchemy import ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.session import Session
    from app.models.answer import Answer


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    question_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Generated role-based screening question"
    )
    source_chunk_ids: Mapped[Optional[List[Any]]] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment="List of ChromaDB chunk IDs referenced to synthesize this question"
    )
    topic: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Domain topic e.g. System Design, Concurrency, SQL, Machine Learning"
    )
    difficulty: Mapped[str] = mapped_column(
        String(50),
        default="medium",
        nullable=False,
        comment="Difficulty rating: easy, medium, hard"
    )
    order_index: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Sequence index within the screening session"
    )

    # Relationships
    session: Mapped["Session"] = relationship(
        "Session",
        back_populates="questions"
    )
    answers: Mapped[List["Answer"]] = relationship(
        "Answer",
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="Answer.created_at.desc()"
    )

    def __repr__(self) -> str:
        return f"<Question(id='{self.id}', session_id='{self.session_id}', topic='{self.topic}', difficulty='{self.difficulty}')>"
