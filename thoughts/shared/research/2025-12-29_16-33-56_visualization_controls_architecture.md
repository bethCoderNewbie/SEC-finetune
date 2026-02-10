---
date: 2025-12-29T16:33:56-06:00
researcher: bethCoderNewbie
git_commit: 648bf25
branch: main
repository: SEC finetune
topic: "Visualization and Controls Architecture for Data Health Checks and Feature Extraction"
tags: [research, architecture, visualization, ui-ux, data-health, feature-extraction]
status: complete
last_updated: 2025-12-29
last_updated_by: bethCoderNewbie
---

# Research: Visualization and Controls Architecture for Data Health Checks and Feature Extraction

**Date**: 2025-12-29T16:33:56-06:00
**Researcher**: bethCoderNewbie
**Git Commit**: 648bf25
**Branch**: main
**Repository**: SEC finetune
**Topic**: Visualization and Controls Architecture for Data Health Checks and Feature Extraction
**tags**: [research, architecture, visualization, ui-ux, data-health, feature-extraction]
**status**: complete
**last_updated**: 2025-12-29
**last_updated_by**: bethCoderNewbie

## Research Question

Design a comprehensive visualization and control system that:
1. **Visualizes data health checks** across all validation layers (extraction, preprocessing, features)
2. **Monitors systematic extraction quality issues** including size anomalies, noise contamination, and boundary detection failures
3. **Provides interactive UX/UI controls** for configuring feature extraction parameters
4. **Enables real-time monitoring** of pipeline quality metrics with anomaly detection
5. **Supports future extensibility** for additional features and validation metrics

## Summary

The current validation architecture produces comprehensive JSON reports across 4 validation layers (extraction QA, preprocessing health check, feature validation, test results), but lacks a unified visualization dashboard. This research proposes a **Data Health & Control Center** - a Streamlit-based dashboard that consolidates all validation outputs and provides interactive controls for feature extraction configuration.

**Key Insight**: The existing `src/visualization/app.py` provides a foundation (risk classification MVP), but we need a separate **validation-focused dashboard** that serves a different user persona (data scientists monitoring pipeline health vs. end-users analyzing individual filings).

## Current State Analysis

### Existing Visualization Infrastructure

**Current Dashboard** - `src/visualization/app.py`:
* **Purpose**: Risk classification MVP for end-users
* **Features**:
  - File selection from `data/raw/`
  - Pipeline execution (parse → extract → clean → segment → classify)
  - Results display (category distribution, confidence scores, segment viewer)
  - CSV export
* **Technology**: Streamlit with Paper Dashboard color scheme
* **Limitations**:
  - Single-file focused (no batch monitoring)
  - No validation metrics visualization
  - No configuration controls
  - No historical trend analysis

### Validation Output Ecosystem

The validation system produces 4 types of JSON reports:

#### 1. Extraction QA Reports
**Location**: `data/interim/extracted/{run_id}/extractor_qa_report.json`
**Size**: ~784KB for 309 files
**Schema**:
```json
{
  "status": "PASS|FAIL",
  "timestamp": "ISO-8601",
  "run_directory": "path",
  "metadata": {"git_commit": "...", "platform": "..."},
  "total_files": 309,
  "files_validated": 309,
  "overall_summary": {
    "passed": 285,
    "warned": 0,
    "failed": 24,
    "errors": 0
  },
  "metric_statistics": {
    "section_boundary_precision_start": {...},
    "section_boundary_precision_end": {...},
    "key_item_recall": {...},
    "false_positive_rate": {...},
    "toc_filtering_rate": {...}
  },
  "per_file_results": [...]
}
```

**Visualization Opportunities**:
- Pass/fail/warn distribution pie chart
- Metric statistics histograms (precision, recall, FPR)
- Per-file heatmap (file × metric)
- Trend analysis across multiple runs

#### 2. Preprocessing Health Check Reports
**Location**: `data/processed/{run_id}/validation_report.json`
**Size**: ~619KB
**Schema**:
```json
{
  "status": "PASS|FAIL",
  "timestamp": "ISO-8601",
  "overall_summary": {"passed": 0, "warned": 0, "failed": 0, "errors": 0},
  "blocking_summary": {
    "total_blocking": 0,
    "passed": 0,
    "failed": 0,
    "all_pass": true
  },
  "per_file_results": [
    {
      "file": "filename",
      "overall_status": "PASS",
      "validation_results": [
        {
          "category": "identity_completeness",
          "metric": "cik_present_rate",
          "display_name": "CIK Present Rate",
          "target": 1.0,
          "actual": 1.0,
          "status": "PASS",
          "go_no_go": "GO"
        }
      ]
    }
  ]
}
```

**Validation Categories**:
1. **Identity Completeness**: CIK, company name, SIC code presence
2. **Data Cleanliness**: HTML artifacts, page numbers
3. **Content Substance**: Empty segments, short segments
4. **Domain Rules**: Duplicates, risk keywords

**Visualization Opportunities**:
- Go/No-Go dashboard with color-coded statuses
- Category performance radar chart
- Blocking failures priority list
- Per-file validation heatmap

#### 3. NLP Feature Validation Reports
**Location**: `data/processed/{run_id}/nlp_validation_report.json`
**Size**: ~7KB
**Schema**:
```json
{
  "status": "FAIL",
  "timestamp": "ISO-8601",
  "aggregate_metrics": {
    "avg_lm_hit_rate": 0.0234,
    "avg_zero_vector_rate": 0.42,
    "avg_unc_neg_corr": 0.58,
    "avg_gunning_fog": 23.4,
    "avg_fk_fog_corr": 0.89
  },
  "per_file_results": [
    {
      "sentiment_metrics": {...},
      "readability_metrics": {...},
      "validation_results": [...],
      "blocking_failures": ["gunning_fog_in_range"]
    }
  ]
}
```

**Metrics Tracked**:
- **Sentiment**: LM hit rate, zero-vector rate, polarity, uncertainty-negative correlation
- **Readability**: Gunning Fog, FK-Fog correlation, financial adjustment delta, obfuscation score

**Visualization Opportunities**:
- Metric distribution histograms (Gunning Fog range)
- Target vs. actual comparison bar charts
- Correlation scatter plots (uncertainty vs. negative)
- Sentiment profile heatmap (file × category)

#### 4. Test Results
**Location**: `tests/outputs/{run_id}/test_results.json`
**Schema**:
```json
{
  "run_id": "...",
  "timestamp": "...",
  "total": 50,
  "passed": 48,
  "failed": 2,
  "skipped": 0,
  "details": {
    "passed": [{"nodeid": "...", "duration": 0.5}],
    "failed": [...],
    "skipped": [],
    "errors": []
  }
}
```

**Visualization Opportunities**:
- Test pass rate trend over time
- Test duration analysis
- Failed test drill-down

### Feature Extraction Configuration System

The system has 3 feature extractors with YAML configs:

#### 1. Sentiment Analysis (`configs/features/sentiment.yaml`)
**Configurable Parameters**:
- `active_categories`: Subset of 8 LM categories to extract
- `text_processing.case_sensitive`: Case matching mode
- `text_processing.lemmatize`: Apply lemmatization
- `text_processing.remove_stopwords`: Stopword removal
- `normalization.method`: count | tfidf | log
- `features.include_counts/ratios/tfidf/proportions`: Feature set selection
- `processing.batch_size`: Batch processing size
- `processing.parallel_workers`: Parallelization level

#### 2. Readability Analysis (`configs/features/readability.yaml`)
**Configurable Parameters**:
- `indices.include_*`: Toggle 6 standard indices + obfuscation score
- `text_processing.min_text_length`: Minimum text length threshold
- `adjustments.use_financial_adjustments`: Financial domain exception list
- `obfuscation_weights.*`: Custom weights for obfuscation score
- `validation.strict_text_length`: Error vs. warning mode
- `expected_ranges.*`: Custom validation ranges

#### 3. Topic Modeling (`configs/features/topic_modeling.yaml`)
**Configurable Parameters**:
- `model.num_topics`: Number of latent topics
- `model.passes/iterations`: Training hyperparameters
- `preprocessing.min_word_length/max_word_length`: Word filters
- `preprocessing.no_below/no_above`: Document frequency filters
- `features.dominant_threshold`: Dominant topic threshold
- `evaluation.compute_coherence`: Enable coherence computation

### Systematic Extraction Quality Issues (Critical Findings)

**Analysis Date**: 2025-12-29
**Report Analyzed**: `data/interim/extracted/20251229_140905_batch_extract_648bf25/extractor_qa_report.json`
**Files Analyzed**: 309 SEC 10-K filings

#### Overall Health Status
- **Pass Rate**: 2.3% (7/309 files) ⚠️ CRITICAL
- **Fail Rate**: 87.7% (271/309 files)
- **Primary Failure Modes**: ToC filtering (56.6%), boundary detection (52.8%)

#### Critical Anomalies Identified

**1. Extreme Size Anomalies**
- **Oversized Extractions** (>1M chars, expected: 5k-50k):
  - `CAH_10K_2024`: 8,001,069 chars (160x expected maximum)
  - `EBAY_10K_2024`: 6,661,489 chars (133x expected maximum)
  - Pattern: 10 files exceed 5M chars
- **Undersized Extractions** (<1k chars):
  - `BK_10K_*`: Consistently 175 chars across 4 years (identical size = extraction failure)
  - `BSX_10K_2022/2023`: Identical 526 chars (suspicious pattern)
  - Pattern: 9 files fail substantial content validation

**2. Extreme Noise Contamination**
- **High Noise Files** (>40% noise, expected: <15%):
  - `COST_10K_2023`: 88.82% noise (majority contamination)
  - `AMAT_10K_2020`: 66.00% noise
  - `EBAY` files: 39-62% noise (consistent pattern across years)
  - Pattern: 19 files exceed 15% noise threshold

**3. Systematic Company-Specific Failures**
- **100% Failure Rate** (all years failed): 53+ companies including AAPL, AMZN, BA, DIS
- **100% Success Rate** (all years passed): 1 company (EMR - Emerson Electric)
- **Implication**: Filing format/structure variations cause systematic extraction failures

**4. ToC Filtering Failure**
- **Failure Rate**: 56.6% (175/309 files)
- **Impact**: Table of Contents contamination in extracted text
- **Most Common Single Failure**: 93 files (34.3%) fail only ToC filtering

**5. Boundary Detection Issues**
- **Failure Rate**: 52.8% (163/309 files)
- **Binary Scoring**: Scores are strictly 0.0 or 1.0 (no partial success)
- **Implication**: Algorithm threshold issue preventing graceful degradation

**Dashboard Requirements**:
✅ Real-time anomaly detection for size outliers (>10x expected)
✅ Noise contamination heatmap (file × year with color gradient)
✅ Company-level failure pattern tracking
✅ ToC filtering effectiveness monitor
✅ Boundary detection score distribution visualization
✅ Automatic alerts for critical failures (>80% noise, <200 chars, 100% company failure)

### Gap Analysis

**What Exists**:
✅ Comprehensive validation reports (JSON format)
✅ Feature extraction configs (YAML format)
✅ Basic visualization MVP (risk classification)
✅ Color-coded UI theme (Paper Dashboard)

**What's Missing**:
❌ Validation metrics dashboard
❌ Systematic extraction quality monitoring
❌ Anomaly detection and alerting system
❌ Company-level failure pattern tracking
❌ Historical trend tracking
❌ Interactive configuration controls
❌ Batch run comparison
❌ Real-time monitoring during pipeline execution
❌ Export/reporting capabilities for validation results
❌ Feature extraction parameter tuning interface
❌ Size distribution analyzer (detect 160x oversized extractions)
❌ Noise contamination heatmap (detect 88% noise files)

## Proposed Architecture

### System Name: Data Health & Control Center (DHCC)

**Purpose**: Unified dashboard for monitoring pipeline health and configuring feature extraction.

**User Personas**:
1. **Data Scientists**: Monitor validation metrics, debug failures, tune extraction parameters
2. **MLOps Engineers**: Track pipeline performance, identify regressions, configure CI/CD thresholds
3. **Researchers**: Analyze feature distributions, experiment with extraction configs

### Directory Structure

```
src/visualization/
├── __init__.py
├── app.py                          # ✅ EXISTING: Risk classification MVP
├── dhcc/                           # 🆕 NEW: Data Health & Control Center
│   ├── __init__.py
│   ├── app.py                      # Main dashboard application
│   ├── pages/                      # Multi-page app structure
│   │   ├── 1_📊_Validation_Dashboard.py
│   │   ├── 2_🔴_Extraction_Quality_Monitor.py  # 🆕 NEW: Systematic quality issues
│   │   ├── 3_⚙️_Extraction_Controls.py
│   │   ├── 4_📈_Trend_Analysis.py
│   │   └── 5_🔍_File_Inspector.py
│   ├── components/                 # Reusable UI components
│   │   ├── __init__.py
│   │   ├── metrics_card.py
│   │   ├── status_indicator.py
│   │   ├── heatmap_viewer.py
│   │   ├── config_editor.py
│   │   ├── report_exporter.py
│   │   ├── anomaly_detector.py     # 🆕 NEW: Detect size/noise anomalies
│   │   ├── size_analyzer.py        # 🆕 NEW: Character count distribution
│   │   ├── noise_heatmap.py        # 🆕 NEW: Noise contamination visualization
│   │   └── company_failure_tracker.py  # 🆕 NEW: Company-level patterns
│   ├── data_loaders/               # Data loading utilities
│   │   ├── __init__.py
│   │   ├── validation_loader.py
│   │   ├── feature_loader.py
│   │   └── test_loader.py
│   └── utils/                      # Helper functions
│       ├── __init__.py
│       ├── report_aggregator.py
│       ├── threshold_checker.py
│       ├── trend_calculator.py
│       ├── anomaly_detector.py     # 🆕 NEW: Statistical anomaly detection
│       └── alert_generator.py      # 🆕 NEW: Generate alerts for critical issues

configs/visualization/              # 🆕 NEW: Visualization configs
└── dhcc.yaml                       # Dashboard configuration

scripts/utils/visualization/        # 🆕 NEW: Visualization utilities
├── aggregate_validation_reports.py # Aggregate reports across runs
└── export_dashboard_report.py      # Export dashboard state to PDF/HTML
```

### Page Designs

#### Page 1: Validation Dashboard (📊)

**Purpose**: Real-time view of validation status across all layers

**Layout**:
```
┌────────────────────────────────────────────────────────────┐
│ Data Health & Control Center                               │
│ Last Updated: 2025-12-29 16:33:56 | Run: 648bf25          │
├────────────────────────────────────────────────────────────┤
│ Overall Status                                             │
│ ┌─────────────┬─────────────┬─────────────┬─────────────┐ │
│ │ Extraction  │ Preprocessing│   Features  │    Tests    │ │
│ │    🟢 PASS  │    🟡 WARN   │    🔴 FAIL  │   🟢 PASS   │ │
│ │  285/309    │   300/309    │   150/309   │   48/50     │ │
│ └─────────────┴─────────────┴─────────────┴─────────────┘ │
├────────────────────────────────────────────────────────────┤
│ Go/No-Go Metrics (Blocking Failures)                       │
│ ┌──────────────────────────────────────────────────────┐   │
│ │ ❌ gunning_fog_in_range: 24 files exceed threshold   │   │
│ │ ❌ key_item_recall: 12 files below 90%               │   │
│ │ ⚠️  html_artifact_rate: 5 files have >1% artifacts   │   │
│ └──────────────────────────────────────────────────────┘   │
├────────────────────────────────────────────────────────────┤
│ Metric Distribution                                         │
│ [Histogram: Gunning Fog Scores]   [Histogram: LM Hit Rate] │
│                                                             │
│ [Heatmap: Files × Validation Metrics]                      │
└────────────────────────────────────────────────────────────┘
```

**Data Sources**:
- Latest `extractor_qa_report.json`
- Latest `validation_report.json`
- Latest `nlp_validation_report.json`
- Latest `test_results.json`

**Interactions**:
- Click on metric card → drill down to file-level details
- Click on blocking failure → show affected files
- Hover on heatmap cell → show metric details

#### Page 2: Extraction Quality Monitor (🔴)

**Purpose**: Monitor systematic extraction quality issues and anomalies

**Layout**:
```
┌────────────────────────────────────────────────────────────┐
│ Extraction Quality Monitor - Critical Issues              │
│ Last Run: 2025-12-29 14:09:05 | Files: 309 | Pass: 2.3% │
├────────────────────────────────────────────────────────────┤
│ 🚨 Critical Alerts                                         │
│ ┌──────────────────────────────────────────────────────┐   │
│ │ ❌ CRITICAL: 87.7% overall failure rate (271/309)    │   │
│ │ ❌ SIZE ANOMALY: CAH_10K_2024 (8.0M chars, 160x max) │   │
│ │ ❌ NOISE: COST_10K_2023 (88.82% noise contamination) │   │
│ │ ⚠️  PATTERN: BK ticker (175 chars × 4 years = fail)  │   │
│ └──────────────────────────────────────────────────────┘   │
├────────────────────────────────────────────────────────────┤
│ Size Distribution Analysis                                 │
│ ┌─────────────────────────────────────────────────────┐    │
│ │ [Box Plot: Character Count Distribution]            │    │
│ │  • Expected range: 5k-50k chars (green zone)        │    │
│ │  • Oversized outliers: 10 files >1M chars (red)     │    │
│ │  • Undersized outliers: 9 files <1k chars (red)     │    │
│ │                                                       │    │
│ │ Top Oversized:                                        │    │
│ │  • CAH_10K_2024: 8,001,069 chars (160x)             │    │
│ │  • EBAY_10K_2024: 6,661,489 chars (133x)            │    │
│ │  • EBAY_10K_2022: 6,599,379 chars (132x)            │    │
│ │                                                       │    │
│ │ Top Undersized:                                       │    │
│ │  • BK_10K_2021/2022/2024/2025: 175 chars (0.0035x)  │    │
│ │  • BSX_10K_2022/2023: 526 chars (0.01x)             │    │
│ └─────────────────────────────────────────────────────┘    │
├────────────────────────────────────────────────────────────┤
│ Noise Contamination Heatmap                                │
│ [Heatmap: Company (rows) × Year (cols), Color = Noise %]  │
│  • COST: ░░░░█ (2023: 88.82% noise)                       │
│  • AMAT: ░░░░░ (2020: 66.00% noise)                       │
│  • EBAY: ▓▓▓▓▓ (39-62% noise across all years)            │
│  • CAH:  ▓▓▓▓▓ (37-43% noise across all years)            │
│  • Legend: ░ <15% ▒ 15-40% ▓ 40-60% █ >60%               │
├────────────────────────────────────────────────────────────┤
│ Company-Level Failure Patterns                             │
│ ┌─────────────────────────────────────────────────────┐    │
│ │ 100% Failure Rate (53+ companies):                   │    │
│ │ • AAPL, AMZN, BA, BAC, DIS, FDX... [View All]       │    │
│ │                                                       │    │
│ │ 100% Success Rate (1 company):                       │    │
│ │ • EMR (Emerson Electric) ✓ 5/5 files passed         │    │
│ │                                                       │    │
│ │ [Bar Chart: Companies by Success Rate]               │    │
│ └─────────────────────────────────────────────────────┘    │
├────────────────────────────────────────────────────────────┤
│ Failure Mode Breakdown                                     │
│ [Stacked Bar Chart: Failure Combinations]                  │
│  • ToC filtering only: 93 files (34.3%)                   │
│  • Boundary precision only: 82 files (30.3%)              │
│  • Both ToC + Boundary: 67 files (24.7%)                  │
│  • Noise ratio: 8 files (3.0%)                            │
│  • Other combinations: 21 files (7.7%)                    │
├────────────────────────────────────────────────────────────┤
│ Boundary Detection Score Distribution                      │
│ [Histogram: Section Boundary Precision End Scores]        │
│  • Binary distribution: 146 files at 1.0, 163 at 0.0     │
│  • ⚠️  NO PARTIAL SCORES (algorithm threshold issue)      │
│  • Mean: 0.472 | Median: 0.000                            │
└────────────────────────────────────────────────────────────┘
```

**Data Sources**:
- `extractor_qa_report.json` - All metrics and per-file results
- Statistical analysis: character counts, noise ratios, boundary scores
- Company-level aggregation: group by ticker, calculate pass rates

**Interactions**:
- Click on oversized file → view extraction details
- Click on company name → show all years for that company
- Click on failure combination → filter to affected files
- Hover on heatmap cell → show exact noise % and file name
- Export button → generate "Critical Issues Report.pdf"

**Alerting Logic**:
```python
CRITICAL_THRESHOLDS = {
    "overall_pass_rate": 0.50,        # Alert if <50%
    "size_outlier_multiplier": 10,    # Alert if >10x expected
    "noise_threshold": 0.80,          # Alert if >80% noise
    "undersized_chars": 200,          # Alert if <200 chars
    "company_failure_rate": 1.0,      # Alert if 100% failure for company
    "toc_failure_rate": 0.50,         # Alert if ToC fails >50%
    "boundary_binary_ratio": 0.95     # Alert if >95% scores are 0 or 1
}
```

#### Page 3: Extraction Controls (⚙️)

**Purpose**: Interactive configuration editor for feature extraction

**Layout**:
```
┌────────────────────────────────────────────────────────────┐
│ Feature Extraction Configuration                           │
├────────────────────────────────────────────────────────────┤
│ Feature Type:  [Sentiment ▼] [Readability] [Topic Modeling]│
├────────────────────────────────────────────────────────────┤
│ Sentiment Analysis Settings                                │
│ ┌────────────────────────────────────────────────────────┐ │
│ │ Active Categories (5/8 selected)                       │ │
│ │ ☑ Negative  ☑ Positive  ☑ Uncertainty  ☑ Litigious   │ │
│ │ ☑ Constraining  ☐ Strong_Modal  ☐ Weak_Modal          │ │
│ │ ☐ Complexity                                           │ │
│ │                                                         │ │
│ │ Text Processing                                        │ │
│ │ Case Sensitive:     ○ Yes  ● No                       │ │
│ │ Lemmatize:          ● Yes  ○ No                       │ │
│ │ Remove Stopwords:   ○ Yes  ● No                       │ │
│ │                                                         │ │
│ │ Normalization Method                                   │ │
│ │ ○ count  ● tfidf  ○ log                               │ │
│ │                                                         │ │
│ │ Features to Extract                                    │ │
│ │ ☑ Counts  ☑ Ratios  ☑ TF-IDF  ☑ Proportions          │ │
│ │                                                         │ │
│ │ Processing Performance                                 │ │
│ │ Batch Size:      [1000] ────────────                  │ │
│ │ Parallel Workers: [4]   ────────────                  │ │
│ └────────────────────────────────────────────────────────┘ │
│                                                             │
│ [Preview Impact]  [Save Configuration]  [Reset to Default] │
│                                                             │
│ Impact Estimate:                                           │
│ • Extraction time: ~15 min (↓25% from default)            │
│ • Features extracted: 25 (↓5 from default)                │
│ • Memory usage: ~2.5 GB (same as default)                 │
└────────────────────────────────────────────────────────────┘
```

**Functionality**:
- Load current config from YAML
- Interactive form controls for all parameters
- Real-time validation (e.g., ensure obfuscation weights sum to 1.0)
- Impact preview (estimate processing time/memory based on config)
- Save to new config file or overwrite existing
- Export config as JSON/YAML

**Data Sources**:
- `configs/features/*.yaml`
- Historical run metadata for impact estimation

#### Page 4: Trend Analysis (📈)

**Purpose**: Historical analysis of validation metrics across runs

**Layout**:
```
┌────────────────────────────────────────────────────────────┐
│ Validation Trend Analysis                                  │
├────────────────────────────────────────────────────────────┤
│ Time Range: [Last 30 days ▼]  Metric: [LM Hit Rate ▼]    │
├────────────────────────────────────────────────────────────┤
│ [Line Chart: LM Hit Rate over time]                        │
│   • Target threshold (horizontal line at 0.02)             │
│   • Actual values (scatter points with trend line)         │
│   • Confidence interval (shaded region)                    │
│                                                             │
│ Statistical Summary:                                        │
│ • Mean: 0.0234  • Std Dev: 0.0045  • Min: 0.015           │
│ • Max: 0.034    • Runs passing: 28/30                     │
├────────────────────────────────────────────────────────────┤
│ Multi-Metric Comparison                                    │
│ [Parallel Coordinates Plot: All metrics across latest run] │
│   • Each line = one file                                   │
│   • Axes = metrics (LM hit rate, Gunning Fog, etc.)       │
│   • Color = pass/fail status                              │
└────────────────────────────────────────────────────────────┘
```

**Functionality**:
- Load historical validation reports
- Time-series analysis of selected metrics
- Statistical summary (mean, std dev, percentiles)
- Anomaly detection (highlight outlier runs)
- Export trend data as CSV

**Data Sources**:
- All `*_validation_report.json` files in `data/processed/` and `data/interim/`
- Timestamp and git commit metadata

#### Page 5: File Inspector (🔍)

**Purpose**: Drill-down view for individual file validation results

**Layout**:
```
┌────────────────────────────────────────────────────────────┐
│ File-Level Validation Inspector                            │
├────────────────────────────────────────────────────────────┤
│ Select File: [AAPL_10K_2023.json ▼]                       │
├────────────────────────────────────────────────────────────┤
│ Overall Status: 🔴 FAIL (3 blocking failures)              │
│                                                             │
│ Validation Results:                                         │
│ ┌────────────────────────────────────────────────────────┐ │
│ │ Category          │ Metric              │ Status │ Go  │ │
│ │ Identity Complete │ CIK Present         │   🟢   │ GO  │ │
│ │ Identity Complete │ Company Name        │   🟢   │ GO  │ │
│ │ Data Cleanliness  │ HTML Artifact Rate  │   🟢   │ GO  │ │
│ │ Content Substance │ Empty Segment Rate  │   🟢   │ GO  │ │
│ │ Features          │ LM Hit Rate         │   🟢   │ GO  │ │
│ │ Features          │ Gunning Fog Range   │   🔴   │ NO-GO│ │
│ │   → Actual: 24.5  │ Target: 14-22       │        │     │ │
│ │ Features          │ Zero Vector Rate    │   🔴   │ NO-GO│ │
│ │   → Actual: 0.55  │ Target: < 0.50      │        │     │ │
│ └────────────────────────────────────────────────────────┘ │
│                                                             │
│ Sentiment Features:                                         │
│ • Negative: 0.045  • Positive: 0.015  • Uncertainty: 0.032│
│                                                             │
│ Readability Features:                                       │
│ • Gunning Fog: 24.5  • FK Grade: 18.2  • Flesch RE: 28.4 │
│                                                             │
│ [View Raw JSON]  [Download File Report]  [Compare to Mean]│
└────────────────────────────────────────────────────────────┘
```

**Functionality**:
- File selector (autocomplete)
- Tabular display of all validation results
- Highlight blocking failures
- Show actual vs. target comparisons
- Link to raw extracted features JSON
- Compare file metrics to batch mean/median

**Data Sources**:
- `per_file_results` array from validation reports
- Feature extraction outputs (sentiment/readability JSON)

### Technology Stack Evaluation

#### Option 1: Streamlit (Current Stack)

**Pros**:
✅ Already in use (`src/visualization/app.py`)
✅ Fast prototyping (declarative Python API)
✅ Multi-page app support (`pages/` directory)
✅ Built-in components (charts, tables, forms)
✅ Session state management
✅ Easy deployment (Streamlit Cloud, Docker)

**Cons**:
❌ Limited real-time streaming capabilities
❌ No native WebSocket support
❌ Less customizable than Dash
❌ Performance issues with large datasets (>10MB)

**Recommended For**: ✅ **DHCC Dashboard** (good fit for batch analysis, not real-time)

#### Option 2: Plotly Dash

**Pros**:
✅ More flexible layout system (Bootstrap components)
✅ Better performance for large datasets
✅ Native support for callbacks and interactivity
✅ Production-ready (Flask-based)
✅ Advanced visualization (Plotly.js integration)

**Cons**:
❌ Steeper learning curve
❌ More boilerplate code
❌ Requires HTML/CSS knowledge for custom layouts

**Recommended For**: ⚠️ Consider if Streamlit performance becomes an issue

#### Option 3: Gradio

**Pros**:
✅ Simplest API (even easier than Streamlit)
✅ Great for ML model demos
✅ Built-in sharing capabilities

**Cons**:
❌ Limited layout customization
❌ Not designed for complex dashboards
❌ Fewer chart types

**Recommended For**: ❌ Not suitable for DHCC (too limited)

#### Visualization Library Comparison

| Library | Strengths | Use Case in DHCC |
|---------|-----------|------------------|
| **Plotly** | Interactive, publish-quality charts | ✅ All charts (heatmaps, histograms, trends) |
| **Altair** | Declarative, Vega-based | ⚠️ Alternative to Plotly (similar capabilities) |
| **Bokeh** | Real-time streaming, large datasets | ❌ Not needed (batch analysis) |
| **Matplotlib** | Customizable, publication-ready | ❌ Not interactive (PDF export only) |

**Recommendation**: Use **Plotly** exclusively for consistency with existing `app.py`.

### Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Pipeline Execution                                          │
│ ┌─────────┐  ┌───────────┐  ┌─────────┐  ┌─────────────┐  │
│ │ Extract │→ │ Preprocess│→ │ Features│→ │ Validation  │  │
│ └─────────┘  └───────────┘  └─────────┘  └─────────────┘  │
│      ↓              ↓             ↓              ↓          │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ Validation Reports (JSON)                               ││
│ │ • data/interim/extracted/{run_id}/extractor_qa_report   ││
│ │ • data/processed/{run_id}/validation_report.json        ││
│ │ • data/processed/{run_id}/nlp_validation_report.json    ││
│ └─────────────────────────────────────────────────────────┘│
│                           ↓                                 │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ Data Health & Control Center (DHCC)                     ││
│ │ ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   ││
│ │ │ Data Loaders │→ │ Aggregators  │→ │ Visualizers  │   ││
│ │ └──────────────┘  └──────────────┘  └──────────────┘   ││
│ │          ↓                                               ││
│ │ ┌─────────────────────────────────────────────────────┐ ││
│ │ │ Streamlit Pages                                     │ ││
│ │ │ • Validation Dashboard  • Extraction Controls       │ ││
│ │ │ • Trend Analysis        • File Inspector            │ ││
│ │ └─────────────────────────────────────────────────────┘ ││
│ └─────────────────────────────────────────────────────────┘│
│                           ↓                                 │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ Outputs                                                  ││
│ │ • Updated configs (configs/features/*.yaml)              ││
│ │ • Dashboard exports (reports/dhcc_report_YYYYMMDD.pdf)  ││
│ │ • Trend data (reports/trends/metric_name.csv)            ││
│ └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### State Management Strategy

**Challenge**: Streamlit re-runs entire script on every interaction

**Solution**: Use `st.session_state` for caching expensive operations

```python
# Example: Cache loaded validation reports
if "validation_reports" not in st.session_state:
    st.session_state.validation_reports = load_all_validation_reports()

# Example: Cache aggregated metrics
if "metric_stats" not in st.session_state:
    st.session_state.metric_stats = compute_metric_statistics(
        st.session_state.validation_reports
    )
```

**Best Practices**:
- Load all reports once on app startup
- Cache expensive computations (aggregations, statistical analysis)
- Invalidate cache when new reports are detected
- Use `@st.cache_data` decorator for pure functions

## Code References

### Existing Infrastructure

**Streamlit App** - `src/visualization/app.py`:
* Lines 23-28: Page configuration
* Lines 31-200: Custom CSS (Paper Dashboard theme)
* Lines 228-246: File discovery pattern (`get_filing_files()`)
* Lines 249-316: Pipeline execution pattern (`run_analysis_pipeline()`)
* Lines 359-449: Results display (metrics, charts, expandable segments)

**Validation Report Schema** - `data/processed/20251212_161906_preprocessing_ea45dd2/validation_report.json`:
* Overall structure: `status`, `timestamp`, `overall_summary`, `blocking_summary`, `per_file_results`
* Per-file schema: `file`, `overall_status`, `validation_results[]`, `elapsed_time`
* Validation result schema: `category`, `metric`, `display_name`, `target`, `actual`, `status`, `go_no_go`

**NLP Validation Report** - `data/processed/20251212_161906_preprocessing_ea45dd2/nlp_validation_report.json`:
* Aggregate metrics: `avg_lm_hit_rate`, `avg_zero_vector_rate`, etc.
* Per-file: `sentiment_metrics`, `readability_metrics`, `validation_results[]`, `blocking_failures`

**Feature Configs** - `configs/features/*.yaml`:
* Sentiment: Lines 12-24 (active categories), Lines 29-40 (text processing), Lines 45-53 (normalization)
* Readability: Lines 17-28 (indices selection), Lines 49-59 (financial adjustments), Lines 77-83 (obfuscation weights)
* Topic Modeling: Lines 6-12 (model architecture), Lines 15-21 (preprocessing), Lines 24-29 (features)

**Threshold Registry** - `src/config/qa_validation.py`:
* `ThresholdRegistry.get(metric_name)` - Retrieve threshold from config
* `ValidationResult` - Compare actual vs. target with go/no-go logic
* Categories: `extraction_accuracy`, `parsing_performance`, `cleaning_effectiveness`, `features_quality`, `health_check`

### Extraction Quality Monitor - Data Requirements

**Analysis Date**: 2025-12-29
**Source Report**: `data/interim/extracted/20251229_140905_batch_extract_648bf25/extractor_qa_report.json`

#### Required Data Extractions

**1. Size Distribution Analysis**
```python
# Extract from per_file_results
for file_result in report['per_file_results']:
    chars = int(file_result['metrics']['substantial_content']['actual'].split()[0])
    char_counts.append({
        'file': file_result['file'],
        'chars': chars,
        'ticker': file_result['file'].split('_')[0],
        'year': file_result['file'].split('_')[2]
    })

# Calculate outliers
expected_min, expected_max = 5000, 50000
oversized = [f for f in char_counts if f['chars'] > 1000000]  # >1M
undersized = [f for f in char_counts if f['chars'] < 1000]    # <1k
```

**2. Noise Contamination Analysis**
```python
# Extract noise ratios
for file_result in report['per_file_results']:
    noise_ratio = file_result['metrics']['noise_to_signal_ratio']['actual']
    if isinstance(noise_ratio, (int, float)):
        noise_data.append({
            'file': file_result['file'],
            'ticker': file_result['file'].split('_')[0],
            'year': file_result['file'].split('_')[2],
            'noise_ratio': noise_ratio
        })

# Build heatmap (ticker × year matrix)
# Color gradient: white <15%, yellow 15-40%, orange 40-60%, red >60%
```

**3. Company-Level Failure Patterns**
```python
# Group by ticker
company_stats = defaultdict(lambda: {'total': 0, 'passed': 0, 'failed': 0})
for file_result in report['per_file_results']:
    ticker = file_result['file'].split('_')[0]
    company_stats[ticker]['total'] += 1
    if file_result['overall_status'] == 'PASS':
        company_stats[ticker]['passed'] += 1
    else:
        company_stats[ticker]['failed'] += 1

# Calculate pass rates
for ticker, stats in company_stats.items():
    stats['pass_rate'] = stats['passed'] / stats['total']

# Identify patterns
perfect_failure = [t for t, s in company_stats.items() if s['pass_rate'] == 0.0 and s['total'] >= 3]
perfect_success = [t for t, s in company_stats.items() if s['pass_rate'] == 1.0 and s['total'] >= 3]
```

**4. Failure Mode Combinations**
```python
# Extract failure combinations
from collections import Counter
failure_combos = Counter()

for file_result in report['per_file_results']:
    if file_result['overall_status'] == 'FAIL':
        failures = [
            metric for metric, result in file_result['metrics'].items()
            if result['status'] == 'FAIL'
        ]
        combo = tuple(sorted(failures))
        failure_combos[combo] += 1

# Top 10 combinations
top_combos = failure_combos.most_common(10)
```

**5. Boundary Detection Distribution**
```python
# Extract boundary precision scores
boundary_scores = []
for file_result in report['per_file_results']:
    score = file_result['metrics']['section_boundary_precision_end']['actual']
    if isinstance(score, (int, float)):
        boundary_scores.append(score)

# Analyze distribution
perfect_count = sum(1 for s in boundary_scores if s == 1.0)
zero_count = sum(1 for s in boundary_scores if s == 0.0)
partial_count = sum(1 for s in boundary_scores if 0.0 < s < 1.0)
binary_ratio = (perfect_count + zero_count) / len(boundary_scores)

# Alert if binary_ratio > 0.95 (indicates algorithm issue)
```

#### Critical Alert Thresholds

```python
CRITICAL_THRESHOLDS = {
    # Overall health
    "overall_pass_rate": 0.50,          # Alert if <50% (currently 2.3%)

    # Size anomalies
    "size_outlier_multiplier": 10,      # Alert if >10x expected (currently 160x)
    "undersized_chars": 200,            # Alert if <200 chars (currently 175)
    "oversized_chars": 500000,          # Alert if >500k chars (currently 8M)

    # Noise contamination
    "noise_threshold": 0.80,            # Alert if >80% noise (currently 88.82%)
    "noise_warning_threshold": 0.40,    # Warn if >40% noise

    # Systematic failures
    "company_failure_rate": 1.0,        # Alert if 100% failure (currently 53 companies)
    "company_min_samples": 3,           # Minimum years to flag pattern

    # Feature-specific
    "toc_failure_rate": 0.50,           # Alert if >50% fail ToC (currently 56.6%)
    "boundary_binary_ratio": 0.95,      # Alert if >95% are 0/1 (currently 100%)
}
```

#### Visualization Component Specifications

**1. Size Distribution Box Plot**
- Library: Plotly Express (`px.box`)
- Y-axis: Character count (log scale)
- Color zones: Green (5k-50k), Yellow (1k-5k or 50k-500k), Red (<1k or >500k)
- Outlier annotations: Show file names for top 5 oversized/undersized

**2. Noise Contamination Heatmap**
- Library: Plotly Express (`px.imshow`)
- Rows: Unique tickers (sorted by max noise)
- Columns: Years (2020-2025)
- Color scale: Viridis (white → yellow → red)
- Hover: File name, exact noise %, file size

**3. Company Failure Tracker**
- Library: Plotly Express (`px.bar`)
- X-axis: Companies (sorted by pass rate)
- Y-axis: Pass rate (0-100%)
- Color: Red (0%), Orange (1-49%), Yellow (50-99%), Green (100%)
- Filter: Show only companies with ≥3 years of data

**4. Failure Mode Stacked Bar**
- Library: Plotly Express (`px.bar` with `barmode='stack'`)
- X-axis: Failure combination type
- Y-axis: File count
- Segments: Individual metrics in combination
- Hover: List of affected files

**5. Boundary Score Histogram**
- Library: Plotly Express (`px.histogram`)
- X-axis: Boundary precision score (0.0 to 1.0)
- Bins: 20 bins (0.05 width)
- Annotation: Highlight binary clustering (0.0 and 1.0 bars)
- Alert badge: Show if binary_ratio > 95%

## Implementation Roadmap

### Phase 1: Foundation & Critical Monitoring (Week 1)

**Goal**: Basic dashboard infrastructure + extraction quality monitoring

**Tasks**:
1. Create `src/visualization/dhcc/` directory structure
2. Implement data loaders:
   - `validation_loader.py` - Load and parse validation reports
   - `feature_loader.py` - Load feature extraction outputs
   - `test_loader.py` - Load test results
3. Implement utility modules:
   - `report_aggregator.py` - Consolidate reports across runs
   - `anomaly_detector.py` - Detect size/noise anomalies
   - `alert_generator.py` - Generate critical alerts
4. Create `dhcc/app.py` - Main dashboard entry point
5. Implement Page 1 (Validation Dashboard) - basic version
   - Overall status cards
   - Go/No-Go metrics table
   - Simple bar charts for pass/fail counts
6. Implement Page 2 (Extraction Quality Monitor) - PRIORITY
   - Critical alerts panel (overall pass rate, size anomalies, noise)
   - Size distribution box plot
   - Company failure rate tracker
   - Failure mode breakdown chart

**Deliverables**:
- Functional dashboard showing latest validation run
- Ability to load and display all 4 report types
- **Critical alerts for systematic extraction issues**
- **Size anomaly detection (oversized/undersized files)**
- **Company-level failure pattern tracking**

**Success Criteria**:
```bash
streamlit run src/visualization/dhcc/app.py
# Should display latest validation status from data/processed/
# Should show critical alert: "CAH_10K_2024 (8.0M chars, 160x max)"
# Should show alert: "87.7% overall failure rate"
# Should identify 53 companies with 100% failure rate
```

### Phase 2: Advanced Visualizations & Quality Components (Week 2)

**Goal**: Rich interactive visualizations for extraction quality monitoring

**Tasks**:
1. Implement reusable components:
   - `metrics_card.py` - Color-coded status cards
   - `status_indicator.py` - Go/No-Go indicators
   - `heatmap_viewer.py` - File × metric heatmap
   - `noise_heatmap.py` - Company × year noise contamination heatmap
   - `size_analyzer.py` - Character count distribution analyzer
   - `company_failure_tracker.py` - Company-level success/failure patterns
2. Add Plotly charts to Page 1:
   - Pie chart: Pass/warn/fail distribution
   - Histograms: Gunning Fog, LM hit rate
   - Heatmap: Files × validation metrics
3. Complete Page 2 (Extraction Quality Monitor):
   - **Noise contamination heatmap** (company × year with color gradient)
   - **Boundary detection histogram** (show binary 0/1 distribution)
   - **Interactive size outlier table** (sortable, filterable)
4. Implement Page 5 (File Inspector):
   - File selector dropdown
   - Validation results table
   - Feature display panels
   - **Anomaly indicators** (flag if size outlier or high noise)

**Deliverables**:
- Interactive charts with hover tooltips
- Drill-down capability (click metric → see files)
- Per-file validation viewer
- **Noise heatmap showing COST (88% noise), EBAY (39-62%), CAH (37-43%)**
- **Size distribution showing 160x oversized and 0.0035x undersized outliers**
- **Company failure tracker showing 53 companies at 100% failure**

**Success Criteria**:
- Heatmap shows color-coded status for all files × metrics
- Click on blocking failure shows list of affected files
- **Noise heatmap correctly identifies COST_10K_2023 as 88.82% noise (red)**
- **Size box plot shows CAH_10K_2024 as extreme outlier (8M chars)**
- **Company tracker shows EMR as only 100% success company**

### Phase 3: Extraction Controls (Week 3)

**Goal**: Interactive configuration editor

**Tasks**:
1. Implement `config_editor.py` component:
   - Load YAML config
   - Generate Streamlit form controls
   - Validate user inputs
   - Save updated config
2. Implement Page 2 (Extraction Controls):
   - Sentiment config form
   - Readability config form
   - Topic modeling config form
3. Add impact preview:
   - Estimate processing time based on config
   - Estimate memory usage
   - Show feature count changes

**Deliverables**:
- Interactive config editor for all 3 feature types
- Real-time validation (e.g., weights sum to 1.0)
- Save/load custom configs

**Success Criteria**:
```bash
# User changes sentiment normalization method from tfidf → count
# Impact preview shows: "Processing time: -30%, Features: -5"
# Click "Save" writes updated configs/features/sentiment.yaml
```

### Phase 4: Trend Analysis (Week 4)

**Goal**: Historical metrics analysis

**Tasks**:
1. Implement `trend_calculator.py`:
   - Load historical reports
   - Compute time-series statistics
   - Detect anomalies
2. Implement Page 3 (Trend Analysis):
   - Metric selector dropdown
   - Time range selector
   - Line chart with target threshold
   - Statistical summary panel
3. Add multi-metric comparison:
   - Parallel coordinates plot
   - Correlation matrix heatmap

**Deliverables**:
- Time-series analysis of any validation metric
- Statistical summary (mean, std dev, percentiles)
- Export trend data as CSV

**Success Criteria**:
- Line chart shows LM hit rate over last 30 days
- Horizontal line shows target threshold (0.02)
- Statistical panel shows mean, std dev, pass rate

### Phase 5: Export & Integration (Week 5)

**Goal**: Production-ready features

**Tasks**:
1. Implement `report_exporter.py`:
   - Export dashboard state to PDF
   - Export to HTML (self-contained)
   - Export trend data to CSV
2. Add dashboard configuration:
   - `configs/visualization/dhcc.yaml`
   - Customizable chart colors
   - Default metric selections
3. Integration with CI/CD:
   - GitHub Actions workflow to generate reports
   - Auto-deploy dashboard to Streamlit Cloud

**Deliverables**:
- PDF export: "DHCC Report - 2025-12-29"
- HTML export: Self-contained dashboard snapshot
- GitHub Actions workflow: `.github/workflows/dhcc_report.yml`

**Success Criteria**:
```bash
python scripts/utils/visualization/export_dashboard_report.py --format pdf
# Generates reports/dhcc_report_20251229.pdf with all charts
```

## Architecture Insights

### Separation of Concerns

| Concern | Component | Responsibility |
|---------|-----------|----------------|
| **Data Loading** | `data_loaders/*.py` | Parse JSON reports, handle errors |
| **Business Logic** | `utils/*.py` | Aggregate metrics, compute statistics |
| **Presentation** | `components/*.py` | Reusable UI widgets |
| **Orchestration** | `pages/*.py` | Page-level logic, user interactions |
| **Configuration** | `configs/visualization/` | Dashboard settings, chart themes |

### Design Patterns

**Pattern 1: Data Loader Factory**
```python
# utils/report_loader.py
class ReportLoader:
    @staticmethod
    def load(report_type: str, run_id: str):
        loaders = {
            "extraction": ExtractionQALoader,
            "preprocessing": PreprocessingHealthLoader,
            "features": NLPValidationLoader,
            "tests": TestResultsLoader
        }
        return loaders[report_type](run_id).load()
```

**Pattern 2: Cached Aggregation**
```python
# pages/1_Validation_Dashboard.py
@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_latest_reports():
    return ReportAggregator().load_all()

reports = load_latest_reports()
```

**Pattern 3: Component Composition**
```python
# pages/1_Validation_Dashboard.py
from components.metrics_card import render_metric_card

col1, col2, col3 = st.columns(3)
with col1:
    render_metric_card("Extraction QA", reports["extraction"])
with col2:
    render_metric_card("Preprocessing", reports["preprocessing"])
```

### Performance Considerations

**Challenge**: Large validation reports (600KB+ JSON)

**Optimizations**:
1. **Lazy Loading**: Load only necessary data for current page
2. **Pagination**: Show 50 files at a time in heatmap
3. **Sampling**: For trend analysis, sample every Nth run if >100 runs
4. **Caching**: Use `@st.cache_data` for expensive aggregations
5. **Indexing**: Create `report_index.json` with metadata (timestamp, status) for fast filtering

**Estimated Performance**:
- Dashboard load time: <3s (with caching)
- Chart rendering: <1s (Plotly)
- Config save: <0.5s (YAML write)

## Open Questions

1. **Real-Time Monitoring**: Should dashboard support WebSocket streaming for live pipeline monitoring?
2. **Multi-User Access**: Do we need authentication/authorization (Streamlit Community Cloud vs. self-hosted)?
3. **Database Integration**: Should we store validation history in SQLite/PostgreSQL instead of JSON files?
4. **Alerting**: Should dashboard send Slack/email alerts for blocking failures?
5. **Version Control for Configs**: Should config changes be auto-committed to git?
6. **Feature Flag System**: Should extraction controls include feature flags (enable/disable features)?
7. **A/B Testing**: Should dashboard support comparing two config variants side-by-side?

## Recommendations

### Priority 0: Extraction Quality Monitor (URGENT - CRITICAL ISSUES)

**Why**: 87.7% extraction failure rate requires immediate visibility and investigation

**Critical Issues Requiring Immediate Attention**:
- **Size Anomalies**: 10 files >1M chars (CAH_10K_2024: 8M chars = 160x expected)
- **Noise Contamination**: 19 files >15% noise (COST_10K_2023: 88.82% noise)
- **Systematic Failures**: 53 companies with 100% failure rate (AAPL, AMZN, BA, etc.)
- **ToC Filtering**: 56.6% failure rate indicates core extraction issue
- **Boundary Detection**: Binary 0/1 scoring suggests algorithm threshold problem

**Scope**:
- Phase 1, Task 6 (Extraction Quality Monitor page) - PRIORITIZE
- Phase 2, Task 3 (Complete quality visualizations)
- Implement critical alert system for:
  - Overall pass rate <50% (currently 2.3%)
  - Size outliers >10x expected (currently 160x)
  - Noise >80% (currently 88.82%)
  - Company 100% failure patterns

**Impact**:
- **Immediate**: Visibility into the 87.7% failure rate crisis
- **Short-term**: Identify root causes (filing format variations, algorithm issues)
- **Long-term**: Track extraction quality improvements, prevent regressions

**Success Metrics**:
- Alert fires when overall pass rate <50% (currently 2.3% → will alert)
- Identify all 10 files >5M chars for investigation
- Track 53 companies with 100% failure for pattern analysis
- Monitor ToC filtering effectiveness (<95% target, currently 43.4%)

### Priority 1: Implement Basic Dashboard (Immediate)

**Why**: Foundation for all monitoring capabilities

**Scope**:
- Phase 1 (Foundation) + Phase 2 (Visualizations)
- Focus on Validation Dashboard, **Extraction Quality Monitor (PRIORITY 0)**, and File Inspector
- Use existing Streamlit/Plotly stack

**Impact**: Data scientists can monitor pipeline quality without manual JSON inspection

### Priority 2: Add Extraction Controls (Next Sprint)

**Why**: Enable parameter tuning without YAML editing

**Scope**:
- Phase 3 (Extraction Controls)
- Focus on sentiment and readability configs (skip topic modeling initially)
- Add impact preview for processing time estimation

**Impact**: Researchers can experiment with extraction configs without editing YAML files

### Priority 3: Trend Analysis (Future Sprint)

**Why**: Long-term quality monitoring

**Scope**:
- Phase 4 (Trend Analysis)
- Implement after 30+ validation runs accumulated
- Focus on detecting regressions

**Impact**: MLOps engineers can track metric drift over time

### Priority 4: Export & CI/CD Integration (Future Sprint)

**Why**: Production deployment and reporting

**Scope**:
- Phase 5 (Export & Integration)
- PDF export for stakeholder reports
- GitHub Actions for automated report generation

**Impact**: Automated quality reports in CI/CD pipeline

### Technology Recommendation

**Primary Stack**: Streamlit + Plotly
- **Rationale**: Consistency with existing `app.py`, fast development, good fit for batch analysis
- **Alternative**: If real-time monitoring becomes required, migrate to Plotly Dash

**Data Storage**: Continue using JSON files
- **Rationale**: Simple, version-controlled, no additional infrastructure
- **Alternative**: If >1000 runs accumulated, migrate to SQLite for faster querying

**Deployment**: Streamlit Community Cloud (free tier)
- **Rationale**: Zero-cost hosting, automatic HTTPS, easy sharing
- **Alternative**: Docker container for self-hosted deployment if authentication required

## Conclusion

The proposed **Data Health & Control Center (DHCC)** provides a comprehensive solution for visualizing validation metrics and controlling feature extraction parameters. By leveraging the existing Streamlit infrastructure and Plotly visualization library, we can deliver a production-ready dashboard in 5 weeks with minimal new dependencies.

**CRITICAL FINDING**: Analysis of the latest extraction QA report (2025-12-29) reveals a **87.7% failure rate** (271/309 files) with systematic extraction quality issues requiring immediate attention:
- **Size anomalies**: CAH_10K_2024 (8M chars = 160x expected maximum)
- **Noise contamination**: COST_10K_2023 (88.82% noise)
- **Systematic company failures**: 53 companies with 100% failure rate across all years
- **ToC filtering failures**: 56.6% of files fail to filter Table of Contents
- **Boundary detection issues**: Binary 0/1 scoring indicates algorithm threshold problem

**Key Achievements**:
1. **Critical Alert System**: Real-time monitoring for extraction quality crises
2. **Anomaly Detection**: Automatic identification of size outliers (160x), noise contamination (88%), and systematic failures
3. **Company-Level Tracking**: Pattern analysis to identify filing format variations causing systematic failures
4. **Unified Monitoring**: All 4 validation layers in single dashboard
5. **Interactive Controls**: No-code config editing for 3 feature types
6. **Historical Analysis**: Trend tracking across unlimited runs to prevent regressions
7. **Drill-Down Capability**: File-level inspection for debugging specific failures
8. **Export/Reporting**: PDF/HTML/CSV export for stakeholders

**Immediate Action Required**:
1. **Priority 0**: Implement Extraction Quality Monitor page (Page 2) to provide visibility into the 87.7% failure rate
2. **Investigation**: Analyze why CAH, EBAY, AMAT, and COST files show extreme anomalies
3. **Root Cause Analysis**: Investigate ToC filtering (43.4% pass rate) and boundary detection (binary scoring) algorithms
4. **Pattern Analysis**: Compare successful EMR extractions vs. failed AAPL/AMZN extractions to identify format differences

**Next Step**: Approve **Priority 0** (Extraction Quality Monitor) for immediate implementation, followed by Phase 1 foundation components.
