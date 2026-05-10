# Evaluation

This folder contains the benchmark template for measuring:

1. Retrieval quality
2. Full agent quality versus a plain LLM baseline

## Files

- [benchmark_template.json](/Users/shengxiangqi/Documents/UIUC/AIAgent/superMew/study-planner-agent/eval/benchmark_template.json): example benchmark schema

## Benchmark Format

Each case should include:

- `course_id`
- `question`
- `query_type`
- `gold_chunk_ids`
- optional `gold_parent_chunk_ids`
- optional `gold_root_chunk_ids`
- `reference_answer`
- `key_points`
- optional `grading_notes`

The retrieval benchmark uses the gold chunk fields.

The end-to-end benchmark uses:

- `reference_answer`
- `key_points`
- `grading_notes`

## Recommended Workflow

1. Dump chunks for one course:

```bash
uv run python scripts/eval_dump_course_chunks.py \
  --username <username> \
  --password <password> \
  --course-id <course_id> \
  --output eval/course_chunks.json
```

2. Copy [benchmark_template.json](/Users/shengxiangqi/Documents/UIUC/AIAgent/superMew/study-planner-agent/eval/benchmark_template.json) and replace placeholder chunk IDs with real gold chunk IDs.

3. Run retrieval evaluation:

```bash
uv run python scripts/eval_retrieval.py \
  --username <username> \
  --password <password> \
  --benchmark eval/benchmark.json \
  --output eval/results/retrieval.json
```

4. Run agent benchmark:

```bash
uv run python scripts/eval_agent_benchmark.py \
  --username <username> \
  --password <password> \
  --benchmark eval/benchmark.json \
  --retrieval-mode hybrid \
  --judge-mode llm \
  --output eval/results/agent_vs_plain_llm.json
```

## Notes

- `eval_agent_benchmark.py` requires `CHAT_BASE_URL`, `CHAT_MODEL`, and `CHAT_API_KEY` in `.env` or the shell environment.
- If you do not want the judge model, use `--judge-mode heuristic`.
- For retrieval evaluation, compare `keyword`, `vector`, and `hybrid`.
- The most informative metrics for this project are `hit@k`, `recall@k`, and `MRR`.
