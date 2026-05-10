# Study Planner Agent Evaluation Report

## Scope

This report summarizes two evaluation rounds:

1. A controlled synthetic benchmark built from an automatically generated mini-course.
2. A real-course benchmark built from the existing `CS 521` course materials in the local database.

The evaluation focused on two questions:

1. How good is retrieval quality?
2. Does the full agent outperform a plain LLM baseline on grounded course questions?

## Method

### Round 1: Controlled Synthetic Benchmark

- Created a temporary operating-systems course.
- Uploaded one generated DOCX with four clean sections:
  - Processes and Threads
  - Synchronization
  - Virtual Memory
  - Page Replacement
- Built a benchmark of 4 questions with known gold chunks.
- Ran retrieval in `keyword`, `vector`, and `hybrid` modes.
- Compared:
  - plain LLM
  - full course agent with `hybrid` retrieval

Artifacts:

- [auto_benchmark.json](/Users/shengxiangqi/Documents/UIUC/AIAgent/superMew/study-planner-agent/eval/auto_benchmark.json)
- [retrieval.json](/Users/shengxiangqi/Documents/UIUC/AIAgent/superMew/study-planner-agent/eval/results/retrieval.json)
- [agent_vs_plain_llm.json](/Users/shengxiangqi/Documents/UIUC/AIAgent/superMew/study-planner-agent/eval/results/agent_vs_plain_llm.json)

### Round 2: Real Course Benchmark

- Selected the real `CS 521` blockchain course.
- Manually curated 8 benchmark questions from real course chunks spanning:
  - crypto primitives
  - Bitcoin
  - Ethereum
  - consensus
- Assigned gold chunk IDs directly from the real stored child chunks.
- Ran the same retrieval and end-to-end comparison pipeline.

Artifacts:

- [real_course_benchmark_cs521.json](/Users/shengxiangqi/Documents/UIUC/AIAgent/superMew/study-planner-agent/eval/real_course_benchmark_cs521.json)
- [retrieval_cs521.json](/Users/shengxiangqi/Documents/UIUC/AIAgent/superMew/study-planner-agent/eval/results/retrieval_cs521.json)
- [agent_vs_plain_llm_cs521.json](/Users/shengxiangqi/Documents/UIUC/AIAgent/superMew/study-planner-agent/eval/results/agent_vs_plain_llm_cs521.json)

## Results

### Retrieval Metrics

Relevance labeling protocol:

- Retrieval relevance was determined by a manually curated gold evidence set for each benchmark question.
- Each question in the benchmark JSON includes one or more `gold_chunk_ids`, and can also include `gold_parent_chunk_ids` or `gold_root_chunk_ids` when a broader match is appropriate.
- A retrieved result is counted as relevant only if its returned `chunk_id`, `parent_chunk_id`, or `root_chunk_id` matches one of those pre-labeled gold identifiers.
- This means `precision@k`, `recall@k`, `hit@k`, and `MRR` were computed by exact evidence matching, not by asking an LLM to judge relevance at evaluation time.

#### Round 1: Synthetic OS Benchmark

| Mode | Hit@5 | Recall@5 | MRR |
|---|---:|---:|---:|
| keyword | 0.00 | 0.00 | 0.00 |
| vector | 1.00 | 1.00 | 1.00 |
| hybrid | 1.00 | 1.00 | 1.00 |

Interpretation:

- `keyword` retrieval failed completely on natural-language questions.
- `vector` and `hybrid` both retrieved the correct chunk at rank 1 for every case.

#### Round 2: Real `CS 521` Benchmark

| Mode | Hit@5 | Recall@5 | MRR |
|---|---:|---:|---:|
| keyword | 0.00 | 0.00 | 0.00 |
| vector | 0.625 | 0.5625 | 0.4792 |
| hybrid | 0.625 | 0.5625 | 0.4167 |

Interpretation:

- `keyword` retrieval was again effectively unusable for natural-language questions.
- `vector` retrieval was meaningfully better, but far from perfect on real course content.
- `hybrid` did not improve over `vector` in this benchmark because `keyword` contributed little useful signal.

### Agent vs Plain LLM

#### Round 1: Synthetic OS Benchmark

Win count:

- agent: 4
- plain LLM: 0
- tie: 0

Average scores:

| System | Correctness | Groundedness | Course Specificity | Study Usefulness |
|---|---:|---:|---:|---:|
| agent | 4.75 | 4.75 | 4.75 | 4.75 |
| plain LLM | 4.75 | 1.00 | 1.00 | 4.25 |

Interpretation:

- Both systems were similarly correct on simple OS content.
- The agent clearly won on groundedness and course specificity.

#### Round 2: Real `CS 521` Benchmark

Win count:

- agent: 7
- plain LLM: 1
- tie: 0

Average scores:

| System | Correctness | Groundedness | Course Specificity | Study Usefulness |
|---|---:|---:|---:|---:|
| agent | 4.625 | 4.50 | 4.50 | 4.50 |
| plain LLM | 4.125 | 1.125 | 1.125 | 3.875 |

Interpretation:

- The full agent strongly outperformed the plain LLM overall.
- The main advantage was not raw intelligence, but groundedness and course-specificity.
- The plain LLM gave reasonable general explanations, but they were usually not anchored to the actual course material.

## Key Findings

### 1. The project's core value is grounded course-specific assistance

The evaluation does not show that the agent is always more factually knowledgeable than a strong general LLM. Instead, it shows that the agent is much better at:

- tying answers to the actual course material
- surfacing sources
- giving study answers that are course-specific rather than generic

### 2. Retrieval is the main bottleneck

The biggest weakness is retrieval, especially keyword retrieval.

Observed behavior:

- Short term queries like `virtual memory` or `page replacement` can still work with keyword retrieval.
- Natural questions like `What are the core properties of consensus?` often fail under keyword search.
- Real-course performance drops significantly relative to the clean synthetic benchmark.

This means the current system is only as strong as its vector retrieval path.

### 3. Hybrid retrieval is not yet adding real value

On the real-course benchmark, `hybrid` did not beat `vector`.

Most likely reason:

- keyword retrieval contributes near-zero useful matches for natural questions
- therefore reciprocal-rank fusion mostly preserves the vector ordering

### 4. Failure cases are informative

The clearest failure in the real benchmark was `secret-key cryptography`.

What happened:

- the benchmark expected chunks from the Topic 2 crypto lecture
- retrieval surfaced unrelated later-course Schnorr-signature chunks from Topic 6
- the agent then correctly admitted the retrieved sources did not support the question

This is a good evaluation failure:

- the answering layer behaved responsibly
- the retrieval layer failed to find the right evidence

## Overall Judgment

The project is successful as a retrieval-grounded study assistant, but not yet fully reliable as a retrieval system.

Current status:

- End-to-end agent quality: strong
- Groundedness and course specificity: strong
- Retrieval quality on real data: moderate
- Keyword retrieval quality on real questions: weak

## Recommended Next Steps

1. Improve retrieval before adding more product features.
2. Add query rewriting for natural-language questions before keyword retrieval.
3. Consider chunk reranking after initial vector retrieval.
4. Revisit chunking quality for slide-style PDFs with noisy titles and fragmented text.
5. Expand the real-course benchmark to 20-30 questions per course across multiple courses.

## Bottom Line

This evaluation supports the claim that the project is meaningfully better than a plain LLM for course-grounded study assistance.

It also clearly shows that the main engineering priority is retrieval quality, not answer generation.
