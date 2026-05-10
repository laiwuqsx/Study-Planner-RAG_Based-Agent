from collections import defaultdict
from urllib.parse import quote

from eval_common import (
    load_benchmark,
    parse_common_args,
    request_json,
    resolve_token,
    safe_int_set,
    safe_str_set,
    write_output,
)


def first_relevant_rank(case: dict, results: list[dict]) -> int | None:
    gold_chunk_ids = safe_str_set(case.get("gold_chunk_ids", []))
    gold_root_chunk_ids = safe_str_set(case.get("gold_root_chunk_ids", []))
    gold_parent_chunk_ids = safe_int_set(case.get("gold_parent_chunk_ids", []))

    for index, result in enumerate(results, start=1):
        if gold_chunk_ids and str(result.get("chunk_id", "")).strip() in gold_chunk_ids:
            return index
        if gold_root_chunk_ids and str(result.get("root_chunk_id", "")).strip() in gold_root_chunk_ids:
            return index
        if gold_parent_chunk_ids and int(result.get("parent_chunk_id", -1)) in gold_parent_chunk_ids:
            return index
    return None


def relevant_count(case: dict, results: list[dict], top_k: int) -> int:
    gold_chunk_ids = safe_str_set(case.get("gold_chunk_ids", []))
    gold_root_chunk_ids = safe_str_set(case.get("gold_root_chunk_ids", []))
    gold_parent_chunk_ids = safe_int_set(case.get("gold_parent_chunk_ids", []))
    if gold_chunk_ids:
        return len({str(result.get("chunk_id", "")).strip() for result in results[:top_k]} & gold_chunk_ids)
    if gold_root_chunk_ids:
        return len({str(result.get("root_chunk_id", "")).strip() for result in results[:top_k]} & gold_root_chunk_ids)
    if gold_parent_chunk_ids:
        matched = set()
        for result in results[:top_k]:
            try:
                parent_chunk_id = int(result.get("parent_chunk_id", -1))
            except (TypeError, ValueError):
                continue
            if parent_chunk_id in gold_parent_chunk_ids:
                matched.add(parent_chunk_id)
        return len(matched)
    return 0


def gold_size(case: dict) -> int:
    if case.get("gold_chunk_ids"):
        return max(1, len(safe_str_set(case.get("gold_chunk_ids", []))))
    if case.get("gold_root_chunk_ids"):
        return max(1, len(safe_str_set(case.get("gold_root_chunk_ids", []))))
    if case.get("gold_parent_chunk_ids"):
        return max(1, len(safe_int_set(case.get("gold_parent_chunk_ids", []))))
    return 1


def aggregate_metrics(rows: list[dict], top_k: int) -> dict:
    if not rows:
        return {
            f"precision_at_{top_k}": 0.0,
            f"recall_at_{top_k}": 0.0,
            f"hit_at_{top_k}": 0.0,
            "mrr": 0.0,
            "case_count": 0,
        }
    precision = sum(row[f"precision_at_{top_k}"] for row in rows) / len(rows)
    recall = sum(row[f"recall_at_{top_k}"] for row in rows) / len(rows)
    hit = sum(1.0 if row["first_relevant_rank"] is not None and row["first_relevant_rank"] <= top_k else 0.0 for row in rows) / len(rows)
    mrr = sum((1.0 / row["first_relevant_rank"]) if row["first_relevant_rank"] else 0.0 for row in rows) / len(rows)
    return {
        f"precision_at_{top_k}": round(precision, 4),
        f"recall_at_{top_k}": round(recall, 4),
        f"hit_at_{top_k}": round(hit, 4),
        "mrr": round(mrr, 4),
        "case_count": len(rows),
    }


def main() -> None:
    parser = parse_common_args("Evaluate keyword, vector, and hybrid retrieval quality against labeled gold chunks.")
    parser.add_argument("--modes", nargs="+", default=["keyword", "vector", "hybrid"], choices=["keyword", "vector", "hybrid"])
    parser.add_argument("--top-k", type=int, default=5, help="Search depth for metrics. Defaults to %(default)s.")
    args = parser.parse_args()

    if args.benchmark is None:
        raise SystemExit("--benchmark is required for retrieval evaluation.")

    benchmark = load_benchmark(args.benchmark)
    cases = benchmark.get("cases", [])
    if not cases:
        raise SystemExit("Benchmark file does not contain any cases.")

    token = resolve_token(base_url=args.base_url, token=args.token, username=args.username, password=args.password)
    summary: dict[str, dict] = {}
    by_mode_rows: dict[str, list[dict]] = defaultdict(list)

    for case in cases:
        case_id = str(case.get("id", "")).strip() or "unnamed-case"
        question = str(case.get("question", "")).strip()
        course_id = int(case["course_id"])
        if not question:
            raise SystemExit(f"Benchmark case {case_id} is missing a question.")

        for mode in args.modes:
            response = request_json(
                base_url=args.base_url,
                path=f"/courses/{course_id}/search?query={quote(question)}&retrieval_mode={mode}&top_k={args.top_k}",
                token=token,
            )
            results = response.get("results", [])
            rank = first_relevant_rank(case, results)
            matched = relevant_count(case, results, args.top_k)
            denominator = gold_size(case)
            row = {
                "id": case_id,
                "course_id": course_id,
                "question": question,
                "query_type": case.get("query_type", ""),
                "retrieval_mode": mode,
                "result_count": len(results),
                "first_relevant_rank": rank,
                f"precision_at_{args.top_k}": round(matched / max(1, min(args.top_k, len(results)) or 1), 4),
                f"recall_at_{args.top_k}": round(matched / denominator, 4),
                "top_results": [
                    {
                        "chunk_id": result.get("chunk_id"),
                        "root_chunk_id": result.get("root_chunk_id"),
                        "parent_chunk_id": result.get("parent_chunk_id"),
                        "filename": result.get("filename"),
                        "section_title": result.get("section_title"),
                        "score": result.get("score"),
                    }
                    for result in results[: min(args.top_k, 5)]
                ],
            }
            by_mode_rows[mode].append(row)

    for mode, rows in by_mode_rows.items():
        summary[mode] = {
            "metrics": aggregate_metrics(rows, args.top_k),
            "cases": rows,
        }

    payload = {
        "benchmark_name": benchmark.get("meta", {}).get("name", args.benchmark.name),
        "top_k": args.top_k,
        "modes": args.modes,
        "summary": summary,
    }
    write_output(args.output, payload)


if __name__ == "__main__":
    main()
