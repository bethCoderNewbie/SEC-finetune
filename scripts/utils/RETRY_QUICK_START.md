# Retry Failed Files - Quick Start Guide

## TL;DR

Automatically retry failed preprocessing files with increased timeout and resources.

## Most Common Commands

### 1. Preview What Will Be Retried
```bash
python scripts/utils/retry_failed_files.py --dry-run
```

### 2. Retry All Failed Files (2x Timeout)
```bash
python scripts/utils/retry_failed_files.py --timeout-multiplier 2.0 --update-dlq
```

### 3. Retry Large Files Only (>40MB) with 3x Timeout
```bash
python scripts/utils/retry_failed_files.py --min-size 40 --timeout-multiplier 3.0 --update-dlq
```

### 4. Force Isolation for Problematic Files
```bash
python scripts/utils/retry_failed_files.py --force-isolated --timeout-multiplier 2.5 --update-dlq
```

### 5. Check DLQ Status
```bash
cat logs/failed_files.json | jq '. | length'
cat logs/failed_files.json | jq '.[] | {file, attempts: .attempt_count, size: .file_size_mb}'
```

## Key Options

| Flag | Purpose | Example |
|------|---------|---------|
| `--dry-run` | Preview without processing | `--dry-run` |
| `--timeout-multiplier N` | Increase timeout by Nx | `--timeout-multiplier 2.5` |
| `--force-isolated` | Single-core processing | `--force-isolated` |
| `--min-size N` | Only retry files ≥N MB | `--min-size 50` |
| `--max-attempts N` | Skip files with N+ attempts | `--max-attempts 3` |
| `--update-dlq` | Update DLQ after retry | `--update-dlq` (REQUIRED to modify DLQ) |

## Timeout Reference

| File Size | Base Timeout | 2x | 2.5x | 3x |
|-----------|-------------|-----|------|-----|
| <20MB (Small) | 10 min | 20 min | 25 min | 30 min |
| 20-50MB (Medium) | 20 min | 40 min | 50 min | 60 min |
| >50MB (Large) | 40 min | 80 min | 100 min | 120 min |

## Typical Workflow

```bash
# 1. Check failed files
cat logs/failed_files.json | jq 'length'

# 2. Dry run to preview
python scripts/utils/retry_failed_files.py --dry-run

# 3. Retry with 2.5x timeout
python scripts/utils/retry_failed_files.py --timeout-multiplier 2.5 --update-dlq

# 4. Check results
cat logs/failed_files.json | jq 'length'  # Should be fewer

# 5. Retry remaining with isolation
python scripts/utils/retry_failed_files.py --force-isolated --timeout-multiplier 3.0 --update-dlq
```

## Full Documentation

See [docs/RETRY_MECHANISM.md](../../docs/RETRY_MECHANISM.md) for complete documentation.
