from dataclasses import dataclass

from backend.app.services.document_parser import ParsedSection

PARENT_TARGET_WORDS = 220
CHILD_TARGET_WORDS = 90
CHILD_OVERLAP_WORDS = 20


@dataclass
class ParentChunkPayload:
    chunk_index: int
    page_number: int | None
    section_title: str
    text: str


@dataclass
class ChildChunkPayload:
    parent_index: int
    chunk_index: int
    page_number: int | None
    section_title: str
    text: str


def build_hierarchical_chunks(sections: list[ParsedSection]) -> tuple[list[ParentChunkPayload], list[ChildChunkPayload]]:
    parents: list[ParentChunkPayload] = []

    for section in sections:
        for text in _split_parent_text(section.text):
            parents.append(
                ParentChunkPayload(
                    chunk_index=len(parents),
                    page_number=section.page_number,
                    section_title=section.section_title,
                    text=text,
                )
            )

    children: list[ChildChunkPayload] = []
    for parent in parents:
        for text in _split_child_text(parent.text):
            children.append(
                ChildChunkPayload(
                    parent_index=parent.chunk_index,
                    chunk_index=len(children),
                    page_number=parent.page_number,
                    section_title=parent.section_title,
                    text=text,
                )
            )

    return parents, children


def _split_parent_text(text: str) -> list[str]:
    paragraphs = [part.strip() for part in text.split("\n") if part.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    buffer: list[str] = []
    buffer_words = 0

    for paragraph in paragraphs:
        paragraph_words = len(paragraph.split())
        if buffer and buffer_words + paragraph_words > PARENT_TARGET_WORDS:
            chunks.append("\n".join(buffer))
            buffer = [paragraph]
            buffer_words = paragraph_words
        else:
            buffer.append(paragraph)
            buffer_words += paragraph_words

    if buffer:
        chunks.append("\n".join(buffer))
    return chunks


def _split_child_text(text: str) -> list[str]:
    words = text.split()
    if not words:
        return []
    if len(words) <= CHILD_TARGET_WORDS:
        return [" ".join(words)]

    chunks: list[str] = []
    step = max(1, CHILD_TARGET_WORDS - CHILD_OVERLAP_WORDS)
    for start in range(0, len(words), step):
        slice_words = words[start : start + CHILD_TARGET_WORDS]
        if not slice_words:
            break
        chunks.append(" ".join(slice_words))
        if start + CHILD_TARGET_WORDS >= len(words):
            break
    return chunks
