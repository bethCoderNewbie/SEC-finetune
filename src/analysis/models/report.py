"""ReportBundle — paths to files written in a stamped analysis run directory (PRD-005 §3.2)."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ReportBundle(BaseModel):
    """Output artifact paths for one analysis run (ADR-007 stamped directory)."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    run_dir: Path
    report_md: Optional[Path] = None
    report_json: Optional[Path] = None
    report_csv: Optional[Path] = None
    agent_trace_jsonl: Optional[Path] = None
