# Validation

Documentation for `src/validation/`: QA checks, schema validation, and shared domain knowledge.

## Documents

| File | Purpose |
|------|---------|
| [DATA_HEALTH_CHECK_GUIDE.md](DATA_HEALTH_CHECK_GUIDE.md) | **Start here.** How to run QA checks and interpret results |
| [SHARED_KNOWLEDGE.md](SHARED_KNOWLEDGE.md) | Ground-truth learnings: SEC parser behavior, extraction gotchas, and known edge cases |

## Config (QA thresholds)

QA thresholds are defined in `configs/qa_validation/` and loaded via `src/config/qa_validation.py`.
