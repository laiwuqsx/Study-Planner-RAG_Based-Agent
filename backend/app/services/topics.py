import json
import re
from collections import Counter, defaultdict

from sqlalchemy.orm import Session

from backend.app.config import CHAT_API_KEY, TOPIC_EXTRACTION_MODE
from backend.app.models import ChildChunk, Course, Document, DocumentTopic, ParentChunk, StudyPlanItem, Topic, TopicSource
from backend.app.services.llm_chat import ChatProviderError, run_chat_completion

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
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "using",
    "with",
}
GENERIC_SECTION_TITLES = {"introduction", "overview", "summary", "notes", "content", "materials"}
WEAK_TOPIC_TITLES = {
    "aware",
    "challenge",
    "challenges",
    "example",
    "examples",
    "exercise",
    "exercises",
    "problem",
    "problems",
    "question",
    "questions",
    "ticket",
    "tickets",
    "running",
    "ready",
    "fixed",
    "waiting",
    "blocked",
    "load",
}
QUESTION_PREFIXES = {"what", "how", "why", "when", "where", "which", "who", "is", "are", "do", "does", "can", "will", "should"}
NOISE_LABEL_PATTERNS = [
    re.compile(r"^[a-d]$", re.IGNORECASE),
    re.compile(r"^(option|choice|answer)\s*[a-d]$", re.IGNORECASE),
    re.compile(r"^(q|question)\s*\d+$", re.IGNORECASE),
    re.compile(r"^(name|student name|date|score|id|student id)$", re.IGNORECASE),
]
LIKELY_METADATA_TERMS = {
    "attendance",
    "date",
    "email",
    "firstname",
    "lastname",
    "name",
    "netid",
    "phone",
    "score",
    "student",
    "student id",
}
DEFAULT_REVIEW_NOTE = "Auto-generated from document topic extraction."


def list_course_topics(db: Session, *, user_id: int, course_id: int, include_hidden: bool = False) -> list[Topic]:
    query = db.query(Topic).filter(Topic.user_id == user_id, Topic.course_id == course_id)
    if not include_hidden:
        query = query.filter(Topic.status != "hidden")
    topics = query.order_by(Topic.importance.desc(), Topic.difficulty.desc(), Topic.name.asc()).all()
    return [topic for topic in topics if json.loads(topic.source_chunk_ids_json or "[]")]


def list_plannable_topics(db: Session, *, user_id: int, course_id: int) -> list[Topic]:
    topics = (
        db.query(Topic)
        .filter(Topic.user_id == user_id, Topic.course_id == course_id, Topic.status == "active")
        .order_by(Topic.importance.desc(), Topic.difficulty.desc(), Topic.name.asc())
        .all()
    )
    return [topic for topic in topics if json.loads(topic.source_chunk_ids_json or "[]")]


def get_course_topic(db: Session, *, user_id: int, course_id: int, topic_id: int) -> Topic | None:
    topic = (
        db.query(Topic)
        .filter(Topic.id == topic_id, Topic.user_id == user_id, Topic.course_id == course_id, Topic.status != "hidden")
        .first()
    )
    if not topic:
        return None
    if not json.loads(topic.source_chunk_ids_json or "[]"):
        return None
    return topic


def refresh_course_topics(db: Session, *, course: Course) -> list[Topic]:
    documents = (
        db.query(Document)
        .filter(Document.user_id == course.user_id, Document.course_id == course.id)
        .order_by(Document.id.asc())
        .all()
    )
    for document in documents:
        sync_document_topics(db, document=document)
    return list_course_topics(db, user_id=course.user_id, course_id=course.id)


def curate_course_topics(db: Session, *, course: Course) -> tuple[list[Topic], int]:
    topics = list_course_topics(db, user_id=course.user_id, course_id=course.id, include_hidden=True)
    touched_topic_ids = {topic.id for topic in topics}
    if not touched_topic_ids:
        return [], 0

    if _should_use_llm_for_topics():
        try:
            operations = _plan_course_topic_curation_with_llm(course=course, topics=topics)
        except ChatProviderError:
            operations = _build_rule_curation_operations(topics)
    else:
        operations = _build_rule_curation_operations(topics)

    updated_count = _apply_course_topic_operations(db, course=course, operations=operations)
    visible_topics = list_course_topics(db, user_id=course.user_id, course_id=course.id)
    return visible_topics, updated_count


def sync_document_topics(db: Session, *, document: Document) -> list[Topic]:
    parents = (
        db.query(ParentChunk)
        .filter(ParentChunk.user_id == document.user_id, ParentChunk.course_id == document.course_id, ParentChunk.document_id == document.id)
        .order_by(ParentChunk.chunk_index.asc())
        .all()
    )
    children = (
        db.query(ChildChunk)
        .filter(ChildChunk.user_id == document.user_id, ChildChunk.course_id == document.course_id, ChildChunk.document_id == document.id)
        .order_by(ChildChunk.chunk_index.asc())
        .all()
    )

    previous_topic_ids = _delete_document_topic_links(db, document=document)
    if not parents or not children:
        _refresh_topics_from_documents(db, topic_ids=previous_topic_ids)
        document.topic_count = 0
        db.commit()
        return []

    topics_payload = _extract_document_topics(document=document, parents=parents, children=children)
    existing_topics = _topic_lookup_by_normalized_name(db, user_id=document.user_id, course_id=document.course_id)
    touched_topic_ids = set(previous_topic_ids)

    for item in topics_payload:
        topic = existing_topics.get(item["normalized_name"])
        quality = _assess_topic_quality(item)
        if topic is None:
            topic = Topic(
                user_id=document.user_id,
                course_id=document.course_id,
                name=item["name"],
                normalized_name=item["normalized_name"],
                description=item["description"],
                keywords_json="[]",
                importance=item["importance"],
                difficulty=item["difficulty"],
                status=quality["status"],
                quality_score=quality["quality_score"],
                review_note=quality["review_note"],
                source_chunk_ids_json="[]",
                prerequisites_json="[]",
            )
            db.add(topic)
            db.flush()
            existing_topics[item["normalized_name"]] = topic
        else:
            if len(item["name"]) > len(topic.name):
                topic.name = item["name"]
            if len(item["description"]) > len(topic.description):
                topic.description = item["description"]
            if topic.status != "hidden" and quality["quality_score"] >= topic.quality_score:
                topic.status = quality["status"]
                topic.quality_score = quality["quality_score"]
                topic.review_note = quality["review_note"]

        db.add(
            DocumentTopic(
                user_id=document.user_id,
                course_id=document.course_id,
                document_id=document.id,
                topic_id=topic.id,
                name=item["name"],
                normalized_name=item["normalized_name"],
                description=item["description"],
                keywords_json=json.dumps(item["keywords"]),
                importance=item["importance"],
                difficulty=item["difficulty"],
                source_chunk_ids_json=json.dumps(item["source_chunk_ids"]),
                prerequisites_json=json.dumps(item["prerequisites"]),
            )
        )
        touched_topic_ids.add(topic.id)

    document.topic_count = len(topics_payload)
    db.flush()
    _refresh_topics_from_documents(db, topic_ids=touched_topic_ids)
    db.commit()
    return [existing_topics[item["normalized_name"]] for item in topics_payload if item["normalized_name"] in existing_topics]


def delete_document_topics(db: Session, *, document: Document) -> None:
    touched_topic_ids = _delete_document_topic_links(db, document=document)
    _refresh_topics_from_documents(db, topic_ids=touched_topic_ids)
    db.commit()


def update_topic(
    db: Session,
    *,
    topic: Topic,
    name: str | None = None,
    description: str | None = None,
    keywords: list[str] | None = None,
    importance: int | None = None,
    difficulty: int | None = None,
    status: str | None = None,
    quality_score: int | None = None,
    review_note: str | None = None,
    prerequisites: list[str] | None = None,
) -> Topic:
    if name is not None:
        topic.name = " ".join(name.strip().split())
        topic.normalized_name = normalize_topic_name(topic.name)
    if description is not None:
        topic.description = description.strip()
    if keywords is not None:
        topic.keywords_json = json.dumps(_unique_preserve_order([keyword.strip() for keyword in keywords if keyword.strip()]))
    if importance is not None:
        topic.importance = max(1, min(5, importance))
    if difficulty is not None:
        topic.difficulty = max(1, min(5, difficulty))
    if status is not None:
        topic.status = status
    if quality_score is not None:
        topic.quality_score = max(1, min(5, quality_score))
    if review_note is not None:
        topic.review_note = review_note.strip()
    if prerequisites is not None:
        topic.prerequisites_json = json.dumps(_unique_preserve_order([item.strip() for item in prerequisites if item.strip()]))
    db.commit()
    db.refresh(topic)
    return topic


def serialize_topic(topic: Topic) -> dict:
    return {
        "id": topic.id,
        "course_id": topic.course_id,
        "name": topic.name,
        "description": topic.description,
        "keywords": json.loads(topic.keywords_json or "[]"),
        "importance": topic.importance,
        "difficulty": topic.difficulty,
        "status": topic.status,
        "quality_score": topic.quality_score,
        "review_note": topic.review_note,
        "source_chunk_ids": json.loads(topic.source_chunk_ids_json or "[]"),
        "prerequisites": json.loads(topic.prerequisites_json or "[]"),
        "created_at": topic.created_at,
        "updated_at": topic.updated_at,
    }


def normalize_topic_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9\s]+", " ", (value or "").strip().lower())
    return " ".join(normalized.split())


def _extract_document_topics(*, document: Document, parents: list[ParentChunk], children: list[ChildChunk]) -> list[dict]:
    candidates = _build_topic_candidates(parents=parents, children=children)
    if not candidates:
        return []
    if _should_use_llm_for_topics():
        existing_topics = _serialize_existing_topics(document.course.topics)
        try:
            operations = _plan_document_topic_operations_with_llm(course=document.course, existing_topics=existing_topics, candidates=candidates)
            extracted = _apply_document_topic_operations(candidates=candidates, existing_topics=existing_topics, operations=operations)
            if extracted:
                return _normalize_topics_payload(extracted)
        except ChatProviderError:
            pass
    return _extract_topics_from_candidates(candidates)


def _build_topic_candidates(*, parents: list[ParentChunk], children: list[ChildChunk]) -> list[dict]:
    children_by_root: dict[str, list[ChildChunk]] = defaultdict(list)
    for child in children:
        children_by_root[child.root_chunk_id].append(child)

    candidates: list[dict] = []
    for parent in parents:
        source_chunk_ids = [child.chunk_id for child in children_by_root.get(parent.root_chunk_id, [])]
        if not source_chunk_ids:
            continue
        candidate_name = _choose_topic_name(parent)
        summary_text = _build_candidate_summary(parent.text)
        keywords = _extract_keywords(parent.text, parent.section_title)[:6]
        candidate = {
            "candidate_id": parent.root_chunk_id,
            "name": candidate_name,
            "section_title": parent.section_title,
            "summary_text": summary_text,
            "raw_text": " ".join(parent.text.split())[:500],
            "keywords": keywords,
            "importance": _score_importance(parent, children_by_root.get(parent.root_chunk_id, [])),
            "difficulty": _score_difficulty(parent.text, keywords),
            "source_chunk_ids": source_chunk_ids,
            "prerequisites": _infer_prerequisites(keywords, candidate_name),
        }
        noise_reason = _candidate_noise_reason(candidate)
        if noise_reason:
            continue
        candidates.append(candidate)
    return candidates


def _serialize_existing_topics(topics: list[Topic]) -> list[dict]:
    serialized: list[dict] = []
    for topic in topics:
        source_chunk_ids = json.loads(topic.source_chunk_ids_json or "[]")
        if not source_chunk_ids or topic.status == "hidden":
            continue
        serialized.append(
            {
                "topic_id": topic.id,
                "topic_key": topic.normalized_name,
                "name": topic.name,
                "normalized_name": topic.normalized_name,
                "description": topic.description,
                "keywords": json.loads(topic.keywords_json or "[]"),
                "importance": topic.importance,
                "difficulty": topic.difficulty,
                "status": topic.status,
                "quality_score": topic.quality_score,
                "source_chunk_ids": source_chunk_ids,
                "prerequisites": json.loads(topic.prerequisites_json or "[]"),
            }
        )
    return serialized


def _topic_lookup_by_normalized_name(db: Session, *, user_id: int, course_id: int) -> dict[str, Topic]:
    topics = db.query(Topic).filter(Topic.user_id == user_id, Topic.course_id == course_id).all()
    return {topic.normalized_name: topic for topic in topics}


def _delete_document_topic_links(db: Session, *, document: Document) -> set[int]:
    topic_ids = {
        topic_id
        for topic_id, in db.query(DocumentTopic.topic_id)
        .filter(DocumentTopic.document_id == document.id, DocumentTopic.topic_id.isnot(None))
        .all()
    }
    db.query(TopicSource).filter(TopicSource.document_id == document.id).delete(synchronize_session=False)
    db.query(DocumentTopic).filter(DocumentTopic.document_id == document.id).delete(synchronize_session=False)
    return topic_ids


def _refresh_topics_from_documents(db: Session, *, topic_ids: set[int]) -> None:
    if not topic_ids:
        return

    document_topics = (
        db.query(DocumentTopic)
        .filter(DocumentTopic.topic_id.in_(sorted(topic_ids)))
        .order_by(DocumentTopic.document_id.asc(), DocumentTopic.id.asc())
        .all()
    )
    grouped: dict[int, list[DocumentTopic]] = defaultdict(list)
    for row in document_topics:
        if row.topic_id is not None:
            grouped[row.topic_id].append(row)

    db.query(TopicSource).filter(TopicSource.topic_id.in_(sorted(topic_ids))).delete(synchronize_session=False)
    topics = db.query(Topic).filter(Topic.id.in_(sorted(topic_ids))).all()
    for topic in topics:
        rows = grouped.get(topic.id, [])
        if not rows:
            has_plan_references = db.query(StudyPlanItem.id).filter(StudyPlanItem.topic_id == topic.id).first() is not None
            if has_plan_references:
                topic.source_chunk_ids_json = "[]"
                topic.keywords_json = "[]"
                topic.prerequisites_json = "[]"
                topic.importance = 1
                topic.difficulty = 1
                if topic.status != "hidden":
                    topic.status = "suspect"
                    topic.quality_score = 1
                    topic.review_note = "Topic lost all supporting chunks but is still referenced by a study plan."
                continue
            db.delete(topic)
            continue

        payload = _aggregate_document_topic_rows(rows)
        quality = _assess_topic_quality(payload)

        topic.name = payload["name"]
        topic.normalized_name = payload["normalized_name"]
        topic.description = payload["description"]
        topic.keywords_json = json.dumps(payload["keywords"])
        topic.source_chunk_ids_json = json.dumps(payload["source_chunk_ids"])
        topic.prerequisites_json = json.dumps(payload["prerequisites"])
        topic.importance = payload["importance"]
        topic.difficulty = payload["difficulty"]
        if topic.status != "hidden":
            topic.status = quality["status"]
            topic.quality_score = quality["quality_score"]
            topic.review_note = quality["review_note"]

        for source_chunk_id in payload["source_chunk_ids"]:
            db.add(
                TopicSource(
                    user_id=topic.user_id,
                    course_id=topic.course_id,
                    topic_id=topic.id,
                    document_id=_document_id_for_source_chunk(rows, source_chunk_id),
                    source_chunk_id=source_chunk_id,
                )
            )


def _aggregate_document_topic_rows(rows: list[DocumentTopic]) -> dict:
    keywords: list[str] = []
    source_chunk_ids: list[str] = []
    prerequisites: list[str] = []
    best_name = rows[0].name
    best_description = rows[0].description
    importance = 1
    difficulty = 1
    normalized_name = rows[0].normalized_name

    for row in rows:
        row_keywords = json.loads(row.keywords_json or "[]")
        row_source_chunk_ids = json.loads(row.source_chunk_ids_json or "[]")
        row_prerequisites = json.loads(row.prerequisites_json or "[]")
        keywords.extend(row_keywords)
        source_chunk_ids.extend(row_source_chunk_ids)
        prerequisites.extend(row_prerequisites)
        importance = max(importance, row.importance)
        difficulty = max(difficulty, row.difficulty)
        if len(row.name) > len(best_name):
            best_name = row.name
        if len(row.description) > len(best_description):
            best_description = row.description

    return {
        "name": best_name,
        "normalized_name": normalized_name,
        "description": best_description,
        "keywords": _unique_preserve_order(keywords)[:6],
        "source_chunk_ids": _unique_preserve_order(source_chunk_ids),
        "prerequisites": _unique_preserve_order(prerequisites)[:4],
        "importance": max(1, min(5, importance)),
        "difficulty": max(1, min(5, difficulty)),
    }


def _document_id_for_source_chunk(rows: list[DocumentTopic], source_chunk_id: str) -> int:
    for row in rows:
        if source_chunk_id in json.loads(row.source_chunk_ids_json or "[]"):
            return row.document_id
    return rows[0].document_id


def _extract_topics_from_candidates(candidates: list[dict]) -> list[dict]:
    topics_by_name: dict[str, dict] = {}
    for candidate in candidates:
        normalized_name = normalize_topic_name(candidate["name"])
        if not normalized_name:
            continue
        entry = topics_by_name.setdefault(
            normalized_name,
            {
                "name": candidate["name"],
                "normalized_name": normalized_name,
                "description": _sanitize_description(candidate["summary_text"]),
                "keywords": [],
                "importance": candidate["importance"],
                "difficulty": candidate["difficulty"],
                "source_chunk_ids": [],
                "prerequisites": [],
            },
        )
        entry["keywords"].extend(candidate["keywords"])
        entry["source_chunk_ids"].extend(candidate["source_chunk_ids"])
        entry["prerequisites"].extend(candidate["prerequisites"])
        entry["importance"] = max(entry["importance"], candidate["importance"])
        entry["difficulty"] = max(entry["difficulty"], candidate["difficulty"])
        if len(candidate["summary_text"]) > len(entry["description"]):
            entry["description"] = _sanitize_description(candidate["summary_text"])
    return _normalize_topics_payload(list(topics_by_name.values()))


def _plan_document_topic_operations_with_llm(*, course: Course, existing_topics: list[dict], candidates: list[dict]) -> list[dict]:
    prompt = _build_document_topic_operation_prompt(course=course, existing_topics=existing_topics, candidates=candidates)
    response = run_chat_completion(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are curating durable study topics for one university course. "
                    "You must return JSON only. "
                    "For every candidate, choose exactly one action: discard, merge_into_existing, or create_topic. "
                    "Discard noisy labels, question fragments, names, option letters, numeric traces, and metadata. "
                    "Reuse an existing topic when possible instead of creating near-duplicates."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=1300,
    )
    payload = _parse_json_object(response)
    operations = payload.get("operations")
    if not isinstance(operations, list):
        raise ChatProviderError("Topic extractor did not return operations")
    return operations


def _apply_document_topic_operations(*, candidates: list[dict], existing_topics: list[dict], operations: list[dict]) -> list[dict]:
    candidate_lookup = {candidate["candidate_id"]: candidate for candidate in candidates}
    existing_by_key = {topic["normalized_name"]: topic for topic in existing_topics}
    results: list[dict] = []
    seen_candidates: set[str] = set()

    for operation in operations:
        action = str(operation.get("action", "")).strip().lower()
        candidate_id = str(operation.get("candidate_id", "")).strip()
        candidate = candidate_lookup.get(candidate_id)
        if candidate is None or candidate_id in seen_candidates:
            continue
        seen_candidates.add(candidate_id)

        if action == "discard":
            continue

        if action == "merge_into_existing":
            topic_key = normalize_topic_name(str(operation.get("topic_key", "")).strip())
            target = existing_by_key.get(topic_key)
            if target is None:
                continue
            results.append(
                {
                    "topic_key": target["normalized_name"],
                    "name": target["name"],
                    "normalized_name": target["normalized_name"],
                    "description": target["description"] or _sanitize_description(candidate["summary_text"]),
                    "keywords": _unique_preserve_order(target["keywords"] + candidate["keywords"])[:6],
                    "importance": max(target["importance"], candidate["importance"]),
                    "difficulty": max(target["difficulty"], candidate["difficulty"]),
                    "source_chunk_ids": candidate["source_chunk_ids"],
                    "prerequisites": _unique_preserve_order(target["prerequisites"] + candidate["prerequisites"])[:4],
                }
            )
            continue

        if action == "create_topic":
            name = " ".join(str(operation.get("name", candidate["name"])).split()).strip()
            normalized_name = normalize_topic_name(name)
            if not normalized_name:
                continue
            results.append(
                {
                    "topic_key": normalized_name,
                    "name": name,
                    "normalized_name": normalized_name,
                    "description": _sanitize_description(str(operation.get("description", candidate["summary_text"])).strip()),
                    "keywords": _unique_preserve_order(
                        [str(item).strip() for item in operation.get("keywords", candidate["keywords"]) if str(item).strip()]
                    )[:6],
                    "importance": _clamp_score(operation.get("importance"), default=candidate["importance"]),
                    "difficulty": _clamp_score(operation.get("difficulty"), default=candidate["difficulty"]),
                    "source_chunk_ids": candidate["source_chunk_ids"],
                    "prerequisites": _unique_preserve_order(
                        [str(item).strip() for item in operation.get("prerequisites", candidate["prerequisites"]) if str(item).strip()]
                    )[:4],
                }
            )

    if not results:
        return _extract_topics_from_candidates(candidates)
    return results


def _build_document_topic_operation_prompt(*, course: Course, existing_topics: list[dict], candidates: list[dict]) -> str:
    compact_existing_topics = [
        {
            "topic_key": topic["normalized_name"],
            "name": topic["name"],
            "description": topic["description"],
            "keywords": topic["keywords"][:5],
            "status": topic["status"],
        }
        for topic in existing_topics
    ]
    return json.dumps(
        {
            "task": "Classify each candidate into discard, merge_into_existing, or create_topic.",
            "course_context": {"name": course.name, "term": course.term, "description": course.description},
            "rules": [
                "A valid topic is a study-worthy concept, not a name, option label, answer fragment, score row, or document header.",
                "Discard candidate names like A, B, C, D, names, dates, IDs, and short metadata labels.",
                "Create a new topic only when the candidate is a durable concept not already covered by existing topics.",
                "If in doubt between discard and create_topic for a noisy candidate, discard it.",
            ],
            "output_schema": {
                "operations": [
                    {
                        "candidate_id": "candidate id",
                        "action": "discard | merge_into_existing | create_topic",
                        "topic_key": "required when merging into an existing topic",
                        "name": "required when creating a topic",
                        "description": "required when creating a topic",
                        "keywords": ["optional keyword list when creating"],
                        "importance": "optional integer 1-5 when creating",
                        "difficulty": "optional integer 1-5 when creating",
                        "prerequisites": ["optional prerequisite list when creating"],
                        "reason": "short explanation",
                    }
                ]
            },
            "existing_topics": compact_existing_topics,
            "candidates": candidates,
        },
        ensure_ascii=False,
        indent=2,
    )


def _plan_course_topic_curation_with_llm(*, course: Course, topics: list[Topic]) -> list[dict]:
    topic_payload = [
        {
            "topic_id": topic.id,
            "name": topic.name,
            "description": topic.description,
            "keywords": json.loads(topic.keywords_json or "[]"),
            "importance": topic.importance,
            "difficulty": topic.difficulty,
            "status": topic.status,
            "quality_score": topic.quality_score,
            "review_note": topic.review_note,
            "source_chunk_ids": json.loads(topic.source_chunk_ids_json or "[]"),
            "prerequisites": json.loads(topic.prerequisites_json or "[]"),
        }
        for topic in topics
        if json.loads(topic.source_chunk_ids_json or "[]")
    ]
    prompt = json.dumps(
        {
            "task": "Clean up the current course topic catalog. Remove noisy topics, merge duplicates, and rename vague topics.",
            "course_context": {"name": course.name, "term": course.term, "description": course.description},
            "rules": [
                "Hide topics that are names, option letters, document metadata, or other non-study concepts.",
                "Mark low-confidence but possibly useful topics as suspect.",
                "Merge duplicates into one stronger topic when they represent the same concept.",
                "Rename vague but valid topics into clearer concept names when the evidence supports it.",
            ],
            "output_schema": {
                "operations": [
                    {
                        "type": "keep_topic | rename_topic | merge_topics | hide_topic | mark_topic_suspect | update_topic_metadata",
                        "topic_id": "topic id",
                        "target_topic_id": "required for merge_topics",
                        "new_name": "required for rename_topic",
                        "description": "optional",
                        "keywords": ["optional"],
                        "importance": "optional 1-5",
                        "difficulty": "optional 1-5",
                        "review_note": "short reason",
                    }
                ]
            },
            "topics": topic_payload,
        },
        ensure_ascii=False,
        indent=2,
    )
    response = run_chat_completion(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are reviewing a course topic catalog for quality. "
                    "Return JSON only. "
                    "Do not keep topics that are names, letters, quiz labels, or metadata. "
                    "Use merge_topics for duplicates and hide_topic for clear garbage."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=1200,
    )
    payload = _parse_json_object(response)
    operations = payload.get("operations")
    if not isinstance(operations, list):
        raise ChatProviderError("Topic curator did not return operations")
    return operations


def _build_rule_curation_operations(topics: list[Topic]) -> list[dict]:
    operations: list[dict] = []
    by_name: dict[str, Topic] = {}
    for topic in topics:
        payload = serialize_topic(topic)
        quality = _assess_topic_quality(payload)
        if quality["status"] == "suspect":
            operations.append(
                {
                    "type": "mark_topic_suspect",
                    "topic_id": topic.id,
                    "review_note": quality["review_note"],
                }
            )
        if _looks_like_extreme_noise(topic.normalized_name):
            operations.append(
                {
                    "type": "hide_topic",
                    "topic_id": topic.id,
                    "review_note": "Hidden automatically because the topic looks like a label or metadata.",
                }
            )
        existing = by_name.get(topic.normalized_name)
        if existing is not None and existing.id != topic.id:
            operations.append(
                {
                    "type": "merge_topics",
                    "topic_id": topic.id,
                    "target_topic_id": existing.id,
                    "review_note": "Merged duplicate normalized topic name.",
                }
            )
        else:
            by_name[topic.normalized_name] = topic
    return operations


def _apply_course_topic_operations(db: Session, *, course: Course, operations: list[dict]) -> int:
    topics = {
        topic.id: topic
        for topic in db.query(Topic).filter(Topic.user_id == course.user_id, Topic.course_id == course.id).all()
    }
    touched_topic_ids: set[int] = set()
    updated_count = 0

    for operation in operations:
        op_type = str(operation.get("type", "")).strip().lower()
        topic_id = _safe_int(operation.get("topic_id"))
        if topic_id is None or topic_id not in topics:
            continue
        topic = topics[topic_id]

        if op_type == "rename_topic":
            new_name = " ".join(str(operation.get("new_name", "")).split()).strip()
            if not new_name:
                continue
            topic.name = new_name
            topic.normalized_name = normalize_topic_name(new_name)
            topic.review_note = str(operation.get("review_note", topic.review_note)).strip() or topic.review_note
            touched_topic_ids.add(topic.id)
            updated_count += 1
            continue

        if op_type == "update_topic_metadata":
            if operation.get("description"):
                topic.description = _sanitize_description(str(operation["description"]))
            if isinstance(operation.get("keywords"), list):
                topic.keywords_json = json.dumps(_unique_preserve_order([str(item).strip() for item in operation["keywords"] if str(item).strip()])[:6])
            if operation.get("importance") is not None:
                topic.importance = _clamp_score(operation.get("importance"), default=topic.importance)
            if operation.get("difficulty") is not None:
                topic.difficulty = _clamp_score(operation.get("difficulty"), default=topic.difficulty)
            if operation.get("review_note"):
                topic.review_note = str(operation["review_note"]).strip()
            touched_topic_ids.add(topic.id)
            updated_count += 1
            continue

        if op_type == "hide_topic":
            topic.status = "hidden"
            topic.quality_score = 1
            topic.review_note = str(operation.get("review_note", "Hidden during topic curation.")).strip()
            updated_count += 1
            continue

        if op_type == "mark_topic_suspect":
            if topic.status != "hidden":
                topic.status = "suspect"
                topic.quality_score = min(topic.quality_score, 2)
                topic.review_note = str(operation.get("review_note", "Marked suspect during topic curation.")).strip()
                updated_count += 1
            continue

        if op_type == "merge_topics":
            target_topic_id = _safe_int(operation.get("target_topic_id"))
            if target_topic_id is None or target_topic_id not in topics or target_topic_id == topic.id:
                continue
            target_topic = topics[target_topic_id]
            db.query(DocumentTopic).filter(DocumentTopic.topic_id == topic.id).update({DocumentTopic.topic_id: target_topic.id}, synchronize_session=False)
            topic.status = "hidden"
            topic.quality_score = 1
            topic.review_note = str(operation.get("review_note", f"Merged into topic {target_topic.id}.")).strip()
            touched_topic_ids.update({topic.id, target_topic.id})
            updated_count += 1
            continue

    db.flush()
    _refresh_topics_from_documents(db, topic_ids=touched_topic_ids)
    db.commit()
    return updated_count


def _choose_topic_name(parent: ParentChunk) -> str:
    section_title = " ".join((parent.section_title or "").split())
    normalized_title = normalize_topic_name(section_title)
    if normalized_title and normalized_title not in GENERIC_SECTION_TITLES:
        return section_title
    first_line = parent.text.splitlines()[0] if parent.text else ""
    words = first_line.strip().split()
    candidate = " ".join(words[:6]).strip(" .:-")
    return candidate.title() if candidate else ""


def _build_candidate_summary(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.splitlines()]
    cleaned_lines = [line for line in lines if line]
    preferred_lines: list[str] = []
    for line in cleaned_lines:
        lowered = line.lower()
        if _is_question_like(line):
            continue
        if _looks_like_numeric_example(lowered):
            continue
        if len(line) < 18:
            continue
        preferred_lines.append(line)
        if len(preferred_lines) >= 2:
            break
    if preferred_lines:
        return " ".join(preferred_lines)[:260]
    return (_build_description(text) or " ".join(text.split())[:260]).strip()


def _build_description(text: str) -> str:
    cleaned = " ".join(text.split())
    if not cleaned:
        return ""
    sentence = re.split(r"(?<=[.!?])\s+", cleaned, maxsplit=1)[0]
    sentence = sentence[:220].strip()
    if len(cleaned) > len(sentence) and not sentence.endswith("."):
        sentence += "."
    return sentence


def _extract_keywords(text: str, section_title: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", f"{section_title} {text}".lower())
    counts = Counter(token for token in tokens if token not in STOPWORDS and len(token) > 2)
    return [token.replace("-", " ") for token, _ in counts.most_common(8)]


def _score_importance(parent: ParentChunk, children: list[ChildChunk]) -> int:
    score = 2
    if parent.section_title:
        score += 1
    score += min(2, max(0, len(children) - 1))
    return max(1, min(5, score))


def _score_difficulty(text: str, keywords: list[str]) -> int:
    lowered = text.lower()
    score = 2
    if any(term in lowered for term in {"proof", "optimization", "asymptotic", "derivative", "concurrency"}):
        score += 2
    elif any(term in lowered for term in {"algorithm", "analysis", "dynamic", "recursion"}):
        score += 1
    if len(keywords) >= 5:
        score += 1
    return max(1, min(5, score))


def _infer_prerequisites(keywords: list[str], topic_name: str) -> list[str]:
    lowered = f"{topic_name.lower()} {' '.join(keywords)}"
    prerequisites: list[str] = []
    if "dynamic programming" in lowered:
        prerequisites.extend(["Recursion", "Time Complexity"])
    if "graph" in lowered:
        prerequisites.extend(["Basic Data Structures"])
    if "concurrency" in lowered or "thread" in lowered:
        prerequisites.extend(["Processes", "Synchronization"])
    return _unique_preserve_order(prerequisites)


def _assess_topic_quality(topic: dict) -> dict:
    name = " ".join(str(topic.get("name", "")).split()).strip()
    normalized_name = normalize_topic_name(name)
    keywords = [str(item).strip().lower() for item in topic.get("keywords", []) if str(item).strip()]

    if _looks_like_extreme_noise(normalized_name):
        return {"status": "suspect", "quality_score": 1, "review_note": "Topic looks like a label, option, metadata field, or non-concept text."}
    if len(normalized_name.split()) == 1 and len(keywords) <= 1:
        return {"status": "suspect", "quality_score": 2, "review_note": "Topic is very short and may not be a durable study concept."}
    return {"status": "active", "quality_score": 4, "review_note": DEFAULT_REVIEW_NOTE}


def _candidate_noise_reason(candidate: dict) -> str:
    name = " ".join(str(candidate.get("name", "")).split()).strip()
    normalized_name = normalize_topic_name(name)
    summary = " ".join(str(candidate.get("summary_text", "")).split()).strip()
    keywords = [str(item).strip().lower() for item in candidate.get("keywords", []) if str(item).strip()]

    if not summary:
        return "missing_summary"
    if _is_question_like(name) or _is_question_like(summary):
        return "question_like"
    if any(pattern.fullmatch(normalized_name) for pattern in NOISE_LABEL_PATTERNS):
        return "label_like"
    if normalized_name in GENERIC_SECTION_TITLES and not keywords:
        return "generic_title"
    if _looks_like_numeric_example(summary.lower()):
        return "numeric_trace"
    if len(summary) < 24:
        return "too_short"
    if _looks_like_extreme_noise(normalized_name):
        return "noise_name"
    return ""


def _looks_like_extreme_noise(normalized_name: str) -> bool:
    if not normalized_name:
        return True
    if _is_weak_or_noisy_label(normalized_name):
        return True
    if normalized_name in LIKELY_METADATA_TERMS:
        return True
    if len(normalized_name) <= 2:
        return True
    if re.fullmatch(r"[a-z](\s+[a-z]){0,3}", normalized_name):
        return True
    if re.search(r"\d", normalized_name) and len(re.findall(r"[a-z]+", normalized_name)) <= 1:
        return True
    return False


def _unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(value.strip())
    return result


def _normalize_topics_payload(topics: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for index, topic in enumerate(topics, start=1):
        name = " ".join(str(topic.get("name", "")).strip().split())
        normalized_name = normalize_topic_name(str(topic.get("topic_key", name)).strip()) or normalize_topic_name(name)
        source_chunk_ids = _unique_preserve_order([str(item).strip() for item in topic.get("source_chunk_ids", []) if str(item).strip()])
        if not normalized_name or not source_chunk_ids:
            continue
        keywords = _unique_preserve_order([str(item).strip() for item in topic.get("keywords", []) if str(item).strip()])[:6]
        prerequisites = _unique_preserve_order([str(item).strip() for item in topic.get("prerequisites", []) if str(item).strip()])[:4]
        normalized.append(
            {
                "topic_key": str(topic.get("topic_key", f"topic-{index}")).strip() or f"topic-{index}",
                "name": name,
                "normalized_name": normalized_name,
                "description": _sanitize_description(str(topic.get("description", "")).strip()),
                "keywords": keywords or [word for word in normalized_name.split()[:3]],
                "importance": _clamp_score(topic.get("importance"), default=3),
                "difficulty": _clamp_score(topic.get("difficulty"), default=3),
                "source_chunk_ids": source_chunk_ids,
                "prerequisites": prerequisites,
            }
        )
    filtered = [topic for topic in normalized if _should_keep_topic(topic)]
    return _merge_topic_lists([], filtered)[:12]


def _merge_topic_lists(existing_topics: list[dict], new_topics: list[dict]) -> list[dict]:
    topics_by_name: dict[str, dict] = {topic["normalized_name"]: {**topic} for topic in existing_topics}
    for topic in new_topics:
        normalized_name = topic["normalized_name"]
        current = topics_by_name.get(normalized_name)
        if current is None:
            topics_by_name[normalized_name] = {**topic}
            continue
        current["keywords"] = _unique_preserve_order(current["keywords"] + topic["keywords"])[:6]
        current["source_chunk_ids"] = _unique_preserve_order(current["source_chunk_ids"] + topic["source_chunk_ids"])
        current["prerequisites"] = _unique_preserve_order(current["prerequisites"] + topic["prerequisites"])
        current["importance"] = max(current["importance"], topic["importance"])
        current["difficulty"] = max(current["difficulty"], topic["difficulty"])
        if len(topic["description"]) > len(current["description"]):
            current["description"] = topic["description"]
    return sorted(topics_by_name.values(), key=lambda item: (-item["importance"], -item["difficulty"], item["name"]))


def _should_keep_topic(topic: dict) -> bool:
    name = " ".join(str(topic.get("name", "")).split()).strip()
    normalized_name = normalize_topic_name(name)
    description = " ".join(str(topic.get("description", "")).split()).strip().lower()
    keywords = [str(item).strip().lower() for item in topic.get("keywords", []) if str(item).strip()]

    if not normalized_name:
        return False
    if _is_question_like(name) or _is_question_like(description):
        return False
    if _looks_like_extreme_noise(normalized_name):
        return False
    if _looks_like_numeric_example(description):
        return False
    if not topic.get("source_chunk_ids"):
        return False
    if not keywords and len(normalized_name.split()) == 1:
        return False
    return True


def _is_question_like(value: str) -> bool:
    cleaned = " ".join((value or "").split()).strip().lower()
    if not cleaned:
        return False
    if "?" in cleaned:
        return True
    first_word = cleaned.split()[0]
    return first_word in QUESTION_PREFIXES


def _is_weak_or_noisy_label(normalized_title: str) -> bool:
    if not normalized_title:
        return False
    if normalized_title in WEAK_TOPIC_TITLES:
        return True
    if normalized_title.endswith("s") and normalized_title[:-1] in WEAK_TOPIC_TITLES:
        return True
    if len(normalized_title.split()) == 1 and len(normalized_title) <= 4 and normalized_title.isalpha():
        return True
    return False


def _looks_like_numeric_example(value: str) -> bool:
    digits = len(re.findall(r"\d", value or ""))
    letters = len(re.findall(r"[a-zA-Z]", value or ""))
    return digits >= 2 and digits >= letters


def _sanitize_description(value: str) -> str:
    cleaned = " ".join(value.split())
    return cleaned[:260]


def _clamp_score(value, *, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(1, min(5, number))


def _safe_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_json_object(raw: str) -> dict:
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ChatProviderError("Topic extractor did not return JSON")
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ChatProviderError("Topic extractor returned invalid JSON") from exc


def _should_use_llm_for_topics() -> bool:
    mode = TOPIC_EXTRACTION_MODE.lower()
    if mode == "rule":
        return False
    if mode == "llm":
        return bool(CHAT_API_KEY)
    return bool(CHAT_API_KEY)
