from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.auth import get_current_user, get_db
from backend.app.dependencies import get_user_course_or_404, get_user_study_plan_item_or_404, get_user_study_plan_or_404
from backend.app.models import Course, StudyPlan, StudyPlanItem, User
from backend.app.schemas import StudyPlanGenerateRequest, StudyPlanGenerateResponse, StudyPlanItemUpdateRequest, StudyPlanListResponse, StudyPlanResponse
from backend.app.services.study_plans import delete_study_plan, generate_study_plan, get_latest_study_plan, list_course_study_plans, serialize_study_plan, update_study_plan_item_status

router = APIRouter(prefix="/courses/{course_id}/study-plan", tags=["study-plan"])


@router.get("", response_model=StudyPlanResponse)
async def get_course_study_plan(
    course: Course = Depends(get_user_course_or_404),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plan = get_latest_study_plan(db, user_id=current_user.id, course_id=course.id)
    if not plan:
        raise HTTPException(status_code=404, detail="Study plan not found")
    return serialize_study_plan(plan)


@router.get("/all", response_model=StudyPlanListResponse)
async def list_course_study_plans_route(
    course: Course = Depends(get_user_course_or_404),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plans = list_course_study_plans(db, user_id=current_user.id, course_id=course.id)
    return StudyPlanListResponse(plans=[serialize_study_plan(plan) for plan in plans])


@router.post("/generate", response_model=StudyPlanGenerateResponse, status_code=status.HTTP_201_CREATED)
async def create_course_study_plan(
    request: StudyPlanGenerateRequest,
    course: Course = Depends(get_user_course_or_404),
    db: Session = Depends(get_db),
):
    try:
        plan = generate_study_plan(
            db,
            course=course,
            goal=request.goal,
            sessions_per_week=request.sessions_per_week,
            minutes_per_session=request.minutes_per_session,
            topic_limit=request.topic_limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return StudyPlanGenerateResponse(plan=serialize_study_plan(plan))


@router.post("/regenerate", response_model=StudyPlanGenerateResponse)
async def regenerate_course_study_plan(
    request: StudyPlanGenerateRequest,
    course: Course = Depends(get_user_course_or_404),
    db: Session = Depends(get_db),
):
    try:
        plan = generate_study_plan(
            db,
            course=course,
            goal=request.goal,
            sessions_per_week=request.sessions_per_week,
            minutes_per_session=request.minutes_per_session,
            topic_limit=request.topic_limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return StudyPlanGenerateResponse(plan=serialize_study_plan(plan))


@router.patch("/items/{item_id}", response_model=StudyPlanResponse)
async def patch_study_plan_item(
    request: StudyPlanItemUpdateRequest,
    course: Course = Depends(get_user_course_or_404),
    item: StudyPlanItem = Depends(get_user_study_plan_item_or_404),
    db: Session = Depends(get_db),
):
    if item.plan.course_id != course.id:
        raise HTTPException(status_code=404, detail="Study plan item not found")
    plan = update_study_plan_item_status(db, item=item, status=request.status)
    return serialize_study_plan(plan)


@router.delete("/{plan_id}")
async def remove_study_plan(
    course: Course = Depends(get_user_course_or_404),
    plan: StudyPlan = Depends(get_user_study_plan_or_404),
    db: Session = Depends(get_db),
):
    if plan.course_id != course.id:
        raise HTTPException(status_code=404, detail="Study plan not found")
    plan_id = plan.id
    delete_study_plan(db, plan=plan)
    return {"id": plan_id, "message": "Study plan deleted"}
