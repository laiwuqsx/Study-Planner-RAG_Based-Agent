from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class CurrentUserResponse(BaseModel):
    id: int
    username: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CourseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    term: str = Field(default="", max_length=80)
    description: str = ""


class CourseUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=160)
    term: Optional[str] = Field(default=None, max_length=80)
    description: Optional[str] = None


class CourseResponse(BaseModel):
    id: int
    name: str
    term: str
    description: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CourseListResponse(BaseModel):
    courses: list[CourseResponse]


class DeleteResponse(BaseModel):
    id: int
    message: str


class DocumentResponse(BaseModel):
    id: int
    course_id: int
    filename: str
    file_type: str
    material_type: str
    status: str
    chunk_count: int
    topic_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]


class JobStepResponse(BaseModel):
    step: str
    status: str
    message: str = ""


class ProcessingJobResponse(BaseModel):
    id: int
    user_id: int
    course_id: int
    document_id: int
    status: str
    current_step: str
    message: str
    error: str
    steps: list[JobStepResponse]
    created_at: datetime
    updated_at: datetime


class UploadDocumentResponse(BaseModel):
    document: DocumentResponse
    job: ProcessingJobResponse


class ParentChunkResponse(BaseModel):
    id: int
    page_number: int | None
    section_title: str
    root_chunk_id: str
    chunk_level: int
    chunk_index: int
    text: str

    model_config = ConfigDict(from_attributes=True)


class ChildChunkResponse(BaseModel):
    id: int
    parent_chunk_id: int
    page_number: int | None
    section_title: str
    chunk_id: str
    root_chunk_id: str
    chunk_level: int
    chunk_index: int
    text: str

    model_config = ConfigDict(from_attributes=True)


class DocumentChunkSummaryResponse(BaseModel):
    document_id: int
    parent_chunks: list[ParentChunkResponse]
    child_chunks: list[ChildChunkResponse]


class SearchResultResponse(BaseModel):
    chunk_id: str
    root_chunk_id: str
    parent_chunk_id: int
    document_id: int
    filename: str
    material_type: str
    page_number: int | None
    section_title: str
    text: str
    score: float


class SearchResponse(BaseModel):
    query: str
    retrieval_mode: str
    results: list[SearchResultResponse]


class TopicResponse(BaseModel):
    id: int
    course_id: int
    name: str
    description: str
    keywords: list[str]
    importance: int
    difficulty: int
    status: str
    quality_score: int
    review_note: str
    mastery_status: str
    last_reviewed_at: datetime | None
    source_chunk_ids: list[str]
    prerequisites: list[str]
    created_at: datetime
    updated_at: datetime


class TopicListResponse(BaseModel):
    topics: list[TopicResponse]


class TopicRefreshResponse(BaseModel):
    topic_count: int
    topics: list[TopicResponse]


class TopicCurateResponse(BaseModel):
    topic_count: int
    updated_topic_count: int
    topics: list[TopicResponse]


class TopicReviewChunkResponse(BaseModel):
    chunk_id: str
    document_id: int
    filename: str
    material_type: str
    page_number: int | None
    section_title: str
    text: str


class TopicReviewResponse(BaseModel):
    topic: TopicResponse
    source_chunks: list[TopicReviewChunkResponse]
    related_topics: list[TopicResponse]


class TopicUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    keywords: Optional[list[str]] = None
    importance: Optional[int] = Field(default=None, ge=1, le=5)
    difficulty: Optional[int] = Field(default=None, ge=1, le=5)
    status: Optional[str] = Field(default=None, pattern="^(active|suspect|hidden)$")
    quality_score: Optional[int] = Field(default=None, ge=1, le=5)
    review_note: Optional[str] = None
    mastery_status: Optional[str] = Field(default=None, pattern="^(not_started|reviewing|mastered)$")
    prerequisites: Optional[list[str]] = None


class TopicMasteryUpdateRequest(BaseModel):
    mastery_status: str = Field(pattern="^(not_started|reviewing|mastered)$")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: Optional[int] = None
    retrieval_mode: str = Field(default="hybrid", pattern="^(keyword|vector|hybrid)$")
    top_k: int = Field(default=5, ge=1, le=10)


class ChatSourceResponse(BaseModel):
    chunk_id: str
    document_id: int
    filename: str
    page_number: int | None
    section_title: str
    text: str
    score: float


class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    retrieval_mode: str
    sources: list[ChatSourceResponse]
    created_at: datetime


class ChatSessionSummaryResponse(BaseModel):
    id: int
    course_id: int
    title: str
    created_at: datetime
    updated_at: datetime


class ChatSessionListResponse(BaseModel):
    sessions: list[ChatSessionSummaryResponse]


class ChatSessionDetailResponse(BaseModel):
    id: int
    course_id: int
    title: str
    messages: list[ChatMessageResponse]
    created_at: datetime
    updated_at: datetime


class ChatResponse(BaseModel):
    session: ChatSessionSummaryResponse
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse


class StudyPlanGenerateRequest(BaseModel):
    goal: str = Field(default="Build a focused study plan for this course.", max_length=400)
    sessions_per_week: int = Field(default=4, ge=1, le=14)
    minutes_per_session: int = Field(default=90, ge=20, le=240)
    topic_limit: int = Field(default=10, ge=1, le=16)


class StudyPlanItemResponse(BaseModel):
    id: int
    topic_id: int
    order_index: int
    title: str
    notes: str
    focus_points: list[str]
    context_snippets: list[str]
    estimated_effort_minutes: int
    importance: int
    difficulty: int
    source_chunk_count: int
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class StudyPlanResponse(BaseModel):
    id: int
    course_id: int
    title: str
    summary: str
    generation_mode: str
    item_count: int
    completed_item_count: int
    next_item_id: int | None
    created_at: datetime
    updated_at: datetime
    items: list[StudyPlanItemResponse]


class StudyPlanGenerateResponse(BaseModel):
    plan: StudyPlanResponse


class StudyPlanItemUpdateRequest(BaseModel):
    status: str = Field(pattern="^(pending|in_progress|completed)$")
