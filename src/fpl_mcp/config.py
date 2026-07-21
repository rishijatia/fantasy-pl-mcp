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

# OIDC (PingOne) authentication. FPL migrated from the old users.premierleague.com
# form login to Ping Identity, fronted by the custom domain account.premierleague.com.
# The fantasy web app is a public OIDC client (authorization code + PKCE) that
# requests "openid profile email offline_access", so it receives a refresh token.
# The SPA (oidc-client-ts) persists its tokens in browser web storage under a key
# named "oidc.user:https://account.premierleague.com/as:<client_id>". We exchange
# that refresh token for short-lived access tokens and send them with the same
# "X-API-Authorization: Bearer" header the web app uses.
FPL_OIDC_AUTHORITY = os.getenv("FPL_OIDC_AUTHORITY", "https://account.premierleague.com/as")
FPL_TOKEN_URL = os.getenv("FPL_TOKEN_URL", f"{FPL_OIDC_AUTHORITY}/token")
FPL_OIDC_CLIENT_ID = os.getenv(
    "FPL_OIDC_CLIENT_ID", "bfcbaf69-aade-4c1b-8f00-c1cb8a193030"
)

# Caching configuration
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))  # Default: 1 hour

# Schema paths
STATIC_SCHEMA_PATH = SCHEMAS_DIR / "static_schema.json"

# Rate limiting configuration
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "20"))
RATE_LIMIT_PERIOD_SECONDS = int(os.getenv("RATE_LIMIT_PERIOD_SECONDS", "60"))

# League configuration. Team fetches are parallelized, so the ceiling can be
# higher than the old 25; keep a hard cap to stay polite to the FPL API.
LEAGUE_RESULTS_LIMIT = int(os.getenv("LEAGUE_RESULTS_LIMIT", "50"))