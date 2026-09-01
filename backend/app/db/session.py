from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.config import settings

# SQLite requires check_same_thread=False for multi-threaded use (e.g. FastAPI with multiple workers).
# For Postgres this arg is silently ignored, so it's safe to pass unconditionally.
_connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a scoped database session and ensures
    it is closed after request completion, even on errors.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
