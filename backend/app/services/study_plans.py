import json
from collections import defaultdict
from datetime import datetime

from sqlalchemy.orm import Session, selectinload

from backend.app.models import ChildChunk, Course, StudyPlan, StudyPlanItem, Topic
from backend.app.schemas import StudyPlanItemResponse, StudyPlanResponse
from backend.app.services.llm_chat import ChatProviderError, run_chat_completion, should_use_llm
from backend.app.services.topics import list_plannable_topics, serialize_topic


def get_latest_study_plan(db: Session, *, user_id: int, course_id: int) -> StudyPlan | None:
    return (
        db.query(StudyPlan)
        .options(selectinload(StudyPlan.items))
        .filter(StudyPlan.user_id == user_id, StudyPlan.course_id == course_id)
        .order_by(StudyPlan.created_at.desc(), StudyPlan.id.desc())
        .first()
    )


def delete_course_study_plans(db: Session, *, user_id: int, course_id: int) -> None:
    plans = db.query(StudyPlan).filter(StudyPlan.user_id == user_id, StudyPlan.course_id == course_id).all()
    for plan in plans:
        db.delete(plan)
    db.commit()


def generate_study_plan(
    db: Session,
    *,
    course: Course,
    goal: str,
    sessions_per_week: int,
    minutes_per_session: int,
    topic_limit: int,
) -> StudyPlan:
    topics = list_plannable_topics(db, user_id=course.user_id, course_id=course.id)
    if not topics:
        raise ValueError("No topics available. Refresh topic extraction before generating a study plan.")

    topic_catalog = _build_topic_catalog(db, topics=topics, user_id=course.user_id, course_id=course.id, topic_limit=topic_limit)
    if not topic_catalog:
        raise ValueError("No usable topics available for study plan generation.")

    mode = "rule"
    if should_use_llm():
        try:
            plan_payload = _generate_plan_with_llm(
                course=course,
                topic_catalog=topic_catalog,
                goal=goal,
                sessions_per_week=sessions_per_week,
                minutes_per_session=minutes_per_session,
            )
            normalized_plan = _normalize_plan_payload(
                raw_plan=plan_payload,
                topic_catalog=topic_catalog,
                minutes_per_session=minutes_per_session,
            )
            mode = "llm"
        except ChatProviderError:
            normalized_plan = _build_rule_plan(
                course=course,
                topic_catalog=topic_catalog,
                goal=goal,
                sessions_per_week=sessions_per_week,
                minutes_per_session=minutes_per_session,
            )
    else:
        normalized_plan = _build_rule_plan(
            course=course,
            topic_catalog=topic_catalog,
            goal=goal,
            sessions_per_week=sessions_per_week,
            minutes_per_session=minutes_per_session,
        )

    delete_course_study_plans(db, user_id=course.user_id, course_id=course.id)

    plan = StudyPlan(
        user_id=course.user_id,
        course_id=course.id,
        title=normalized_plan["title"],
        summary=normalized_plan["summary"],
        generation_mode=mode,
        item_count=len(normalized_plan["items"]),
    )
    db.add(plan)
    db.flush()

    for index, item in enumerate(normalized_plan["items"], start=1):
        topic = item["topic"]
        db.add(
            StudyPlanItem(
                plan_id=plan.id,
                topic_id=topic.id,
                order_index=index,
                title=item["title"],
                notes=item["notes"],
                focus_points_json=json.dumps(item["focus_points"]),
                context_snippets_json=json.dumps(item["context_snippets"]),
                estimated_effort_minutes=item["estimated_effort_minutes"],
                importance=topic.importance,
                difficulty=topic.difficulty,
                source_chunk_count=item["source_chunk_count"],
            )
        )

    db.commit()
    db.refresh(plan)
    return get_latest_study_plan(db, user_id=course.user_id, course_id=course.id) or plan


def serialize_study_plan(plan: StudyPlan) -> StudyPlanResponse:
    items = sorted(plan.items, key=lambda item: (item.order_index, item.id))
    completed_item_count = sum(1 for item in items if item.status == "completed")
    next_item = next((item for item in items if item.status != "completed"), None)
    return StudyPlanResponse(
        id=plan.id,
        course_id=plan.course_id,
        title=plan.title,
        summary=plan.summary,
        generation_mode=plan.generation_mode,
        item_count=plan.item_count,
        completed_item_count=completed_item_count,
        next_item_id=next_item.id if next_item else None,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        items=[
            StudyPlanItemResponse(
                id=item.id,
                topic_id=item.topic_id,
                order_index=item.order_index,
                title=item.title,
                notes=item.notes,
                focus_points=json.loads(item.focus_points_json or "[]"),
                context_snippets=json.loads(item.context_snippets_json or "[]"),
                estimated_effort_minutes=item.estimated_effort_minutes,
                importance=item.importance,
                difficulty=item.difficulty,
                source_chunk_count=item.source_chunk_count,
                status=item.status,
                started_at=item.started_at,
                completed_at=item.completed_at,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in items
        ],
    )


def update_study_plan_item_status(db: Session, *, item: StudyPlanItem, status: str) -> StudyPlan:
    now = datetime.utcnow()
    if status == "pending":
        item.status = "pending"
        item.started_at = None
        item.completed_at = None
    elif status == "in_progress":
        item.status = "in_progress"
        if item.started_at is None:
            item.started_at = now
        item.completed_at = None
    elif status == "completed":
        item.status = "completed"
        if item.started_at is None:
            item.started_at = now
        item.completed_at = now

    db.commit()
    plan = (
        db.query(StudyPlan)
        .options(selectinload(StudyPlan.items))
        .filter(StudyPlan.id == item.plan_id)
        .first()
    )
    return plan or item.plan


def _build_topic_catalog(
    db: Session,
    *,
    topics: list[Topic],
    user_id: int,
    course_id: int,
    topic_limit: int,
) -> list[dict]:
    topic_rows: list[dict] = []
    all_chunk_ids: set[str] = set()
    for topic in topics:
        row = serialize_topic(topic)
        row["topic_record"] = topic
        row["source_chunk_count"] = len(row["source_chunk_ids"])
        topic_rows.append(row)
        all_chunk_ids.update(row["source_chunk_ids"])

    chunk_lookup: dict[str, ChildChunk] = {}
    if all_chunk_ids:
        chunks = (
            db.query(ChildChunk)
            .filter(ChildChunk.user_id == user_id, ChildChunk.course_id == course_id, ChildChunk.chunk_id.in_(sorted(all_chunk_ids)))
            .order_by(ChildChunk.document_id.asc(), ChildChunk.chunk_index.asc())
            .all()
        )
        chunk_lookup = {chunk.chunk_id: chunk for chunk in chunks}

    ranked = sorted(
        topic_rows,
        key=lambda item: (-item["importance"], -item["source_chunk_count"], item["difficulty"], item["name"].lower()),
    )[:topic_limit]

    catalog: list[dict] = []
    for item in ranked:
        source_chunks = [chunk_lookup[chunk_id] for chunk_id in item["source_chunk_ids"] if chunk_id in chunk_lookup]
        snippets = _pick_context_snippets(source_chunks)
        description = item["description"].strip() or (snippets[0] if snippets else "")
        catalog.append(
            {
                "topic_id": item["id"],
                "name": item["name"],
                "description": description[:220],
                "keywords": item["keywords"][:5],
                "importance": item["importance"],
                "difficulty": item["difficulty"],
                "source_chunk_count": item["source_chunk_count"],
                "context_snippets": snippets,
                "topic": item["topic_record"],
            }
        )
    return catalog


def _pick_context_snippets(chunks: list[ChildChunk]) -> list[str]:
    by_root: dict[str, list[ChildChunk]] = defaultdict(list)
    for chunk in chunks:
        by_root[chunk.root_chunk_id].append(chunk)

    candidates: list[ChildChunk] = []
    for root in sorted(by_root.keys()):
        group = sorted(by_root[root], key=lambda item: item.chunk_index)
        medium = next((chunk for chunk in group if 120 <= len(chunk.text) <= 420), None)
        candidates.append(medium or group[0])

    snippets: list[str] = []
    for chunk in sorted(candidates, key=lambda item: (item.document_id, item.chunk_index))[:2]:
        text = " ".join(chunk.text.split())
        if not text:
            continue
        snippets.append(text[:320])
    return snippets


def _generate_plan_with_llm(
    *,
    course: Course,
    topic_catalog: list[dict],
    goal: str,
    sessions_per_week: int,
    minutes_per_session: int,
) -> dict:
    prompt = json.dumps(
        {
            "task": "Create a focused study plan for one course. Use the topic catalog below. Return JSON only.",
            "constraints": {
                "goal": goal,
                "sessions_per_week": sessions_per_week,
                "minutes_per_session": minutes_per_session,
                "requirements": [
                    "Cover each topic exactly once in the item list.",
                    "Put foundational topics before more advanced topics when the descriptions suggest that dependency.",
                    "Do not invent course facts outside the topic catalog.",
                    "Use concise notes aimed at a student preparing to review this course.",
                ],
            },
            "output_schema": {
                "title": "short plan title",
                "summary": "1-2 sentence overview",
                "items": [
                    {
                        "topic_id": "existing topic id",
                        "order_index": "1-based order",
                        "title": "short study item title",
                        "notes": "1-2 sentence study guidance",
                        "focus_points": ["2-4 bullets as short strings"],
                        "estimated_effort_minutes": "integer",
                    }
                ],
            },
            "topic_catalog": [
                {
                    "topic_id": item["topic_id"],
                    "name": item["name"],
                    "description": item["description"],
                    "keywords": item["keywords"],
                    "importance": item["importance"],
                    "difficulty": item["difficulty"],
                    "source_chunk_count": item["source_chunk_count"],
                    "context_snippets": item["context_snippets"],
                }
                for item in topic_catalog
            ],
        },
        ensure_ascii=False,
        indent=2,
    )
    response = run_chat_completion(
        messages=[
            {
                "role": "system",
                "content": (
                    "You generate structured study plans for one course. "
                    "Base the order and notes on the supplied topic catalog. "
                    "You may infer likely learning progression from the descriptions and snippets, but do not invent unsupported specifics. "
                    "Return JSON only."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=1400,
    )
    return _parse_json_object(response)


def _normalize_plan_payload(*, raw_plan: dict, topic_catalog: list[dict], minutes_per_session: int) -> dict:
    topics_by_id = {item["topic_id"]: item for item in topic_catalog}
    raw_items = raw_plan.get("items")
    if not isinstance(raw_items, list):
        raise ChatProviderError("Study plan generator did not return an items list")

    normalized_items: list[dict] = []
    used_topic_ids: set[int] = set()
    for raw_item in raw_items:
        topic_id = _coerce_int(raw_item.get("topic_id"))
        if topic_id is None or topic_id not in topics_by_id or topic_id in used_topic_ids:
            continue
        topic_entry = topics_by_id[topic_id]
        used_topic_ids.add(topic_id)
        title = " ".join(str(raw_item.get("title", "")).strip().split()) or topic_entry["name"]
        notes = _limit_text(str(raw_item.get("notes", "")).strip(), 320) or topic_entry["description"]
        focus_points = _normalize_string_list(raw_item.get("focus_points"), limit=4)
        if not focus_points:
            focus_points = topic_entry["keywords"][:3]
        normalized_items.append(
            {
                "topic": topic_entry["topic"],
                "title": title,
                "notes": notes,
                "focus_points": focus_points,
                "context_snippets": topic_entry["context_snippets"],
                "estimated_effort_minutes": _normalize_effort(
                    raw_item.get("estimated_effort_minutes"),
                    default=max(45, min(minutes_per_session, 120)),
                ),
                "source_chunk_count": topic_entry["source_chunk_count"],
            }
        )

    for topic_entry in topic_catalog:
        if topic_entry["topic_id"] in used_topic_ids:
            continue
        normalized_items.append(
            {
                "topic": topic_entry["topic"],
                "title": topic_entry["name"],
                "notes": topic_entry["description"],
                "focus_points": topic_entry["keywords"][:3],
                "context_snippets": topic_entry["context_snippets"],
                "estimated_effort_minutes": max(45, min(minutes_per_session, 120)),
                "source_chunk_count": topic_entry["source_chunk_count"],
            }
        )

    title = " ".join(str(raw_plan.get("title", "")).strip().split()) or f"{topic_catalog[0]['topic'].course.name} Study Plan"
    summary = _limit_text(str(raw_plan.get("summary", "")).strip(), 280)
    if not summary:
        summary = "A focused review plan generated from the current topic catalog and linked material snippets."
    return {
        "title": title,
        "summary": summary,
        "items": normalized_items,
    }


def _build_rule_plan(
    *,
    course: Course,
    topic_catalog: list[dict],
    goal: str,
    sessions_per_week: int,
    minutes_per_session: int,
) -> dict:
    ranked = sorted(
        topic_catalog,
        key=lambda item: (-item["importance"], item["difficulty"], -item["source_chunk_count"], item["name"].lower()),
    )
    ordered: list[dict] = []
    hard_topics = [item for item in ranked if item["difficulty"] >= 4]
    easier_topics = [item for item in ranked if item["difficulty"] < 4]
    while easier_topics or hard_topics:
        if easier_topics:
            ordered.append(easier_topics.pop(0))
        if hard_topics:
            ordered.append(hard_topics.pop(0))

    items = []
    for topic_entry in ordered:
        effort = min(150, max(45, minutes_per_session + (topic_entry["difficulty"] - 3) * 15))
        focus = topic_entry["keywords"][:3] or [topic_entry["name"]]
        items.append(
            {
                "topic": topic_entry["topic"],
                "title": topic_entry["name"],
                "notes": _limit_text(
                    f"Review this topic with emphasis on {', '.join(focus)}. "
                    f"Use the linked material snippets to reinforce the core idea before moving on.",
                    320,
                ),
                "focus_points": focus,
                "context_snippets": topic_entry["context_snippets"],
                "estimated_effort_minutes": effort,
                "source_chunk_count": topic_entry["source_chunk_count"],
            }
        )

    summary = (
        f"{goal.strip()} "
        f"This version balances {len(items)} topics across roughly {sessions_per_week} study sessions per week."
    ).strip()
    return {
        "title": f"{course.name} Study Plan",
        "summary": _limit_text(summary, 280),
        "items": items,
    }


def _parse_json_object(raw: str) -> dict:
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ChatProviderError("Study plan generator did not return JSON")
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ChatProviderError("Study plan generator returned invalid JSON") from exc


def _normalize_string_list(value, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    seen: set[str] = set()
    for raw_item in value:
        item = " ".join(str(raw_item).strip().split())
        normalized = item.lower()
        if not item or normalized in seen:
            continue
        seen.add(normalized)
        items.append(item[:80])
        if len(items) >= limit:
            break
    return items


def _normalize_effort(value, *, default: int) -> int:
    number = _coerce_int(value)
    if number is None:
        number = default
    return max(30, min(180, number))


def _coerce_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _limit_text(value: str, limit: int) -> str:
    return " ".join(value.split())[:limit]
