---
date: {{DATE_ISO}}
researcher: {{RESEARCHER}}
git_commit: {{GIT_COMMIT}}
branch: {{BRANCH}}
repository: {{REPOSITORY}}
topic: "Experiment: {{EXPERIMENT_NAME}}"
tags: [experiment, mlops, {{TAGS}}]
status: in_progress
last_updated: {{DATE_SHORT}}
last_updated_by: {{RESEARCHER}}
run_id: {{YYYYMMDD_HHMMSS}}_{{EXPERIMENT_NAME}}
data_version: {{GIT_COMMIT}}
---

# Experiment: {{EXPERIMENT_NAME}}

**Date**: {{DATE_ISO}}
**Researcher**: {{RESEARCHER}}
**Git Commit**: {{GIT_COMMIT}}
**Run ID**: {{RUN_ID}}

## Hypothesis

<!--
What are you testing? What do you expect to happen?
Be specific and falsifiable.
-->

{{HYPOTHESIS}}

## Experiment Design

### Objective
{{OBJECTIVE}}

### Variables

| Variable | Type | Values |
|----------|------|--------|
| {{VAR_1}} | Independent | {{VALUES}} |
| {{VAR_2}} | Dependent | Measured |
| {{VAR_3}} | Control | Fixed at {{VALUE}} |

### Data

| Dataset | Location | Records | Version |
|---------|----------|---------|---------|
| Training | `data/processed/train/` | {{N}} | {{GIT_COMMIT}} |
| Validation | `data/processed/val/` | {{N}} | {{GIT_COMMIT}} |
| Test | `data/processed/test/` | {{N}} | {{GIT_COMMIT}} |

---

## Configuration

### Model Configuration
```yaml
model:
  name: {{MODEL_NAME}}
  version: {{MODEL_VERSION}}
  parameters:
    learning_rate: {{LR}}
    batch_size: {{BATCH}}
    epochs: {{EPOCHS}}
    seed: {{SEED}}
```

### Preprocessing Configuration
```yaml
preprocessing:
  min_segment_length: {{MIN_LEN}}
  max_segment_length: {{MAX_LEN}}
  tokenizer: {{TOKENIZER}}
```

### Full Config Snapshot
<!--
Copy from run_config.yaml or inline the full config
-->

```yaml
{{FULL_CONFIG}}
```

---

## Execution

### Commands Run
```bash
# Training command
python scripts/train.py --config configs/experiment.yaml

# Evaluation command
python scripts/evaluate.py --checkpoint {{CHECKPOINT_PATH}}
```

### Runtime Information
| Metric | Value |
|--------|-------|
| Start Time | {{START_TIME}} |
| End Time | {{END_TIME}} |
| Duration | {{DURATION}} |
| Hardware | {{GPU/CPU}} |
| Memory Used | {{MEMORY}} |

### Checkpoints Saved
| Checkpoint | Location | Epoch | Metric |
|------------|----------|-------|--------|
| Best | `models/experiments/{{RUN_ID}}/best.pt` | {{EPOCH}} | {{METRIC}} |
| Final | `models/experiments/{{RUN_ID}}/final.pt` | {{EPOCH}} | {{METRIC}} |

---

## Results

### Primary Metrics
| Metric | Train | Validation | Test |
|--------|-------|------------|------|
| Accuracy | {{ACC_TRAIN}} | {{ACC_VAL}} | {{ACC_TEST}} |
| F1 Score | {{F1_TRAIN}} | {{F1_VAL}} | {{F1_TEST}} |
| Loss | {{LOSS_TRAIN}} | {{LOSS_VAL}} | {{LOSS_TEST}} |

### Secondary Metrics
| Metric | Value | Notes |
|--------|-------|-------|
| {{METRIC_1}} | {{VALUE}} | {{NOTES}} |
| {{METRIC_2}} | {{VALUE}} | {{NOTES}} |

### Learning Curves
<!--
Include path to saved plots or embed base64 images
-->

![Training Loss](models/experiments/{{RUN_ID}}/training_loss.png)
![Validation Metrics](models/experiments/{{RUN_ID}}/val_metrics.png)

### Confusion Matrix (if classification)
```
              Predicted
              Neg    Pos
Actual  Neg   {{TN}}  {{FP}}
        Pos   {{FN}}  {{TP}}
```

---

## Analysis

### Hypothesis Evaluation
<!--
Was the hypothesis supported? Why or why not?
-->

{{HYPOTHESIS_EVALUATION}}

### Key Observations
1. {{OBSERVATION_1}}
2. {{OBSERVATION_2}}
3. {{OBSERVATION_3}}

### Comparison with Baseline
| Metric | Baseline | This Experiment | Delta |
|--------|----------|-----------------|-------|
| {{METRIC}} | {{BASELINE}} | {{CURRENT}} | {{DELTA}} |

### Error Analysis
<!--
What kinds of errors is the model making?
-->

{{ERROR_ANALYSIS}}

---

## Artifacts

### Output Files
| File | Location | Description |
|------|----------|-------------|
| Model Checkpoint | `models/experiments/{{RUN_ID}}/best.pt` | Best validation model |
| Config | `models/experiments/{{RUN_ID}}/run_config.yaml` | Full configuration |
| Metrics | `models/experiments/{{RUN_ID}}/metrics.json` | Training metrics |
| Predictions | `models/experiments/{{RUN_ID}}/predictions.json` | Test predictions |
| Logs | `logs/{{RUN_ID}}.log` | Training logs |

### Reproducibility Checklist
- [ ] Config saved: `run_config.yaml`
- [ ] Random seed set: `{{SEED}}`
- [ ] Git commit recorded: `{{GIT_COMMIT}}`
- [ ] Data version recorded: `{{DATA_VERSION}}`
- [ ] Environment captured: `requirements.txt` or `environment.yaml`

---

## Conclusions

### Summary
{{SUMMARY}}

### Next Steps
1. {{NEXT_STEP_1}}
2. {{NEXT_STEP_2}}

### Should This Model Be Promoted?
<!--
Decision on whether to move to models/registry/
-->

- [ ] Yes - Promote to `models/registry/{{MODEL_NAME}}_v{{VERSION}}/`
- [ ] No - Document why and archive

---

## Quick Start: Using This Template

### Before Experiment
1. Run `./hack/spec_metadata.sh --yaml` for metadata
2. Fill in Configuration section
3. Set `status: in_progress`

### During Experiment
1. Update Commands Run section
2. Note any issues in Analysis

### After Experiment
1. Fill Results section with actual metrics
2. Complete Analysis and Conclusions
3. Update `status: complete`
4. Save artifacts to `models/experiments/{{RUN_ID}}/`

### Using RunContext (Python)
```python
from src.config import RunContext

# Auto-capture git SHA for data-code linkage
run = RunContext(name="{{EXPERIMENT_NAME}}", auto_git_sha=True)
run.create()

# Your experiment code here

# Save configuration
run.save_config({
    "model": "{{MODEL_NAME}}",
    "learning_rate": {{LR}},
    "seed": {{SEED}}
})

# Save metrics after training
run.save_metrics({
    "accuracy": {{ACC_TEST}},
    "f1_score": {{F1_TEST}},
    "loss": {{LOSS_TEST}}
})

# Output directory now includes git SHA:
# data/processed/labeled/{timestamp}_{name}_{git_sha}/
print(f"Artifacts at: {run.output_dir}")
```
