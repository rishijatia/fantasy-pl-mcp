# Tests for Fantasy Premier League MCP Server

This directory contains tests for the Fantasy Premier League MCP server package.

## Running Tests

To run the tests, make sure you have pytest and pytest-asyncio installed:

```bash
pip install pytest pytest-asyncio
```

Then run the tests:

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test
pytest tests/test_api.py::test_bootstrap_static_api
```

## Test Structure

- `test_api.py` - Tests for the FPL API client and data formatting
- `conftest.py` - Pytest configuration

## Test Design Principles

1. **Isolation**: Tests use mocks to avoid real API calls, making them reliable and fast
2. **Independence**: Each test can run independently of others
3. **Coverage**: Tests cover core functionality needed for MCP server operation
4. **CI-friendly**: Tests run automatically on GitHub through the workflow

## Adding Tests

When adding new tests, follow these guidelines:

1. Mock external dependencies (like API calls)
2. Use descriptive test names and docstrings
3. Add assertions that verify both data structure and content
4. Group related tests in the same file
5. Ensure tests are stateless and don't leave side effects