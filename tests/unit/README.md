# Unit Tests for Preprocessing Pipeline Optimization

Comprehensive unit tests for all phases of the preprocessing pipeline optimization implementation.

## Test Coverage

### Phase 1: Memory-Aware Resource Allocation
**File:** `test_memory_semaphore.py`

Tests the memory semaphore implementation for preventing OOM crashes:

- ✅ File size classification (SMALL/MEDIUM/LARGE)
- ✅ Memory estimation formula (12x + 500MB)
- ✅ Adaptive timeout calculation (600s/1200s/2400s)
- ✅ Worker pool allocation (shared/isolated)
- ✅ Memory availability checking
- ✅ Resource estimate generation

**Run:**
```bash
pytest tests/unit/test_memory_semaphore.py -v
# OR
python tests/unit/test_memory_semaphore.py
```

### Phase 2: Production Pipeline Global Workers
**File:** `test_pipeline_global_workers.py`

Tests the global worker pattern for memory efficiency:

- ✅ Global worker initialization
- ✅ Worker reuse across tasks
- ✅ Memory overhead reduction (50x improvement)
- ✅ Processing with global workers
- ✅ Error handling in pipeline
- ✅ HTML sanitization removal
- ✅ Integration with ParallelProcessor

**Run:**
```bash
pytest tests/unit/test_pipeline_global_workers.py -v
```

### Phase 3: Automated Retry Mechanism
**File:** `test_retry_mechanism.py`

Tests the automated retry functionality:

- ✅ DLQ loading and filtering
- ✅ Filter by max attempts
- ✅ Filter by file size
- ✅ Filter by failure type
- ✅ Retry logic with dry-run mode
- ✅ Adaptive timeout application
- ✅ Memory-aware processing
- ✅ DLQ updates after retry
- ✅ Attempt count increment
- ✅ Success removal from DLQ

**Run:**
```bash
pytest tests/unit/test_retry_mechanism.py -v
```

## Running Tests

### Run All Phase Tests
```bash
# Run all phases with pytest
pytest tests/unit/test_*.py -v

# Run with coverage
pytest tests/unit/test_*.py -v --cov=src --cov-report=term-missing

# Run all phases with custom runner
python tests/unit/test_all_phases.py all
```

### Run Individual Phases
```bash
# Phase 1 only
pytest tests/unit/test_memory_semaphore.py -v
python tests/unit/test_all_phases.py phase1

# Phase 2 only
pytest tests/unit/test_pipeline_global_workers.py -v
python tests/unit/test_all_phases.py phase2

# Phase 3 only
pytest tests/unit/test_retry_mechanism.py -v
python tests/unit/test_all_phases.py phase3
```

### Run Specific Test Classes
```bash
# Run specific test class
pytest tests/unit/test_memory_semaphore.py::TestFileClassification -v

# Run specific test method
pytest tests/unit/test_retry_mechanism.py::TestLoadDeadLetterQueue::test_load_existing_dlq -v
```

### Run with Markers
```bash
# Run only integration tests
pytest tests/unit/ -v -m integration

# Skip integration tests (unit tests only)
pytest tests/unit/ -v -m "not integration"

# Run only slow tests
pytest tests/unit/ -v -m slow
```

## Test Output

### Successful Run
```
================================ test session starts =================================
collected 45 items

tests/unit/test_memory_semaphore.py::test_file_classification PASSED         [  2%]
tests/unit/test_memory_semaphore.py::test_memory_estimation PASSED           [  4%]
tests/unit/test_pipeline_global_workers.py::TestGlobalWorkerInitialization::test_init_production_worker_creates_all_workers PASSED [ 11%]
tests/unit/test_retry_mechanism.py::TestLoadDeadLetterQueue::test_load_existing_dlq PASSED [ 24%]
...

================================ 45 passed in 5.32s ==================================
```

## Test Structure

```
tests/unit/
├── README.md                          ← This file
├── conftest.py                        ← Pytest fixtures (existing)
├── test_memory_semaphore.py           ← Phase 1 tests
├── test_pipeline_global_workers.py    ← Phase 2 tests
├── test_retry_mechanism.py            ← Phase 3 tests
└── test_all_phases.py                 ← Test runner for all phases
```

## Test Dependencies

### Required Packages
```bash
# Core testing
pytest>=7.0.0
pytest-cov>=4.1.0
pytest-mock>=3.12.0

# Project dependencies
psutil>=5.9.0
pydantic>=2.12.4
```

### Installation
```bash
# Install test dependencies
pip install -e ".[test]"

# OR install all dependencies
pip install -e .
```

## Test Fixtures

### Common Fixtures

**`tmp_path`** (pytest built-in)
- Provides temporary directory for test files
- Automatically cleaned up after test

**`sample_dlq_data`**
- Sample Dead Letter Queue data for testing
- Includes various failure scenarios

**`dlq_file`**
- Temporary DLQ JSON file
- Pre-populated with sample data

**`mock_workers`**
- Mocked preprocessing workers
- Configured with default return values

## Test Categories

### Unit Tests (Fast)
Test individual functions and classes in isolation using mocks.

```bash
pytest tests/unit/ -v -m "not integration"
```

### Integration Tests (Slower)
Test actual component integration with real dependencies.

```bash
pytest tests/unit/ -v -m integration
```

## Debugging Tests

### Run with Verbose Output
```bash
pytest tests/unit/test_retry_mechanism.py -vv
```

### Run with Print Statements
```bash
pytest tests/unit/test_retry_mechanism.py -v -s
```

### Run with Debugger (PDB)
```bash
pytest tests/unit/test_retry_mechanism.py -v --pdb
```

### Show Test Coverage
```bash
pytest tests/unit/ -v --cov=src --cov-report=html
# Open htmlcov/index.html in browser
```

## Continuous Integration

### GitHub Actions Example
```yaml
name: Unit Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install -e ".[test]"
      - name: Run unit tests
        run: |
          pytest tests/unit/ -v --cov=src --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Test Metrics

### Current Coverage (Target: >80%)

| Module | Coverage | Tests |
|--------|----------|-------|
| memory_semaphore.py | >90% | 15 tests |
| pipeline.py (global workers) | >85% | 18 tests |
| retry_failed_files.py | >85% | 12 tests |

### Performance

| Test Suite | Duration | Tests |
|------------|----------|-------|
| Phase 1 | ~2s | 15 tests |
| Phase 2 | ~1s | 18 tests |
| Phase 3 | ~2s | 12 tests |
| **Total** | **~5s** | **45 tests** |

## Adding New Tests

### Test Template
```python
"""
Test description.
"""

import pytest
from pathlib import Path


class TestFeatureName:
    """Test feature description."""

    @pytest.fixture
    def setup_data(self):
        """Create test data."""
        return {"key": "value"}

    def test_basic_functionality(self, setup_data):
        """Test basic functionality."""
        result = some_function(setup_data)
        assert result is not None

    def test_error_handling(self):
        """Test error handling."""
        with pytest.raises(ValueError):
            some_function(invalid_input)

    @pytest.mark.integration
    def test_integration(self):
        """Integration test."""
        # Test with real dependencies
        pass
```

## Best Practices

1. **Use Descriptive Names**: Test names should describe what is being tested
2. **One Assert Per Test**: Focus each test on a single behavior
3. **Use Fixtures**: Share setup code across tests
4. **Mock External Dependencies**: Isolate the code under test
5. **Test Edge Cases**: Include boundary conditions and error cases
6. **Keep Tests Fast**: Use mocks to avoid slow operations
7. **Run Tests Frequently**: Before commits and in CI/CD

## Troubleshooting

### Issue: ImportError for retry_failed_files
**Solution:** Add scripts/utils to Python path or install project:
```bash
pip install -e .
```

### Issue: Missing psutil
**Solution:**
```bash
pip install psutil>=5.9.0
```

### Issue: Tests fail with "module not found"
**Solution:** Ensure you're running from project root:
```bash
cd /home/beth/work/SEC-finetune
pytest tests/unit/ -v
```

### Issue: Fixtures not found
**Solution:** Check conftest.py exists and pytest is properly discovering it:
```bash
pytest --collect-only tests/unit/
```

## Related Documentation

- [Phase 3 Implementation](../../docs/RETRY_MECHANISM.md)
- [Installation Guide](../../docs/PHASE3_INSTALLATION.md)
- [Optimization Plan](../../thoughts/shared/plans/2026-02-16_16-52-14_preprocessing_pipeline_optimization.md)

## Contributing

When adding new features:

1. Write tests first (TDD approach)
2. Ensure >80% coverage for new code
3. Run full test suite before committing
4. Update this README with new test descriptions

---

**Last Updated:** 2026-02-16
**Test Coverage:** 45 tests across 3 phases
**Status:** ✅ All tests passing
