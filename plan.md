# Implementation Plan: Retrieval-Augmented Study Planner Agent

## 1. Project Goal

Build a web-based study planner agent for students. The application should let a student upload course materials, automatically organize them into searchable topics, retrieve relevant course content, generate personalized study plans, and support interactive topic-by-topic review.

The system should be implemented as a retrieval-augmented agent with tool calling. It should not behave as a generic chatbot only. Its primary workflow is:

1. Student uploads course materials.
2. System extracts text and chunks the documents.
3. System indexes chunks for keyword and semantic retrieval.
4. System extracts topics, keywords, and source references.
5. Student asks for review help or a study plan.
6. Agent retrieves relevant materials and uses planning tools.
7. Agent explains topics, cites source chunks, and guides the student through review.

## 2. Recommended Architecture

Use a modular architecture with clear boundaries:

```text
React Frontend
  -> FastAPI Backend
    -> Auth and User Context
    -> Document Ingestion Pipeline
    -> Topic Extraction Pipeline
    -> Retrieval Layer
    -> Agent and Planning Layer
    -> Study Plan and Progress Layer
    -> PostgreSQL
    -> Elasticsearch or Milvus
    -> Redis optional
```

Recommended stack:

- Frontend: React, TypeScript, Vite
- Backend: FastAPI, Python 3.12+
- Relational database: PostgreSQL
- Retrieval engine: Elasticsearch if keyword/BM25 + vector retrieval is required in one system; Milvus if the implementation prioritizes vector retrieval and follows with sparse/hybrid retrieval later
- Cache: Redis optional
- Agent framework: LangChain or LangGraph
- LLM provider: OpenAI-compatible chat API
- Embedding model: OpenAI embedding, BGE, E5, or another consistent embedding model

The implementation should keep the retrieval backend behind an interface so Elasticsearch and Milvus can be swapped without rewriting the agent.

## 3. Core Product Requirements

### 3.1 Student-Facing Features

Implement these features first:

- Student registration and login
- Course creation
- Course material upload
- Material list grouped by course
- Automatic topic extraction
- Topic dashboard
- Topic search
- Chat-based question answering over uploaded materials
- Study plan generation
- Topic-by-topic review mode
- Source citation display for retrieved chunks
- Study progress tracking

### 3.2 Material Types

Support these material types:

- Lecture slides
- Course notes
- Assignments
- Example problems
- Syllabus
- Other documents

At upload time, allow the student to choose the material type. If no type is selected, classify it as `other`.

### 3.3 Agent Capabilities

The agent should be able to:

- Search uploaded course materials
- Extract or refresh topics for a course
- Generate a study plan based on exam date, available time, and target topics
- Explain a topic using retrieved course materials
- Generate practice questions for a topic
- Review an example problem step by step
- Track topic progress
- Recommend the next topic to review

## 4. Key Design Practices To Apply

The implementation should include the following design practices.

### 4.1 Asynchronous Document Processing

Document upload should return quickly after the file is saved. Expensive work should run in the background:

1. Save file.
2. Create processing job.
3. Parse document.
4. Chunk document.
5. Generate embeddings.
6. Index chunks.
7. Extract topics.
8. Update job status.

Expose a job status endpoint so the frontend can show step-level progress.

Minimum job steps:

```text
upload
parse
chunk
index
topic_extract
complete
```

Recommended job fields:

```text
job_id
user_id
course_id
document_id
status
current_step
message
error
created_at
updated_at
steps[]
```

### 4.2 Hierarchical Chunking

Use hierarchical chunking rather than flat chunking only.

Recommended structure:

```text
Course
  Document
    Section or Page
      Parent Chunk
        Child Chunk
```

Store child chunks in the retrieval system. Store parent chunks in PostgreSQL. At retrieval time, retrieve child chunks first. If several child chunks from the same parent are retrieved, merge upward to parent context before sending to the LLM.

This improves answer quality because the model receives enough surrounding context while retrieval remains precise.

### 4.3 Retrieval Trace

Every agent answer that uses retrieval should return a trace object:

```text
tool_used
query
retrieval_mode
retrieved_chunks
rerank_applied
topic_ids
source_documents
rewrite_needed
expanded_query
```

The frontend should display this trace in a collapsible source panel. Students should be able to see which lecture, note, assignment, or example problem supported the answer.

### 4.4 Streaming Responses

Implement streaming chat responses. The frontend should show incremental output and allow the student to stop generation.

The backend should stream events such as:

```text
content
retrieval_step
trace
done
error
```

The frontend should display intermediate states:

- Searching course materials
- Evaluating retrieved sources
- Generating study plan
- Explaining topic
- Producing final answer

### 4.5 Query Rewriting

Students often ask questions using different wording from the course material. Add query rewriting before or after initial retrieval:

- Step-back rewriting for conceptual questions
- HyDE-style hypothetical answer generation for vague questions
- Direct query for exact topic names and terminology

Start simple:

1. Try direct retrieval.
2. If retrieved chunks are weak or empty, rewrite the query.
3. Retrieve again.
4. Merge and rerank results.

### 4.6 Role and Data Isolation

The first version can be student-only. Every entity must be scoped by `user_id`.

Required rule:

```text
A student can only access their own courses, documents, topics, study plans, sessions, and progress.
```

Do not require an admin role for the first version. If an instructor role is added later, keep it separate from the initial student workflow.

## 5. Data Model

Use PostgreSQL for relational data.

### 5.1 User

```text
id
username
password_hash
created_at
```

### 5.2 Course

```text
id
user_id
name
term
description
created_at
updated_at
```

### 5.3 Document

```text
id
user_id
course_id
filename
file_path
file_type
material_type
status
chunk_count
topic_count
created_at
updated_at
```

### 5.4 Chunk

If using Elasticsearch, chunk text and metadata can live directly in the index. Still keep a relational record if progress and source management are needed.

Recommended chunk metadata:

```text
chunk_id
user_id
course_id
document_id
filename
material_type
page_number
section_title
parent_chunk_id
root_chunk_id
chunk_level
chunk_index
text
embedding
topic_ids
```

### 5.5 ParentChunk

```text
chunk_id
user_id
course_id
document_id
text
filename
material_type
page_number
section_title
parent_chunk_id
root_chunk_id
chunk_level
chunk_index
updated_at
```

### 5.6 Topic

```text
id
user_id
course_id
name
normalized_name
description
keywords
importance
difficulty
source_document_ids
source_chunk_ids
prerequisite_topic_ids
created_at
updated_at
```

Importance and difficulty can start as LLM-estimated integer values from 1 to 5.

### 5.7 StudyPlan

```text
id
user_id
course_id
title
goal
exam_date
available_days
daily_minutes
status
created_at
updated_at
```

### 5.8 StudyPlanItem

```text
id
study_plan_id
topic_id
date
task_type
title
description
estimated_minutes
status
source_chunk_ids
order_index
```

Task types:

```text
read
review
practice
quiz
summarize
weak_topic_revisit
```

### 5.9 ChatSession and ChatMessage

```text
ChatSession:
id
user_id
course_id
session_id
metadata_json
created_at
updated_at

ChatMessage:
id
session_id
message_type
content
rag_trace
created_at
```

## 6. Retrieval Design

### 6.1 Retrieval Interface

Create a retriever interface:

```python
class BaseRetriever:
    def index_chunks(self, chunks: list[dict]) -> None:
        ...

    def delete_document(self, user_id: str, document_id: str) -> None:
        ...

    def search(self, query: str, user_id: str, course_id: str, top_k: int) -> dict:
        ...
```

The agent should call this interface, not a database-specific client directly.

### 6.2 Elasticsearch Option

If using Elasticsearch, create one index for course chunks:

```text
study_chunks
```

Mapping should include:

- `text`: `text`
- `filename`: `keyword`
- `material_type`: `keyword`
- `user_id`: `keyword`
- `course_id`: `keyword`
- `document_id`: `keyword`
- `topic_ids`: `keyword`
- `embedding`: `dense_vector`

Use:

- BM25 through `match` or `multi_match`
- kNN through `dense_vector`
- Hybrid retrieval by combining BM25 and kNN results using Reciprocal Rank Fusion or weighted score fusion

### 6.3 Milvus Option

If using Milvus, store dense vectors and metadata fields:

```text
dense_embedding
text
user_id
course_id
document_id
filename
material_type
page_number
chunk_id
parent_chunk_id
root_chunk_id
chunk_level
chunk_index
```

For keyword retrieval, choose one:

- Add sparse/BM25 vectors to Milvus if supported by the implementation
- Store a separate BM25 index in PostgreSQL or a lightweight local service
- Add Elasticsearch later only for keyword retrieval

### 6.4 Reranking

Add reranking after initial retrieval if time allows.

Inputs:

```text
query
candidate chunk texts
```

Outputs:

```text
top_k reranked chunks
rerank_score
```

Reranking can be optional. The system should still work if reranking is not configured.

## 7. Topic Extraction Pipeline

After document indexing, run topic extraction.

### 7.1 Input

Use document metadata and selected chunks:

```text
filename
material_type
section titles
chunk texts
```

### 7.2 Output Schema

Ask the LLM to return structured JSON:

```json
{
  "topics": [
    {
      "name": "Dynamic Programming",
      "description": "Using overlapping subproblems and optimal substructure to solve problems efficiently.",
      "keywords": ["memoization", "recurrence", "optimal substructure"],
      "importance": 5,
      "difficulty": 4,
      "source_chunk_ids": ["..."],
      "prerequisites": ["Recursion", "Time Complexity"]
    }
  ]
}
```

### 7.3 Deduplication

Topic extraction will produce duplicates. Implement deduplication:

1. Normalize topic names.
2. Merge exact normalized matches.
3. Use embedding similarity or LLM comparison for near-duplicates if time allows.
4. Merge source chunks and keywords.

### 7.4 Topic Refresh

Provide an endpoint:

```text
POST /courses/{course_id}/topics/refresh
```

It should rerun topic extraction for the course.

## 8. Agent Tools

Implement tools as backend functions callable by the agent.

### 8.1 search_course_materials

Input:

```text
query
course_id
material_type optional
topic_id optional
```

Output:

```text
retrieved chunks with source metadata
```

### 8.2 list_course_topics

Input:

```text
course_id
```

Output:

```text
topics sorted by importance and difficulty
```

### 8.3 generate_study_plan

Input:

```text
course_id
exam_date
daily_minutes
target_topics optional
weak_topics optional
```

Output:

```text
study plan with dated tasks
```

The tool should persist the plan in PostgreSQL.

### 8.4 review_topic

Input:

```text
course_id
topic_id or topic_name
```

Output:

```text
topic explanation
key definitions
source chunks
practice suggestions
```

### 8.5 generate_practice_questions

Input:

```text
course_id
topic_id
difficulty
count
```

Output:

```text
practice questions with answers or hints
```

### 8.6 update_progress

Input:

```text
topic_id
status
confidence optional
```

Output:

```text
updated progress record
```

## 9. Agent Behavior

The agent system prompt should define it as a study planning assistant for students.

Rules:

- Always prefer retrieved course materials when answering course-specific questions.
- Cite sources when using uploaded materials.
- Do not invent facts about course content when retrieval is insufficient.
- Ask for missing planning constraints when necessary, such as exam date or available study time.
- When generating a plan, prioritize syllabus topics, assignment topics, and high-importance topics.
- When reviewing, explain incrementally and offer practice questions.
- Avoid repeatedly calling the same retrieval tool in one turn unless the query was rewritten.

Recommended turn flow:

```text
Classify user intent:
  - ask_question
  - generate_plan
  - review_topic
  - practice
  - manage_course

Select tool:
  - retrieve if content is needed
  - list topics if planning
  - generate plan if constraints are available
  - ask clarification if required fields are missing

Generate final answer:
  - concise explanation
  - sources
  - next action
```

## 10. Backend API Plan

### 10.1 Auth

```text
POST /auth/register
POST /auth/login
GET /auth/me
```

### 10.2 Courses

```text
POST /courses
GET /courses
GET /courses/{course_id}
PATCH /courses/{course_id}
DELETE /courses/{course_id}
```

### 10.3 Documents

```text
POST /courses/{course_id}/documents/upload
GET /courses/{course_id}/documents
GET /documents/jobs/{job_id}
DELETE /courses/{course_id}/documents/{document_id}
```

### 10.4 Topics

```text
GET /courses/{course_id}/topics
POST /courses/{course_id}/topics/refresh
GET /courses/{course_id}/topics/{topic_id}
PATCH /courses/{course_id}/topics/{topic_id}
```

### 10.5 Study Plans

```text
POST /courses/{course_id}/study-plans
GET /courses/{course_id}/study-plans
GET /study-plans/{plan_id}
PATCH /study-plans/{plan_id}
PATCH /study-plans/{plan_id}/items/{item_id}
```

### 10.6 Chat

```text
POST /courses/{course_id}/chat
POST /courses/{course_id}/chat/stream
GET /courses/{course_id}/sessions
GET /sessions/{session_id}
DELETE /sessions/{session_id}
```

## 11. Frontend Plan

Use React with these pages:

### 11.1 Login and Register

Simple authentication pages. Store JWT in local storage for the first version.

### 11.2 Course Dashboard

Show:

- Courses
- Recent documents
- Extracted topics
- Active study plans
- Progress summary

### 11.3 Upload Materials

Allow:

- Select course
- Upload file
- Choose material type
- Show processing job progress
- Show extracted topic count after completion

### 11.4 Topics Page

Show topic cards/table:

- Name
- Importance
- Difficulty
- Source documents
- Review status
- Start review button

### 11.5 Study Planner Page

Inputs:

- Exam date
- Daily minutes
- Target topics
- Weak topics

Outputs:

- Calendar-like plan
- Task list
- Mark complete controls

### 11.6 Review Page

Interactive topic review:

- Topic explanation
- Source citations
- Key definitions
- Examples
- Practice questions
- Next topic button

### 11.7 Chat Page

Streaming chat UI:

- Message list
- Stop generation button
- Collapsible retrieval trace
- Source chunks
- Session history

## 12. Implementation Phases

### Phase 0: Project Setup

Deliverables:

- Backend FastAPI project
- React frontend project
- Docker Compose for PostgreSQL and retrieval backend
- Environment variable template
- Basic README

Acceptance criteria:

- Backend starts locally.
- Frontend starts locally.
- Database connection works.

### Phase 1: Auth, Courses, and Base Data Model

Deliverables:

- User registration and login
- JWT authentication
- Course CRUD
- SQLAlchemy models and migrations or create-table bootstrap

Acceptance criteria:

- Student can register, log in, create a course, and view only their own courses.

### Phase 2: Document Upload and Background Jobs

Deliverables:

- Upload endpoint
- File storage
- Background job manager
- Job status endpoint
- Frontend upload page with progress

Acceptance criteria:

- Student uploads a PDF or DOCX.
- UI shows processing progress.
- Document record is created and scoped to the student.

### Phase 3: Document Parsing and Chunking

Deliverables:

- PDF parsing
- DOCX parsing
- Optional PPTX parsing if lecture slides are a priority
- Hierarchical chunking
- Parent chunk storage

Acceptance criteria:

- Uploaded documents produce parent and child chunks.
- Chunk metadata includes course, document, page, material type, and hierarchy fields.

### Phase 4: Retrieval Indexing

Deliverables:

- Embedding service
- Retrieval backend client
- Chunk indexing
- Document deletion from index
- Basic search endpoint

Acceptance criteria:

- Given a query, backend returns relevant chunks from the student course.
- Retrieval is filtered by `user_id` and `course_id`.

### Phase 5: Topic Extraction

Deliverables:

- LLM topic extraction prompt
- Structured topic parser
- Topic persistence
- Topic deduplication
- Topics frontend page

Acceptance criteria:

- After document processing, topics are visible in the course.
- Each topic has keywords and source references.

### Phase 6: RAG Chat

Deliverables:

- Retrieval tool
- RAG answer generation
- Streaming chat endpoint
- Chat frontend with source trace
- Conversation persistence

Acceptance criteria:

- Student can ask a question about uploaded course materials.
- Agent retrieves relevant chunks and answers with visible sources.

### Phase 7: Study Plan Generation

Deliverables:

- Study plan data model
- Study plan generation tool
- Study plan API
- Study planner frontend

Acceptance criteria:

- Student enters exam date and daily available time.
- System generates a dated study plan using extracted topics and course materials.
- Plan is saved and can be reopened.

### Phase 8: Interactive Review Workflow

Deliverables:

- Review topic tool
- Practice question generation
- Progress tracking
- Review page

Acceptance criteria:

- Student can select a topic and start a guided review.
- System explains the topic with sources and generates practice questions.
- Student can mark topic/task progress.

### Phase 9: Evaluation

Deliverables:

- Retrieval evaluation dataset
- Evaluation script
- Manual user evaluation rubric
- Comparison against baselines

Retrieval metrics:

- Precision@k
- Recall@k
- Hit@k

Baselines:

- Direct LLM without retrieval
- Keyword-only retrieval
- Embedding-only retrieval
- Hybrid retrieval if implemented

Test query categories:

- Topic-based queries
- Example-question-based queries
- Exam review queries

User evaluation categories:

- Study plan usefulness
- Topic explanation quality
- Source relevance
- Learning efficiency

Acceptance criteria:

- Evaluation script runs on a small test dataset.
- Results are summarized in a report-ready format.

### Phase 10: Final Polish and Presentation

Deliverables:

- End-to-end demo scenario
- Seed sample course materials
- Error handling improvements
- Final README
- Project report content
- Presentation screenshots or video flow

Acceptance criteria:

- A fresh user can upload materials, extract topics, generate a plan, review a topic, and ask course questions.

## 13. Suggested Execution Order for Another Agent

Follow this order:

1. Set up backend, frontend, and database.
2. Implement auth and course CRUD.
3. Implement upload job pipeline.
4. Implement document parsing and chunking.
5. Implement retrieval indexing and search.
6. Implement topic extraction.
7. Implement RAG chat with streaming.
8. Implement study plan generation.
9. Implement interactive review and progress.
10. Add evaluation and polish.

Avoid building the full agent before ingestion and retrieval work. The agent will be much easier to implement after documents, chunks, topics, and retrieval are stable.

## 14. Minimum Viable Product

If time is limited, the MVP should include:

- Student login
- Course creation
- Upload PDF/DOCX
- Chunk and index materials
- Extract topics
- Search/retrieve course chunks
- Generate a simple study plan
- Chat with retrieved sources

Defer these if necessary:

- Advanced reranking
- Complex query rewriting
- Instructor role
- Multi-course analytics
- Sophisticated progress recommendations
- PPTX parsing

## 15. Quality Checklist

Before final delivery, verify:

- All user data is scoped by `user_id`.
- Retrieval never returns chunks from another student.
- Uploaded documents can be deleted from both database and retrieval index.
- Agent answers include sources when retrieval is used.
- Study plans are persisted, not only printed in chat.
- Topic extraction handles duplicate topics.
- Frontend handles long processing jobs gracefully.
- Streaming chat can be stopped by the user.
- Environment variables are documented.
- Demo can run locally from a clean setup.

