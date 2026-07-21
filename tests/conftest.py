import os
import sys
import tempfile

# Add the src directory to the path so pytest can import the package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Point the disk cache at a temporary directory BEFORE fpl_mcp is imported,
# so tests never read or write the user's real cache.
os.environ["FPL_CACHE_DIR"] = tempfile.mkdtemp(prefix="fpl-mcp-test-cache-")

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the FPL cache before each test to avoid cross-test contamination."""
    from fpl_mcp.fpl.cache import cache

    cache.clear()
    yield
    cache.clear()
