import json
import urllib.error
import urllib.request

from backend.app.config import CHAT_API_KEY, CHAT_BASE_URL, CHAT_MAX_OUTPUT_TOKENS, CHAT_MODEL, CHAT_PROVIDER


class ChatProviderError(RuntimeError):
    pass


def should_use_llm() -> bool:
    if CHAT_PROVIDER == "extractive":
        return False
    if CHAT_PROVIDER == "openai_compatible":
        return bool(CHAT_API_KEY)
    if CHAT_PROVIDER == "auto":
        return bool(CHAT_API_KEY)
    return False


def generate_grounded_answer(*, question: str, results: list[dict]) -> str:
    if not should_use_llm():
        raise ChatProviderError("LLM chat provider is not configured")

    system_prompt = (
        "You answer only from the provided course sources. "
        "Give a concise study-oriented explanation. "
        "Cite claims with source numbers like [1] or [2]. "
        "If the sources do not support an answer, say that directly."
    )
    source_lines = []
    for index, item in enumerate(results, start=1):
        source_lines.append(
            f"[{index}] filename={item['filename']} section={item.get('section_title', '')} "
            f"page={item.get('page_number')} text={item['text']}"
        )
    user_prompt = "\n".join(
        [
            f"Question: {question}",
            "",
            "Sources:",
            *source_lines,
            "",
            "Answer using the sources only.",
        ]
    )

    payload = {
        "model": CHAT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": CHAT_MAX_OUTPUT_TOKENS,
    }
    request = urllib.request.Request(
        f"{CHAT_BASE_URL.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {CHAT_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise ChatProviderError(detail or f"Chat provider HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise ChatProviderError(str(exc.reason)) from exc

    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise ChatProviderError("Chat provider returned an unexpected response shape") from exc
