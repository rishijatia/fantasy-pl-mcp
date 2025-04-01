import os
import pathlib
from importlib import resources
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

# Base paths - handle both development and installed package
try:
    # When installed as package
    with resources.path("fpl_mcp", "__init__.py") as p:
        BASE_DIR = p.parent
except (ImportError, ModuleNotFoundError):
    # During development
    BASE_DIR = pathlib.Path(__file__).parent.absolute()

SCHEMAS_DIR = BASE_DIR / "schemas"
# Use user cache dir for persistent cache
CACHE_DIR = pathlib.Path(os.getenv("FPL_CACHE_DIR", str(pathlib.Path.home() / ".cache" / "fpl-mcp")))

# FPL API configuration
FPL_API_BASE_URL = "https://fantasy.premierleague.com/api"
FPL_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
FPL_LOGIN_URL = "https://users.premierleague.com/accounts/login/"

# Caching configuration
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))  # Default: 1 hour

# Schema paths
STATIC_SCHEMA_PATH = SCHEMAS_DIR / "static_schema.json"

# Rate limiting configuration
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "20"))
RATE_LIMIT_PERIOD_SECONDS = int(os.getenv("RATE_LIMIT_PERIOD_SECONDS", "60"))

# League configuration
LEAGUE_RESULTS_LIMIT = 25