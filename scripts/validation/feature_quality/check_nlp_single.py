"""
Generate a human-readable validation report for Sentiment and Readability metrics.

This script:
1. Loads the latest test data (AAPL 10-K 2021).
2. Calculates key validation metrics (same as pytest suite).
3. Generates a comprehensive Markdown report with interpretation guides.
4. Saves the report to the 'reports/' directory.

Usage:
    python scripts/utils/generate_validation_report.py
"""

import sys
import json
import datetime
import platform
import subprocess
import os
from pathlib import Path
import numpy as np

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import settings
from src.features.sentiment import SentimentAnalyzer
from src.features.dictionaries import LMDictionaryManager
from src.features.readability import ReadabilityAnalyzer


def get_git_info():
    """Retrieve git metadata safely."""
    def _run_git(args):
        try:
            return subprocess.check_output(["git"] + args, stderr=subprocess.DEVNULL).decode('utf-8').strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return "unknown"

    return {
        "commit": _run_git(["rev-parse", "--short", "HEAD"]),
        "branch": _run_git(["rev-parse", "--abbrev-ref", "HEAD"]),
        "user": _run_git(["config", "user.name"]) or os.environ.get("USERNAME", "unknown")
    }


def get_run_metadata():
    """Gather comprehensive run environment metadata."""
    git = get_git_info()
    return {
        "timestamp": datetime.datetime.now().astimezone().isoformat(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": git["commit"],
        "git_branch": git["branch"],
        "researcher": git["user"],
        "working_dir": str(Path.cwd()),
    }


def load_test_data():
    """Load AAPL 10-K data using dynamic path resolution."""
    print("Finding latest test data...")
    test_data_config = settings.testing.data
    
    file_path = test_data_config.get_test_file(
        run_name="preprocessing",
        filename="AAPL_10K_2021_segmented_risks.json"
    )
    
    if not file_path or not file_path.exists():
        print("Error: Test data file not found.")
        print(f"Searched for: AAPL_10K_2021_segmented_risks.json in runs matching 'preprocessing'")
        return None
        
    print(f"Loaded data from: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def calculate_sentiment_metrics(data, segments):
    """Calculate sentiment validation metrics."""
    print("Calculating sentiment metrics...")
    metrics = {}
    
    # 1. LM Hit Rate
    analyzer = SentimentAnalyzer()
    mgr = LMDictionaryManager.get_instance()
    
    all_text = " ".join(seg["text"] for seg in segments)
    tokens = analyzer.tokenize(all_text)
    
    if not tokens:
        return metrics

    lm_hits = sum(1 for t in tokens if mgr.get_word_categories(t))
    metrics['lm_hit_rate'] = (lm_hits / len(tokens)) * 100
    
    # 2. Zero Vector Rate
    zero_count = sum(1 for seg in segments if seg["sentiment"]["total_sentiment_words"] == 0)
    metrics['zero_vector_rate'] = (zero_count / len(segments)) * 100
    metrics['zero_vector_count'] = zero_count
    
    # 3. Polarity Ratios
    agg = data.get("aggregate_sentiment", {})
    metrics['avg_negative'] = agg.get("avg_negative_ratio", 0)
    metrics['avg_positive'] = agg.get("avg_positive_ratio", 0)
    metrics['avg_uncertainty'] = agg.get("avg_uncertainty_ratio", 0)
    
    # 4. Uncertainty-Negative Correlation
    uncertainty_counts = [seg["sentiment"]["uncertainty_count"] for seg in segments]
    negative_counts = [seg["sentiment"]["negative_count"] for seg in segments]
    
    if len(segments) > 1:
        metrics['unc_neg_corr'] = np.corrcoef(uncertainty_counts, negative_counts)[0, 1]
    else:
        metrics['unc_neg_corr'] = 0.0
        
    return metrics


def calculate_readability_metrics(segments):
    """Calculate readability validation metrics."""
    print("Calculating readability metrics...")
    metrics = {}
    analyzer = ReadabilityAnalyzer()
    
    # Filter for long segments (>200 chars) for reliability
    long_segments = [seg["text"] for seg in segments if len(seg["text"]) > 200]
    
    if not long_segments:
        return metrics

    fog_scores = []
    indices = {'fk': [], 'fog': [], 'ari': []}
    deltas = []
    obfuscation_scores = []
    complexity_proxies = []
    
    for text in long_segments:
        features = analyzer.extract_features(text)
        
        # Fog
        fog_scores.append(features.gunning_fog_index)
        
        # Correlations
        indices['fk'].append(features.flesch_kincaid_grade)
        indices['fog'].append(features.gunning_fog_index)
        indices['ari'].append(features.automated_readability_index)
        
        # Adjustment Delta
        delta = features.pct_complex_words - features.pct_complex_words_adjusted
        deltas.append(delta)
        
        # Obfuscation
        obfuscation_scores.append(features.obfuscation_score)
        
        # Complexity Proxy (for correlation check)
        proxy = (features.avg_sentence_length / 50 * 50 + features.pct_complex_words_adjusted)
        complexity_proxies.append(proxy)

    # Aggregates
    metrics['avg_fog'] = np.mean(fog_scores)
    metrics['min_fog'] = np.min(fog_scores)
    metrics['max_fog'] = np.max(fog_scores)
    
    metrics['fk_fog_corr'] = np.corrcoef(indices['fk'], indices['fog'])[0, 1]
    metrics['fk_ari_corr'] = np.corrcoef(indices['fk'], indices['ari'])[0, 1]
    
    metrics['avg_adjustment_delta'] = np.mean(deltas)
    metrics['avg_obfuscation'] = np.mean(obfuscation_scores)
    
    metrics['obfuscation_complexity_corr'] = np.corrcoef(obfuscation_scores, complexity_proxies)[0, 1]
    
    return metrics


def generate_markdown_report(sent_metrics, read_metrics, file_info, metadata):
    """Generate the Markdown content with metadata header."""
    
    md = f"""# NLP Validation Report

**Status**: `GENERATED`
**Data Source**: `{file_info}`

## 0. Run Environment (Metadata)

| Key | Value |
|-----|-------|
| **Timestamp** | `{metadata['timestamp']}` |
| **Researcher** | `{metadata['researcher']}` |
| **Git Commit** | `{metadata['git_commit']}` (Branch: `{metadata['git_branch']}`) |
| **Python** | `{metadata['python_version']}` |
| **Platform** | `{metadata['platform']}` |

---

## 1. Executive Summary

This report validates the internal consistency and domain-appropriateness of the NLP feature extraction pipelines.

| Category | Metric | Value | Target | Status |
|----------|--------|-------|--------|--------|
| **Sentiment** | LM Dictionary Hit Rate | {sent_metrics.get('lm_hit_rate', 0):.2f}% | > 2% | {'✅ PASS' if sent_metrics.get('lm_hit_rate', 0) > 2 else '❌ FAIL'} |
| **Sentiment** | Zero-Vector Rate | {sent_metrics.get('zero_vector_rate', 0):.2f}% | < 50% | {'✅ PASS' if sent_metrics.get('zero_vector_rate', 0) < 50 else '❌ FAIL'} |
| **Sentiment** | Polarity (Neg > Pos) | {sent_metrics.get('avg_negative', 0) > sent_metrics.get('avg_positive', 0)} | True | {'✅ PASS' if sent_metrics.get('avg_negative', 0) > sent_metrics.get('avg_positive', 0) else '❌ FAIL'} |
| **Readability** | Avg Gunning Fog | {read_metrics.get('avg_fog', 0):.1f} | 14-22 | {'✅ PASS' if 14 <= read_metrics.get('avg_fog', 0) <= 22 else '❌ FAIL'} |
| **Readability** | Metric Correlation | {read_metrics.get('fk_fog_corr', 0):.2f} | > 0.7 | {'✅ PASS' if read_metrics.get('fk_fog_corr', 0) > 0.7 else '❌ FAIL'} |

---

## 2. Sentiment Analysis Details

### Dictionary Effectiveness
* **LM Hit Rate**: `{sent_metrics.get('lm_hit_rate', 0):.2f}%`
    * *Interpretation*: Percentage of tokens found in the Loughran-McDonald dictionary.
    * *Target*: > 2% (Typical 10-K is 3-5%). A low value suggests tokenization issues.

* **Zero-Vector Rate**: `{sent_metrics.get('zero_vector_rate', 0):.2f}%` ({sent_metrics.get('zero_vector_count')} segments)
    * *Interpretation*: Percentage of segments with NO sentiment words.
    * *Target*: < 50%. High values indicate "silent failures" in matching.

### 10-K Domain Profile
* **Negative Ratio**: `{sent_metrics.get('avg_negative', 0):.4f}`
* **Positive Ratio**: `{sent_metrics.get('avg_positive', 0):.4f}`
* **Uncertainty Ratio**: `{sent_metrics.get('avg_uncertainty', 0):.4f}`
* **Uncertainty-Negative Correlation**: `{sent_metrics.get('unc_neg_corr', 0):.2f}`
    * *Interpretation*: "Risk" words should correlate with "Uncertainty" words (e.g., "may", "could"). A positive correlation (> 0.3) confirms this relationship.

---

## 3. Readability Analysis Details

### Score Plausibility
* **Gunning Fog Index**:
    * Average: `{read_metrics.get('avg_fog', 0):.1f}` (Target: 14-22)
    * Min: `{read_metrics.get('min_fog', 0):.1f}` (Target: > 8)
    * Max: `{read_metrics.get('max_fog', 0):.1f}` (Target: < 35)
    * *Interpretation*: 10-K Risk Factors are complex (college grad level). 
        * < 10: Check for splitter splitting on abbreviations (e.g., "U.S.").
        * > 35: Check for splitter missing periods.

### Domain Adjustment
* **Financial Adjustment Delta**: `{read_metrics.get('avg_adjustment_delta', 0):.2f}%`
    * *Interpretation*: Reduction in "complex word" count after excluding common financial terms (e.g., "financial", "company").
    * *Target*: > 0.5%. Ensures we aren't penalizing necessary domain jargon.

### Custom Metrics
* **Obfuscation Score**: `{read_metrics.get('avg_obfuscation', 0):.1f}`
    * *Interpretation*: Composite score (0-100) of structural complexity and passive voice.
    * *Target*: 35-80 for Risk Factors.

* **Obfuscation-Complexity Correlation**: `{read_metrics.get('obfuscation_complexity_corr', 0):.2f}`
    * *Target*: > 0.6. Confirms the custom score tracks with standard complexity proxies.

---

## 4. How to Interpret Failures

| Failure Mode | Likely Cause | Suggested Fix |
|--------------|--------------|---------------|
| **LM Hit Rate < 2%** | Tokenizer splitting words or casing mismatch. | Check `SentimentAnalyzer.tokenize` for casing/punctuation handling. |
| **Zero-Vector Rate > 50%** | Dictionary not loading or matching logic broken. | Verify `LMDictionaryManager` path and `_count_matches` logic. |
| **Positive > Negative** | Wrong file or severe bug. | Ensure analyzing **Risk Factors** (Item 1A), not marketing sections. |
| **Fog Index > 35** | Sentence splitter failing. | Check `Segmenter` logic for handling bullet points or missing whitespace. |
| **Fog Index < 10** | Over-splitting. | Check handling of abbreviations (e.g., "Inc.", "Ltd."). |

"""
    return md


def main():
    metadata = get_run_metadata()
    print(f"Run Environment: {metadata['platform']} | Python {metadata['python_version']}")
    
    data = load_test_data()
    if not data:
        print("Skipping report generation due to missing data.")
        return

    segments = data.get("segments", [])
    if not segments:
        print("No segments found in data.")
        return

    sent_metrics = calculate_sentiment_metrics(data, segments)
    read_metrics = calculate_readability_metrics(segments)
    
    file_name = "AAPL_10K_2021_segmented_risks.json"
    report_content = generate_markdown_report(sent_metrics, read_metrics, file_name, metadata)
    
    output_dir = PROJECT_ROOT / "reports"
    output_dir.mkdir(exist_ok=True)
    
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    output_path = output_dir / f"validation_report_{today}.md"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report_content)
        
    print(f"\nReport generated successfully: {output_path}")


if __name__ == "__main__":
    main()
