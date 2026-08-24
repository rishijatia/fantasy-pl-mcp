# src/fpl_mcp/fpl/oauth.py
"""OAuth2 / OIDC client for Premier League's PingOne identity provider.

FPL retired the old ``users.premierleague.com/accounts/login/`` form POST and
moved to PingOne (Ping Identity). The new provider does **not** support the
resource-owner-password grant, so an email/password pair cannot be exchanged
for a token directly. The supported route is authorization_code + PKCE, which
needs one interactive browser sign-in; after that the refresh_token grant keeps
access tokens alive without further interaction.

The registered redirect URI belongs to premierleague.com, so we cannot capture
the callback on a loopback port. Instead the user pastes the redirected URL
back and we parse the ``code`` out of it.
"""

import base64
import hashlib
import json
import logging
import os
import time
import urllib.parse
from typing import Any, Dict, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# Public client configuration, as published by the FPL web app bootstrap.
PING_ENVIRONMENT_ID = "68340de1-dfb9-412e-937c-20172986d129"
PING_CLIENT_ID = "1f243d70-a140-4035-8c41-341f5af5aa12"
PING_AUTH_BASE = f"https://auth.pingone.eu/{PING_ENVIRONMENT_ID}/as"

AUTHORIZE_ENDPOINT = f"{PING_AUTH_BASE}/authorize"
TOKEN_ENDPOINT = f"{PING_AUTH_BASE}/token"
DISCOVERY_ENDPOINT = f"{PING_AUTH_BASE}/.well-known/openid-configuration"

# The client accepts any path on www.premierleague.com. We deliberately pick a
# static text file: the site's own pages are OAuth clients themselves and their
# JS redeems any "?code=" it sees (and their router strips the fragment), which
# consumes our single-use code before the user can copy it. robots.txt serves
# text/plain with no JS at all, so the code stays intact in the address bar.
REDIRECT_URI = "https://www.premierleague.com/robots.txt"

# offline_access is what gets us a refresh token.
SCOPES = "openid profile email offline_access"

# Refresh a little early so a token never expires mid-request.
EXPIRY_SKEW_SECONDS = 120

REQUEST_TIMEOUT = 30


class OAuthError(RuntimeError):
    """Raised when the identity provider rejects a request."""


def generate_pkce_pair() -> Tuple[str, str]:
    """Return a (code_verifier, code_challenge) pair for PKCE S256."""
    verifier = base64.urlsafe_b64encode(os.urandom(64)).decode().rstrip("=")
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


def generate_state() -> str:
    """Return an opaque CSRF state value."""
    return base64.urlsafe_b64encode(os.urandom(24)).decode().rstrip("=")


def build_authorize_url(code_challenge: str, state: str) -> str:
    """Build the URL the user opens to sign in."""
    params = {
        "client_id": PING_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTHORIZE_ENDPOINT}?{urllib.parse.urlencode(params)}"


def parse_redirect_url(redirect_url: str, expected_state: Optional[str] = None) -> str:
    """Extract the authorization code from the URL the browser landed on.

    Accepts either a full URL or a bare code, so a user who copies only the
    code parameter still gets a working flow.
    """
    redirect_url = redirect_url.strip()
    if not redirect_url:
        raise OAuthError("No URL provided.")

    parsed = urllib.parse.urlparse(redirect_url)
    # The code may arrive in either half depending on response_mode; the
    # fragment is what we request, but accept a query-string code too.
    query = urllib.parse.parse_qs(parsed.query or "")
    query.update(urllib.parse.parse_qs(parsed.fragment or ""))

    # The provider reports failures in the query string rather than by status.
    if "error" in query:
        detail = query.get("error_description", query["error"])[0]
        raise OAuthError(f"Sign-in failed: {detail}")

    codes = query.get("code")
    if not codes:
        # Tolerate the user pasting just the code value.
        if not parsed.scheme and "&" not in redirect_url and "=" not in redirect_url:
            return redirect_url
        if "state" in query:
            raise OAuthError(
                "That URL has 'state' but no 'code' - the premierleague.com page "
                "consumed the code before you could copy it. Start the login "
                "again and copy the URL the moment it appears, or grab the "
                "redirect from your browser's Network tab."
            )
        raise OAuthError(
            "No 'code' parameter found in that URL. Copy the full address bar "
            "contents after being redirected to premierleague.com."
        )

    if expected_state is not None:
        returned_state = (query.get("state") or [None])[0]
        if returned_state != expected_state:
            raise OAuthError(
                "State mismatch between request and redirect - discarding this "
                "sign-in. Start the login again."
            )

    return codes[0]


def _post_token_request(data: Dict[str, str]) -> Dict[str, Any]:
    """POST to the token endpoint and return the parsed token response.

    The FPL client is a public client, so no client secret is sent.
    """
    try:
        response = requests.post(
            TOKEN_ENDPOINT,
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise OAuthError(f"Could not reach the identity provider: {exc}") from exc

    try:
        payload = response.json()
    except ValueError:
        raise OAuthError(
            f"Unexpected non-JSON response from token endpoint "
            f"(HTTP {response.status_code})."
        )

    if response.status_code >= 400 or "error" in payload:
        detail = payload.get("error_description") or payload.get("error") or "unknown error"
        raise OAuthError(f"Token request rejected: {detail}")

    if not payload.get("access_token"):
        raise OAuthError("Token response contained no access_token.")

    return payload


def _stamp_expiry(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Convert the relative expires_in into an absolute epoch timestamp."""
    tokens = dict(payload)
    expires_in = tokens.pop("expires_in", None)
    try:
        expires_in = int(expires_in)
    except (TypeError, ValueError):
        expires_in = 3600
    tokens["expires_at"] = int(time.time()) + expires_in
    return tokens


def exchange_code(code: str, code_verifier: str) -> Dict[str, Any]:
    """Exchange an authorization code for tokens."""
    payload = _post_token_request(
        {
            "grant_type": "authorization_code",
            "client_id": PING_CLIENT_ID,
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": code_verifier,
        }
    )
    tokens = _stamp_expiry(payload)
    if not tokens.get("refresh_token"):
        logger.warning(
            "No refresh_token returned; you will need to sign in again when the "
            "access token expires."
        )
    return tokens


def refresh_tokens(refresh_token: str) -> Dict[str, Any]:
    """Mint a new access token from a refresh token."""
    payload = _post_token_request(
        {
            "grant_type": "refresh_token",
            "client_id": PING_CLIENT_ID,
            "refresh_token": refresh_token,
        }
    )
    tokens = _stamp_expiry(payload)
    # Providers may or may not rotate the refresh token; keep the old one if not.
    tokens.setdefault("refresh_token", refresh_token)
    return tokens


def is_expired(tokens: Dict[str, Any], skew: int = EXPIRY_SKEW_SECONDS) -> bool:
    """Return True if the stored access token is missing or (nearly) expired."""
    if not tokens or not tokens.get("access_token"):
        return True
    expires_at = tokens.get("expires_at")
    if not expires_at:
        # Unknown expiry - assume usable and let a 401 trigger the refresh.
        return False
    try:
        return time.time() + skew >= float(expires_at)
    except (TypeError, ValueError):
        return True


def describe_token(tokens: Dict[str, Any]) -> str:
    """Human-readable summary of a token's remaining lifetime."""
    if not tokens or not tokens.get("access_token"):
        return "no access token stored"
    expires_at = tokens.get("expires_at")
    if not expires_at:
        return "access token stored (expiry unknown)"
    remaining = int(float(expires_at) - time.time())
    if remaining <= 0:
        return "access token expired"
    return f"access token valid for a further {remaining // 60}m {remaining % 60}s"


PENDING_FILE = ".fpl-mcp/pending_login.json"


def _pending_path():
    import pathlib as _pl
    return _pl.Path.home() / ".fpl-mcp" / "pending_login.json"


def save_pending_login(verifier: str, state: str) -> None:
    """Remember the PKCE verifier so the exchange can happen in a later run.

    PKCE binds the authorization code to a verifier held by the client. If the
    process that printed the sign-in URL exits, that verifier is lost and the
    code becomes unusable. Persisting it lets the user finish the sign-in
    whenever they like, from a fresh process.
    """
    path = _pending_path()
    path.parent.mkdir(exist_ok=True)
    payload = {"code_verifier": verifier, "state": state, "created_at": int(time.time())}
    with open(path, "w") as f:
        json.dump(payload, f)
    os.chmod(path, 0o600)


def load_pending_login() -> Optional[Dict[str, Any]]:
    """Return the stored PKCE verifier/state, if a sign-in is in progress."""
    path = _pending_path()
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not read pending login state: {e}")
        return None


def clear_pending_login() -> None:
    """Discard any stored PKCE verifier."""
    path = _pending_path()
    try:
        if path.exists():
            path.unlink()
    except Exception as e:
        logger.warning(f"Could not clear pending login state: {e}")


def jwt_expiry(token: str) -> Optional[int]:
    """Read the 'exp' claim from a JWT without verifying its signature.

    Used only to avoid sending a token we can already tell is dead; the
    provider remains the authority on validity.
    """
    if not token or token.count(".") != 2:
        return None
    try:
        body = token.split(".")[1]
        body += "=" * (-len(body) % 4)
        claims = json.loads(base64.urlsafe_b64decode(body).decode())
        exp = claims.get("exp")
        return int(exp) if exp is not None else None
    except Exception:
        return None


def is_jwt_expired(token: str, skew: int = EXPIRY_SKEW_SECONDS) -> bool:
    """True only when a token's own 'exp' claim proves it is expired."""
    exp = jwt_expiry(token)
    if exp is None:
        # Opaque or unparseable: let the provider decide.
        return False
    return time.time() + skew >= exp


def token_subject(tokens: Dict[str, Any]) -> Optional[str]:
    """Best-effort read of the 'sub' claim, for display only.

    The signature is not verified: this is a convenience for showing who is
    signed in, never for making an authorization decision.
    """
    token = (tokens or {}).get("id_token") or (tokens or {}).get("access_token")
    if not token or token.count(".") != 2:
        return None
    try:
        body = token.split(".")[1]
        body += "=" * (-len(body) % 4)
        claims = json.loads(base64.urlsafe_b64decode(body).decode())
        return claims.get("email") or claims.get("sub")
    except Exception:
        return None
