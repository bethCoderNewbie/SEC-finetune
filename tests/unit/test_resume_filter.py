"""Unit tests for src/utils/resume.py — ResumeFilter."""

import pytest
from pathlib import Path

from src.utils.resume import ResumeFilter


class TestIsProcessed:
    """Tests for ResumeFilter.is_processed()."""

    def test_returns_true_when_output_exists(self, tmp_path):
        output_dir = tmp_path / "processed"
        output_dir.mkdir()
        (output_dir / "AAPL_10K_segmented.json").touch()

        rf = ResumeFilter(output_dir, "_segmented.json")
        assert rf.is_processed(Path("data/raw/AAPL_10K.html")) is True

    def test_returns_false_when_output_missing(self, tmp_path):
        output_dir = tmp_path / "processed"
        output_dir.mkdir()

        rf = ResumeFilter(output_dir, "_segmented.json")
        assert rf.is_processed(Path("data/raw/AAPL_10K.html")) is False

    def test_returns_false_when_output_dir_missing(self, tmp_path):
        rf = ResumeFilter(tmp_path / "nonexistent", "_segmented.json")
        assert rf.is_processed(Path("data/raw/AAPL_10K.html")) is False

    def test_uses_stem_only_not_full_path(self, tmp_path):
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        (output_dir / "MSFT_10K_segmented.json").touch()

        rf = ResumeFilter(output_dir, "_segmented.json")
        # Deep path — only stem matters
        assert rf.is_processed(Path("a/b/c/MSFT_10K.html")) is True

    def test_custom_suffix(self, tmp_path):
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        (output_dir / "AAPL_10K_extracted_risks.json").touch()

        rf = ResumeFilter(output_dir, "_extracted_risks.json")
        assert rf.is_processed(Path("AAPL_10K.html")) is True


class TestGetProcessedStems:
    """Tests for ResumeFilter.get_processed_stems()."""

    def test_empty_dir_returns_empty_set(self, tmp_path):
        output_dir = tmp_path / "out"
        output_dir.mkdir()

        rf = ResumeFilter(output_dir, "_segmented.json")
        assert rf.get_processed_stems() == set()

    def test_nonexistent_dir_returns_empty_set(self, tmp_path):
        rf = ResumeFilter(tmp_path / "nonexistent", "_segmented.json")
        assert rf.get_processed_stems() == set()

    def test_returns_correct_stems(self, tmp_path):
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        (output_dir / "AAPL_10K_segmented.json").touch()
        (output_dir / "MSFT_10K_segmented.json").touch()
        (output_dir / "GOOG_10K_segmented.json").touch()

        rf = ResumeFilter(output_dir, "_segmented.json")
        stems = rf.get_processed_stems()

        assert stems == {"AAPL_10K", "MSFT_10K", "GOOG_10K"}

    def test_ignores_files_with_wrong_suffix(self, tmp_path):
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        (output_dir / "AAPL_10K_segmented.json").touch()
        (output_dir / "AAPL_10K_extracted_risks.json").touch()  # different suffix
        (output_dir / "notes.txt").touch()

        rf = ResumeFilter(output_dir, "_segmented.json")
        stems = rf.get_processed_stems()

        assert stems == {"AAPL_10K"}

    def test_custom_suffix_strips_correctly(self, tmp_path):
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        (output_dir / "AAPL_10K_extracted_risks.json").touch()

        rf = ResumeFilter(output_dir, "_extracted_risks.json")
        assert rf.get_processed_stems() == {"AAPL_10K"}


class TestFilterUnprocessed:
    """Tests for ResumeFilter.filter_unprocessed()."""

    def test_all_files_returned_when_none_processed(self, tmp_path):
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        files = [Path("raw/A.html"), Path("raw/B.html"), Path("raw/C.html")]

        rf = ResumeFilter(output_dir, "_segmented.json")
        result = rf.filter_unprocessed(files, quiet=True)

        assert result == files

    def test_returns_only_unprocessed(self, tmp_path):
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        (output_dir / "A_segmented.json").touch()

        files = [Path("raw/A.html"), Path("raw/B.html"), Path("raw/C.html")]
        rf = ResumeFilter(output_dir, "_segmented.json")
        result = rf.filter_unprocessed(files, quiet=True)

        assert Path("raw/A.html") not in result
        assert Path("raw/B.html") in result
        assert Path("raw/C.html") in result
        assert len(result) == 2

    def test_returns_empty_when_all_processed(self, tmp_path):
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        for name in ["A", "B", "C"]:
            (output_dir / f"{name}_segmented.json").touch()

        files = [Path("raw/A.html"), Path("raw/B.html"), Path("raw/C.html")]
        rf = ResumeFilter(output_dir, "_segmented.json")
        result = rf.filter_unprocessed(files, quiet=True)

        assert result == []

    def test_prints_skip_count_when_not_quiet(self, tmp_path, capsys):
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        (output_dir / "A_segmented.json").touch()

        files = [Path("A.html"), Path("B.html")]
        rf = ResumeFilter(output_dir, "_segmented.json")
        rf.filter_unprocessed(files, quiet=False)

        captured = capsys.readouterr()
        assert "Skipping 1" in captured.out

    def test_quiet_suppresses_print(self, tmp_path, capsys):
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        (output_dir / "A_segmented.json").touch()

        files = [Path("A.html"), Path("B.html")]
        rf = ResumeFilter(output_dir, "_segmented.json")
        rf.filter_unprocessed(files, quiet=True)

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_empty_input_returns_empty(self, tmp_path):
        rf = ResumeFilter(tmp_path / "out", "_segmented.json")
        assert rf.filter_unprocessed([], quiet=True) == []


class TestStripStemSuffix:
    """Tests for ResumeFilter._strip_stem_suffix() internal helper."""

    def test_strips_suffix_from_right(self):
        rf = ResumeFilter(Path("."), "_segmented.json")
        assert rf._strip_stem_suffix("AAPL_10K_segmented") == "AAPL_10K"

    def test_does_not_strip_from_middle(self):
        rf = ResumeFilter(Path("."), "_segmented.json")
        # "_segmented" appears in the middle but suffix check only strips from right
        result = rf._strip_stem_suffix("file_segmented_v2_segmented")
        assert result == "file_segmented_v2"

    def test_no_match_returns_original(self):
        rf = ResumeFilter(Path("."), "_segmented.json")
        assert rf._strip_stem_suffix("AAPL_10K_other") == "AAPL_10K_other"

    def test_multi_part_suffix(self):
        rf = ResumeFilter(Path("."), "_extracted_risks.json")
        assert rf._strip_stem_suffix("AAPL_10K_extracted_risks") == "AAPL_10K"
