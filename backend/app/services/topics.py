import json
import re
from collections import Counter, defaultdict

from sqlalchemy.orm import Session

from backend.app.models import ChildChunk, Course, Document, ParentChunk, Topic

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
    topics_payload = _extract_topics(parents=parents, children=children)

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
