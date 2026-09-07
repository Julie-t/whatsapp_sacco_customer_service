# System 6 Evaluation

This package evaluates retrieval, answerability, generated-answer groundedness,
relevance, language consistency, and fallback behavior without changing the
production RAG path.

## Layout

- `datasets/` contains evaluation cases.
- `results/` contains generated JSON reports and is not source data.
- `runner.py` orchestrates application components.
- `metrics.py` contains deterministic offline metrics.

The current compatibility dataset remains at `data/evaluation/rag_eval.json`.
Use it until the dataset migration is completed rather than maintaining two
authoritative copies.

## Commands

```bash
python scripts/evaluate_rag.py
python scripts/evaluate_rag.py --live
python scripts/evaluate_rag.py --live --limit 3 --show-answers
python scripts/evaluate_rag.py --verification-mode high-risk
```

The default mode uses a deterministic local generator and does not require
Groq. `--live` uses the configured Groq provider and should be run only when
Qdrant and provider credentials are available. Live generation uses the
configured model, token limit, temperature, and reasoning effort settings.
Live evaluation waits between cases using `EVAL_REQUEST_DELAY_SECONDS`; Groq
429 retries use the provider's `Retry-After` header or response-body timing,
bounded by `EVAL_PROVIDER_MAX_RETRIES` and the configured delay limits. The
`--limit` option is intended for a small live smoke sample before a full run.

Groundedness is claim-level where `expected_claims` are provided. A claim is
unsupported when its important terms or numeric values are absent from the
retrieved evidence. This is a deterministic screening metric, not a substitute
for human review.

Offline verification is deterministic and provider-free. Standard mode runs one
structured evidence check per generated answer; high-risk mode records two
deterministic checks offline and is intended to exercise the consensus report
shape. Generated-answer metrics exclude fallback, escalation, clarification, and
provider-failure cases from their denominator.
