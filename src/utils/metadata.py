"""Run metadata collection for validation reports."""

import os
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List


class RunMetadata:
    """
    Collects comprehensive run environment metadata.

    Gathers git information, platform details, and timestamp for validation reports.

    Usage:
        metadata = RunMetadata.gather()

        # Returns dict with keys:
        # - timestamp: ISO 8601 timestamp with timezone
        # - python_version: Python version
        # - platform: Platform string
        # - git_commit: Short SHA
        # - git_branch: Branch name
        # - researcher: Git username or OS username
        # - working_dir: Current working directory
    """

    @staticmethod
    def gather() -> Dict[str, str]:
        """
        Gather comprehensive run environment metadata.

        Returns:
            Dict with metadata keys:
            - timestamp: ISO 8601 timestamp with timezone
            - python_version: Python version string
            - platform: Platform identification string
            - git_commit: Short git SHA (or "unknown")
            - git_branch: Git branch name (or "unknown")
            - researcher: Git user.name or OS username (or "unknown")
            - working_dir: Current working directory path
        """
        git_commit = RunMetadata._run_git(["rev-parse", "--short", "HEAD"])
        git_branch = RunMetadata._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        git_user = RunMetadata._run_git(["config", "user.name"])

        # Fallback to OS username if git user not found
        researcher = git_user if git_user != "unknown" else os.environ.get("USERNAME", "unknown")

        return {
            "timestamp": datetime.now().astimezone().isoformat(),
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "git_commit": git_commit,
            "git_branch": git_branch,
            "researcher": researcher,
            "working_dir": str(Path.cwd()),
        }

    @staticmethod
    def _run_git(args: List[str]) -> str:
        """
        Run git command safely, return 'unknown' on error.

        Args:
            args: Git command arguments (e.g., ["rev-parse", "HEAD"])

        Returns:
            Git command output or "unknown" if error
        """
        try:
            return subprocess.check_output(
                ["git"] + args,
                stderr=subprocess.DEVNULL
            ).decode('utf-8').strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return "unknown"
