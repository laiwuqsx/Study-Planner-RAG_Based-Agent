from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.auth import get_current_user, get_db
from backend.app.dependencies import get_user_course_or_404, get_user_topic_or_404
from backend.app.models import Course, Topic, User
from backend.app.schemas import TopicListResponse, TopicRefreshResponse, TopicResponse, TopicUpdateRequest
from backend.app.services.topics import get_course_topic, list_course_topics, refresh_course_topics, serialize_topic, update_topic

router = APIRouter(prefix="/courses/{course_id}/topics", tags=["topics"])


@router.get("", response_model=TopicListResponse)
async def list_topics(
    course: Course = Depends(get_user_course_or_404),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    topics = list_course_topics(db, user_id=current_user.id, course_id=course.id)
    return TopicListResponse(topics=[TopicResponse(**serialize_topic(topic)) for topic in topics])


@router.post("/refresh", response_model=TopicRefreshResponse)
async def refresh_topics(
    course: Course = Depends(get_user_course_or_404),
    db: Session = Depends(get_db),
):
    topics = refresh_course_topics(db, course=course)
    return TopicRefreshResponse(
        topic_count=len(topics),
        topics=[TopicResponse(**serialize_topic(topic)) for topic in topics],
    )


@router.get("/{topic_id}", response_model=TopicResponse)
async def get_topic(
    course: Course = Depends(get_user_course_or_404),
    topic: Topic = Depends(get_user_topic_or_404),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if topic.course_id != course.id:
        raise HTTPException(status_code=404, detail="Topic not found")
    record = get_course_topic(db, user_id=current_user.id, course_id=course.id, topic_id=topic.id)
    if not record:
        raise HTTPException(status_code=404, detail="Topic not found")
    return TopicResponse(**serialize_topic(record))


@router.patch("/{topic_id}", response_model=TopicResponse)
async def patch_topic(
    request: TopicUpdateRequest,
    course: Course = Depends(get_user_course_or_404),
    topic: Topic = Depends(get_user_topic_or_404),
    db: Session = Depends(get_db),
):
    if topic.course_id != course.id:
        raise HTTPException(status_code=404, detail="Topic not found")
    updated = update_topic(
        db,
        topic=topic,
        name=request.name,
        description=request.description,
        keywords=request.keywords,
        importance=request.importance,
        difficulty=request.difficulty,
        prerequisites=request.prerequisites,
    )
    return TopicResponse(**serialize_topic(updated))
