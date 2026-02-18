"""Unit tests for src/utils/dead_letter_queue.py — DeadLetterQueue."""

import json
import pytest
from pathlib import Path
from datetime import datetime

from src.utils.dead_letter_queue import DeadLetterQueue


@pytest.fixture
def dlq(tmp_path) -> DeadLetterQueue:
    return DeadLetterQueue(tmp_path / "logs" / "failed_files.json")


@pytest.fixture
def sample_items():
    return [Path("/data/raw/file1.html"), Path("/data/raw/file2.html")]


class TestLoad:
    """Tests for DeadLetterQueue.load()."""

    def test_returns_empty_list_when_file_missing(self, dlq):
        assert dlq.load() == []

    def test_returns_empty_list_on_corrupt_json(self, tmp_path):
        log_path = tmp_path / "bad.json"
        log_path.write_text("not valid json {{{")
        dlq = DeadLetterQueue(log_path)
        assert dlq.load() == []

    def test_loads_existing_records(self, dlq, sample_items):
        dlq.add_failures(sample_items, script_name="test")
        records = dlq.load()
        assert len(records) == 2

    def test_returns_list_of_dicts(self, dlq, sample_items):
        dlq.add_failures(sample_items, script_name="test")
        records = dlq.load()
        assert all(isinstance(r, dict) for r in records)


class TestAddFailures:
    """Tests for DeadLetterQueue.add_failures()."""

    def test_creates_log_file_on_first_write(self, dlq, sample_items):
        assert not dlq.log_path.exists()
        dlq.add_failures(sample_items, script_name="pipeline.py")
        assert dlq.log_path.exists()

    def test_creates_parent_directories(self, tmp_path):
        deep_path = tmp_path / "a" / "b" / "c" / "dlq.json"
        dlq = DeadLetterQueue(deep_path)
        dlq.add_failures([Path("/some/file.html")], script_name="test")
        assert deep_path.exists()

    def test_empty_list_is_no_op(self, dlq):
        dlq.add_failures([], script_name="test")
        assert not dlq.log_path.exists()

    def test_record_schema_has_required_fields(self, dlq):
        dlq.add_failures([Path("/data/raw/AAPL.html")], script_name="pipeline.py", reason="timeout")
        record = dlq.load()[0]
        assert "file" in record
        assert "timestamp" in record
        assert "reason" in record
        assert "script" in record
        assert "attempt_count" in record

    def test_attempt_count_starts_at_one(self, dlq):
        dlq.add_failures([Path("/data/raw/AAPL.html")], script_name="test")
        assert dlq.load()[0]["attempt_count"] == 1

    def test_script_name_stored_correctly(self, dlq):
        dlq.add_failures([Path("/data/raw/AAPL.html")], script_name="my_script.py")
        assert dlq.load()[0]["script"] == "my_script.py"

    def test_reason_stored_correctly(self, dlq):
        dlq.add_failures([Path("/data/raw/AAPL.html")], script_name="s", reason="oom")
        assert dlq.load()[0]["reason"] == "oom"

    def test_appends_to_existing_records(self, dlq):
        dlq.add_failures([Path("/data/raw/A.html")], script_name="s1")
        dlq.add_failures([Path("/data/raw/B.html")], script_name="s2")
        records = dlq.load()
        assert len(records) == 2

    def test_multiple_items_written_together(self, dlq, sample_items):
        dlq.add_failures(sample_items, script_name="test")
        assert len(dlq.load()) == 2

    def test_timestamp_is_iso_format(self, dlq):
        dlq.add_failures([Path("/data/raw/AAPL.html")], script_name="test")
        timestamp = dlq.load()[0]["timestamp"]
        dt = datetime.fromisoformat(timestamp)
        assert dt is not None


class TestExtractPath:
    """Tests for DeadLetterQueue._extract_path() static method."""

    def test_path_object_returns_string(self):
        result = DeadLetterQueue._extract_path(Path("/data/raw/file.html"))
        assert result == "/data/raw/file.html"
        assert isinstance(result, str)

    def test_string_returned_as_is(self):
        result = DeadLetterQueue._extract_path("/data/raw/file.html")
        assert result == "/data/raw/file.html"

    def test_tuple_extracts_first_element(self):
        result = DeadLetterQueue._extract_path(("/data/raw/file.html", "10-K", None))
        assert result == "/data/raw/file.html"

    def test_tuple_with_path_first_element(self):
        result = DeadLetterQueue._extract_path((Path("/data/raw/file.html"), "10-K"))
        assert result == "/data/raw/file.html"

    def test_other_type_converted_to_string(self):
        result = DeadLetterQueue._extract_path(42)
        assert result == "42"


class TestRemoveSuccesses:
    """Tests for DeadLetterQueue.remove_successes()."""

    @pytest.fixture
    def populated_dlq(self, dlq):
        files = [
            Path("/data/raw/A.html"),
            Path("/data/raw/B.html"),
            Path("/data/raw/C.html"),
        ]
        dlq.add_failures(files, script_name="test")
        return dlq

    def test_removes_successful_files(self, populated_dlq):
        populated_dlq.remove_successes(["/data/raw/A.html"])
        remaining = populated_dlq.load()
        files = [r["file"] for r in remaining]
        assert "/data/raw/A.html" not in files
        assert len(remaining) == 2

    def test_returns_count_of_removed(self, populated_dlq):
        removed = populated_dlq.remove_successes(["/data/raw/A.html", "/data/raw/B.html"])
        assert removed == 2

    def test_increments_attempt_count_on_remaining(self, populated_dlq):
        populated_dlq.remove_successes(["/data/raw/A.html"])
        remaining = populated_dlq.load()
        for record in remaining:
            assert record["attempt_count"] == 2

    def test_adds_last_retry_timestamp(self, populated_dlq):
        before = datetime.now()
        populated_dlq.remove_successes(["/data/raw/A.html"])
        after = datetime.now()

        for record in populated_dlq.load():
            ts = datetime.fromisoformat(record["last_retry"])
            assert before <= ts <= after

    def test_remove_all_leaves_empty(self, populated_dlq):
        populated_dlq.remove_successes([
            "/data/raw/A.html",
            "/data/raw/B.html",
            "/data/raw/C.html",
        ])
        assert populated_dlq.load() == []

    def test_remove_nonexistent_is_no_op(self, populated_dlq):
        removed = populated_dlq.remove_successes(["/data/raw/Z.html"])
        assert removed == 0
        assert len(populated_dlq.load()) == 3

    def test_noop_on_empty_dlq(self, dlq):
        removed = dlq.remove_successes(["/data/raw/A.html"])
        assert removed == 0


class TestClear:
    """Tests for DeadLetterQueue.clear()."""

    def test_clears_all_records(self, dlq, sample_items):
        dlq.add_failures(sample_items, script_name="test")
        dlq.clear()
        assert dlq.load() == []

    def test_creates_empty_file(self, dlq, sample_items):
        dlq.add_failures(sample_items, script_name="test")
        dlq.clear()
        assert dlq.log_path.exists()
        assert json.loads(dlq.log_path.read_text()) == []


class TestLen:
    """Tests for DeadLetterQueue.__len__()."""

    def test_len_zero_on_empty(self, dlq):
        assert len(dlq) == 0

    def test_len_matches_record_count(self, dlq, sample_items):
        dlq.add_failures(sample_items, script_name="test")
        assert len(dlq) == 2

    def test_len_updates_after_remove(self, dlq, sample_items):
        dlq.add_failures(sample_items, script_name="test")
        dlq.remove_successes([str(sample_items[0])])
        assert len(dlq) == 1
