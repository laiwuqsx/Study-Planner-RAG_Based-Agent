from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.auth import get_current_user, get_db
from backend.app.dependencies import get_user_course_or_404
from backend.app.models import Course, User
from backend.app.schemas import SearchResponse, SearchResultResponse
from backend.app.services.retrievers.factory import get_retriever

router = APIRouter(prefix="/courses/{course_id}/search", tags=["search"])


@router.get("", response_model=SearchResponse)
async def search_course_chunks(
    course: Course = Depends(get_user_course_or_404),
    query: str = Query(min_length=1, max_length=300),
    retrieval_mode: str = Query(default="keyword", pattern="^(keyword|vector|hybrid)$"),
    top_k: int = Query(default=8, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cleaned = query.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="Search query is required")

    retriever = get_retriever(db)
    results = retriever.search(
        query=cleaned,
        user_id=current_user.id,
        course_id=course.id,
        top_k=top_k,
        retrieval_mode=retrieval_mode,
    )
    return SearchResponse(
        query=cleaned,
        retrieval_mode=retrieval_mode,
        results=[SearchResultResponse(**result) for result in results],
    )
