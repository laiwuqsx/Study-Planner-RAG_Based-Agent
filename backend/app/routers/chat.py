import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.app.auth import get_current_user, get_db
from backend.app.dependencies import get_user_course_or_404, get_user_session_or_404
from backend.app.models import ChatSession, Course, User
from backend.app.schemas import ChatRequest, ChatResponse, ChatSessionListResponse
from backend.app.services.chat import (
    answer_course_question,
    delete_session,
    get_session_detail,
    list_sessions,
    serialize_message,
    serialize_session_summary,
    stream_answer_chunks,
)

router = APIRouter(tags=["chat"])


@router.post("/courses/{course_id}/chat", response_model=ChatResponse)
async def chat_course(
    request: ChatRequest,
    course: Course = Depends(get_user_course_or_404),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session, user_message, assistant_message = answer_course_question(
        db,
        course=course,
        current_user=current_user,
        message=request.message,
        session_id=request.session_id,
        retrieval_mode=request.retrieval_mode,
        top_k=request.top_k,
    )
    return ChatResponse(
        session=serialize_session_summary(session),
        user_message=serialize_message(user_message),
        assistant_message=serialize_message(assistant_message),
    )


@router.post("/courses/{course_id}/chat/stream")
async def stream_chat_course(
    request: ChatRequest,
    course: Course = Depends(get_user_course_or_404),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session, user_message, assistant_message = answer_course_question(
        db,
        course=course,
        current_user=current_user,
        message=request.message,
        session_id=request.session_id,
        retrieval_mode=request.retrieval_mode,
        top_k=request.top_k,
    )

    def event_stream():
        yield f"event: session\ndata: {json.dumps({'session_id': session.id})}\n\n"
        yield f"event: user_message\ndata: {json.dumps({'message_id': user_message.id})}\n\n"
        for chunk in stream_answer_chunks(assistant_message.content):
            yield f"event: token\ndata: {json.dumps({'text': chunk})}\n\n"
        payload = serialize_message(assistant_message).model_dump(mode="json")
        yield f"event: done\ndata: {json.dumps(payload)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/courses/{course_id}/sessions", response_model=ChatSessionListResponse)
async def list_course_sessions(
    course: Course = Depends(get_user_course_or_404),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sessions = list_sessions(db, user_id=current_user.id, course_id=course.id)
    return ChatSessionListResponse(sessions=[serialize_session_summary(session) for session in sessions])


@router.get("/sessions/{session_id}")
async def get_session(
    session: ChatSession = Depends(get_user_session_or_404),
):
    return get_session_detail(session)


@router.delete("/sessions/{session_id}")
async def remove_session(
    session: ChatSession = Depends(get_user_session_or_404),
    db: Session = Depends(get_db),
):
    session_id = session.id
    delete_session(db, session)
    return {"id": session_id, "message": "Session deleted"}
