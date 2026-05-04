# Study Planner Agent

Retrieval-augmented study planner agent for students.

## Completed Scope

### Phase 0: Project Setup

- FastAPI backend project
- React frontend project
- Docker Compose for PostgreSQL and Milvus retrieval backend
- Environment variable templates
- Basic README

### Phase 1: Auth, Courses, and Base Data Model

- Student registration and login
- JWT authentication
- Current user endpoint
- Course CRUD
- User-scoped course access
- SQLAlchemy base models

### Phase 2: Document Upload and Background Jobs

- PDF and DOCX upload endpoint
- User-scoped document records
- Local file storage
- Background processing job lifecycle
- Job status endpoint
- Frontend upload workspace with progress polling

### Phase 3: Document Parsing and Chunking

- PDF text extraction
- DOCX text extraction
- Hierarchical parent/child chunking
- Parent and child chunk persistence
- Chunk inspection endpoint

### Phase 4: Retrieval Indexing

- Retriever abstraction
- PostgreSQL keyword retrieval over child chunks
- Milvus vector retrieval over child chunks
- Hybrid retrieval via reciprocal-rank fusion
- Course-scoped search API
- Search page in the frontend

### Phase 5: Topic Extraction

- Topic persistence in PostgreSQL
- Course-level topic refresh pipeline
- Topic deduplication by normalized name
- Topic source chunk references and keywords
- Topics page in the frontend

### Phase 6: RAG Chat

- Course chat sessions in PostgreSQL
- Synchronous chat endpoint
- Streaming chat endpoint
- Retrieved source trace on assistant messages
- Chat page in the frontend
- Optional OpenAI-compatible grounded answer generation with extractive fallback

## Prerequisites

Install the local development tools:

```bash
brew install python@3.12 uv node
```

Docker Desktop must be running before starting middleware.

## Quick Start

From the project root:

```bash
cd study-planner-agent
```

Start middleware:

```bash
docker compose up -d
```

Install backend dependencies:

```bash
uv sync
cp .env.example .env
```

Use PostgreSQL by setting this in `.env`:

```env
DATABASE_URL=postgresql+psycopg2://<db_user>:<db_password>@127.0.0.1:5433/study_planner
```

For local Docker defaults, use the database credentials configured in `docker-compose.yml` or override them through your own uncommitted `.env`.

SQLite can still be used as an explicit fallback for quick experiments, but PostgreSQL is the intended default for the project.

Start backend:

```bash
uv run uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

API docs:

```text
http://127.0.0.1:8000/docs
```

In a second terminal, start frontend:

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Frontend:

```text
http://127.0.0.1:5173
```

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

Run Phase 1 smoke test after backend is running:

```bash
uv run python scripts/smoke_phase1.py
```

The script registers two users, creates a course for one user, and verifies the second user cannot access it.

Run Phase 2 smoke test after backend is running:

```bash
uv run python scripts/smoke_phase2.py
```

The script uploads a placeholder DOCX, polls the background job to completion, verifies the document appears in the course, and checks cross-user job isolation.

Run Phase 3 smoke test after backend is running:

```bash
uv run python scripts/smoke_phase3.py
```

The script uploads generated DOCX and PDF samples, waits for parsing and hierarchical chunking to finish, and verifies that parent and child chunks were persisted.

Run Phase 4 smoke test after backend is running:

```bash
uv run python scripts/smoke_phase4.py
```

The script uploads a sample DOCX, waits for chunk processing, and verifies that PostgreSQL search returns matching child chunks for a course-scoped query.

Run the Phase 4 vector smoke test after backend is running:

```bash
EMBEDDING_PROVIDER=hash uv run python scripts/smoke_phase4_vector.py
```

The script uploads a sample DOCX, waits for indexing to finish, and verifies that vector and hybrid retrieval return course-scoped results through Milvus. Keep `EMBEDDING_PROVIDER=voyage` in your real `.env`; the `hash` override is only for deterministic local verification without hitting the remote embedding API.

Run the Phase 5 smoke test after backend is running:

```bash
EMBEDDING_PROVIDER=hash uv run python scripts/smoke_phase5.py
```

The script uploads a sample DOCX, waits for topic extraction to finish, and verifies that topics are deduplicated, have keywords, and retain source chunk references.

Run the Phase 6 smoke test after backend is running:

```bash
EMBEDDING_PROVIDER=hash uv run python scripts/smoke_phase6.py
```

The script uploads a sample DOCX, waits for indexing, sends a course question to the chat endpoint, and verifies that the saved session contains a sourced assistant answer.

To enable LLM-grounded chat generation, set these in `.env`:

```env
CHAT_PROVIDER=auto
CHAT_MODEL=gpt-4.1-mini
CHAT_BASE_URL=https://api.openai.com/v1
CHAT_API_KEY=<your-api-key>
```

If `CHAT_API_KEY` is unset, the backend falls back to the local extractive chat baseline so the app still works without an LLM provider.

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

## Middleware

Start PostgreSQL and Milvus:

```bash
docker compose up -d
```

PostgreSQL is exposed on host port `5433`.

Milvus is exposed on host port `19531`.

Attu is exposed on host port `8081`.

Check middleware status:

```bash
docker compose ps
```

View logs:

```bash
docker compose logs -f postgres
docker compose logs -f milvus
```

Stop middleware:

```bash
docker compose down
```

Stop middleware and remove persisted local volumes:

```bash
docker compose down -v
```

Use `down -v` only when you intentionally want to delete local PostgreSQL and Milvus data.

For PostgreSQL, set:

```env
DATABASE_URL=postgresql+psycopg2://<db_user>:<db_password>@127.0.0.1:5433/study_planner
```

SQLite remains optional for quick throwaway local runs only:

```env
DATABASE_URL=sqlite:///./study_planner.db
```

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
