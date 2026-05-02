from dataclasses import dataclass
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from pypdf import PdfReader


WORD_NAMESPACE = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


@dataclass
class ParsedSection:
    text: str
    page_number: int | None
    section_title: str


def parse_document(file_path: str, file_type: str) -> list[ParsedSection]:
    suffix = file_type.lower()
    if suffix == "pdf":
        return parse_pdf(file_path)
    if suffix == "docx":
        return parse_docx(file_path)
    raise ValueError(f"Unsupported document type: {file_type}")


def parse_pdf(file_path: str) -> list[ParsedSection]:
    reader = PdfReader(file_path)
    sections: list[ParsedSection] = []
    current_title = ""

    for page_index, page in enumerate(reader.pages, start=1):
        raw_text = page.extract_text() or ""
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        if not lines:
            continue

        buffer: list[str] = []
        for line in lines:
            if _looks_like_heading(line):
                if buffer:
                    sections.append(ParsedSection(text="\n".join(buffer), page_number=page_index, section_title=current_title))
                    buffer = []
                current_title = line
                continue
            buffer.append(line)

        if buffer:
            sections.append(ParsedSection(text="\n".join(buffer), page_number=page_index, section_title=current_title))

    return sections


def parse_docx(file_path: str) -> list[ParsedSection]:
    styles = _load_docx_styles(file_path)
    document_xml = _read_docx_xml(file_path, "word/document.xml")
    body = document_xml.find("w:body", WORD_NAMESPACE)
    if body is None:
        return []

    sections: list[ParsedSection] = []
    current_title = ""
    buffer: list[str] = []

    for paragraph in body.findall("w:p", WORD_NAMESPACE):
        text = _paragraph_text(paragraph).strip()
        if not text:
            continue

        style_id = _paragraph_style_id(paragraph)
        style_name = styles.get(style_id, style_id or "")
        if _is_heading_style(style_name):
            if buffer:
                sections.append(ParsedSection(text="\n".join(buffer), page_number=None, section_title=current_title))
                buffer = []
            current_title = text
            continue
        buffer.append(text)

    if buffer:
        sections.append(ParsedSection(text="\n".join(buffer), page_number=None, section_title=current_title))
    return sections


def _read_docx_xml(file_path: str, inner_path: str) -> ET.Element:
    with ZipFile(file_path) as archive:
        xml_bytes = archive.read(inner_path)
    return ET.fromstring(xml_bytes)


def _load_docx_styles(file_path: str) -> dict[str, str]:
    try:
        styles_xml = _read_docx_xml(file_path, "word/styles.xml")
    except KeyError:
        return {}

    styles: dict[str, str] = {}
    for style in styles_xml.findall("w:style", WORD_NAMESPACE):
        style_id = style.attrib.get(f"{{{WORD_NAMESPACE['w']}}}styleId", "")
        name_node = style.find("w:name", WORD_NAMESPACE)
        if style_id:
            styles[style_id] = name_node.attrib.get(f"{{{WORD_NAMESPACE['w']}}}val", style_id) if name_node is not None else style_id
    return styles


def _paragraph_text(paragraph: ET.Element) -> str:
    runs = paragraph.findall(".//w:t", WORD_NAMESPACE)
    return "".join(run.text or "" for run in runs)


def _paragraph_style_id(paragraph: ET.Element) -> str:
    style = paragraph.find("w:pPr/w:pStyle", WORD_NAMESPACE)
    if style is None:
        return ""
    return style.attrib.get(f"{{{WORD_NAMESPACE['w']}}}val", "")


def _is_heading_style(style_name: str) -> bool:
    normalized = (style_name or "").lower()
    return normalized.startswith("heading")


def _looks_like_heading(value: str) -> bool:
    words = value.split()
    if not words or len(words) > 12:
        return False
    if value.isupper():
        return True
    titled_words = sum(1 for word in words if word[:1].isupper())
    return titled_words >= max(2, len(words) - 1)
