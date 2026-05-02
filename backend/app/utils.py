from pathlib import Path


def normalize_name(value: str) -> str:
    return " ".join((value or "").strip().split())


def normalize_material_type(value: str | None) -> str:
    normalized = (value or "").strip().lower().replace(" ", "_")
    return normalized or "other"


def secure_filename(value: str) -> str:
    name = Path(value or "").name.strip()
    return name or "upload"
