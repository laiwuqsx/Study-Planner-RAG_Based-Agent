import argparse
import json
import os
import pathlib
import re
import ssl
import sys
import urllib.error
import urllib.request
from collections.abc import Iterable

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - optional convenience import
    load_dotenv = None


if load_dotenv is not None:
    load_dotenv()
else:
    for candidate in (pathlib.Path(".env"), pathlib.Path("frontend/.env")):
        if not candidate.exists():
            continue
        for raw_line in candidate.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

DEFAULT_BASE_URL = os.getenv("EVAL_BASE_URL", "http://127.0.0.1:8000")
INSECURE_CHAT_SSL = os.getenv("EVAL_INSECURE_CHAT_SSL", "0").strip() in {"1", "true", "TRUE", "yes", "YES"}


def parse_common_args(description: str, *, include_benchmark: bool = True) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Backend base URL. Defaults to %(default)s.")
    parser.add_argument("--username", help="Existing application username.")
    parser.add_argument("--password", help="Existing application password.")
    parser.add_argument("--token", help="Existing bearer token. If provided, username/password are not required.")
    if include_benchmark:
        parser.add_argument("--benchmark", type=pathlib.Path, help="Path to a benchmark JSON file.")
    parser.add_argument("--output", type=pathlib.Path, help="Optional path to write JSON results.")
    return parser


def request_json(
    *,
    base_url: str,
    path: str,
    method: str = "GET",
    payload: dict | None = None,
    token: str | None = None,
    timeout: int = 60,
) -> dict:
    headers: dict[str, str] = {}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(detail or f"HTTP {exc.code} for {path}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Request failed for {path}: {exc.reason}") from exc


def login(*, base_url: str, username: str, password: str) -> str:
    payload = request_json(
        base_url=base_url,
        path="/auth/login",
        method="POST",
        payload={"username": username, "password": password},
        timeout=30,
    )
    token = str(payload.get("access_token", "")).strip()
    if not token:
        raise RuntimeError("Login succeeded but access_token is missing.")
    return token


def resolve_token(*, base_url: str, token: str | None, username: str | None, password: str | None) -> str:
    if token:
        return token
    if not username or not password:
        raise SystemExit("Provide either --token or both --username and --password.")
    return login(base_url=base_url, username=username, password=password)


def load_benchmark(path: pathlib.Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Benchmark file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Benchmark file is not valid JSON: {path}: {exc}") from exc


def write_output(path: pathlib.Path | None, payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    print(text)


def safe_int_set(values: Iterable[object]) -> set[int]:
    result: set[int] = set()
    for value in values:
        try:
            result.add(int(value))
        except (TypeError, ValueError):
            continue
    return result


def safe_str_set(values: Iterable[object]) -> set[str]:
    return {str(value).strip() for value in values if str(value).strip()}


def normalize_text(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def contains_phrase(text: str, phrase: str) -> bool:
    normalized_text = normalize_text(text)
    normalized_phrase = normalize_text(phrase)
    return bool(normalized_phrase) and normalized_phrase in normalized_text


def coverage_score(text: str, phrases: list[str]) -> float:
    if not phrases:
        return 0.0
    hits = sum(1 for phrase in phrases if contains_phrase(text, phrase))
    return hits / len(phrases)


def require_chat_provider() -> tuple[str, str, str]:
    base_url = os.getenv("CHAT_BASE_URL", "").strip()
    model = os.getenv("CHAT_MODEL", "").strip()
    api_key = os.getenv("CHAT_API_KEY", "").strip()
    if not base_url or not model or not api_key:
        raise SystemExit(
            "CHAT_BASE_URL, CHAT_MODEL, and CHAT_API_KEY must be set in the environment or .env for LLM benchmarking."
        )
    return base_url, model, api_key


def call_chat_completion(*, messages: list[dict], temperature: float = 0.2, max_tokens: int = 900) -> str:
    base_url, model, api_key = require_chat_provider()
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        context = None
        if INSECURE_CHAT_SSL:
            context = ssl._create_unverified_context()
        with urllib.request.urlopen(request, timeout=90, context=context) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(detail or f"Chat provider HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Chat provider request failed: {exc.reason}") from exc

    try:
        return str(data["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Chat provider returned an unexpected response shape.") from exc


def abort(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)
