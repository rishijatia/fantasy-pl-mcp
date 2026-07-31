import os
import sys
import tempfile

# Add the src directory to the path so pytest can import the package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Point the disk cache at a temporary directory BEFORE fpl_mcp is imported,
# so tests never read or write the user's real cache. Held in a module-level
# global so the directory is removed when the test process exits.
_cache_tmpdir = tempfile.TemporaryDirectory(prefix="fpl-mcp-test-cache-")
os.environ["FPL_CACHE_DIR"] = _cache_tmpdir.name

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the FPL cache before each test to avoid cross-test contamination."""
    from fpl_mcp.fpl.cache import cache

    cache.clear()
    yield
    cache.clear()
