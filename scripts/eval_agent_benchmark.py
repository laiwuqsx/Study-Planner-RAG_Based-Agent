import json

from eval_common import (
    call_chat_completion,
    contains_phrase,
    coverage_score,
    load_benchmark,
    normalize_text,
    parse_common_args,
    request_json,
    resolve_token,
    write_output,
)


def ask_agent(*, base_url: str, token: str, course_id: int, question: str, retrieval_mode: str, top_k: int) -> dict:
    return request_json(
        base_url=base_url,
        path=f"/courses/{course_id}/chat",
        method="POST",
        token=token,
        payload={
            "message": question,
            "retrieval_mode": retrieval_mode,
            "top_k": top_k,
        },
    )


def ask_plain_llm(*, course_context: dict, question: str) -> str:
    course_name = str(course_context.get("course_name", "")).strip()
    course_term = str(course_context.get("course_term", "")).strip()
    course_description = str(course_context.get("course_description", "")).strip()
    context_lines = []
    if course_name:
        context_lines.append(f"Course name: {course_name}")
    if course_term:
        context_lines.append(f"Course term: {course_term}")
    if course_description:
        context_lines.append(f"Course description: {course_description}")
    user_prompt = "\n".join(
        [
            *context_lines,
            f"Question: {question}",
            "",
            "Answer as a general-purpose study assistant. You do not have access to the course documents.",
        ]
    )
    return call_chat_completion(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful study assistant. "
                    "Answer the user's question as well as you can using general knowledge only. "
                    "Do not claim to have access to course-specific materials."
                ),
            },
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=900,
    )


def heuristic_scores(*, answer: str, sources: list[dict], key_points: list[str]) -> dict:
    key_point_coverage = coverage_score(answer, key_points)
    has_sources = 1.0 if sources else 0.0
    mention_density = 1.0 if len(normalize_text(answer).split()) >= 30 else 0.6
    correctness = max(1, round(1 + 4 * key_point_coverage))
    groundedness = 5 if has_sources else 1
    course_specificity = max(1, round(1 + 4 * min(1.0, 0.6 * key_point_coverage + 0.4 * has_sources)))
    study_usefulness = max(1, round(1 + 4 * min(1.0, 0.7 * key_point_coverage + 0.3 * mention_density)))
    return {
        "correctness": correctness,
        "groundedness": groundedness,
        "course_specificity": course_specificity,
        "study_usefulness": study_usefulness,
    }


def judge_with_llm(*, case: dict, agent_answer: dict, plain_answer: str) -> dict:
    payload = {
        "question": case.get("question", ""),
        "reference_answer": case.get("reference_answer", ""),
        "key_points": case.get("key_points", []),
        "grading_notes": case.get("grading_notes", ""),
        "agent_answer": agent_answer["content"],
        "agent_sources": [
            {
                "filename": source.get("filename"),
                "section_title": source.get("section_title"),
                "chunk_id": source.get("chunk_id"),
                "score": source.get("score"),
            }
            for source in agent_answer.get("sources", [])
        ],
        "plain_llm_answer": plain_answer,
    }
    user_prompt = "\n".join(
        [
            "Evaluate two answers to the same study question.",
            "Return JSON only.",
            "",
            json.dumps(payload, ensure_ascii=False, indent=2),
            "",
            (
                "Score each answer from 1 to 5 on correctness, groundedness, course_specificity, and study_usefulness. "
                "Groundedness means whether the answer is explicitly supported by the provided course material. "
                "Then choose preferred_system as one of: agent, plain_llm, tie. "
                "Return this schema exactly: "
                '{"agent":{"correctness":1,"groundedness":1,"course_specificity":1,"study_usefulness":1},'
                '"plain_llm":{"correctness":1,"groundedness":1,"course_specificity":1,"study_usefulness":1},'
                '"preferred_system":"agent","rationale":"..."}'
            ),
        ]
    )
    raw = call_chat_completion(
        messages=[
            {
                "role": "system",
                "content": "You are a strict evaluator for RAG-based study assistants. Return valid JSON only.",
            },
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
        max_tokens=700,
    )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Judge model did not return valid JSON: {raw}") from exc
    return normalize_judge_scores(data)


def normalize_judge_scores(data: dict) -> dict:
    def clamp(value: object) -> int:
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            return 1
        return max(1, min(5, numeric))

    def normalize_side(side: str) -> dict:
        payload = data.get(side, {}) if isinstance(data, dict) else {}
        return {
            "correctness": clamp(payload.get("correctness", 1)),
            "groundedness": clamp(payload.get("groundedness", 1)),
            "course_specificity": clamp(payload.get("course_specificity", 1)),
            "study_usefulness": clamp(payload.get("study_usefulness", 1)),
        }

    preferred = str(data.get("preferred_system", "tie")).strip() if isinstance(data, dict) else "tie"
    if preferred not in {"agent", "plain_llm", "tie"}:
        preferred = "tie"
    return {
        "agent": normalize_side("agent"),
        "plain_llm": normalize_side("plain_llm"),
        "preferred_system": preferred,
        "rationale": str(data.get("rationale", "")).strip() if isinstance(data, dict) else "",
    }


def average_score(rows: list[dict], side: str, metric: str) -> float:
    if not rows:
        return 0.0
    return round(sum(float(row["scores"][side][metric]) for row in rows) / len(rows), 4)


def keyword_hit_count(answer: str, key_points: list[str]) -> int:
    return sum(1 for point in key_points if contains_phrase(answer, point))


def main() -> None:
    parser = parse_common_args("Benchmark the full course agent against a plain LLM baseline.")
    parser.add_argument("--retrieval-mode", default="hybrid", choices=["keyword", "vector", "hybrid"])
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--judge-mode", default="llm", choices=["llm", "heuristic"])
    args = parser.parse_args()

    if args.benchmark is None:
        raise SystemExit("--benchmark is required for agent benchmarking.")

    benchmark = load_benchmark(args.benchmark)
    cases = benchmark.get("cases", [])
    if not cases:
        raise SystemExit("Benchmark file does not contain any cases.")

    token = resolve_token(base_url=args.base_url, token=args.token, username=args.username, password=args.password)
    evaluated_cases: list[dict] = []
    wins = {"agent": 0, "plain_llm": 0, "tie": 0}

    for case in cases:
        case_id = str(case.get("id", "")).strip() or "unnamed-case"
        course_id = int(case["course_id"])
        question = str(case.get("question", "")).strip()
        if not question:
            raise SystemExit(f"Benchmark case {case_id} is missing a question.")

        agent_payload = ask_agent(
            base_url=args.base_url,
            token=token,
            course_id=course_id,
            question=question,
            retrieval_mode=args.retrieval_mode,
            top_k=args.top_k,
        )
        agent_answer = agent_payload["assistant_message"]
        plain_answer = ask_plain_llm(course_context=case, question=question)
        key_points = [str(item).strip() for item in case.get("key_points", []) if str(item).strip()]

        if args.judge_mode == "llm":
            scores = judge_with_llm(case=case, agent_answer=agent_answer, plain_answer=plain_answer)
        else:
            agent_scores = heuristic_scores(answer=agent_answer["content"], sources=agent_answer.get("sources", []), key_points=key_points)
            plain_scores = heuristic_scores(answer=plain_answer, sources=[], key_points=key_points)
            agent_total = sum(agent_scores.values())
            plain_total = sum(plain_scores.values())
            preferred = "tie"
            if agent_total > plain_total:
                preferred = "agent"
            elif plain_total > agent_total:
                preferred = "plain_llm"
            scores = {
                "agent": agent_scores,
                "plain_llm": plain_scores,
                "preferred_system": preferred,
                "rationale": "Heuristic comparison based on key-point coverage and source availability.",
            }

        preferred_system = str(scores.get("preferred_system", "tie")).strip() or "tie"
        if preferred_system not in wins:
            preferred_system = "tie"
        wins[preferred_system] += 1

        evaluated_cases.append(
            {
                "id": case_id,
                "course_id": course_id,
                "question": question,
                "query_type": case.get("query_type", ""),
                "reference_answer": case.get("reference_answer", ""),
                "key_points": key_points,
                "agent": {
                    "answer": agent_answer["content"],
                    "source_count": len(agent_answer.get("sources", [])),
                    "sources": agent_answer.get("sources", []),
                    "key_point_hits": keyword_hit_count(agent_answer["content"], key_points),
                },
                "plain_llm": {
                    "answer": plain_answer,
                    "key_point_hits": keyword_hit_count(plain_answer, key_points),
                },
                "scores": scores,
            }
        )

    summary = {
        "benchmark_name": benchmark.get("meta", {}).get("name", args.benchmark.name),
        "judge_mode": args.judge_mode,
        "retrieval_mode": args.retrieval_mode,
        "top_k": args.top_k,
        "wins": wins,
        "agent_average": {
            "correctness": average_score(evaluated_cases, "agent", "correctness"),
            "groundedness": average_score(evaluated_cases, "agent", "groundedness"),
            "course_specificity": average_score(evaluated_cases, "agent", "course_specificity"),
            "study_usefulness": average_score(evaluated_cases, "agent", "study_usefulness"),
        },
        "plain_llm_average": {
            "correctness": average_score(evaluated_cases, "plain_llm", "correctness"),
            "groundedness": average_score(evaluated_cases, "plain_llm", "groundedness"),
            "course_specificity": average_score(evaluated_cases, "plain_llm", "course_specificity"),
            "study_usefulness": average_score(evaluated_cases, "plain_llm", "study_usefulness"),
        },
        "cases": evaluated_cases,
    }
    write_output(args.output, summary)


if __name__ == "__main__":
    main()
