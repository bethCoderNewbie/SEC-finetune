---
date: 2025-12-12T20:20:07-06:00
researcher: bethCoderNewbie
git_commit: ea45dd2
branch: main
repository: SEC finetune
topic: "Naming Convention Configuration Design"
tags: [config, naming, automation, runcontext, mlops]
status: complete
---

# Research: Naming Convention Configuration Design

## Objective

Design a centralized configuration system for folder and file naming patterns used across all data pipeline scripts.

## Current State Analysis

### Folder Naming Pattern
**Location**: `src/config/run_context.py:100-102`
```python
if self.git_sha:
    return self.base_dir / f"{self.run_id}_{self.name}_{self.git_sha}"
return self.base_dir / f"{self.run_id}_{self.name}"
```

**Pattern**: `{run_id}_{name}_{git_sha}/` or `{run_id}_{name}/`

### File Naming Pattern
**Location**: `scripts/data_preprocessing/batch_parse.py:298-299`
```python
filename = f"{html_file.stem}_{run_id}_parsed.json"
```

**Pattern**: `{original_stem}_{run_id}_{output_type}.json`

### Run ID Format
**Location**: `src/config/run_context.py:87-89`
```python
@property
def run_id(self) -> str:
    return self.timestamp.strftime("%Y%m%d_%H%M%S")
```

**Format**: `YYYYMMDD_HHMMSS`

## Working Paths vs Broken Paths

| Component | Working Path | Broken Path (Avoided) |
|-----------|--------------|----------------------|
| Folder | `20251212_200149_batch_parse_ea45dd2/` | `batch_parse_20251212/` |
| File | `AAPL_10K_20251212_200149_parsed.json` | `AAPL_10K_parsed_20251212_200149.json` |
| Resume | Checks ALL run folders for existing stems | Checks only current (empty) folder |

## Design: NamingConfig

### Location
- Config class: `src/config/naming.py` (new)
- YAML section: `configs/config.yaml` under `naming:` key

### Proposed Schema

```python
class NamingConfig(BaseSettings):
    """Centralized naming pattern configuration."""

    # Timestamp format for run_id
    timestamp_format: str = "%Y%m%d_%H%M%S"

    # Folder pattern components
    folder_pattern: str = "{run_id}_{name}_{git_sha}"
    folder_pattern_no_sha: str = "{run_id}_{name}"

    # File pattern components
    file_pattern: str = "{stem}_{run_id}_{output_type}.json"

    # Output type identifiers
    output_types: Dict[str, str] = {
        "parsed": "parsed",
        "extracted": "extracted_risks",
        "cleaned": "cleaned_risks",
        "segmented": "segmented_risks",
        "labeled": "labeled"
    }
```

### YAML Configuration

```yaml
naming:
  timestamp_format: "%Y%m%d_%H%M%S"
  folder_pattern: "{run_id}_{name}_{git_sha}"
  folder_pattern_no_sha: "{run_id}_{name}"
  file_pattern: "{stem}_{run_id}_{output_type}.json"
  output_types:
    parsed: "parsed"
    extracted: "extracted_risks"
    cleaned: "cleaned_risks"
    segmented: "segmented_risks"
    labeled: "labeled"
```

## Integration Points

### 1. RunContext Integration
**File**: `src/config/run_context.py`
- Import `NamingConfig` from `src/config/naming.py`
- Use `naming.folder_pattern` in `output_dir` property
- Use `naming.timestamp_format` in `run_id` property

### 2. Batch Script Integration
**Files**: `batch_parse.py`, `batch_extract.py`, `run_preprocessing_pipeline.py`
- Import naming config via `from src.config import settings`
- Use `settings.naming.file_pattern` for output filenames
- Use `settings.naming.output_types["parsed"]` for output type

### 3. Resume Logic Integration
**Files**: Helper functions in batch scripts
- Use naming patterns to construct expected filenames for resume checks

## Benefits

1. **Single Source of Truth**: All naming patterns defined in one place
2. **Easy Modification**: Change patterns via config without code changes
3. **Consistency**: Guaranteed consistent naming across all scripts
4. **Testability**: Config can be validated at startup
5. **Documentation**: Config file serves as self-documenting spec

## Files to Modify

| File | Change |
|------|--------|
| `src/config/naming.py` | NEW: NamingConfig class |
| `src/config/__init__.py` | Export NamingConfig |
| `configs/config.yaml` | Add `naming:` section |
| `src/config/run_context.py` | Use NamingConfig for patterns |
| `scripts/data_preprocessing/batch_parse.py` | Use settings.naming |
| `scripts/data_preprocessing/batch_extract.py` | Use settings.naming |
| `scripts/data_preprocessing/run_preprocessing_pipeline.py` | Use settings.naming |

## Next Steps

1. Create `src/config/naming.py` with `NamingConfig` class
2. Add `naming:` section to `configs/config.yaml`
3. Update `src/config/__init__.py` to export naming config
4. Update `RunContext` to use naming config
5. Update batch scripts to use centralized naming
