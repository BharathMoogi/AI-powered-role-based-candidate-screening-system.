"""
Backend service layer package.

Provides the following production services:
- vector_db       — ChromaDB client factory and collection management
- ingestion       — PDF extraction, recursive token chunking, embedding + upsert
- resume          — LLM-based structured resume parsing with schema validation and extract_resume_data
- query_builder   — Conceptual retrieval query synthesis from parsed resume data
- interview_engine — Resume-driven question generation and RAG context retrieval
- evaluator       — Per-answer rubric evaluation and dynamic difficulty adaptation
- summary         — Full session synthesis with narrative prose and DB persistence
"""

from app.services.vector_db import get_chroma_client, get_or_create_collection
from app.services.ingestion import (
    ingest_pdf,
    KnowledgeIngestionService,
    PDFExtractor,
    RecursiveTokenChunker,
    EmbeddingGenerator,
)
from app.services.resume import (
    parse_resume,
    extract_resume_data,
    ResumeParserService,
    ParsedResume,
    ProjectDetail,
)
from app.services.query_builder import (
    build_retrieval_queries,
    DynamicQueryBuilder,
    RetrievalQueryItem,
    RetrievalQueryPlan,
)
from app.services.interview_engine import (
    retrieve_chunks,
    retrieve_context,
    generate_question,
    generate_interview_session_questions,
    QuestionGenerator,
    RetrievedChunk,
    GeneratedQuestion,
)
from app.services.evaluator import (
    evaluate_candidate_answer,
    synthesize_session_summary,
)
from app.services.summary import (
    generate_session_summary,
    SessionSummaryService,
    StructuredSessionSummary,
    TopicAssessment,
)

__all__ = [
    # vector_db
    "get_chroma_client",
    "get_or_create_collection",
    # ingestion
    "ingest_pdf",
    "KnowledgeIngestionService",
    "PDFExtractor",
    "RecursiveTokenChunker",
    "EmbeddingGenerator",
    # resume
    "parse_resume",
    "extract_resume_data",
    "ResumeParserService",
    "ParsedResume",
    "ProjectDetail",
    # query_builder
    "build_retrieval_queries",
    "DynamicQueryBuilder",
    "RetrievalQueryItem",
    "RetrievalQueryPlan",
    # interview_engine
    "retrieve_chunks",
    "retrieve_context",
    "generate_question",
    "generate_interview_session_questions",
    "QuestionGenerator",
    "RetrievedChunk",
    "GeneratedQuestion",
    # evaluator
    "evaluate_candidate_answer",
    "synthesize_session_summary",
    # summary
    "generate_session_summary",
    "SessionSummaryService",
    "StructuredSessionSummary",
    "TopicAssessment",
]
