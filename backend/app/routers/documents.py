from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.app.auth import get_current_user, get_db
from backend.app.dependencies import get_user_course_or_404, get_user_document_or_404
from backend.app.models import ChildChunk, Course, Document, ParentChunk, User
from backend.app.schemas import (
    DeleteResponse,
    DocumentChunkSummaryResponse,
    DocumentListResponse,
    UploadDocumentResponse,
)
from backend.app.services.documents import create_document_upload, delete_document_record
from backend.app.services.jobs import serialize_job
from backend.app.services.pipeline import run_processing_job

router = APIRouter(prefix="/courses/{course_id}/documents", tags=["documents"])


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    course: Course = Depends(get_user_course_or_404),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    documents = (
        db.query(Document)
        .filter(Document.course_id == course.id, Document.user_id == current_user.id)
        .order_by(Document.created_at.desc(), Document.id.desc())
        .all()
    )
    return DocumentListResponse(documents=documents)


@router.post("", response_model=UploadDocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    material_type: str = Form("other"),
    course: Course = Depends(get_user_course_or_404),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document, job = await create_document_upload(db, current_user, course, file, material_type)
    background_tasks.add_task(run_processing_job, job.id)
    return UploadDocumentResponse(document=document, job=serialize_job(job))


@router.get("/{document_id}/chunks", response_model=DocumentChunkSummaryResponse)
async def get_document_chunks(
    document_id: int,
    course: Course = Depends(get_user_course_or_404),
    document: Document = Depends(get_user_document_or_404),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if document.course_id != course.id:
        raise HTTPException(status_code=404, detail="Document not found")

    parent_chunks = (
        db.query(ParentChunk)
        .filter(
            ParentChunk.document_id == document_id,
            ParentChunk.course_id == course.id,
            ParentChunk.user_id == current_user.id,
        )
        .order_by(ParentChunk.chunk_index.asc())
        .all()
    )
    child_chunks = (
        db.query(ChildChunk)
        .filter(
            ChildChunk.document_id == document_id,
            ChildChunk.course_id == course.id,
            ChildChunk.user_id == current_user.id,
        )
        .order_by(ChildChunk.chunk_index.asc())
        .all()
    )
    return DocumentChunkSummaryResponse(
        document_id=document_id,
        parent_chunks=parent_chunks,
        child_chunks=child_chunks,
    )


@router.delete("/{document_id}", response_model=DeleteResponse)
async def delete_document(
    course: Course = Depends(get_user_course_or_404),
    document: Document = Depends(get_user_document_or_404),
    db: Session = Depends(get_db),
):
    if document.course_id != course.id:
        raise HTTPException(status_code=404, detail="Document not found")

    document_id = document.id
    delete_document_record(db, document)
    return DeleteResponse(id=document_id, message="Document deleted")
