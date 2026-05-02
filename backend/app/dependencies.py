from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.auth import get_current_user, get_db
from backend.app.models import Course, Document, ProcessingJob, User


def get_user_course_or_404(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Course:
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == current_user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


def get_user_job_or_404(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProcessingJob:
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id, ProcessingJob.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def get_user_document_or_404(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Document:
    document = db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document
