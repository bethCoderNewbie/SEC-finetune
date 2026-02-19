---
id: US-026
epic: EP-7
priority: P1
status: not_started
source_prd: PRD-004
estimation: 3d
---

## The Story

As a **Risk Manager**, I want to see a change velocity score comparing a company's current
and prior-year risk language, so that I can instantly flag filings where the risk profile
changed materially and prioritise them for deep review.

---

## Acceptance Criteria

### Scenario: Change velocity score is produced for a company with two filing years

```gherkin
Given a labelled corpus containing 10-K filings for CIK "0000320193" for both 2020 and 2021
When the user runs:
  python -m sec_intel query --ciks 0000320193 --compare-years --run-dir <run_dir> --output json
Then the command exits with code 0
  And results[0].analytics.change_velocity is a float between 0.0 and 1.0
  And results[0].analytics.emerging_topics is a list (may be empty)
```

### Scenario: Low change velocity (copy-paste filing) is distinguishable from high change velocity

```gherkin
Given a corpus containing:
  - "CompanyA" with year_N and year_{N-1} filings that are 95% identical by cosine similarity
  - "CompanyB" with year_N and year_{N-1} filings that are 60% similar (40% new content)
When the user queries --compare-years for both companies
Then results for CompanyA have analytics.change_velocity <= 0.10
  And results for CompanyB have analytics.change_velocity >= 0.35
```

### Scenario: Filing with no prior year returns null velocity, not an error

```gherkin
Given a corpus where CIK "0007777777" has only one filing year
When the user runs:
  python -m sec_intel query --ciks 0007777777 --compare-years --run-dir <run_dir>
Then the command exits with code 0
  And results[0].analytics.change_velocity is null
  And results[0].analytics.emerging_topics is null
  And a warning is printed to stderr: "No prior-year filing found for CIK 0007777777; change velocity unavailable"
```

### Scenario: Emerging topics correctly identify new risk themes

```gherkin
Given a corpus where CompanyB's 2021 filing contains multiple segments about "ransomware"
  And CompanyB's 2020 filing contains no segments with cosine similarity > 0.70 to those segments
When the user queries --compare-years for CompanyB
Then "ransomware" or a semantically equivalent label appears in analytics.emerging_topics
```

---

## Technical Notes

- **CLI flag:** `--compare-years` implemented in `src/cli/query.py` (PRD-004 Phase 5)
- **Comparator:** `src/inference/comparator.py` — cosine similarity on TF-IDF or sentence embeddings of concatenated segment text per filing year
- **Velocity score definition:** `change_velocity = 1 − cosine_similarity(text_year_N, text_year_{N−1})`; range 0.0 (identical) to 1.0 (no overlap)
- **Emerging topics source:** `src/inference/topic_model.py` — topics present in year_N with cosine distance > 0.30 from all topics in year_{N−1} for same CIK
- **Algorithm choice:** See PRD-004 Q-06 (LDA vs. BERTopic); default to LDA in Phase 5
- **Current status:** Blocked on PRD-004 Phase 5 (comparator + topic modeler)
