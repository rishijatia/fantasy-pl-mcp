# Fantasy Premier League MCP - Development Guide

## Build & Test Commands
- Run server: `python src/fpl_mcp/__main__.py`
- Run with MCP Inspector: `npx @modelcontextprotocol/inspector uv run src/fpl_mcp/__main__.py`
- Run all tests: `pytest`
- Run single test: `pytest tests/test_api.py::test_bootstrap_static_api`
- Typecheck: `mypy src`
- Lint: `flake8 src`
- Format: `black src && isort src`
- Build package: `uv build`

## Code Style
- Use PEP8 naming: snake_case for functions/variables, PascalCase for classes
- Include type hints for all functions and return values
- Format docstrings with Args/Returns sections
- Use black (line length 88) and isort for formatting
- Implement comprehensive error handling with specific exceptions
- Follow repository structure: src/fpl_mcp/fpl/{resources, tools}
- Tests should use mocks to avoid actual API calls

## Project Structure
- Resources provide data (in fpl.resources.*)
- Tools provide functionality (in fpl.tools.*)
- All API calls should use caching and rate limiting
- Use async/await pattern for all network operations
- Log all requests with detailed information