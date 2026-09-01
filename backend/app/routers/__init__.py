from app.routers.health import router as health_router
from app.routers.candidates import router as candidates_router
from app.routers.sessions import router as sessions_router
from app.routers.questions import router as questions_router
from app.routers.evaluations import router as evaluations_router
from app.routers.interview import router as interview_router

__all__ = [
    "health_router",
    "candidates_router",
    "sessions_router",
    "questions_router",
    "evaluations_router",
    "interview_router",
]
