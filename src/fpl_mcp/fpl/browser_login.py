# src/fpl_mcp/fpl/browser_login.py
"""Interactive FPL login through a real browser window.

FPL's PingOne client only redirects back to fantasy.premierleague.com, so we
can't run the OIDC flow ourselves with a localhost callback. Instead we launch
Chrome (or another Chromium browser) with a dedicated profile and the DevTools
protocol enabled, let the user sign in normally, and read the refresh token the
web app stores in web storage once login completes. The browser is closed as
soon as the token is captured so the web app can't rotate it out from under us.
"""

import asyncio
import json
import logging
import os
import platform
import shutil
import socket
import subprocess
from pathlib import Path

import httpx
import websockets

logger = logging.getLogger(__name__)

FPL_LOGIN_URL = "https://fantasy.premierleague.com/"
PROFILE_DIR = Path.home() / ".fpl-mcp" / "browser-profile"

# Reads the oidc-client-ts user record from either web storage area and
# returns just its refresh token (or null while the user is still signing in).
_READ_TOKEN_JS = """
(() => {
  for (const store of [localStorage, sessionStorage]) {
    for (let i = 0; i < store.length; i++) {
      const key = store.key(i);
      if (!key.startsWith('oidc.user:')) continue;
      try {
        const token = JSON.parse(store.getItem(key)).refresh_token;
        if (token) return token;
      } catch (e) {}
    }
  }
  return null;
})()
"""

# Drops the web app's copy of the tokens. The MCP now owns (and rotates) that
# refresh token, so the saved profile must not replay it on the next launch;
# only the account.premierleague.com SSO cookie is kept.
_CLEAR_TOKEN_JS = """
(() => {
  for (const store of [localStorage, sessionStorage]) {
    Object.keys(store).filter(k => k.startsWith('oidc.')).forEach(k => store.removeItem(k));
  }
})()
"""


class BrowserLoginError(Exception):
    """Raised when the browser can't be launched or login doesn't complete."""


def find_browser() -> str | None:
    """Locate a Chromium-based browser, honouring FPL_BROWSER_PATH."""
    override = os.getenv("FPL_BROWSER_PATH")
    if override:
        return override if Path(override).exists() else None

    system = platform.system()
    if system == "Darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
    elif system == "Windows":
        roots = [os.getenv(v) for v in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
        suffixes = [
            r"Google\Chrome\Application\chrome.exe",
            r"Microsoft\Edge\Application\msedge.exe",
            r"BraveSoftware\Brave-Browser\Application\brave.exe",
        ]
        candidates = [str(Path(r) / s) for r in roots if r for s in suffixes]
    else:
        names = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "brave-browser"]
        candidates = [p for p in (shutil.which(n) for n in names) if p]

    return next((c for c in candidates if Path(c).exists()), None)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def _cdp_call(ws_url: str, method: str, params: dict | None = None) -> dict:
    """Send one DevTools protocol command and return its result."""
    async with websockets.connect(ws_url, max_size=None, open_timeout=5) as ws:
        await ws.send(json.dumps({"id": 1, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            if msg.get("id") == 1:
                if "error" in msg:
                    raise BrowserLoginError(f"{method} failed: {msg['error']}")
                return msg.get("result", {})


async def _read_token(client: httpx.AsyncClient, port: int) -> str | None:
    """Check every open FPL tab for a stored refresh token."""
    targets = (await client.get(f"http://127.0.0.1:{port}/json/list")).json()
    for target in targets:
        if target.get("type") != "page":
            continue
        if not target.get("url", "").startswith("https://fantasy.premierleague.com"):
            continue
        result = await _cdp_call(
            target["webSocketDebuggerUrl"],
            "Runtime.evaluate",
            {"expression": _READ_TOKEN_JS, "returnByValue": True},
        )
        token = result.get("result", {}).get("value")
        if token:
            await _cdp_call(target["webSocketDebuggerUrl"], "Runtime.evaluate", {"expression": _CLEAR_TOKEN_JS})
            return token
    return None


async def _close_browser(client: httpx.AsyncClient, port: int, proc: subprocess.Popen) -> None:
    """Close the browser cleanly so the profile (and its SSO session) is saved."""
    try:
        version = (await client.get(f"http://127.0.0.1:{port}/json/version")).json()
        await _cdp_call(version["webSocketDebuggerUrl"], "Browser.close")
    except Exception as e:
        logger.debug(f"Browser.close failed, terminating instead: {e}")
    try:
        await asyncio.to_thread(proc.wait, 10)
    except subprocess.TimeoutExpired:
        proc.terminate()


async def capture_refresh_token(timeout: float = 300) -> str:
    """Open a browser at the FPL site and wait for the user to log in.

    Returns the refresh token once the web app has stored one. The dedicated
    profile persists between runs, so later logins are usually one click.
    """
    browser = find_browser()
    if not browser:
        raise BrowserLoginError(
            "No Chrome, Edge, Brave or Chromium install found. Set FPL_BROWSER_PATH "
            "to a Chromium-based browser executable."
        )

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    port = _free_port()
    proc = subprocess.Popen(
        [
            browser,
            f"--user-data-dir={PROFILE_DIR}",
            f"--remote-debugging-port={port}",
            "--remote-allow-origins=http://127.0.0.1",
            "--no-first-run",
            "--no-default-browser-check",
            "--new-window",
            FPL_LOGIN_URL,
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            while loop.time() < deadline:
                if proc.poll() is not None:
                    raise BrowserLoginError("The login window was closed before sign-in finished.")
                try:
                    token = await _read_token(client, port)
                except (httpx.HTTPError, OSError, BrowserLoginError, asyncio.TimeoutError, websockets.WebSocketException):
                    # DevTools not up yet, or a tab is mid-navigation; try again.
                    token = None
                if token:
                    await _close_browser(client, port, proc)
                    return token
                await asyncio.sleep(2)
            raise BrowserLoginError(f"Timed out after {int(timeout)}s waiting for FPL sign-in.")
    finally:
        if proc.poll() is None:
            proc.terminate()
