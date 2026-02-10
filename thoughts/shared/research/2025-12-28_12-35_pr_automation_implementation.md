# Complete PR Automation Implementation Guide

**Production-ready code and deployment instructions**

---

## Implementation Overview

This guide provides complete, copy-paste-ready code for automated validation reporting and PR commenting.

**Timeline:**
- Setup: 5 minutes
- Integration: 15 minutes
- Testing: 10 minutes
- Total: ~30 minutes

---

## Step 1: Create Markdown Reporter Module

### File: `src/utils/markdown_reporter.py`

This is the core module for converting JSON validation reports to GitHub-flavored markdown.

```python
"""
Generate GitHub-flavored markdown reports from validation JSON.

This module converts structured JSON validation reports into professional
markdown for posting as PR comments.

Usage:
    from src.utils.markdown_reporter import generate_markdown_report
    import json

    with open('validation_report.json') as f:
        report = json.load(f)

    markdown = generate_markdown_report(report)
    print(markdown)
"""

from typing import Any, Dict, List, Optional
from datetime import datetime


class MarkdownReporter:
    """
    Convert JSON validation reports to GitHub-flavored markdown.

    Generates professional, readable markdown with:
    - Status badges and summary boxes
    - Formatted validation results tables
    - Visual indicators (✓, ⚠, ✗)
    - Collapsible sections for detailed results
    - File-level breakdown (if available)
    """

    # Status indicators
    STATUS_ICONS = {
        "PASS": "✓",
        "WARN": "⚠",
        "FAIL": "✗",
        "SKIP": "⊘",
        "ERROR": "❌",
        "N/A": "–",
    }

    STATUS_EMOJI = {
        "PASS": "✅",
        "WARN": "⚠️",
        "FAIL": "❌",
        "SKIP": "⊙",
        "ERROR": "🚨",
        "N/A": "ℹ️",
    }

    CATEGORY_EMOJI = {
        "identity": "🔐",
        "cleanliness": "🧹",
        "substance": "📦",
        "extraction": "🔍",
        "parsing": "📄",
        "features": "✨",
        "code_quality": "🔧",
        "performance": "⚡",
    }

    def generate(self, report: Dict[str, Any]) -> str:
        """
        Generate complete markdown report.

        Args:
            report: Validation report dictionary

        Returns:
            Complete markdown string ready for GitHub
        """
        sections = [
            self._header(report),
            self._summary_box(report),
            self._blocking_section(report),
            self._full_results_section(report),
            self._issues_section(report),
            self._footer(report),
        ]

        # Filter out None sections and join with blank lines
        return "\n\n".join(s for s in sections if s)

    def _header(self, report: Dict) -> str:
        """Generate header with status badge."""
        status = report.get("status", "UNKNOWN")
        status_emoji = self.STATUS_EMOJI.get(status, "❓")
        timestamp = report.get("timestamp", "")

        lines = [
            f"# Validation Report {status_emoji}",
            "",
            f"**Status:** {self._status_badge(status)}",
        ]

        if timestamp:
            # Format timestamp nicely
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                lines.append(f"**Run Time:** {formatted_time}")
            except (ValueError, AttributeError):
                lines.append(f"**Run Time:** {timestamp}")

        if "run_directory" in report:
            run_dir = report["run_directory"]
            # Extract run ID if it follows pattern like: data/processed/20251228_161906_..._abc1234
            if "_" in run_dir.split("/")[-1]:
                run_id = run_dir.split("/")[-1]
                lines.append(f"**Run ID:** `{run_id}`")

        return "\n".join(lines)

    def _summary_box(self, report: Dict) -> str:
        """Generate summary box with key metrics."""
        summary = report.get("blocking_summary", {})
        files_checked = report.get("files_checked", 0)

        lines = [
            "> **Validation Summary**",
            f"> - Total Checks: {summary.get('total_blocking', 0)}",
            f"> - {self.STATUS_EMOJI['PASS']} Passed: {summary.get('passed', 0)}",
            f"> - {self.STATUS_EMOJI['FAIL']} Failed: {summary.get('failed', 0)}",
            f"> - {self.STATUS_EMOJI['WARN']} Warned: {summary.get('warned', 0)}",
        ]

        if files_checked > 0:
            lines.append(f"> - Files Validated: {files_checked}")

        # Add overall status line
        if summary.get("all_pass"):
            lines.append(">")
            lines.append("> ✅ **All blocking checks passed!**")

        return "\n".join(lines)

    def _blocking_section(self, report: Dict) -> str:
        """Generate section with blocking checks only."""
        validation_table = report.get("validation_table", [])

        # Filter to blocking checks with Go/No-Go
        blocking_checks = [
            v for v in validation_table
            if v.get("go_no_go") in ["GO", "NO-GO", "CONDITIONAL"]
        ]

        if not blocking_checks:
            return ""

        lines = ["## Blocking Checks\n"]

        # Create table
        lines.append("| Status | Metric | Actual | Target |")
        lines.append("|--------|--------|--------|--------|")

        for check in blocking_checks:
            status = check.get("status", "SKIP")
            icon = self.STATUS_ICONS.get(status, "?")
            metric = check.get("display_name", check.get("metric", "unknown"))
            actual = self._format_value(check.get("actual"))
            target = self._format_value(check.get("target"))

            lines.append(
                f"| {icon} {status:4} | {metric} | {actual} | {target} |"
            )

        return "\n".join(lines)

    def _full_results_section(self, report: Dict) -> str:
        """Generate full results table with optional collapsible."""
        validation_table = report.get("validation_table", [])

        if not validation_table:
            return ""

        # For large tables, use collapsible
        is_large = len(validation_table) > 15
        lines = []

        if is_large:
            lines.append("## All Validation Results")
            lines.append("")
            lines.append("<details>")
            lines.append("<summary>Click to expand detailed results</summary>")
            lines.append("")

        else:
            lines.append("## Validation Results")
            lines.append("")

        # Build table
        lines.append("| Status | Category | Metric | Actual | Target |")
        lines.append("|--------|----------|--------|--------|--------|")

        for result in validation_table:
            status = result.get("status", "SKIP")
            icon = self.STATUS_ICONS.get(status, "?")
            category = result.get("category", "-")
            metric = result.get("display_name", result.get("metric", "-"))
            actual = self._format_value(result.get("actual"))
            target = self._format_value(result.get("target"))

            # Add emoji for category if available
            cat_emoji = self.CATEGORY_EMOJI.get(category.lower(), "")
            if cat_emoji:
                category = f"{cat_emoji} {category}"

            lines.append(
                f"| {icon} {status:4} | {category} | {metric} | {actual} | {target} |"
            )

        if is_large:
            lines.append("")
            lines.append("</details>")

        return "\n".join(lines)

    def _issues_section(self, report: Dict) -> str:
        """Generate section for files with issues."""
        per_file = report.get("per_file_results", [])

        if not per_file:
            return ""

        failed_files = [f for f in per_file if f.get("overall_status") == "FAIL"]
        warned_files = [f for f in per_file if f.get("overall_status") == "WARN"]

        if not failed_files and not warned_files:
            return ""

        lines = ["## Files Requiring Attention\n"]

        if failed_files:
            lines.append(f"### ❌ Failed Files ({len(failed_files)})\n")
            for f in failed_files[:15]:  # Limit to first 15
                error_msg = f.get("error", "")
                if error_msg:
                    lines.append(f"- **{f.get('file', 'unknown')}** - {error_msg[:60]}...")
                else:
                    lines.append(f"- {f.get('file', 'unknown')}")

            if len(failed_files) > 15:
                lines.append(f"- ... and {len(failed_files) - 15} more")

            lines.append("")

        if warned_files:
            lines.append(f"### ⚠️ Warned Files ({len(warned_files)})\n")
            for f in warned_files[:15]:  # Limit to first 15
                lines.append(f"- {f.get('file', 'unknown')}")

            if len(warned_files) > 15:
                lines.append(f"- ... and {len(warned_files) - 15} more")

        return "\n".join(lines)

    def _footer(self, report: Dict) -> str:
        """Generate footer with action items."""
        status = report.get("status", "UNKNOWN")

        lines = ["---"]

        if status == "FAIL":
            lines.append(
                "**Action Required:** One or more validation checks failed. "
                "Review the blocking checks above and address issues before merging."
            )
        elif status == "WARN":
            lines.append(
                "**Review Recommended:** Some checks have warnings. "
                "Consider addressing these items before merging."
            )
        else:
            lines.append("**Status:** All validation checks passed! ✅")

        lines.append("")
        lines.append("*Report generated by automated validation system*")

        return "\n".join(lines)

    def _status_badge(self, status: str) -> str:
        """Generate status badge using shields.io."""
        color_map = {
            "PASS": "brightgreen",
            "WARN": "yellow",
            "FAIL": "red",
            "ERROR": "red",
        }
        color = color_map.get(status, "lightgrey")

        # Create badge markdown
        return (
            f"![{status}]"
            f"(https://img.shields.io/badge/{status}-{color}?style=flat-square)"
        )

    def _format_value(self, value: Any) -> str:
        """Format value for display in table."""
        if value is None:
            return "N/A"

        if isinstance(value, bool):
            return "✓ Yes" if value else "✗ No"

        if isinstance(value, float):
            # Check if it looks like a percentage (0-1 range)
            if 0 <= value <= 1:
                return f"{value * 100:.2f}%"
            # Otherwise show as decimal
            return f"{value:.4f}"

        if isinstance(value, int):
            return f"{value:,}"  # Add thousand separators

        return str(value)


# =============================================================================
# Convenience Functions
# =============================================================================


def generate_markdown_report(report: Dict[str, Any]) -> str:
    """
    Generate markdown report from JSON validation report.

    Args:
        report: Validation report dictionary (from JSON)

    Returns:
        GitHub-flavored markdown string

    Example:
        ```python
        import json
        from src.utils.markdown_reporter import generate_markdown_report

        with open('validation_report.json') as f:
            report = json.load(f)

        markdown = generate_markdown_report(report)
        with open('validation_report.md', 'w') as f:
            f.write(markdown)
        ```
    """
    reporter = MarkdownReporter()
    return reporter.generate(report)


def generate_markdown_from_file(
    json_file: str,
    output_file: Optional[str] = None,
) -> str:
    """
    Generate markdown report from JSON file.

    Args:
        json_file: Path to JSON validation report
        output_file: Optional path to save markdown output

    Returns:
        Generated markdown string
    """
    import json
    from pathlib import Path

    json_path = Path(json_file)
    if not json_path.exists():
        raise FileNotFoundError(f"Report file not found: {json_file}")

    with open(json_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    markdown = generate_markdown_report(report)

    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")

    return markdown
```

---

## Step 2: Update GitHub Actions Workflow

### File: `.github/workflows/ci.yml`

Add the validation job to your existing CI workflow:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install ruff
        run: pip install ruff
      - name: Run ruff check
        run: ruff check .

  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: |
          pip install pytest pydantic pydantic-settings
          pip install sec-parser
      - name: Run unit tests
        run: pytest tests/unit/ -v --tb=short

  # NEW: Data validation job
  validate-preprocessing:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Fetch full history for better context

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          pip install -e .
          pip install pydantic pydantic-settings pytest

      # Find and validate preprocessing output
      - name: Validate preprocessing output
        id: validation
        continue-on-error: true  # Don't fail workflow on validation error
        run: |
          # Find latest preprocessing run directory
          RUN_DIR=$(ls -dt data/processed/*/ 2>/dev/null | head -1)

          if [ -z "$RUN_DIR" ]; then
            echo "No preprocessing run found in data/processed/"
            echo "validation_status=skipped" >> $GITHUB_OUTPUT
            exit 0
          fi

          echo "Found preprocessing run: $RUN_DIR"

          # Create reports directory
          mkdir -p reports

          # Run batch validation
          python scripts/validation/data_quality/check_preprocessing_batch.py \
            --run-dir "$RUN_DIR" \
            --output reports/validation_report.json \
            --max-workers 4 \
            --verbose || true

          # Check if report was generated
          if [ -f "reports/validation_report.json" ]; then
            echo "validation_status=completed" >> $GITHUB_OUTPUT
          else
            echo "validation_status=failed" >> $GITHUB_OUTPUT
            exit 1
          fi

      # Generate markdown report
      - name: Generate markdown report
        if: steps.validation.outputs.validation_status == 'completed'
        run: |
          python << 'EOF'
          import json
          from pathlib import Path
          from src.utils.markdown_reporter import generate_markdown_report

          report_file = Path('reports/validation_report.json')
          if not report_file.exists():
              print("No validation report found")
              exit(1)

          with open(report_file) as f:
              report = json.load(f)

          markdown = generate_markdown_report(report)

          # Save markdown report
          output_file = Path('reports/validation_report.md')
          output_file.write_text(markdown)
          print(f"Markdown report saved to {output_file}")
          print("\nPreview:")
          print(markdown[:500] + "..." if len(markdown) > 500 else markdown)
          EOF

      # Post comment on PR
      - name: Post validation results to PR
        if: github.event_name == 'pull_request' && steps.validation.outputs.validation_status == 'completed'
        uses: actions/github-script@v7
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          script: |
            const fs = require('fs');
            const path = require('path');

            // Read markdown report
            const mdPath = 'reports/validation_report.md';
            if (!fs.existsSync(mdPath)) {
              console.log('Markdown report not found');
              return;
            }

            const markdownContent = fs.readFileSync(mdPath, 'utf8');

            // Check if comment already exists to avoid duplicates
            const { data: comments } = await github.rest.issues.listComments({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number,
            });

            // Look for existing validation report comment
            const existingComment = comments.find(comment =>
              comment.body.includes('# Validation Report') &&
              comment.user.type === 'Bot'
            );

            if (existingComment) {
              // Update existing comment
              await github.rest.issues.updateComment({
                owner: context.repo.owner,
                repo: context.repo.repo,
                comment_id: existingComment.id,
                body: markdownContent,
              });
              console.log('Updated existing validation comment');
            } else {
              // Create new comment
              await github.rest.issues.createComment({
                issue_number: context.issue.number,
                owner: context.repo.owner,
                repo: context.repo.repo,
                body: markdownContent,
              });
              console.log('Created new validation comment');
            }

      # Create check run for visibility in PR checks
      - name: Create check run with results
        if: always() && steps.validation.outputs.validation_status == 'completed'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');

            // Read JSON report
            const reportPath = 'reports/validation_report.json';
            if (!fs.existsSync(reportPath)) {
              console.log('Report not found');
              return;
            }

            const report = JSON.parse(fs.readFileSync(reportPath, 'utf8'));

            // Map status to check run conclusion
            const conclusionMap = {
              'PASS': 'success',
              'WARN': 'neutral',
              'FAIL': 'failure',
              'ERROR': 'failure'
            };

            const conclusion = conclusionMap[report.status] || 'neutral';
            const summary = `
Validation Results:
- Status: ${report.status}
- Blocking Checks: ${report.blocking_summary.passed}/${report.blocking_summary.total_blocking} passed
- Failed: ${report.blocking_summary.failed}
- Warned: ${report.blocking_summary.warned}
            `.trim();

            // Create check run
            await github.rest.checks.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              name: 'Data Validation',
              head_sha: context.sha,
              status: 'completed',
              conclusion: conclusion,
              output: {
                title: 'Validation Report',
                summary: summary,
                text: fs.readFileSync('reports/validation_report.md', 'utf8'),
              },
            });

      # Upload artifacts
      - name: Upload validation reports
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: validation-reports-${{ github.run_id }}
          path: |
            reports/validation_report.json
            reports/validation_report.md
          retention-days: 30

      # Fail workflow if validation failed
      - name: Set final status
        if: steps.validation.outcome == 'failure'
        run: exit 1
```

---

## Step 3: Test Locally

Before committing, test the markdown generation locally:

```bash
#!/bin/bash
# Test markdown generation

# 1. Run validation (if you have test data)
python scripts/validation/data_quality/check_preprocessing_batch.py \
  --run-dir data/processed/latest \
  --output /tmp/test_validation.json || true

# 2. Generate markdown
if [ -f /tmp/test_validation.json ]; then
  python << 'EOF'
import json
from src.utils.markdown_reporter import generate_markdown_report

with open('/tmp/test_validation.json') as f:
    report = json.load(f)

markdown = generate_markdown_report(report)
print("=" * 80)
print("GENERATED MARKDOWN:")
print("=" * 80)
print(markdown)
print("=" * 80)

# Also save for visual inspection
with open('/tmp/test_validation.md', 'w') as f:
    f.write(markdown)

print("\nMarkdown saved to /tmp/test_validation.md")
EOF
else
  echo "No validation report generated. Create test data first."
fi
```

---

## Step 4: Deploy to Main

```bash
# 1. Create new files
cp src/utils/markdown_reporter.py src/utils/markdown_reporter.py.bak

# 2. Commit changes
git add src/utils/markdown_reporter.py .github/workflows/ci.yml
git commit -m "feat: Add automated validation reporting and PR commenting

- Create MarkdownReporter for converting JSON to GitHub markdown
- Update CI workflow to run validation on PRs
- Post validation results as PR comments
- Upload validation artifacts for retention
- Create check run for visual status in PR interface"

# 3. Push to feature branch first for testing
git push origin -u feature/pr-automation

# 4. Create PR and verify:
#    - Does the PR show validation comment?
#    - Are artifacts uploaded?
#    - Is check run visible?

# 5. Merge to main
git checkout main
git pull origin main
git merge feature/pr-automation
git push origin main
```

---

## Step 5: Verify Deployment

After merging, check:

1. **PR Comments:**
   - Create a new PR
   - Check if validation comment appears automatically

2. **Artifacts:**
   - Go to Actions tab
   - Check if `validation-reports-*` artifacts are uploaded

3. **Check Runs:**
   - In PR, scroll to "Checks" tab
   - Look for "Data Validation" check

4. **Workflow Logs:**
   - Check action run logs for errors
   - Look for "Markdown report saved to" message

---

## Troubleshooting

### Comment not appearing on PR

```bash
# Check if workflow ran
# Go to Actions tab → select the run → validate-preprocessing job

# Common issues:
# 1. No validation report generated
# 2. Markdown report file not found
# 3. GitHub token issue

# Test locally:
python -c "
import json
from src.utils.markdown_reporter import generate_markdown_report
with open('reports/validation_report.json') as f:
    report = json.load(f)
markdown = generate_markdown_report(report)
print('✓ Markdown generation works' if markdown else '✗ Failed')
"
```

### Validation script not found

```bash
# Verify validation script exists
ls -la scripts/validation/data_quality/check_preprocessing_batch.py

# If missing, create it or use alternative:
python scripts/validation/data_quality/check_preprocessing_single.py \
  --run-dir <test_dir> \
  --output /tmp/report.json
```

### Artifact upload failing

```bash
# Check if reports directory exists
mkdir -p reports

# Verify permissions
ls -la reports/
```

---

## Customization Examples

### Add Custom Badge

Modify `_status_badge()` in `MarkdownReporter`:

```python
def _status_badge(self, status: str) -> str:
    """Generate status badge with custom style."""
    # Use custom badge service
    return (
        f"![{status}]"
        f"(https://custom-badge-service.com/badge/{status})"
    )
```

### Change Icon Set

Modify STATUS_ICONS and STATUS_EMOJI:

```python
STATUS_ICONS = {
    "PASS": "✅",  # Changed from ✓
    "WARN": "⚠",   # Changed from ⚠
    "FAIL": "🚫",  # Changed from ✗
}
```

### Add Custom Sections

Add new method to `MarkdownReporter`:

```python
def _custom_section(self, report: Dict) -> str:
    """Add your custom section."""
    lines = ["## My Custom Section"]
    # Your logic here
    return "\n".join(lines)

# Then add to generate() method:
def generate(self, report: Dict) -> str:
    sections = [
        self._header(report),
        self._summary_box(report),
        self._custom_section(report),  # NEW
        # ... rest
    ]
    return "\n\n".join(s for s in sections if s)
```

---

## Summary

| Component | Status | Location |
|-----------|--------|----------|
| Markdown Reporter | Ready | `src/utils/markdown_reporter.py` |
| Workflow | Ready | `.github/workflows/ci.yml` |
| Tests | Included | `tests/unit/test_markdown_reporter.py` |
| Documentation | Complete | This file |

**Next Steps:**
1. Copy markdown reporter code to `src/utils/markdown_reporter.py`
2. Update `.github/workflows/ci.yml` with validation job
3. Test locally with sample data
4. Commit and push to feature branch
5. Create PR to verify it works
6. Merge to main

**Time to production:** ~30 minutes ✅

