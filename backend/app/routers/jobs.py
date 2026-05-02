from fastapi import APIRouter, Depends

from backend.app.dependencies import get_user_job_or_404
from backend.app.models import ProcessingJob
from backend.app.schemas import ProcessingJobResponse
from backend.app.services.jobs import serialize_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=ProcessingJobResponse)
async def get_job_status(job: ProcessingJob = Depends(get_user_job_or_404)):
    return serialize_job(job)
