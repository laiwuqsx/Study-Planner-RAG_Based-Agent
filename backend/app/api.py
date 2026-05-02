import json
import os
import time
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    get_db,
    get_password_hash,
)
from backend.app.database import SessionLocal
from backend.app.models import Course, Document, ProcessingJob, User
from backend.app.schemas import (
    AuthResponse,
    CourseCreate,
    CourseListResponse,
    CourseResponse,
    CourseUpdate,
    CurrentUserResponse,
    DeleteResponse,
    DocumentListResponse,
    DocumentResponse,
    JobStepResponse,
    LoginRequest,
    ProcessingJobResponse,
    RegisterRequest,
    UploadDocumentResponse,
)

router = APIRouter()

UPLOAD_STEPS = [
    ("upload", "File uploaded"),
    ("parse", "Preparing document parsing"),
    ("chunk", "Preparing chunk generation"),
    ("index", "Preparing retrieval indexing"),
    ("topic_extract", "Preparing topic extraction"),
    ("complete", "Document ready for the next pipeline stage"),
]
SUPPORTED_UPLOAD_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}
ALLOWED_EXTENSIONS = {".pdf", ".docx"}
DEFAULT_STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "./storage/uploads"))


def _normalize_name(value: str) -> str:
    return " ".join((value or "").strip().split())


def _normalize_material_type(value: str | None) -> str:
    normalized = (value or "").strip().lower().replace(" ", "_")
    return normalized or "other"


def _job_steps_payload(current_step: str, failed: bool = False, error_message: str = "") -> list[dict]:
    steps: list[dict] = []
    seen_current = False
    for step, message in UPLOAD_STEPS:
        if failed and step == current_step:
            status_value = "error"
        elif step == current_step:
            status_value = "in_progress"
            seen_current = True
        elif not seen_current:
            status_value = "completed"
        else:
            status_value = "pending"

        step_message = error_message if failed and step == current_step else message
        steps.append({"step": step, "status": status_value, "message": step_message})

    if current_step == "complete" and not failed:
        for item in steps:
            item["status"] = "completed"
    return steps


def _serialize_job(job: ProcessingJob) -> ProcessingJobResponse:
    steps = [JobStepResponse(**item) for item in json.loads(job.steps_json or "[]")]
    return ProcessingJobResponse(
        id=job.id,
        user_id=job.user_id,
        course_id=job.course_id,
        document_id=job.document_id,
        status=job.status,
        current_step=job.current_step,
        message=job.message,
        error=job.error,
        steps=steps,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _get_user_course_or_404(db: Session, current_user: User, course_id: int) -> Course:
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == current_user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


def _get_user_job_or_404(db: Session, current_user: User, job_id: int) -> ProcessingJob:
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id, ProcessingJob.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _validate_upload(file: UploadFile) -> tuple[str, str]:
    filename = Path(file.filename or "").name
    extension = Path(filename).suffix.lower()
    content_type = (file.content_type or "").lower()

    if extension not in ALLOWED_EXTENSIONS and content_type not in SUPPORTED_UPLOAD_TYPES:
        raise HTTPException(status_code=400, detail="Only PDF and DOCX uploads are supported")

    if extension not in ALLOWED_EXTENSIONS:
        extension = SUPPORTED_UPLOAD_TYPES[content_type]
        filename = f"{filename}{extension}" if not filename.endswith(extension) else filename

    file_type = extension.lstrip(".")
    return filename, file_type


def _run_processing_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            return

        document = db.query(Document).filter(Document.id == job.document_id).first()
        if not document:
            return

        job.status = "processing"
        document.status = "processing"
        db.commit()

        for step, message in UPLOAD_STEPS[1:]:
            job.current_step = step
            job.message = message
            job.steps_json = json.dumps(_job_steps_payload(step))
            if step == "complete":
                job.status = "completed"
                document.status = "completed"
            db.commit()
            time.sleep(0.6 if step != "complete" else 0.0)
    except Exception as exc:
        db.rollback()
        failed_job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        failed_document = failed_job and db.query(Document).filter(Document.id == failed_job.document_id).first()
        error_message = str(exc)
        if failed_job:
            failed_job.status = "failed"
            failed_job.error = error_message
            failed_job.message = "Document processing failed"
            failed_job.steps_json = json.dumps(
                _job_steps_payload(failed_job.current_step or "upload", failed=True, error_message=error_message)
            )
        if failed_document:
            failed_document.status = "failed"
        db.commit()
    finally:
        db.close()


@router.post("/auth/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    username = _normalize_name(request.username)
    password = (request.password or "").strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required")

    exists = db.query(User).filter(User.username == username).first()
    if exists:
        raise HTTPException(status_code=409, detail="Username already exists")

    user = User(username=username, password_hash=get_password_hash(password))
    db.add(user)
    db.commit()
    db.refresh(user)

    return AuthResponse(access_token=create_access_token(user), username=user.username)


@router.post("/auth/login", response_model=AuthResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, _normalize_name(request.username), request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    return AuthResponse(access_token=create_access_token(user), username=user.username)


@router.get("/auth/me", response_model=CurrentUserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/courses", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(
    request: CourseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    name = _normalize_name(request.name)
    if not name:
        raise HTTPException(status_code=400, detail="Course name is required")

    course = Course(
        user_id=current_user.id,
        name=name,
        term=(request.term or "").strip(),
        description=(request.description or "").strip(),
    )
    db.add(course)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Course name already exists for this user")
    db.refresh(course)
    return course


@router.get("/courses", response_model=CourseListResponse)
async def list_courses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    courses = (
        db.query(Course)
        .filter(Course.user_id == current_user.id)
        .order_by(Course.updated_at.desc(), Course.id.desc())
        .all()
    )
    return CourseListResponse(courses=courses)


@router.get("/courses/{course_id}", response_model=CourseResponse)
async def get_course(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_user_course_or_404(db, current_user, course_id)


@router.patch("/courses/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: int,
    request: CourseUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    course = _get_user_course_or_404(db, current_user, course_id)
    updates = request.model_dump(exclude_unset=True)

    if "name" in updates:
        name = _normalize_name(updates["name"])
        if not name:
            raise HTTPException(status_code=400, detail="Course name is required")
        course.name = name
    if "term" in updates:
        course.term = (updates["term"] or "").strip()
    if "description" in updates:
        course.description = (updates["description"] or "").strip()

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Course name already exists for this user")
    db.refresh(course)
    return course


@router.delete("/courses/{course_id}", response_model=DeleteResponse)
async def delete_course(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    course = _get_user_course_or_404(db, current_user, course_id)
    db.delete(course)
    db.commit()
    return DeleteResponse(id=course_id, message="Course deleted")


@router.get("/courses/{course_id}/documents", response_model=DocumentListResponse)
async def list_documents(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_user_course_or_404(db, current_user, course_id)
    documents = (
        db.query(Document)
        .filter(Document.course_id == course_id, Document.user_id == current_user.id)
        .order_by(Document.created_at.desc(), Document.id.desc())
        .all()
    )
    return DocumentListResponse(documents=documents)


@router.post(
    "/courses/{course_id}/documents",
    response_model=UploadDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    course_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    material_type: str = Form("other"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_user_course_or_404(db, current_user, course_id)
    filename, file_type = _validate_upload(file)

    storage_dir = DEFAULT_STORAGE_DIR / str(current_user.id) / str(course_id)
    storage_dir.mkdir(parents=True, exist_ok=True)

    document = Document(
        user_id=current_user.id,
        course_id=course_id,
        filename=filename,
        file_path="",
        file_type=file_type,
        material_type=_normalize_material_type(material_type),
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
        course_id=course_id,
        document_id=document.id,
        status="queued",
        current_step="upload",
        message="File uploaded",
        steps_json=json.dumps(_job_steps_payload("upload")),
    )
    db.add(job)
    db.commit()
    db.refresh(document)
    db.refresh(job)

    background_tasks.add_task(_run_processing_job, job.id)
    return UploadDocumentResponse(document=document, job=_serialize_job(job))


@router.get("/jobs/{job_id}", response_model=ProcessingJobResponse)
async def get_job_status(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = _get_user_job_or_404(db, current_user, job_id)
    return _serialize_job(job)
