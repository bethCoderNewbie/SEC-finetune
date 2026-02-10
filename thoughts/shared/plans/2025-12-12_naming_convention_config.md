---
date: 2025-12-12T20:20:07-06:00
researcher: bethCoderNewbie
git_commit: ea45dd2
branch: main
repository: SEC finetune
topic: "Naming Convention Configuration Implementation"
tags: [config, naming, automation, runcontext, mlops]
status: ready_for_review
related_research: thoughts/shared/research/2025-12-12_20-20_naming_convention_config.md
---

# Plan: Naming Convention Configuration Implementation

## Desired End State

The system will have:
1. **Centralized naming configuration** in `src/config/naming.py`
2. **YAML-configurable patterns** in `configs/config.yaml`
3. **Automated filename generation** via helper methods
4. **RunContext integration** using the naming config
5. **Batch script updates** to use centralized naming

## Anti-Scope

- NOT changing existing output directory structures
- NOT migrating existing data files to new naming
- NOT adding validation for existing files against new patterns
- NOT changing the timestamp format (keeping YYYYMMDD_HHMMSS)

## Implementation Strategy

### Phase 1: Create NamingConfig Class

**File**: `src/config/naming.py` (NEW)

```python
"""Centralized naming convention configuration."""

from typing import Dict
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class NamingConfig(BaseSettings):
    """
    Configuration for file and folder naming patterns.

    Patterns support these placeholders:
    - {run_id}: Timestamp in YYYYMMDD_HHMMSS format
    - {name}: User-provided run name
    - {git_sha}: Git commit SHA (optional)
    - {stem}: Original input file stem
    - {output_type}: Processing stage identifier
    """
    model_config = SettingsConfigDict(
        env_prefix="NAMING_",
        extra="ignore"
    )

    timestamp_format: str = Field(
        default="%Y%m%d_%H%M%S",
        description="strftime format for run_id timestamps"
    )

    folder_pattern: str = Field(
        default="{run_id}_{name}_{git_sha}",
        description="Pattern for run folder names (with git SHA)"
    )

    folder_pattern_no_sha: str = Field(
        default="{run_id}_{name}",
        description="Pattern for run folder names (without git SHA)"
    )

    file_pattern: str = Field(
        default="{stem}_{run_id}_{output_type}.json",
        description="Pattern for output file names"
    )

    output_types: Dict[str, str] = Field(
        default={
            "parsed": "parsed",
            "extracted": "extracted_risks",
            "cleaned": "cleaned_risks",
            "segmented": "segmented_risks",
            "labeled": "labeled"
        },
        description="Mapping of stage names to output type suffixes"
    )

    def format_folder(self, run_id: str, name: str, git_sha: str = None) -> str:
        """Generate folder name from pattern."""
        if git_sha:
            return self.folder_pattern.format(
                run_id=run_id, name=name, git_sha=git_sha
            )
        return self.folder_pattern_no_sha.format(run_id=run_id, name=name)

    def format_filename(self, stem: str, run_id: str, output_type: str) -> str:
        """Generate filename from pattern."""
        type_suffix = self.output_types.get(output_type, output_type)
        return self.file_pattern.format(
            stem=stem, run_id=run_id, output_type=type_suffix
        )
```

### Phase 2: Add YAML Configuration

**File**: `configs/config.yaml` - Add section:

```yaml
# ===========================
# Naming Convention
# ===========================
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

### Phase 3: Update Config Exports

**File**: `src/config/__init__.py` - Add:

```python
from src.config.naming import NamingConfig
```

And ensure `settings.naming` is accessible.

### Phase 4: Update RunContext

**File**: `src/config/run_context.py` - Modify:

```python
# In output_dir property:
@property
def output_dir(self) -> Path:
    from src.config import settings
    folder_name = settings.naming.format_folder(
        run_id=self.run_id,
        name=self.name,
        git_sha=self.git_sha
    )
    return self.base_dir / folder_name

# In run_id property:
@property
def run_id(self) -> str:
    from src.config import settings
    return self.timestamp.strftime(settings.naming.timestamp_format)
```

### Phase 5: Update Batch Scripts (Optional Enhancement)

**Files**: `batch_parse.py`, `batch_extract.py`, `run_preprocessing_pipeline.py`

Replace hardcoded filename patterns with:
```python
from src.config import settings

filename = settings.naming.format_filename(
    stem=html_file.stem,
    run_id=run_id,
    output_type="parsed"
)
```

## Verification

1. **Config Loading**:
   ```bash
   python -c "from src.config import settings; print(settings.naming.folder_pattern)"
   ```
   Expected: `{run_id}_{name}_{git_sha}`

2. **Folder Formatting**:
   ```bash
   python -c "from src.config import settings; print(settings.naming.format_folder('20251212_200149', 'test', 'ea45dd2'))"
   ```
   Expected: `20251212_200149_test_ea45dd2`

3. **File Formatting**:
   ```bash
   python -c "from src.config import settings; print(settings.naming.format_filename('AAPL_10K', '20251212_200149', 'parsed'))"
   ```
   Expected: `AAPL_10K_20251212_200149_parsed.json`

4. **RunContext Integration**:
   ```bash
   python -c "from src.config import RunContext; r = RunContext(name='test', git_sha='abc123'); print(r.output_dir)"
   ```
   Expected: Path ending with `{timestamp}_test_abc123`
