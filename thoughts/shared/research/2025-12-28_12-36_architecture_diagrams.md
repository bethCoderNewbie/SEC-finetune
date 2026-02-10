# Architecture Diagrams & Visual Reference

**Visual representation of PR automation system**

---

## 1. System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     Developer Pushes Code to PR                   │
└──────────────────────┬───────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│              GitHub Actions Workflow Triggered                    │
│                      (ci.yml)                                     │
└──────────────────────┬───────────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
    ┌────────┐   ┌────────┐   ┌──────────────┐
    │  Lint  │   │ Tests  │   │  Validation  │  ◄─── NEW JOB
    │        │   │        │   │              │
    └────────┘   └────────┘   └──────┬───────┘
                                     │
                                     ▼
                        ┌────────────────────────┐
                        │ Run Preprocessing      │
                        │ Validation Script      │
                        │ (batch_validate)       │
                        └────────┬───────────────┘
                                 │
                                 ▼
                        ┌────────────────────────┐
                        │ JSON Report            │
                        │ (validation_report     │
                        │  .json)                │
                        └────────┬───────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
              ┌──────────┐  ┌──────────┐  ┌──────────┐
              │ Generate │  │ Create   │  │ Upload   │
              │ Markdown │  │ Check    │  │ Artifacts│
              │ Report   │  │ Run      │  │          │
              └────┬─────┘  └────┬─────┘  └──────────┘
                   │             │
                   └──────┬──────┘
                          ▼
                ┌─────────────────────────┐
                │ Post Comment on PR      │
                │ (GitHub API)            │
                └─────────────────────────┘
                          │
                          ▼
        ┌─────────────────────────────────────┐
        │  PR Visible with:                   │
        │  1. Comment (validation results)    │
        │  2. Check (pass/fail status)        │
        │  3. Artifacts (reports for review)  │
        └─────────────────────────────────────┘
```

---

## 2. Data Flow

```
VALIDATION SCRIPTS (EXISTING)
    │
    ├─ preprocessing_batch.py
    │  └─ Input: data/processed/20251228_*/
    │  └─ Output: validation_report.json
    │      {
    │        "status": "PASS|WARN|FAIL",
    │        "blocking_summary": {...},
    │        "validation_table": [...]
    │      }
    │
    └─ Output Location: reports/validation_report.json
              │
              ▼
    MARKDOWN REPORTER (NEW)
    src/utils/markdown_reporter.py
              │
              ├─ Input: JSON report
              │
              ├─ Processing:
              │  ├─ Generate header (status badge)
              │  ├─ Create summary box
              │  ├─ Build validation tables
              │  ├─ Add visual indicators (✓, ⚠, ✗)
              │  └─ Format collapsible sections
              │
              └─ Output: GitHub-flavored markdown
                   │
                   ▼
    GITHUB ACTIONS WORKFLOW (UPDATED)
    .github/workflows/ci.yml
                   │
                   ├─ Step 1: Generate markdown
                   │
                   ├─ Step 2: Comment on PR
                   │   └─ POST /repos/{owner}/{repo}/issues/{number}/comments
                   │
                   ├─ Step 3: Create check run
                   │   └─ POST /repos/{owner}/{repo}/check-runs
                   │
                   └─ Step 4: Upload artifacts
                       └─ Store validation_report.json & .md
                           │
                           ▼
                  GITHUB PR INTERFACE
                  ├─ PR Comment (with markdown)
                  ├─ Check Status (pass/fail)
                  └─ Artifacts Tab (for detailed review)
```

---

## 3. File Processing Pipeline

```
INPUT (Existing Validation Script)
┌─────────────────────────────────────┐
│ check_preprocessing_batch.py         │
│ ├─ Loads JSON files from data/      │
│ ├─ Runs HealthCheckValidator        │
│ └─ Outputs: validation_report.json  │
└──────────────┬──────────────────────┘
               │
               ▼
PROCESSING (New Markdown Reporter)
┌──────────────────────────────────────────┐
│ MarkdownReporter.generate()               │
│                                          │
│ 1. Header Section                        │
│    ├─ Title with emoji                   │
│    ├─ Status badge                       │
│    ├─ Timestamp                          │
│    └─ Run ID                             │
│                                          │
│ 2. Summary Box                           │
│    ├─ Total checks                       │
│    ├─ Passed count                       │
│    ├─ Failed count                       │
│    └─ Warned count                       │
│                                          │
│ 3. Blocking Checks Section               │
│    └─ Table of critical metrics          │
│                                          │
│ 4. Full Results Section                  │
│    └─ Table of all validation results    │
│       (collapsible if large)             │
│                                          │
│ 5. Issues Section                        │
│    ├─ Failed files (if any)              │
│    └─ Warned files (if any)              │
│                                          │
│ 6. Footer Section                        │
│    └─ Action items & instructions        │
└──────────────┬───────────────────────────┘
               │
               ▼
OUTPUT
┌──────────────────────────────────────┐
│ validation_report.md                  │
│                                       │
│ # Validation Report ✅                │
│                                       │
│ **Status:** ![PASS](...)              │
│ **Run Time:** 2025-12-28 15:30:00    │
│                                       │
│ > **Validation Summary**              │
│ > - Total Checks: 7                   │
│ > - ✅ Passed: 7                      │
│ > - ❌ Failed: 0                      │
│ > - ⚠️ Warned: 0                      │
│                                       │
│ ## Blocking Checks                    │
│ | Status | Metric | Actual | Target |│
│ | ✓ PASS | ... | ... | ... |        │
│                                       │
│ ...                                   │
└──────────────┬──────────────────────┘
               │
               ▼
DESTINATION
┌────────────────────────────────────┐
│ GitHub PR Interface                 │
│                                    │
│ ├─ Comment Tab                     │
│ │  └─ Rendered markdown report     │
│ │                                  │
│ ├─ Checks Tab                      │
│ │  └─ "Data Validation" check      │
│ │     with status & summary        │
│ │                                  │
│ └─ Artifacts                       │
│    └─ validation_reports-{id}.zip  │
│       ├─ validation_report.json    │
│       └─ validation_report.md      │
└────────────────────────────────────┘
```

---

## 4. GitHub Actions Job Dependencies

```
WORKFLOW: ci.yml
│
├─ PARALLEL JOBS (Independent)
│
│  ┌──────────────────┐
│  │  lint            │
│  │ (ruff check)     │
│  └──────────────────┘
│
│  ┌──────────────────┐
│  │  unit-tests      │
│  │ (pytest)         │
│  └──────────────────┘
│
│  ┌──────────────────────────────────────────┐
│  │  validate-preprocessing (NEW)             │
│  │                                          │
│  │  Steps (Sequential):                     │
│  │  ├─ Checkout code                        │
│  │  ├─ Setup Python                         │
│  │  ├─ Install dependencies                 │
│  │  ├─ Run validation                       │
│  │  │  └─ Outputs: validation_report.json   │
│  │  ├─ Generate markdown                    │
│  │  │  └─ Outputs: validation_report.md     │
│  │  ├─ Post PR comment (if PR event)        │
│  │  │  └─ Uses: actions/github-script       │
│  │  ├─ Create check run (if PR event)       │
│  │  │  └─ Uses: GitHub API                  │
│  │  └─ Upload artifacts                     │
│  │     └─ Uses: actions/upload-artifact     │
│  └──────────────────────────────────────────┘
│
└─ All jobs complete ─→ Workflow completes
```

---

## 5. Markdown Output Structure

```
MARKDOWN REPORT HIERARCHY
│
├─ H1: Main Title with Emoji
│   └─ # Validation Report ✅
│
├─ Metadata Section
│   ├─ Status Badge (shields.io)
│   ├─ Run Time (ISO format)
│   └─ Run ID (tracking)
│
├─ Summary Box (quoted section)
│   ├─ Total Checks
│   ├─ Passed count
│   ├─ Failed count
│   ├─ Warned count
│   └─ [Status line]
│
├─ H2: Blocking Checks Section
│   └─ Table
│       ├─ Status (icon)
│       ├─ Metric name
│       ├─ Actual value
│       └─ Target value
│
├─ H2: Full Results Section
│   └─ Table (collapsible if >15 rows)
│       ├─ Status
│       ├─ Category
│       ├─ Metric
│       ├─ Actual
│       └─ Target
│
├─ H2: Issues Section (if any failures/warnings)
│   ├─ H3: Failed Files
│   │   └─ Bulleted list
│   └─ H3: Warned Files
│       └─ Bulleted list
│
├─ Horizontal Rule (---)
│
└─ Footer
    └─ Action items
    └─ Generated by system
```

---

## 6. Status Icons & Visual Mapping

```
VALIDATION STATUS → MARKDOWN ICON → VISUAL APPEARANCE
│
├─ PASS       → ✓  PASS  → Green background (success)
│             → ✅         (emoji variant)
│
├─ WARN       → ⚠ WARN  → Yellow background (caution)
│             → ⚠️         (emoji variant)
│
├─ FAIL       → ✗ FAIL  → Red background (error)
│             → ❌         (emoji variant)
│
├─ SKIP       → ⊘ SKIP  → Gray background (skipped)
│             → ⊙          (emoji variant)
│
└─ ERROR      → ❌ ERR   → Red background (critical)
              → 🚨        (emoji variant)

TABLE FORMAT
┌─────────────┬─────────┬───────────┬──────────┐
│ Status      │ Metric  │ Actual    │ Target   │
├─────────────┼─────────┼───────────┼──────────┤
│ ✓ PASS 4sp  │ Name    │ 0.9800    │ 0.9900   │
│ ⚠ WARN 4sp  │ Name    │ 0.1500    │ 0.2000   │
│ ✗ FAIL 4sp  │ Name    │ 0.0100    │ 0.5000   │
└─────────────┴─────────┴───────────┴──────────┘

CATEGORY EMOJI
├─ 🔐 identity      (CIK, company name)
├─ 🧹 cleanliness   (HTML, page numbers)
├─ 📦 substance     (segments, content)
├─ 🔍 extraction    (section extraction)
├─ 📄 parsing       (SEC filing parsing)
├─ ✨ features      (sentiment, readability)
├─ 🔧 code_quality  (code validation)
└─ ⚡ performance   (latency, throughput)
```

---

## 7. GitHub PR Interface Layout

```
PULL REQUEST VIEW
┌─────────────────────────────────────────────────────┐
│  PR #123: Add new preprocessing feature             │
│  by @developer_name                                 │
├─────────────────────────────────────────────────────┤
│                                                     │
│  [Conversation] [Commits] [Changes] [Checks]       │
│                                                     │
│  ┌─────────────────────────────────────────────────┤
│  │ Checks (1 job)                                  │
│  │                                                 │
│  │ ✓ Data Validation                      Neutral  │
│  │   Validation Report                             │
│  │   [View details]                                │
│  └─────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────────────────────────────────────────────┤
│  │ All conversations (1)                           │
│  │                                                 │
│  │ @github-actions[bot]                            │
│  │ posted 2 minutes ago                            │
│  │                                                 │
│  │ ┌─────────────────────────────────────────────┐ │
│  │ │ # Validation Report ✅                      │ │
│  │ │                                             │ │
│  │ │ **Status:** ![PASS](...)                    │ │
│  │ │ **Run Time:** 2025-12-28 15:30:00 UTC      │ │
│  │ │                                             │ │
│  │ │ > **Validation Summary**                    │ │
│  │ │ > - Total Checks: 7                         │ │
│  │ │ > - ✅ Passed: 7                            │ │
│  │ │ > - ❌ Failed: 0                            │ │
│  │ │ > - ⚠️ Warned: 0                            │ │
│  │ │                                             │ │
│  │ │ ## Blocking Checks                          │ │
│  │ │ | Status | Metric | Actual | Target |      │ │
│  │ │ |--------|--------|--------|--------|      │ │
│  │ │ | ✓ PASS | CIK Rate | 99.80% | 99.00% |  │ │
│  │ │ ...                                         │ │
│  │ └─────────────────────────────────────────────┘ │
│  │                                                 │
│  │ [View on GitHub]  [Edit]  [Hide]               │
│  └─────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────────────────────────────────────────────┤
│  │ Artifacts (1)                                   │
│  │                                                 │
│  │ validation-reports-12345                        │
│  │ [Download] (30 days retention)                  │
│  │                                                 │
│  │ Contains:                                       │
│  │  - validation_report.json (structured data)     │
│  │  - validation_report.md (rendered markdown)     │
│  └─────────────────────────────────────────────────┤
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## 8. Implementation Phase Diagram

```
PHASE 1: Markdown Reporter (15 min)
┌──────────────────────────────────┐
│ 1. Copy MarkdownReporter class    │
│    to src/utils/markdown_         │
│    reporter.py                    │
│                                  │
│ 2. Test generation locally:      │
│    python -c "                   │
│      from src.utils....          │
│      generate_markdown_report()  │
│    "                             │
│                                  │
│ Result: Markdown generation ✅   │
└──────────────────────────────────┘
                │
                ▼
PHASE 2: Update Workflow (10 min)
┌──────────────────────────────────┐
│ 1. Add validate-preprocessing    │
│    job to ci.yml                 │
│                                  │
│ 2. Run validation script          │
│                                  │
│ 3. Generate markdown from JSON   │
│                                  │
│ 4. Post PR comment with results  │
│                                  │
│ Result: Workflow updated ✅      │
└──────────────────────────────────┘
                │
                ▼
PHASE 3: Test Locally (5 min)
┌──────────────────────────────────┐
│ 1. Run validation script on       │
│    sample data                    │
│                                  │
│ 2. Generate markdown             │
│                                  │
│ 3. Verify formatting and         │
│    content                        │
│                                  │
│ Result: Testing complete ✅      │
└──────────────────────────────────┘
                │
                ▼
PHASE 4: Deploy (5 min)
┌──────────────────────────────────┐
│ 1. Commit to feature branch       │
│                                  │
│ 2. Push and create PR             │
│                                  │
│ 3. Verify automation works        │
│                                  │
│ 4. Merge to main                  │
│                                  │
│ Result: Live in production ✅     │
└──────────────────────────────────┘
                │
                ▼
       🎉 COMPLETE 🎉
     (Total: 35 minutes)
```

---

## 9. Decision Tree

```
START: Do you need validation reporting?
│
├─ YES
│  │
│  ├─ Is this pure data pipeline (non-ML)?
│  │  │
│  │  ├─ YES → GitHub Actions ✅ (Recommended)
│  │  │        Quick, simple, no dependencies
│  │  │
│  │  └─ NO → Are you using ML models?
│  │      │
│  │      ├─ YES → GitHub Actions OR CML
│  │      │        CML better for experiments
│  │      │
│  │      └─ NO → GitHub Actions (default)
│  │
│  └─ Do you need experiment comparison?
│     │
│     ├─ YES → CML ⭐ (experiment tracking)
│     │
│     └─ NO → GitHub Actions ✅
│
└─ NO → No action needed

YOUR PROJECT:
Data preprocessing pipeline (non-ML)
├─ Pure data validation ✅
├─ No ML models ✅
├─ No experiment tracking needed ✅
└─ DECISION: GitHub Actions ✅✅✅
```

---

## 10. Integration Checklist

```
PRE-IMPLEMENTATION
├─ [ ] Have GitHub Actions enabled
├─ [ ] validation_report.json is being generated
├─ [ ] Can run validation script manually
└─ [ ] Have write access to .github/workflows/

IMPLEMENTATION
├─ [ ] Copy MarkdownReporter to src/utils/
├─ [ ] Update .github/workflows/ci.yml
├─ [ ] Run local test of markdown generation
├─ [ ] Commit both files
└─ [ ] Push to feature branch

TESTING
├─ [ ] Create PR from feature branch
├─ [ ] Verify workflow runs
├─ [ ] Check for markdown comment on PR
├─ [ ] Verify check run appears
├─ [ ] Download and inspect artifacts
└─ [ ] Review formatting and content

DEPLOYMENT
├─ [ ] Review changes with team
├─ [ ] Merge to main
├─ [ ] Verify next PR shows validation
├─ [ ] Monitor first few PRs
└─ [ ] Document in team wiki/docs

POST-DEPLOYMENT
├─ [ ] Share with team how to use reports
├─ [ ] Create runbook for troubleshooting
├─ [ ] Plan future enhancements
└─ [ ] Celebrate! 🎉
```

---

## Summary

These diagrams show:
1. **System Architecture** - How all components fit together
2. **Data Flow** - JSON → Markdown → PR Comment
3. **File Processing** - Input validation through output display
4. **Job Dependencies** - Parallel execution strategy
5. **Markdown Structure** - Report formatting hierarchy
6. **Visual Indicators** - Status icons and emoji meanings
7. **PR Interface** - What users will see
8. **Implementation Phases** - Timeline to production
9. **Decision Tree** - Why GitHub Actions is recommended
10. **Integration Checklist** - Verification steps

Reference these diagrams when implementing or explaining the system to team members.

