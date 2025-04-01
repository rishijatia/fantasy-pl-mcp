import pytest
import os
import sys

# Add the src directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

def test_package_structure():
    """Test that the package structure is correct."""
    # Check that src directory exists
    assert os.path.isdir(os.path.join(os.path.dirname(__file__), "../src")), "src directory should exist"
    
    # Check that fpl_mcp package directory exists
    assert os.path.isdir(os.path.join(os.path.dirname(__file__), "../src/fpl_mcp")), "fpl_mcp package should exist"
    
    # Check that key files exist
    key_files = [
        "../src/fpl_mcp/__init__.py",
        "../src/fpl_mcp/__main__.py",
        "../src/fpl_mcp/config.py",
        "../src/fpl_mcp/fpl/api.py",
        "../src/fpl_mcp/fpl/cache.py",
        "../src/fpl_mcp/fpl/rate_limiter.py",
        "../pyproject.toml"
    ]
    
    for file_path in key_files:
        full_path = os.path.join(os.path.dirname(__file__), file_path)
        assert os.path.isfile(full_path), f"{file_path} should exist"
    
    # Check that package can be imported
    import fpl_mcp
    assert hasattr(fpl_mcp, "__version__"), "Package should have __version__ attribute"
    assert fpl_mcp.__version__ == "0.1.4", "Package version should be 0.1.4"

def test_config_module():
    """Test that the config module has the expected attributes."""
    from fpl_mcp import config
    
    # Check that config module has expected attributes
    expected_attributes = [
        "FPL_API_BASE_URL",
        "FPL_USER_AGENT",
        "CACHE_TTL",
        "CACHE_DIR",
        "SCHEMAS_DIR",
        "STATIC_SCHEMA_PATH",
        "RATE_LIMIT_MAX_REQUESTS",
        "RATE_LIMIT_PERIOD_SECONDS"
    ]
    
    for attr in expected_attributes:
        assert hasattr(config, attr), f"Config should have {attr} attribute"
    
    # Check some values
    assert config.FPL_API_BASE_URL == "https://fantasy.premierleague.com/api", "API URL should be correct"
    assert isinstance(config.CACHE_TTL, int), "CACHE_TTL should be an integer"
    assert isinstance(config.RATE_LIMIT_MAX_REQUESTS, int), "RATE_LIMIT_MAX_REQUESTS should be an integer"