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
    source_chunk_ids: list[str]
    prerequisites: list[str]
    created_at: datetime
    updated_at: datetime


class TopicListResponse(BaseModel):
    topics: list[TopicResponse]


class TopicRefreshResponse(BaseModel):
    topic_count: int
    topics: list[TopicResponse]


class TopicUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    keywords: Optional[list[str]] = None
    importance: Optional[int] = Field(default=None, ge=1, le=5)
    difficulty: Optional[int] = Field(default=None, ge=1, le=5)
    prerequisites: Optional[list[str]] = None


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
