# Preprocessing

Documentation for `src/preprocessing/`: parsing, extraction, cleaning, and segmentation of SEC filings.

## Start Here

1. [USAGE_GUIDE_SEC_PARSER.md](USAGE_GUIDE_SEC_PARSER.md) — How to use `sec-parser`, `SECFilingParser`, and `SECSectionExtractor` end-to-end

## Deep Dives

| File | Purpose |
|------|---------|
| [EXTRACTION_BEST_PRACTICES.md](EXTRACTION_BEST_PRACTICES.md) | Patterns and pitfalls for reliable section extraction |
| [EXTRACTOR_QA_BATCH_GUIDE.md](EXTRACTOR_QA_BATCH_GUIDE.md) | Running QA checks over batch extraction outputs |

## Pipeline Modules

```
src/preprocessing/
├── sanitizer.py    → HTMLSanitizer (pre-parse cleanup)
├── parser.py       → SECFilingParser → ParsedFiling
├── extractor.py    → SECSectionExtractor → ExtractedSection
├── cleaning.py     → Text normalization post-extraction
├── segmenter.py    → Risk segment splitting
└── pipeline.py     → SECPreprocessingPipeline (orchestrator)
```
