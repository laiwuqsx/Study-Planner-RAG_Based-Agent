from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.app.config import STORAGE_DIR
from backend.app.models import ChildChunk, Course, Document, ParentChunk, ProcessingJob, User
from backend.app.services.chunking import build_hierarchical_chunks
from backend.app.services.document_parser import parse_document
from backend.app.services.jobs import UPLOAD_STEPS, mark_job_failed, update_job_step
from backend.app.services.retrievers.factory import get_retriever
from backend.app.services.topics import refresh_course_topics
from backend.app.utils import normalize_material_type, secure_filename

SUPPORTED_UPLOAD_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}
ALLOWED_EXTENSIONS = {".pdf", ".docx"}


def validate_upload(file: UploadFile) -> tuple[str, str]:
    filename = secure_filename(file.filename or "")
    extension = Path(filename).suffix.lower()
    content_type = (file.content_type or "").lower()

    if extension not in ALLOWED_EXTENSIONS and content_type not in SUPPORTED_UPLOAD_TYPES:
        raise HTTPException(status_code=400, detail="Only PDF and DOCX uploads are supported")

    if extension not in ALLOWED_EXTENSIONS:
        extension = SUPPORTED_UPLOAD_TYPES[content_type]
        filename = f"{filename}{extension}" if not filename.endswith(extension) else filename

    return filename, extension.lstrip(".")


async def create_document_upload(
    db: Session,
    current_user: User,
    course: Course,
    file: UploadFile,
    material_type: str,
) -> tuple[Document, ProcessingJob]:
    filename, file_type = validate_upload(file)
    storage_dir = STORAGE_DIR / str(current_user.id) / str(course.id)
    storage_dir.mkdir(parents=True, exist_ok=True)

    document = Document(
        user_id=current_user.id,
        course_id=course.id,
        filename=filename,
        file_path="",
        file_type=file_type,
        material_type=normalize_material_type(material_type),
        status="uploaded",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    storage_path = storage_dir / f"{document.id}_{filename}"
    with storage_path.open("wb") as output:
        while chunk := await file.read(1024 * 1024):
            output.write(chunk)
    await file.close()

    document.file_path = str(storage_path)
    job = ProcessingJob(
        user_id=current_user.id,
        course_id=course.id,
        document_id=document.id,
        status="queued",
        current_step="upload",
        message=dict(UPLOAD_STEPS)["upload"],
    )
    update_job_step(job, "upload")
    db.add(job)
    db.commit()
    db.refresh(document)
    db.refresh(job)
    return document, job


def process_document_job(db: Session, job: ProcessingJob) -> None:
    document = db.query(Document).filter(Document.id == job.document_id).first()
    if not document:
        return

    try:
        job.status = "processing"
        document.status = "processing"
        db.commit()

        update_job_step(job, "parse")
        db.commit()
        sections = parse_document(document.file_path, document.file_type)
        if not sections:
            raise ValueError("No readable text was extracted from the document")

        update_job_step(job, "chunk")
        db.commit()
        _replace_document_chunks(db, document, sections)

        update_job_step(job, "index")
        get_retriever(db).index_document(document_id=document.id)
        db.commit()

        update_job_step(job, "topic_extract")
        refresh_course_topics(db, course=document.course)
        db.commit()

        document.status = "completed"
        update_job_step(job, "complete")
        db.commit()
    except Exception as exc:
        db.rollback()
        failed_job = db.query(ProcessingJob).filter(ProcessingJob.id == job.id).first()
        failed_document = db.query(Document).filter(Document.id == job.document_id).first()
        if failed_job:
            mark_job_failed(failed_job, str(exc))
        if failed_document:
            failed_document.status = "failed"
        db.commit()


def delete_document_record(db: Session, document: Document) -> None:
    file_path = Path(document.file_path) if document.file_path else None
    course = document.course
    get_retriever(db).delete_document(user_id=document.user_id, document_id=document.id)
    db.delete(document)
    db.commit()
    if course:
        refresh_course_topics(db, course=course)

    if file_path and file_path.exists():
        file_path.unlink(missing_ok=True)


def _replace_document_chunks(db: Session, document: Document, sections) -> None:
    db.query(ChildChunk).filter(ChildChunk.document_id == document.id).delete()
    db.query(ParentChunk).filter(ParentChunk.document_id == document.id).delete()
    db.commit()

    parents, children = build_hierarchical_chunks(sections)
    parent_records: dict[int, ParentChunk] = {}

    for parent in parents:
        root_chunk_id = f"doc-{document.id}-parent-{parent.chunk_index}"
        record = ParentChunk(
            user_id=document.user_id,
            course_id=document.course_id,
            document_id=document.id,
            filename=document.filename,
            material_type=document.material_type,
            page_number=parent.page_number,
            section_title=parent.section_title,
            root_chunk_id=root_chunk_id,
            chunk_level=0,
            chunk_index=parent.chunk_index,
            text=parent.text,
        )
        db.add(record)
        db.flush()
        parent_records[parent.chunk_index] = record

    for child in children:
        parent_record = parent_records[child.parent_index]
        db.add(
            ChildChunk(
                user_id=document.user_id,
                course_id=document.course_id,
                document_id=document.id,
                parent_chunk_id=parent_record.id,
                filename=document.filename,
                material_type=document.material_type,
                page_number=child.page_number,
                section_title=child.section_title,
                chunk_id=f"doc-{document.id}-child-{child.chunk_index}",
                root_chunk_id=parent_record.root_chunk_id,
                chunk_level=1,
                chunk_index=child.chunk_index,
                text=child.text,
            )
        )

    document.chunk_count = len(children)
    db.commit()
