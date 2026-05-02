from backend.app.database import SessionLocal
from backend.app.models import ProcessingJob
from backend.app.services.documents import process_document_job


def run_processing_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            return
        process_document_job(db, job)
    finally:
        db.close()
