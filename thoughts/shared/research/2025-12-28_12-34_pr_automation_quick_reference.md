# PR Automation Quick Reference

**Quick guide for implementing validation reporting without deep research**

---

## TL;DR Recommendation

**Use GitHub Actions + Python markdown generator. Not CML.**

Why:
- You already have GitHub Actions
- Your validation is pure Python (non-ML)
- Full control over formatting
- No additional costs/dependencies
- ~2 hours to implement

---

## Implementation Checklist

### Phase 1: Markdown Reporter (30 mins)

Copy this into `src/utils/markdown_reporter.py`:

```python
"""Generate GitHub markdown from JSON validation reports."""

from typing import Any, Dict


class MarkdownReporter:
    """Convert JSON validation to markdown."""

    def generate(self, report: Dict[str, Any]) -> str:
        """Generate markdown report."""
        lines = []

        # Header
        status = report.get("status", "UNKNOWN")
        lines.append(f"# Data Validation Report - {status}\n")

        # Summary
        summary = report.get("blocking_summary", {})
        lines.append("## Summary")
        lines.append(f"- **Passed:** {summary.get('passed', 0)}/{summary.get('total_blocking', 0)}")
        lines.append(f"- **Failed:** {summary.get('failed', 0)}")
        lines.append(f"- **Warned:** {summary.get('warned', 0)}\n")

        # Results table
        lines.append("## Validation Results")
        lines.append("| Metric | Actual | Target | Status |")
        lines.append("|--------|--------|--------|--------|")

        for result in report.get("validation_table", []):
            status_icon = "✓" if result["status"] == "PASS" else "⚠" if result["status"] == "WARN" else "✗"
            actual = f"{result['actual']:.4f}" if isinstance(result['actual'], float) else str(result['actual'])
            target = f"{result['target']:.4f}" if isinstance(result['target'], float) else str(result['target'])
            lines.append(f"| {result.get('display_name', result.get('metric'))} | {actual} | {target} | {status_icon} |")

        return "\n".join(lines)


def generate_markdown_report(report: Dict) -> str:
    """Convenience function."""
    return MarkdownReporter().generate(report)
```

### Phase 2: GitHub Actions Workflow (20 mins)

Add to `.github/workflows/ci.yml`:

```yaml
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -e .

      - name: Run validation
        run: |
          python scripts/validation/data_quality/check_preprocessing_batch.py \
            --run-dir data/processed/latest \
            --output reports/validation.json || true

      - name: Generate markdown
        if: always()
        run: |
          python << 'EOF'
          import json
          from pathlib import Path
          from src.utils.markdown_reporter import generate_markdown_report

          if Path("reports/validation.json").exists():
              with open("reports/validation.json") as f:
                  report = json.load(f)
              markdown = generate_markdown_report(report)
              Path("reports/validation.md").write_text(markdown)
          EOF

      - name: Comment on PR
        if: github.event_name == 'pull_request' && always()
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            if (fs.existsSync('reports/validation.md')) {
              const body = fs.readFileSync('reports/validation.md', 'utf8');
              github.rest.issues.createComment({
                issue_number: context.issue.number,
                owner: context.repo.owner,
                repo: context.repo.repo,
                body
              });
            }

      - name: Upload artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: validation-reports
          path: reports/
```

### Phase 3: Test (10 mins)

```bash
# Test markdown generation locally
python scripts/validation/data_quality/check_preprocessing_batch.py \
  --run-dir data/processed/latest \
  --output /tmp/test.json

python << 'EOF'
import json
from src.utils.markdown_reporter import generate_markdown_report

with open("/tmp/test.json") as f:
    report = json.load(f)

print(generate_markdown_report(report))
EOF
```

### Phase 4: Deploy (5 mins)

```bash
git add .github/workflows/ci.yml src/utils/markdown_reporter.py
git commit -m "Add automated validation reporting to PRs"
git push
```

---

## Visual Examples

### Output Example 1: Clean Report

```
# Data Validation Report - PASS

## Summary
- **Passed:** 7/7
- **Failed:** 0
- **Warned:** 0

## Validation Results
| Metric | Actual | Target | Status |
|--------|--------|--------|--------|
| CIK Present Rate | 0.9980 | 0.9900 | ✓ |
| HTML Artifact Rate | 0.0020 | 0.0500 | ✓ |
| Empty Segment Rate | 0.0001 | 0.0200 | ✓ |
| Short Segment Rate | 0.0150 | 0.2000 | ✓ |
| Duplicate Rate | 0.0000 | 0.0100 | ✓ |
| Company Name Present Rate | 0.9975 | 0.9900 | ✓ |
| Page Number Artifact Rate | 0.0005 | 0.0500 | ✓ |
```

### Output Example 2: Report with Warnings

```
# Data Validation Report - WARN

## Summary
- **Passed:** 6/7
- **Failed:** 0
- **Warned:** 1

## Validation Results
| Metric | Actual | Target | Status |
|--------|--------|--------|--------|
| CIK Present Rate | 0.9800 | 0.9900 | ⚠ |
| HTML Artifact Rate | 0.0020 | 0.0500 | ✓ |
| Empty Segment Rate | 0.0001 | 0.0200 | ✓ |
| Short Segment Rate | 0.0150 | 0.2000 | ✓ |
| Duplicate Rate | 0.0000 | 0.0100 | ✓ |
| Company Name Present Rate | 0.9975 | 0.9900 | ✓ |
```

---

## CML vs GitHub Actions Side-by-Side

```python
# GitHub Actions (Recommended)
from src.utils.markdown_reporter import generate_markdown_report
markdown = generate_markdown_report(json_report)
# Markdown output → PR comment ✅


# CML Alternative
# bash: cml comment create report.md
# Markdown output → PR comment (via CML)
# Requires: pip install cml, new tool to learn
```

**CML Advantages:**
- Native ML metric tracking
- Built-in experiment comparison
- Auto-generated plots

**CML Disadvantages (for your case):**
- Not a data pipeline tool
- More complex setup
- Less control over validation logic
- Overkill for non-ML workflows

---

## Common Questions

### Q: Do I need to install CML?
A: No. GitHub Actions is already installed. Use Python + markdown.

### Q: How do I track metrics over time?
A: Store JSON reports in a `reports/history/` directory and generate comparison.

### Q: Can GitHub comment on PRs for free?
A: Yes. `actions/github-script` uses the workflow token (free).

### Q: What if validation data is very large?
A: Use collapsible `<details>` tags in markdown for big tables.

### Q: How do I fail the workflow on validation failure?
A: Check the status field and exit with code 1:
```bash
if [ "$(jq -r '.status' reports/validation.json)" == "FAIL" ]; then
  exit 1
fi
```

### Q: Can I use this for other validation types?
A: Yes! Make `markdown_reporter.py` flexible:
```python
class MarkdownReporter:
    def generate(self, report: Dict) -> str:
        # Generic table generation
        # Works for any validation JSON structure
```

---

## File Locations

```
.github/workflows/ci.yml
↑ Add validate job here

src/utils/markdown_reporter.py
↑ Create this new file

reports/validation.json
↑ Generated by validation scripts
↑ Uploaded as artifact

reports/validation.md
↑ Generated markdown
↑ Posted as PR comment
```

---

## Minimal Working Example

```bash
# 1. Create reporter
cat > src/utils/markdown_reporter.py << 'EOF'
from typing import Dict, Any

class MarkdownReporter:
    def generate(self, report: Dict[str, Any]) -> str:
        lines = [f"# Validation: {report['status']}"]
        for r in report.get('validation_table', []):
            lines.append(f"- {r.get('display_name')}: {r['status']}")
        return "\n".join(lines)

def generate_markdown_report(report: Dict) -> str:
    return MarkdownReporter().generate(report)
EOF

# 2. Test it
python << 'EOF'
import json
from src.utils.markdown_reporter import generate_markdown_report

test_report = {
    "status": "PASS",
    "validation_table": [
        {"display_name": "CIK Rate", "status": "PASS"}
    ]
}

print(generate_markdown_report(test_report))
EOF

# Output:
# # Validation: PASS
# - CIK Rate: PASS
```

---

## Decision Tree

```
Does your pipeline have ML models?
├─ YES → Consider CML (but GitHub Actions still works)
└─ NO → Use GitHub Actions (recommended)

Do you need experiment comparison?
├─ YES → CML is better
└─ NO → GitHub Actions is simpler

Is team already using CML?
├─ YES → CML keeps consistency
└─ NO → GitHub Actions (lower friction)

Your case: Data preprocessing only → GitHub Actions ✅
```

---

## Summary

| Task | Time | Tool |
|------|------|------|
| Create markdown generator | 10 min | Python |
| Update CI workflow | 10 min | YAML |
| Test locally | 10 min | bash/Python |
| Deploy | 5 min | git |
| **Total** | **35 min** | **GitHub Actions** |

**You're done.** Every PR now gets automated validation reports as comments.

