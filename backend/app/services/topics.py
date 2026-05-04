import json
import re
from collections import Counter, defaultdict

from sqlalchemy.orm import Session

from backend.app.config import CHAT_API_KEY, TOPIC_EXTRACTION_MODE
from backend.app.models import ChildChunk, Course, Document, ParentChunk, Topic
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


def list_course_topics(db: Session, *, user_id: int, course_id: int) -> list[Topic]:
    return (
        db.query(Topic)
        .filter(Topic.user_id == user_id, Topic.course_id == course_id)
        .order_by(Topic.importance.desc(), Topic.difficulty.desc(), Topic.name.asc())
        .all()
    )


def get_course_topic(db: Session, *, user_id: int, course_id: int, topic_id: int) -> Topic | None:
    return (
        db.query(Topic)
        .filter(Topic.id == topic_id, Topic.user_id == user_id, Topic.course_id == course_id)
        .first()
    )


def refresh_course_topics(db: Session, *, course: Course) -> list[Topic]:
    parents = (
        db.query(ParentChunk)
        .filter(ParentChunk.user_id == course.user_id, ParentChunk.course_id == course.id)
        .order_by(ParentChunk.document_id.asc(), ParentChunk.chunk_index.asc())
        .all()
    )
    children = (
        db.query(ChildChunk)
        .filter(ChildChunk.user_id == course.user_id, ChildChunk.course_id == course.id)
        .order_by(ChildChunk.document_id.asc(), ChildChunk.chunk_index.asc())
        .all()
    )
    documents = (
        db.query(Document)
        .filter(Document.user_id == course.user_id, Document.course_id == course.id)
        .all()
    )
    topics_payload = _extract_topics_with_llm(documents=documents, parents=parents, children=children)

    db.query(Topic).filter(Topic.user_id == course.user_id, Topic.course_id == course.id).delete()
    db.commit()

    records: list[Topic] = []
    for item in topics_payload:
        record = Topic(
            user_id=course.user_id,
            course_id=course.id,
            name=item["name"],
            normalized_name=item["normalized_name"],
            description=item["description"],
            keywords_json=json.dumps(item["keywords"]),
            importance=item["importance"],
            difficulty=item["difficulty"],
            source_chunk_ids_json=json.dumps(item["source_chunk_ids"]),
            prerequisites_json=json.dumps(item["prerequisites"]),
        )
        db.add(record)
        records.append(record)
    db.commit()

    document_topic_counts: dict[int, int] = defaultdict(int)
    child_by_chunk_id = {chunk.chunk_id: chunk for chunk in children}
    for item in topics_payload:
        related_document_ids = {
            child_by_chunk_id[source_chunk_id].document_id
            for source_chunk_id in item["source_chunk_ids"]
            if source_chunk_id in child_by_chunk_id
        }
        for document_id in related_document_ids:
            document_topic_counts[document_id] += 1

    for document in documents:
        document.topic_count = document_topic_counts.get(document.id, 0)
    db.commit()

    for record in records:
        db.refresh(record)
    return records


def update_topic(
    db: Session,
    *,
    topic: Topic,
    name: str | None = None,
    description: str | None = None,
    keywords: list[str] | None = None,
    importance: int | None = None,
    difficulty: int | None = None,
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
        "source_chunk_ids": json.loads(topic.source_chunk_ids_json or "[]"),
        "prerequisites": json.loads(topic.prerequisites_json or "[]"),
        "created_at": topic.created_at,
        "updated_at": topic.updated_at,
    }


def normalize_topic_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9\s]+", " ", (value or "").strip().lower())
    return " ".join(normalized.split())


def _extract_topics_with_llm(*, documents: list[Document], parents: list[ParentChunk], children: list[ChildChunk]) -> list[dict]:
    if not _should_use_llm_for_topics():
        return _extract_topics(parents=parents, children=children)

    parents_by_document: dict[int, list[ParentChunk]] = defaultdict(list)
    for parent in parents:
        parents_by_document[parent.document_id].append(parent)

    children_by_root: dict[str, list[ChildChunk]] = defaultdict(list)
    for child in children:
        children_by_root[child.root_chunk_id].append(child)

    accumulated_topics: list[dict] = []
    for document in sorted(documents, key=lambda item: item.id):
        document_parents = parents_by_document.get(document.id, [])
        if not document_parents:
            continue
        candidates = []
        for parent in document_parents:
            source_chunk_ids = [child.chunk_id for child in children_by_root.get(parent.root_chunk_id, [])]
            if not source_chunk_ids:
                continue
            candidates.append(
                {
                    "candidate_id": parent.root_chunk_id,
                    "filename": document.filename,
                    "material_type": document.material_type,
                    "section_title": parent.section_title,
                    "summary_text": _build_description(parent.text) or " ".join(parent.text.split())[:260],
                    "keywords": _extract_keywords(parent.text, parent.section_title)[:6],
                    "source_chunk_ids": source_chunk_ids,
                }
            )
        if not candidates:
            continue

        try:
            merged_topics = _merge_document_topics_with_llm(existing_topics=accumulated_topics, candidates=candidates)
            accumulated_topics = _merge_topic_lists(accumulated_topics, _normalize_topics_payload(merged_topics))
        except ChatProviderError:
            document_topics = _extract_topics(parents=document_parents, children=children)
            accumulated_topics = _merge_topic_lists(accumulated_topics, document_topics)

    return accumulated_topics


def _extract_topics(*, parents: list[ParentChunk], children: list[ChildChunk]) -> list[dict]:
    child_by_root: dict[str, list[ChildChunk]] = defaultdict(list)
    for child in children:
        child_by_root[child.root_chunk_id].append(child)

    topics_by_name: dict[str, dict] = {}
    for parent in parents:
        topic_name = _choose_topic_name(parent)
        if not topic_name:
            continue
        normalized_name = normalize_topic_name(topic_name)
        if not normalized_name:
            continue
        entry = topics_by_name.setdefault(
            normalized_name,
            {
                "name": topic_name,
                "normalized_name": normalized_name,
                "description": "",
                "keywords": [],
                "importance": 3,
                "difficulty": 3,
                "source_chunk_ids": [],
                "prerequisites": [],
                "supporting_texts": [],
            },
        )
        related_children = child_by_root.get(parent.root_chunk_id, [])
        entry["source_chunk_ids"].extend(child.chunk_id for child in related_children)
        entry["supporting_texts"].append(parent.text)
        entry["keywords"].extend(_extract_keywords(parent.text, parent.section_title))
        if not entry["description"]:
            entry["description"] = _build_description(parent.text)
        entry["importance"] = max(entry["importance"], _score_importance(parent, related_children))
        entry["difficulty"] = max(entry["difficulty"], _score_difficulty(parent.text, entry["keywords"]))

    merged_topics: list[dict] = []
    for entry in topics_by_name.values():
        entry["keywords"] = _unique_preserve_order(entry["keywords"])[:6]
        entry["source_chunk_ids"] = _unique_preserve_order(entry["source_chunk_ids"])
        entry["prerequisites"] = _infer_prerequisites(entry["keywords"], entry["name"])
        entry.pop("supporting_texts", None)
        if entry["source_chunk_ids"]:
            merged_topics.append(entry)
    return sorted(merged_topics, key=lambda item: (-item["importance"], -item["difficulty"], item["name"]))


def _merge_document_topics_with_llm(*, existing_topics: list[dict], candidates: list[dict]) -> list[dict]:
    prompt = _build_topic_merge_prompt(existing_topics=existing_topics, candidates=candidates)
    response = run_chat_completion(
        messages=[
            {
                "role": "system",
                "content": (
                    "You maintain a stable course topic catalog. "
                    "Merge new document sections into existing high-level study topics whenever possible. "
                    "Ignore grading criteria, due dates, submission instructions, course codes, and other administrative fragments. "
                    "Prefer broad technical concepts over section headers. "
                    "Return JSON only."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=900,
    )
    payload = _parse_json_object(response)
    topics = payload.get("topics")
    if not isinstance(topics, list):
        raise ChatProviderError("Topic extractor did not return a topics list")
    return topics


def _build_topic_merge_prompt(*, existing_topics: list[dict], candidates: list[dict]) -> str:
    return json.dumps(
        {
            "task": (
                "Update the course topic catalog using the new candidates. "
                "Reuse existing topics whenever a candidate clearly belongs there. "
                "Create a new topic only for a distinct technical concept. "
                "Drop candidates that are purely administrative or too narrow to be a study topic."
            ),
            "output_schema": {
                "topics": [
                    {
                        "topic_key": "stable string key; keep existing keys when reusing a topic",
                        "name": "high-level topic name",
                        "description": "one concise sentence",
                        "keywords": ["3-6 technical terms or short phrases"],
                        "importance": "integer 1-5",
                        "difficulty": "integer 1-5",
                        "source_chunk_ids": ["source chunk ids that belong to this topic"],
                        "prerequisites": ["0-3 prerequisite concepts"],
                    }
                ]
            },
            "existing_topics": existing_topics,
            "new_candidates": candidates,
        },
        ensure_ascii=False,
        indent=2,
    )


def _choose_topic_name(parent: ParentChunk) -> str:
    section_title = " ".join((parent.section_title or "").split())
    normalized_title = normalize_topic_name(section_title)
    if normalized_title and normalized_title not in GENERIC_SECTION_TITLES:
        return section_title
    first_line = parent.text.splitlines()[0] if parent.text else ""
    words = first_line.strip().split()
    candidate = " ".join(words[:6]).strip(" .:-")
    return candidate.title() if candidate else ""


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


def _normalize_topics_payload(topics: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for index, topic in enumerate(topics, start=1):
        name = " ".join(str(topic.get("name", "")).strip().split())
        normalized_name = normalize_topic_name(name)
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
    merged = _merge_topic_lists([], normalized)
    return merged[:12]


def _sanitize_description(value: str) -> str:
    cleaned = " ".join(value.split())
    return cleaned[:260]


def _clamp_score(value, *, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(1, min(5, number))


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
