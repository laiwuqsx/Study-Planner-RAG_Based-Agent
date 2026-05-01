from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    get_db,
    get_password_hash,
)
from backend.app.models import Course, User
from backend.app.schemas import (
    AuthResponse,
    CourseCreate,
    CourseListResponse,
    CourseResponse,
    CourseUpdate,
    CurrentUserResponse,
    DeleteResponse,
    LoginRequest,
    RegisterRequest,
)

router = APIRouter()


def _normalize_name(value: str) -> str:
    return " ".join((value or "").strip().split())


def _get_user_course_or_404(db: Session, current_user: User, course_id: int) -> Course:
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == current_user.id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


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

