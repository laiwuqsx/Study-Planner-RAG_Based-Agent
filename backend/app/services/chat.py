import json
import re
from datetime import datetime
from typing import Iterable

from sqlalchemy.orm import Session

from backend.app.models import ChatMessage, ChatSession, Course, User
from backend.app.schemas import ChatMessageResponse, ChatSessionDetailResponse, ChatSessionSummaryResponse, ChatSourceResponse
from backend.app.services.llm_chat import ChatProviderError, generate_grounded_answer, should_use_llm
from backend.app.services.retrievers.factory import get_retriever

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "what",
    "with",
}


def list_sessions(db: Session, *, user_id: int, course_id: int) -> list[ChatSession]:
    return (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user_id, ChatSession.course_id == course_id)
        .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
        .all()
    )


def get_session_detail(session: ChatSession) -> ChatSessionDetailResponse:
    messages = [
        ChatMessageResponse(
            id=message.id,
            role=message.role,
            content=message.content,
            retrieval_mode=message.retrieval_mode,
            sources=_deserialize_sources(message.sources_json),
            created_at=message.created_at,
        )
        for message in sorted(session.messages, key=lambda item: (item.created_at, item.id))
    ]
    return ChatSessionDetailResponse(
        id=session.id,
        course_id=session.course_id,
        title=session.title,
        messages=messages,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def delete_session(db: Session, session: ChatSession) -> None:
    db.delete(session)
    db.commit()


def answer_course_question(
    db: Session,
    *,
    course: Course,
    current_user: User,
    message: str,
    session_id: int | None,
    retrieval_mode: str,
    top_k: int,
) -> tuple[ChatSession, ChatMessage, ChatMessage]:
    session = _get_or_create_session(
        db,
        user_id=current_user.id,
        course_id=course.id,
        session_id=session_id,
        first_message=message,
    )
    user_message = ChatMessage(
        session_id=session.id,
        role="user",
        content=message.strip(),
        retrieval_mode=retrieval_mode,
        sources_json="[]",
    )
    db.add(user_message)
    db.flush()

    results = get_retriever(db).search(
        query=message.strip(),
        user_id=current_user.id,
        course_id=course.id,
        top_k=top_k,
        retrieval_mode=retrieval_mode,
    )
    if not results:
        simplified_query = " ".join(sorted(_query_terms(message.strip())))
        if simplified_query:
            results = get_retriever(db).search(
                query=simplified_query,
                user_id=current_user.id,
                course_id=course.id,
                top_k=top_k,
                retrieval_mode=retrieval_mode,
            )
    if not results and retrieval_mode != "hybrid":
        results = get_retriever(db).search(
            query=message.strip(),
            user_id=current_user.id,
            course_id=course.id,
            top_k=top_k,
            retrieval_mode="hybrid",
        )
    answer_text = build_answer(message.strip(), results)
    if results and should_use_llm():
        try:
            answer_text = generate_grounded_answer(question=message.strip(), results=results)
        except ChatProviderError:
            pass
    assistant_message = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=answer_text,
        retrieval_mode=retrieval_mode,
        sources_json=json.dumps(results),
    )
    db.add(assistant_message)
    session.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    db.refresh(user_message)
    db.refresh(assistant_message)
    return session, user_message, assistant_message


def serialize_session_summary(session: ChatSession) -> ChatSessionSummaryResponse:
    return ChatSessionSummaryResponse(
        id=session.id,
        course_id=session.course_id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def serialize_message(message: ChatMessage) -> ChatMessageResponse:
    return ChatMessageResponse(
        id=message.id,
        role=message.role,
        content=message.content,
        retrieval_mode=message.retrieval_mode,
        sources=_deserialize_sources(message.sources_json),
        created_at=message.created_at,
    )


def stream_answer_chunks(text: str) -> Iterable[str]:
    for token in text.split():
        yield token + " "


def build_answer(question: str, results: list[dict]) -> str:
    if not results:
        return "I could not find relevant course material for that question in this course yet."

    query_terms = _query_terms(question)
    selected_sentences: list[str] = []
    seen: set[str] = set()
    for index, result in enumerate(results[:3], start=1):
        for sentence in _candidate_sentences(result["text"]):
            normalized = " ".join(sentence.lower().split())
            if normalized in seen:
                continue
            if query_terms and not any(term in normalized for term in query_terms):
                continue
            seen.add(normalized)
            selected_sentences.append(f"[{index}] {sentence}")
            break
        if len(selected_sentences) >= 3:
            break

    if not selected_sentences:
        selected_sentences = [f"[1] {results[0]['text'][:260].strip()}"]

    opening = "Based on the retrieved course material, here is the closest explanation:"
    closing = "Sources are listed inline by bracket number."
    return " ".join([opening, *selected_sentences, closing])


def _get_or_create_session(
    db: Session,
    *,
    user_id: int,
    course_id: int,
    session_id: int | None,
    first_message: str,
) -> ChatSession:
    if session_id is not None:
        session = (
            db.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == user_id, ChatSession.course_id == course_id)
            .first()
        )
        if session:
            return session

    session = ChatSession(
        user_id=user_id,
        course_id=course_id,
        title=_build_session_title(first_message),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _build_session_title(message: str) -> str:
    words = message.strip().split()
    return " ".join(words[:8])[:80] or "New conversation"


def _query_terms(question: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9\-]{2,}", question.lower())
        if token not in STOPWORDS
    }


def _candidate_sentences(text: str) -> list[str]:
    cleaned = " ".join(text.split())
    sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", cleaned) if item.strip()]
    if sentences:
        return sentences[:4]
    return [cleaned[:260].strip()] if cleaned else []


def _deserialize_sources(raw: str) -> list[ChatSourceResponse]:
    payload = json.loads(raw or "[]")
    return [
        ChatSourceResponse(
            chunk_id=item["chunk_id"],
            document_id=item["document_id"],
            filename=item["filename"],
            page_number=item.get("page_number"),
            section_title=item.get("section_title", ""),
            text=item["text"],
            score=float(item.get("score", 0.0)),
        )
        for item in payload
    ]
