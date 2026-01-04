"""
Feature validation tests for SEC Filing Analyzer.

This package contains validation tests for:
- Sentiment analysis (LM dictionary-based)
- Readability analysis (Gunning Fog, Flesch-Kincaid, etc.)
- Golden sentence deterministic verification

Tests use dynamically resolved paths via TestDataConfig to
find test data in timestamped run directories.
"""
