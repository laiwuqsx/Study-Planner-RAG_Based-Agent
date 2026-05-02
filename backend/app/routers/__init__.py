from fastapi import APIRouter

from backend.app.routers import auth, courses, documents, jobs, search

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(courses.router)
api_router.include_router(documents.router)
api_router.include_router(jobs.router)
api_router.include_router(search.router)
