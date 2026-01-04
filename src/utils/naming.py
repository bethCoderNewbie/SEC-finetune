"""Naming convention utilities for parsing and formatting run directories and files."""

import re
from pathlib import Path
from typing import Dict, Optional


def parse_run_dir_metadata(run_dir: Path) -> Dict[str, Optional[str]]:
    """
    Parse run directory name to extract metadata (run_id, name, git_sha).

    Follows naming convention: {run_id}_{name}_{git_sha} or {run_id}_{name}
    where run_id is in format YYYYMMDD_HHMMSS

    Args:
        run_dir: Path to run directory

    Returns:
        Dict with keys: run_id, name, git_sha (git_sha may be None)

    Examples:
        >>> parse_run_dir_metadata(Path("data/interim/extracted/20251229_140905_batch_extract_648bf25"))
        {"run_id": "20251229_140905", "name": "batch_extract", "git_sha": "648bf25"}

        >>> parse_run_dir_metadata(Path("data/interim/extracted/20251229_140905_batch_extract"))
        {"run_id": "20251229_140905", "name": "batch_extract", "git_sha": None}
    """
    folder_name = run_dir.name

    # Pattern: {YYYYMMDD_HHMMSS}_{name}_{git_sha} or {YYYYMMDD_HHMMSS}_{name}
    # Timestamp pattern: 8 digits + underscore + 6 digits
    timestamp_pattern = r'^\d{8}_\d{6}'

    match = re.match(timestamp_pattern, folder_name)
    if not match:
        # Fallback: return folder name as name, no run_id or git_sha
        return {"run_id": None, "name": folder_name, "git_sha": None}

    run_id = match.group(0)  # e.g., "20251229_140905"
    remainder = folder_name[len(run_id) + 1:]  # Skip the timestamp and underscore

    # Split remainder by underscore
    parts = remainder.split("_")

    if len(parts) == 0:
        return {"run_id": run_id, "name": None, "git_sha": None}
    elif len(parts) == 1:
        # Only name, no git_sha
        return {"run_id": run_id, "name": parts[0], "git_sha": None}
    else:
        # Last part is git_sha (7 char hex), rest is name
        # Git SHA pattern: 7 lowercase hex chars
        last_part = parts[-1]
        if re.match(r'^[0-9a-f]{7}$', last_part):
            git_sha = last_part
            name = "_".join(parts[:-1])
        else:
            # Last part is not a valid SHA, treat all as name
            git_sha = None
            name = "_".join(parts)

        return {"run_id": run_id, "name": name, "git_sha": git_sha}


def format_output_filename(
    prefix: str,
    run_metadata: Dict[str, Optional[str]],
    extension: str = "json"
) -> str:
    """
    Format output filename following naming convention.

    Pattern: {prefix}_{run_id}_{name}_{git_sha}.{extension}

    Args:
        prefix: Filename prefix (e.g., "extractor_qa_report")
        run_metadata: Parsed run metadata dict from parse_run_dir_metadata()
        extension: File extension without dot (default: "json")

    Returns:
        Formatted filename string

    Examples:
        >>> metadata = {"run_id": "20251229_140905", "name": "batch_extract", "git_sha": "648bf25"}
        >>> format_output_filename("extractor_qa_report", metadata, "json")
        "extractor_qa_report_20251229_140905_batch_extract_648bf25.json"

        >>> metadata = {"run_id": "20251229_140905", "name": "batch_extract", "git_sha": None}
        >>> format_output_filename("extractor_qa_report", metadata, "md")
        "extractor_qa_report_20251229_140905_batch_extract.md"
    """
    if not run_metadata.get("run_id") or not run_metadata.get("name"):
        # Fallback to simple naming if required metadata missing
        return f"{prefix}.{extension}"

    # Build filename parts
    filename_parts = [prefix, run_metadata["run_id"], run_metadata["name"]]
    if run_metadata.get("git_sha"):
        filename_parts.append(run_metadata["git_sha"])

    return "_".join(filename_parts) + f".{extension}"
