import json

from backend.app.models import ProcessingJob
from backend.app.schemas import JobStepResponse, ProcessingJobResponse

UPLOAD_STEPS = [
    ("upload", "File uploaded"),
    ("parse", "Extracting document text"),
    ("chunk", "Building hierarchical chunks"),
    ("index", "Retrieval indexing not implemented yet"),
    ("topic_extract", "Topic extraction not implemented yet"),
    ("complete", "Document ready for retrieval indexing"),
]


def build_job_steps(current_step: str, failed: bool = False, error_message: str = "") -> list[dict]:
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
        steps.append(
            {
                "step": step,
                "status": status_value,
                "message": error_message if failed and step == current_step else message,
            }
        )

    if current_step == "complete" and not failed:
        for item in steps:
            item["status"] = "completed"
    return steps


def update_job_step(job: ProcessingJob, step: str, message: str | None = None) -> None:
    job.current_step = step
    job.message = message or dict(UPLOAD_STEPS).get(step, "")
    if step == "complete":
        job.status = "completed"
    elif job.status == "queued":
        job.status = "processing"
    job.steps_json = json.dumps(build_job_steps(step))


def mark_job_failed(job: ProcessingJob, error_message: str) -> None:
    job.status = "failed"
    job.error = error_message
    job.message = "Document processing failed"
    job.steps_json = json.dumps(build_job_steps(job.current_step or "upload", failed=True, error_message=error_message))


def serialize_job(job: ProcessingJob) -> ProcessingJobResponse:
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
