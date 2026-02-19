---
id: US-007
epic: EP-5 Observability
priority: P1
status: Implemented
source_prd: PRD-001, PRD-002
estimation: 3 points
---

# US-007: Environment-Agnostic Configuration

## The Story

> **As an** `ML Engineer`,
> **I want** to configure all pipeline settings via YAML and environment variables,
> **So that** I can deploy to different environments without modifying source code.

## Acceptance Criteria

### Scenario A: YAML file overrides built-in defaults
```gherkin
Given configs/config.yaml sets workers: 4 and chunk_size: 50
  And no environment variables are set for these keys
When the pipeline starts
Then it uses workers=4 and chunk_size=50 (from YAML, not compiled defaults)
  And logs "Config loaded from configs/config.yaml" at startup
```

### Scenario B: Environment variable overrides YAML
```gherkin
Given configs/config.yaml sets workers: 4
  And the environment variable SEC_WORKERS=16 is set
When the pipeline starts
Then it uses workers=16 (env var wins over YAML)
  And logs the resolved config at DEBUG level
```

### Scenario C: Invalid config value fails fast at startup
```gherkin
Given configs/config.yaml sets workers: "not_a_number"
When the pipeline starts
Then Pydantic V2 raises a ValidationError before any filing is processed
  And the error message names the offending field and expected type
  And no output directory is created
```

### Scenario D: Secrets are never in plaintext config
```gherkin
Given a deployment requiring an EDGAR API key
When the pipeline is configured
Then the key is read exclusively from the .env file or environment variable
  And configs/config.yaml contains no secrets (verified by git-secrets pre-commit hook)
```

## Technical Notes

- 16-module config system: `src/config/` (Pydantic V2 + pydantic-settings)
- Single cached YAML loader: `src/config/_loader.py`
- Environment prefix: `SEC_` (e.g. `SEC_WORKERS`, `SEC_CHUNK_SIZE`)
- `.env.example` documents all required secrets
- Status: ✅ Implemented
