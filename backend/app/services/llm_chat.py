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
        "You are a study assistant answering questions about one course. "
        "Use the retrieved course sources as the primary basis for your answer. "
        "You may synthesize, rephrase, and connect ideas across the sources when that helps clarity. "
        "If the sources fully support the answer, stay grounded in them and cite source-supported claims with source numbers like [1] or [2]. "
        "If the sources are incomplete or do not directly answer the question, you may add clearly labeled general background knowledge that is consistent with the sources and useful for study. "
        "Do not present general background knowledge as if it came from the course sources. "
        "When you add non-source background, explicitly signal it with wording like 'More generally' or 'As background'. "
        "Do not invent specific course policies, requirements, definitions, dates, formulas, or code details unless they are supported by the retrieved material. "
        "When there is uncertainty, say what is supported by the course materials and what is a broader explanatory inference. "
        "Keep the answer concise, useful, and study-oriented."
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
            (
                "Answer using the sources as your main evidence. "
                "If the sources are enough, answer directly and cite them. "
                "If they are incomplete, first explain what the course materials support, then optionally add a short, clearly labeled general background explanation. "
                "Only cite claims that are actually supported by the provided sources."
            ),
        ]
    )

    data = _post_chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=CHAT_MAX_OUTPUT_TOKENS,
    )
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise ChatProviderError("Chat provider returned an unexpected response shape") from exc


def run_chat_completion(*, messages: list[dict], temperature: float = 0.2, max_tokens: int | None = None) -> str:
    if not should_use_llm():
        raise ChatProviderError("LLM chat provider is not configured")
    data = _post_chat_completion(
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens or CHAT_MAX_OUTPUT_TOKENS,
    )
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise ChatProviderError("Chat provider returned an unexpected response shape") from exc


def _post_chat_completion(*, messages: list[dict], temperature: float, max_tokens: int) -> dict:
    payload = {
        "model": CHAT_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
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
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise ChatProviderError(detail or f"Chat provider HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise ChatProviderError(str(exc.reason)) from exc
