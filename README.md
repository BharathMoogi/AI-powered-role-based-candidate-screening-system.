# AI-Powered Role-Based Candidate Screening System

An end-to-end technical interview system that grounds every question in a domain knowledge base, adapts difficulty in real time, and synthesises a hiring committee report at the end of each session.

**Stack:** FastAPI · Next.js 14 · PostgreSQL 16 · ChromaDB · OpenAI / Gemini · Alembic · Docker

---

## Table of Contents

1. [Quick Start](#1-quick-start)
2. [Environment Variables](#2-environment-variables)
3. [Docker Services](#3-docker-services)
4. [Database Migrations](#4-database-migrations)
5. [Knowledge Ingestion](#5-knowledge-ingestion)
6. [Running the App](#6-running-the-app)
7. [System Architecture](#7-system-architecture)
8. [Key Design Decisions](#8-key-design-decisions)
9. [Known Limitations & Future Work](#9-known-limitations--future-work)

---

## 1. Quick Start

```powershell
# 1. Clone and enter the project
git clone <repo-url>
cd "AI-powered role-based candidate screening system"

# 2. Copy and fill env files
copy backend\.env.example backend\.env      # fill OPENAI_API_KEY or GEMINI_API_KEY
copy frontend\.env.example frontend\.env.local

# 3. Start Postgres + ChromaDB
docker-compose up -d

# 4. Apply DB migrations
cd backend
pip install -r requirements.txt
alembic upgrade head

# 5. Ingest a knowledge base PDF
python scripts/ingest.py --pdf "../data/ml_textbook.pdf" --role "Machine Learning Engineer" --source "Tom Mitchell ML"

# 6. Run the backend
uvicorn app.main:app --reload --port 8000

# 7. Run the frontend (separate terminal)
cd ../frontend
npm install
npm run dev
```

Open **http://localhost:3000** to start a screening session.  
FastAPI docs are at **http://localhost:8000/docs**.

---

## 2. Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `OPENAI_API_KEY` | Recommended | `""` | Primary LLM + embedding provider |
| `GEMINI_API_KEY` | Fallback | `""` | Secondary LLM + embedding provider |
| `DATABASE_URL` | Yes | `postgresql://postgres:postgres@localhost:5432/screening_db` | PostgreSQL connection string |
| `CHROMA_PERSIST_DIR` | No | `./chroma_data` | Local ChromaDB storage directory |
| `CHROMA_USE_SERVER` | No | `false` | Set `true` to use remote ChromaDB container |
| `CHROMA_HOST` | No | `localhost` | ChromaDB server host (when `CHROMA_USE_SERVER=true`) |
| `CHROMA_PORT` | No | `8000` | ChromaDB server port |
| `CORS_ORIGINS` | No | `http://localhost:3000` | Comma-separated allowed CORS origins |
| `ENVIRONMENT` | No | `development` | `development` or `production` |

> **Fallback behaviour:** Both API keys are optional. If neither is set, all LLM and embedding calls fall back to a deterministic heuristic engine — useful for offline testing. The heuristic embeddings are feature-hash based, so ChromaDB retrieval will function but with lower semantic accuracy than real embeddings.

### Frontend (`frontend/.env.local`)

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | Yes | `http://localhost:8000/api/v1` | FastAPI backend URL |

---

## 3. Docker Services

`docker-compose.yml` starts:

| Service | Port | Image |
|---|---|---|
| `postgres` | `5432` | `postgres:16-alpine` |
| `chromadb` | `8001` | `chromadb/chroma:latest` |

```powershell
docker-compose up -d          # start in background
docker-compose down           # stop
docker-compose down -v        # stop + wipe volumes
```

---

## 4. Database Migrations

Alembic is used for schema migrations. After changing any SQLAlchemy model:

```powershell
cd backend

# Auto-generate a new migration
alembic revision --autogenerate -m "describe the change"

# Apply all pending migrations
alembic upgrade head

# Roll back one step
alembic downgrade -1
```

The initial migration (`001_initial_schema.py`) creates all four tables: `candidates`, `sessions`, `questions`, `answers`.

---

## 5. Knowledge Ingestion

Place role-specific PDF textbooks (or any structured domain material) in `/data/`, then run:

```powershell
cd backend

# Basic ingestion
python scripts/ingest.py \
  --pdf "../data/ml_textbook.pdf" \
  --role "Machine Learning Engineer" \
  --source "Tom Mitchell ML"

# Force re-ingest (ignore idempotency check)
python scripts/ingest.py \
  --pdf "../data/system_design.pdf" \
  --role "Distributed Systems Engineer" \
  --source "Designing Data-Intensive Applications" \
  --force

# Flags
#   --pdf      Path to PDF file (required)
#   --role     Exact role string to tag chunks with (required)
#   --source   Human-readable source/book name for metadata
#   --force    Re-ingest even if document hash already exists in ChromaDB
```

Each chunk is stored with metadata `{role, source_book, chunk_index, page_number, token_count}`. The `role` field is used as a ChromaDB `where` filter at retrieval time, so each role's knowledge base is logically isolated.

---

## 6. Running the App

### Backend

```powershell
cd backend
uvicorn app.main:app --reload --port 8000
```

- API root: `http://localhost:8000/`
- OpenAPI docs: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Frontend

```powershell
cd frontend
npm run dev       # development (hot reload on http://localhost:3000)
npm run build     # production build
npm run start     # serve production build
```

### Test Suite

```powershell
cd backend
pytest tests/ -v
```

12 tests cover ingestion, resume parsing, query building, interview engine, API lifecycle, and session summary.

---

## 7. System Architecture

```mermaid
flowchart TB
    subgraph Upload ["1 · Resume Upload (Landing Page)"]
        A[Candidate PDF / Text] -->|POST /candidates| B[FastAPI]
    end

    subgraph Parse ["2 · LLM Resume Parsing"]
        B --> C[LLM JSON Extraction]
        C --> D[ParsedResume\nSkills · Technologies · Domains · Level]
        D --> PG[(PostgreSQL\ncandidates)]
    end

    subgraph Query ["3 · Query Construction"]
        D -->|build_retrieval_queries| E[5-8 Conceptual Queries\nSkill → Underlying Concept]
    end

    subgraph Retrieval ["4 · RAG Retrieval"]
        E -->|where role=X top_k=3| F[(ChromaDB\nRole Knowledge Base)]
        F --> G[Deduplicated Chunks\nwith Source Metadata]
    end

    subgraph QGen ["5 · Question Generation"]
        G --> H[LLM Prompt\nAnti-generic · Scenario-based]
        D --> H
        H --> I[Question\ntopic · difficulty · chunk_ids]
        I --> PG2[(PostgreSQL\nquestions)]
    end

    subgraph Loop ["6 · Interview Loop  POST /answer "]
        I -->|shown to candidate| J[Candidate Answer Textarea]
        J -->|submit| K[LLM Evaluator\nweak / adequate / strong · score · rationale]
        K -->|difficulty adaptation| L{Rating?}
        L -->|strong| M[Escalate Difficulty]
        L -->|adequate| N[Keep Difficulty]
        L -->|weak| O[Reduce Difficulty]
        M & N & O -->|generate next question| F
        K --> PG3[(PostgreSQL\nanswers · evaluation JSON)]
    end

    subgraph Summary ["7 · Session Summary  POST /complete "]
        PG3 -->|pull full transcript| P[LLM Narrative Synthesis]
        P --> Q[StructuredSessionSummary\nProse · Score/10 · Topic Breakdown\nImprovements · Hiring Rec]
        Q --> PG4[(PostgreSQL\nsession.summary JSON)]
        Q --> R[Summary Page\nFrontend]
    end
```

### Data Flow Summary

| Step | Input | Output | Service |
|---|---|---|---|
| Resume Upload | PDF / text + role | `CandidateProfile` in DB | `resume.py` |
| Query Construction | `ParsedResume` + role | 5–8 `{query, source_skill, rationale}` | `query_builder.py` |
| RAG Retrieval | Conceptual queries | Deduplicated chunks from ChromaDB | `interview_engine.py` |
| Question Generation | Chunks + resume context | `{question_text, topic, difficulty, chunk_ids}` | `interview_engine.py` |
| Answer Evaluation | Answer text + question | `{rating, score, rationale, next_difficulty}` | `evaluator.py` |
| Session Summary | Full Q&A transcript | `StructuredSessionSummary` + DB persistence | `summary.py` |

---

## 8. Key Design Decisions

### Chunking Strategy: 600 Tokens, 15% Overlap, Recursive Splitting

Technical domain literature (ML textbooks, system design specs, API references) encodes complete ideas — algorithms, mathematical derivations, architectural patterns — within roughly 400–500 words. The target of **600 tokens** was chosen to:

- **Preserve semantic completeness:** Smaller chunks (150–200 tokens) fragment multi-sentence explanations across embeddings, forcing the retriever to combine incomplete pieces and losing conceptual coherence. Larger chunks (1200+ tokens) dilute the embedding vector by bundling multiple unrelated concepts, reducing cosine-similarity precision for targeted query retrieval.
- **Balance context window budget:** At retrieval time, 3 chunks × 600 tokens = ~1800 tokens of knowledge context fits comfortably inside the question-generation prompt alongside resume context and system instructions, well within GPT-4o-mini's 128K limit.
- **Boundary Overlap:** The **15% overlap (~90 tokens)** prevents definitions, equations, or proof steps that straddle chunk boundaries from being silently truncated. This is particularly important for mathematical notation and pseudocode blocks.
- **Separator hierarchy:** Recursive splitting tries `\n\n` (paragraphs) → `\n` (lines) → `. ` (sentences) → characters, so chunk boundaries always fall at the most natural linguistic break available.

### Embedding Model: OpenAI `text-embedding-3-small` (with Gemini fallback)

**Chosen over `text-embedding-ada-002` and `text-embedding-3-large` because:**
- `text-embedding-3-small` reduces embedding dimension to 1536 vs 3072 for `large`, halving ChromaDB storage and retrieval latency with negligible accuracy loss on domain-specific technical text (MTEB benchmark delta: ~2%).
- Cost is ~5× cheaper than `ada-002` at the same dimension, which matters for bulk ingestion of large textbooks.
- Gemini `text-embedding-004` (768-dim) is wired as the secondary fallback, keeping the system functional if an OpenAI outage occurs.
- A deterministic **feature-hash embedding generator** provides a third fallback for fully offline development and CI — no API keys required to run the test suite.

### Adaptive Difficulty: Score-Gated, Not Time-Gated

Adaptive difficulty is driven entirely by the **evaluator's rating** of each answer (`weak`/`adequate`/`strong`), not by elapsed time or question count. The rules are:

| Current → Rating | Next Difficulty |
|---|---|
| any → `strong` | escalate one level (capped at `hard`) |
| any → `adequate` | unchanged |
| any → `weak` | de-escalate one level (floored at `easy`) |

**Why this approach over alternatives:**
- **Time-gated** difficulty (e.g. reduce after 60s no-answer) is not appropriate for text-based async interview tools where thinking time is expected.
- **Bayesian IRT** (Item Response Theory) would be the theoretically ideal approach but requires pre-calibrated item difficulty parameters, which assumes a large existing question bank. With dynamically generated questions this is not feasible.
- **Simple score thresholds** (85+ → escalate) were considered but add an arbitrary calibration problem — what is 85 vs 84? The rubric-rating gate avoids this by relying on the LLM's holistic judgment rather than raw numeric thresholds.

### Trade-offs Made Under the 48-Hour Constraint

| Decision | Trade-off |
|---|---|
| **Session state in localStorage + URL params** | Simple and refresh-safe; a production system would use server-side JWT session tokens with Redis or a database-backed session store. |
| **Sync endpoints for LLM calls** | LLM calls are made synchronously inside FastAPI route handlers. Under real load this would block async workers; production would use async clients (`AsyncOpenAI`, `aiohttp`) and background tasks with `celery` + a message broker. |
| **In-memory SQLite for tests** | Avoids requiring a running Postgres in CI; however, SQLite and Postgres have subtle dialect differences (especially around JSON queries and UUID handling) that could mask bugs. |
| **Single ChromaDB collection** | All roles share one `role_knowledge_base` collection, filtered by a `where={"role": role}` predicate. A per-role collection design would give better isolation and allow role-specific tuning of embedding dimensionality. |
| **No authentication** | The API has no auth layer. Production would require OAuth 2.0 / JWT, rate limiting, and per-interviewer tenant isolation. |
| **Heuristic fallback LLM** | The deterministic fallback produces plausible but static outputs. It is valuable for testing but would make the system useless for real screening if API keys are missing in production. |

---

## 9. Known Limitations & Future Work

### Limitations

- **No streaming responses:** Question and summary generation are one-shot LLM calls. Long sessions with slow LLM latency will stall the frontend.
- **Question deduplication is per-session only:** The same conceptual question could be generated across different sessions for the same candidate. A question bank cache keyed on `(role, topic, difficulty)` would prevent repetition.
- **ChromaDB similarity threshold:** There is no minimum cosine similarity cutoff on retrieved chunks. If a resume mentions a skill with no matching content in the knowledge base, low-relevance chunks will still be used to generate questions.
- **Summary is re-generated on every `GET /sessions/{id}/summary` call if `session.summary` is null**, which is an unnecessary LLM round-trip for incomplete sessions.
- **No PDF rendering preview:** The frontend shows extracted text, not the original formatted resume.

### What Would Be Built with More Time

| Area | Improvement |
|---|---|
| **Streaming** | Use Server-Sent Events or WebSocket for real-time question streaming and live evaluation token streaming |
| **Async LLM clients** | Replace sync `openai` and `google-generativeai` calls with `AsyncOpenAI` + `asyncio` concurrency throughout |
| **Vector similarity floor** | Add a configurable minimum similarity threshold; if no chunk exceeds it, fall back to a generic conceptual probe rather than a low-confidence grounded question |
| **IRT-calibrated question bank** | Pre-generate and cache a question bank with difficulty calibrated by Item Response Theory; use dynamic generation only as a cache-miss path |
| **Multi-turn conversational follow-up** | Instead of moving to the next question after each answer, allow 1–2 follow-up probes before advancing (akin to real whiteboard interviews) |
| **Interviewer dashboard** | A recruiter-facing panel to review session summaries, compare candidates, and export PDF reports |
| **Auth + multi-tenancy** | JWT authentication, per-company knowledge base isolation, and candidate consent management |
| **Evaluation accuracy benchmarking** | Ground-truth labelled answer dataset to measure LLM evaluator precision/recall vs expert human raters |
| **Per-role collection sharding** | Separate ChromaDB collections per role to enable independent tuning of chunk parameters and embedding models per domain |
