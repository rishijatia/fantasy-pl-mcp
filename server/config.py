import os
import pathlib
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Make this module importable from anywhere
def get_config():
    # Base paths
    BASE_DIR = pathlib.Path(__file__).parent.absolute()
    SCHEMAS_DIR = BASE_DIR / "schemas"
    CACHE_DIR = BASE_DIR / "fpl_cache"

    # FPL API configuration
    FPL_API_BASE_URL = "https://fantasy.premierleague.com/api"
    FPL_USER_AGENT = "Fantasy-PL-MCP/0.1.0"

    # Caching configuration
    CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))  # Default: 1 hour

    # Schema paths
    STATIC_SCHEMA_PATH = SCHEMAS_DIR / "static_schema.json"

    # Rate limiting configuration
    RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "20"))
    RATE_LIMIT_PERIOD_SECONDS = int(os.getenv("RATE_LIMIT_PERIOD_SECONDS", "60"))
    
    return {
        "BASE_DIR": BASE_DIR,
        "SCHEMAS_DIR": SCHEMAS_DIR,
        "CACHE_DIR": CACHE_DIR,
        "FPL_API_BASE_URL": FPL_API_BASE_URL,
        "FPL_USER_AGENT": FPL_USER_AGENT,
        "CACHE_TTL": CACHE_TTL,
        "STATIC_SCHEMA_PATH": STATIC_SCHEMA_PATH,
        "RATE_LIMIT_MAX_REQUESTS": RATE_LIMIT_MAX_REQUESTS,
        "RATE_LIMIT_PERIOD_SECONDS": RATE_LIMIT_PERIOD_SECONDS,
    }

# Export configuration values
config = get_config()
BASE_DIR = config["BASE_DIR"]
SCHEMAS_DIR = config["SCHEMAS_DIR"]
CACHE_DIR = config["CACHE_DIR"]
FPL_API_BASE_URL = config["FPL_API_BASE_URL"]
FPL_USER_AGENT = config["FPL_USER_AGENT"]
CACHE_TTL = config["CACHE_TTL"]
STATIC_SCHEMA_PATH = config["STATIC_SCHEMA_PATH"]
RATE_LIMIT_MAX_REQUESTS = config["RATE_LIMIT_MAX_REQUESTS"]
RATE_LIMIT_PERIOD_SECONDS = config["RATE_LIMIT_PERIOD_SECONDS"]