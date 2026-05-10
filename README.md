# Study Planner Agent

Retrieval-augmented study planner agent for students. The system ingests course materials, extracts course topics, builds a study plan, and supports grounded topic review and course chat in one workspace.

## What It Does

The current product flow is:

1. Create a course workspace.
2. Upload PDF or DOCX course materials.
3. Parse and chunk documents into retrievable sections.
4. Extract course topics and attach source chunks.
5. Generate a study plan from those topics.
6. Review each topic, ask grounded questions, and track mastery and plan progress.

## System Overview

```mermaid
flowchart LR
    A["Upload Course Materials"] --> B["Parse + Chunk Documents"]
    B --> C["Keyword + Vector Retrieval Index"]
    B --> D["Topic Extraction"]
    D --> E["Topic Catalog"]
    E --> F["Study Plan Generation"]
    E --> G["Topic Review"]
    C --> H["Course Chat / Search"]
    G --> I["Mastery Tracking"]
    F --> J["Plan Execution Tracking"]
```

## Current Scope

### Phase 0: Project Setup

- FastAPI backend project
- React frontend project
- Docker Compose for PostgreSQL and Milvus
- Environment variable templates

### Phase 1: Auth, Courses, and Base Data Model

- Student registration and login
- JWT authentication
- Current user endpoint
- Course CRUD
- User-scoped course access

### Phase 2: Document Upload and Background Jobs

- PDF and DOCX upload endpoint
- Local file storage
- Background processing job lifecycle
- Upload progress polling in the frontend

### Phase 3: Document Parsing and Chunking

- PDF text extraction
- DOCX text extraction
- Hierarchical parent/child chunking
- Parent and child chunk persistence
- Chunk inspection endpoint

### Phase 4: Retrieval Indexing

- PostgreSQL keyword retrieval
- Milvus vector retrieval
- Hybrid retrieval via reciprocal-rank fusion
- Course-scoped search API and frontend search page

### Phase 5: Topic Extraction

- Course topic persistence in PostgreSQL
- Incremental document-to-topic synchronization
- Topic source chunk references and keywords
- Optional LLM-assisted topic merge and curation
- Topic review page in the frontend

### Phase 6: RAG Chat

- Course chat sessions in PostgreSQL
- Synchronous and streaming chat endpoints
- Retrieved source trace on assistant messages
- Chat page in the frontend
- Optional OpenAI-compatible grounded answer generation

### Phase 7: Study Plan Generation

- Study plan generation from active topics
- Ordered plan items with focus points and effort estimates
- Study plan page in the frontend

### Phase 8: Interactive Review Workflow

- Topic review page with source chunks
- Topic-internal grounded Q&A
- Topic mastery tracking
- Study plan item execution tracking

## Recommended Demo Flow

Use this sequence for a live demo, presentation, or handoff walkthrough:

1. Sign up or log in.
2. Create a course with a realistic name, term, and description.
3. Upload one or two course files and wait for processing to complete.
4. Open `Topics` and show that extracted topics have keywords and source-backed coverage.
5. Open `Study Plan` and generate a plan from the topic catalog.
6. Open one plan item or topic and enter `Review topic`.
7. Ask a topic-specific question and show grounded source snippets.
8. Mark the topic as `reviewing` or `mastered`.
9. Return to `Study Plan` and mark a plan item `in progress` or `completed`.

If you want the most stable demo, use:

- PostgreSQL, not SQLite
- Milvus running locally through Docker Compose
- `EMBEDDING_PROVIDER=hash` for deterministic local smoke tests
- Real API keys only when you want LLM-assisted chat or topic extraction

## Prerequisites

Install local development tools:

```bash
brew install python@3.12 uv node
```

Docker Desktop must be running before starting middleware.

## Quick Start

From the project root:

```bash
cd study-planner-agent
```

1. Start middleware:

```bash
docker compose up -d
```

2. Install backend dependencies and create a local environment file:

```bash
uv sync
cp .env.example .env
```

3. Start the backend:

```bash
uv run uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

4. In a second terminal, install frontend dependencies and start the frontend:

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Open:

```text
Frontend:   http://127.0.0.1:5173
Backend:    http://127.0.0.1:8000
API docs:   http://127.0.0.1:8000/docs
```

## Environment Variables

### Backend `.env`

The backend environment template is in [.env.example](/Users/shengxiangqi/Documents/UIUC/AIAgent/superMew/study-planner-agent/.env.example).

Core settings:

```env
HOST=0.0.0.0
PORT=8000
DATABASE_URL=postgresql+psycopg2://study_planner:change-me-local-only@127.0.0.1:5433/study_planner
JWT_SECRET_KEY=replace-with-a-strong-random-secret
MILVUS_HOST=127.0.0.1
MILVUS_PORT=19531
MILVUS_COLLECTION=study_chunks
```

Embedding settings:

```env
EMBEDDING_PROVIDER=voyage
EMBEDDING_MODEL=voyage-4-lite
EMBEDDING_DIMENSION=1024
VOYAGE_API_KEY=replace-with-your-voyage-api-key
```

Chat and topic extraction settings:

```env
CHAT_PROVIDER=auto
CHAT_MODEL=gpt-4.1-mini
CHAT_BASE_URL=https://api.openai.com/v1
CHAT_API_KEY=
TOPIC_EXTRACTION_MODE=auto
```

Notes:

- PostgreSQL is the intended default database.
- SQLite is only a quick local fallback:

```env
DATABASE_URL=sqlite:///./study_planner.db
```

- `EMBEDDING_PROVIDER=hash` is useful for deterministic local smoke tests without external API calls.
- `TOPIC_EXTRACTION_MODE=auto` uses the configured chat provider only when `CHAT_API_KEY` is present. Otherwise it falls back to the local rule-based topic pipeline.
- `CHAT_PROVIDER=auto` behaves the same way for course chat.

### Frontend `frontend/.env`

The frontend environment template is in [frontend/.env.example](/Users/shengxiangqi/Documents/UIUC/AIAgent/superMew/study-planner-agent/frontend/.env.example).

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## PostgreSQL and Milvus Setup

The project ships with Docker Compose middleware in [docker-compose.yml](/Users/shengxiangqi/Documents/UIUC/AIAgent/superMew/study-planner-agent/docker-compose.yml).

Services:

- PostgreSQL on `127.0.0.1:5433`
- Milvus on `127.0.0.1:19531`
- Milvus health endpoint on `http://127.0.0.1:9092/healthz`
- Attu on `http://127.0.0.1:8081`
- MinIO API on `http://127.0.0.1:9002`
- MinIO Console on `http://127.0.0.1:9003`

Start middleware:

```bash
docker compose up -d
```

Check status:

```bash
docker compose ps
```

Check logs:

```bash
docker compose logs -f postgres
docker compose logs -f milvus
```

Stop middleware:

```bash
docker compose down
```

Delete local PostgreSQL and Milvus data:

```bash
docker compose down -v
```

Use `down -v` only when you intentionally want to wipe local data.

## Backend Commands

Install or refresh Python dependencies:

```bash
uv sync
```

Run backend:

```bash
uv run uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

Run backend on localhost only:

```bash
uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Verify backend imports:

```bash
uv run python -c "from backend.app.main import app; print(app.title)"
```

Compile-check backend and scripts:

```bash
python3 -m compileall backend scripts
```

## Frontend Commands

Install frontend dependencies:

```bash
cd frontend
npm install
```

Run frontend dev server:

```bash
npm run dev
```

Run frontend dev server on an explicit host and port:

```bash
npm run dev -- --host 127.0.0.1 --port 5173
```

Build frontend:

```bash
npm run build
```

Preview production build:

```bash
npm run preview
```

## Smoke Tests

Run these after the backend is running.

Phase 1:

```bash
uv run python scripts/smoke_phase1.py
```

Phase 2:

```bash
uv run python scripts/smoke_phase2.py
```

Phase 3:

```bash
uv run python scripts/smoke_phase3.py
```

Phase 4 keyword retrieval:

```bash
uv run python scripts/smoke_phase4.py
```

Phase 4 vector retrieval:

```bash
EMBEDDING_PROVIDER=hash uv run python scripts/smoke_phase4_vector.py
```

Phase 5 topic extraction:

```bash
EMBEDDING_PROVIDER=hash uv run python scripts/smoke_phase5.py
```

Phase 6 chat:

```bash
EMBEDDING_PROVIDER=hash uv run python scripts/smoke_phase6.py
```

Phase 7 study plan:

```bash
EMBEDDING_PROVIDER=hash uv run python scripts/smoke_phase7.py
```

Phase 8 topic review:

```bash
EMBEDDING_PROVIDER=hash uv run python scripts/smoke_phase8.py
```

## Typical Development Flow

```bash
# terminal 1
cd study-planner-agent
docker compose up -d

# terminal 2
cd study-planner-agent
uv run uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

# terminal 3
cd study-planner-agent/frontend
npm run dev
```

Then open:

```text
http://127.0.0.1:5173
```

## Deployment Notes

This project is still a local-first development setup, but these are the practical deployment assumptions:

- Backend: FastAPI + Uvicorn
- Frontend: Vite build output
- Database: PostgreSQL
- Vector store: Milvus
- Object/file storage: local filesystem today

Before deploying anywhere shared:

1. Move secrets out of checked-in `.env` files.
2. Use a persistent PostgreSQL instance.
3. Use a persistent Milvus deployment.
4. Replace local file storage with a durable storage target if multi-machine deployment is required.
5. Set real API keys only if you want LLM-assisted chat or topic extraction.

## Common Issues and Fixes

### Backend starts but topic extraction or chat falls back to local mode

Cause:

- `CHAT_API_KEY` is empty
- or `CHAT_PROVIDER` / `TOPIC_EXTRACTION_MODE` is configured for fallback behavior

Check:

```env
CHAT_PROVIDER=auto
TOPIC_EXTRACTION_MODE=auto
CHAT_API_KEY=<your-key>
```

### Upload works but vector retrieval is empty

Cause:

- Milvus is not healthy
- or embedding configuration is mismatched

Check:

```bash
docker compose ps
curl http://127.0.0.1:9092/healthz
```

Also verify:

```env
MILVUS_HOST=127.0.0.1
MILVUS_PORT=19531
EMBEDDING_DIMENSION=1024
```

### PostgreSQL connection fails on startup

Cause:

- Docker Compose middleware is not running
- or `DATABASE_URL` does not match the local container credentials

Check:

```bash
docker compose ps
docker compose logs -f postgres
```

Expected default:

```env
DATABASE_URL=postgresql+psycopg2://study_planner:change-me-local-only@127.0.0.1:5433/study_planner
```

### Frontend loads but API calls fail

Cause:

- backend is not running
- or `VITE_API_BASE_URL` points to the wrong URL

Check:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Then confirm:

```text
http://127.0.0.1:8000/docs
```

### You want a deterministic local demo without external APIs

Use:

```env
EMBEDDING_PROVIDER=hash
CHAT_API_KEY=
TOPIC_EXTRACTION_MODE=rule
CHAT_PROVIDER=extractive
```

That disables remote LLM dependence and makes local demos more predictable.

## Service URLs

```text
Backend API:     http://127.0.0.1:8000
API docs:        http://127.0.0.1:8000/docs
Frontend:        http://127.0.0.1:5173
PostgreSQL:      127.0.0.1:5433
Milvus:          127.0.0.1:19531
Milvus health:   http://127.0.0.1:9092/healthz
MinIO API:       http://127.0.0.1:9002
MinIO Console:   http://127.0.0.1:9003
Attu:            http://127.0.0.1:8081
```

## Before Pushing to GitHub

Do not commit local secrets, dependencies, generated builds, or middleware data.

These paths are intentionally ignored:

```text
.env
frontend/.env
.venv/
frontend/node_modules/
frontend/dist/
__pycache__/
*.pyc
volumes/
study_planner.db
```

Commit `.env.example` and `frontend/.env.example` instead of real `.env` files.
