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
    results: list[SearchResultResponse]
