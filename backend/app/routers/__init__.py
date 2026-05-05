from fastapi import APIRouter

from backend.app.routers import auth, chat, courses, documents, jobs, search, study_plans, topics

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(courses.router)
api_router.include_router(documents.router)
api_router.include_router(jobs.router)
api_router.include_router(search.router)
api_router.include_router(topics.router)
api_router.include_router(chat.router)
api_router.include_router(study_plans.router)
