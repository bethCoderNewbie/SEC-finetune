"""
Schema and identity field validation for SEC filings.

This module enforces schema integrity and checks for the presence
of critical identity fields (CIK, Company Name, SIC Code).
"""

import json
from pathlib import Path
from typing import Dict, Any, List

from src.config.qa_validation import (
    ThresholdRegistry,
    ValidationResult,
)


class SchemaValidator:
    """
    Validates schema integrity and identity field presence.
    
    Checks for:
    1. CIK (Required)
    2. Company Name (Required)
    3. SIC Code (Recommended)
    """

    REQUIRED_IDENTITY_FIELDS = ["cik", "company_name"]
    RECOMMENDED_IDENTITY_FIELDS = ["sic_code", "ticker", "form_type"]

    def __init__(self):
        """Initialize the validator."""
        self.registry = ThresholdRegistry

    def validate_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Validate a single file's schema and identity fields.

        Args:
            file_path: Path to the JSON file

        Returns:
            Dict containing validation details for this file
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            return {
                "file": str(file_path),
                "error": str(e),
                "is_valid_json": False,
                "identity_fields": {},
                "missing_required": self.REQUIRED_IDENTITY_FIELDS
            }

        results = {
            "file": str(file_path),
            "is_valid_json": True,
            "identity_fields": {},
            "missing_required": [],
            "missing_recommended": [],
        }

        # Check required fields
        for field in self.REQUIRED_IDENTITY_FIELDS:
            value = data.get(field)
            # Check for None or empty string
            is_present = value is not None and str(value).strip() != ""
            results["identity_fields"][field] = is_present
            if not is_present:
                results["missing_required"].append(field)

        # Check recommended fields
        for field in self.RECOMMENDED_IDENTITY_FIELDS:
            value = data.get(field)
            is_present = value is not None and str(value).strip() != ""
            results["identity_fields"][field] = is_present
            if not is_present:
                results["missing_recommended"].append(field)

        return results

    def validate_batch(self, file_paths: List[Path]) -> Dict[str, Any]:
        """
        Validate a batch of files and compute aggregate rates.

        Args:
            file_paths: List of paths to JSON files

        Returns:
            Dict with aggregate stats (rates) and list of failed files
        """
        results = []
        for path in file_paths:
            results.append(self.validate_file(path))

        total = len(results)
        if total == 0:
            return {
                "total_files": 0,
                "cik_present_rate": 0.0,
                "company_name_present_rate": 0.0,
                "sic_code_present_rate": 0.0,
                "files_with_issues": []
            }

        # Calculate rates
        cik_present = sum(1 for r in results if r["identity_fields"].get("cik"))
        company_present = sum(1 for r in results if r["identity_fields"].get("company_name"))
        sic_present = sum(1 for r in results if r["identity_fields"].get("sic_code"))

        return {
            "total_files": total,
            "cik_present_rate": cik_present / total,
            "company_name_present_rate": company_present / total,
            "sic_code_present_rate": sic_present / total,
            "files_with_issues": [
                r for r in results 
                if r.get("missing_required") or not r.get("is_valid_json")
            ],
            "raw_results": results
        }
