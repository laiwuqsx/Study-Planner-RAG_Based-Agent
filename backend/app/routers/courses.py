from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.auth import get_current_user, get_db
from backend.app.dependencies import get_user_course_or_404
from backend.app.models import Course, User
from backend.app.schemas import CourseCreate, CourseListResponse, CourseResponse, CourseUpdate, DeleteResponse
from backend.app.utils import normalize_name

router = APIRouter(prefix="/courses", tags=["courses"])


@router.post("", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(
    request: CourseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    name = normalize_name(request.name)
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


@router.get("", response_model=CourseListResponse)
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


@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(course: Course = Depends(get_user_course_or_404)):
    return course


@router.patch("/{course_id}", response_model=CourseResponse)
async def update_course(
    request: CourseUpdate,
    course: Course = Depends(get_user_course_or_404),
    db: Session = Depends(get_db),
):
    updates = request.model_dump(exclude_unset=True)
    if "name" in updates:
        name = normalize_name(updates["name"])
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


@router.delete("/{course_id}", response_model=DeleteResponse)
async def delete_course(
    course: Course = Depends(get_user_course_or_404),
    db: Session = Depends(get_db),
):
    course_id = course.id
    db.delete(course)
    db.commit()
    return DeleteResponse(id=course_id, message="Course deleted")
