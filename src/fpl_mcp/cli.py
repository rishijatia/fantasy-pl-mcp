# src/fpl_mcp/cli.py
import os
import sys
import json
import argparse
import getpass
import asyncio
from pathlib import Path


def _read_long_secret(prompt):
    """Read a possibly very long secret line from the terminal.

    getpass()/input() read the tty in canonical mode, which on macOS/BSD caps a
    single input line at MAX_CANON (~1024 bytes). The OIDC refresh token is over
    1KB, so pasting it into a normal prompt fills that buffer and freezes the
    terminal. Switching the tty to non-canonical mode removes the line limit so
    arbitrarily long pastes are read reliably.
    """
    # Piped / non-interactive stdin: a plain read has no canonical limit.
    if not sys.stdin.isatty():
        return sys.stdin.readline().strip()

    try:
        import termios
    except ImportError:
        # Non-POSIX (e.g. Windows): getpass is fine there.
        return getpass.getpass(prompt).strip()

    sys.stdout.write(prompt)
    sys.stdout.flush()

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    new = termios.tcgetattr(fd)
    new[3] = new[3] & ~(termios.ICANON | termios.ECHO)  # lflags
    new[6][termios.VMIN] = 1  # cc: block until at least 1 byte
    new[6][termios.VTIME] = 0

    buf = b""
    try:
        termios.tcsetattr(fd, termios.TCSANOW, new)
        while True:
            chunk = os.read(fd, 4096)
            if not chunk:
                break
            if b"\x03" in chunk:  # Ctrl-C
                raise KeyboardInterrupt
            terminators = [i for i in (chunk.find(b"\n"), chunk.find(b"\r")) if i != -1]
            if terminators:
                buf += chunk[: min(terminators)]
                break
            buf += chunk
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.write("\n")
        sys.stdout.flush()

    # Strip bracketed-paste markers if the terminal emitted them.
    for marker in (b"\x1b[200~", b"\x1b[201~"):
        buf = buf.replace(marker, b"")
    return buf.decode("utf-8", "replace").strip()


def _extract_refresh_token(pasted):
    """Accept either a bare refresh token or a full oidc.user JSON blob."""
    if pasted.startswith("{"):
        try:
            return json.loads(pasted).get("refresh_token", "") or ""
        except json.JSONDecodeError:
            return ""
    return pasted


def setup_credentials():
    """Interactive CLI for setting up FPL credentials with encryption"""
    print("FPL MCP Server - Credential Setup")
    print("=================================")
    print("FPL now uses PingOne (OIDC) login, so this tool authenticates with an")
    print("OIDC refresh token instead of your email/password.")
    print()
    print("To get your refresh token:")
    print("  1. Log in at https://fantasy.premierleague.com in your browser.")
    print("  2. Open DevTools (F12) -> Application -> Local storage ->")
    print("     https://fantasy.premierleague.com")
    print("  3. Click the key starting with 'oidc.user:'.")
    print("  4. Copy the whole JSON value and paste it below (the refresh token")
    print("     will be extracted), or paste just its 'refresh_token' field.")
    print()
    print("Your token will be encrypted and stored securely in ~/.fpl-mcp/")
    print()

    # Get credentials. The pasted value can exceed the terminal's canonical-mode
    # line limit, so read it in non-canonical mode to avoid a frozen paste.
    pasted = _read_long_secret("Paste the oidc.user JSON (or just the refresh token): ")
    refresh_token = _extract_refresh_token(pasted)
    if not refresh_token:
        print(
            "Error: could not find a refresh token in the pasted value. "
            "Paste the full oidc.user JSON or its 'refresh_token' field."
        )
        return False

    team_id = input("Enter your FPL team ID: ").strip()
    if not team_id:
        print("Error: team ID is required.")
        return False

    try:
        # Import credential manager
        from .fpl.credential_manager import CredentialManager

        # Initialize credential manager and store credentials
        credential_manager = CredentialManager()
        credential_manager.store_credentials(refresh_token, team_id)
        
        print("\nCredentials encrypted and saved successfully!")
        print("Your refresh token is now stored securely using encryption.")
        print("Run 'fpl-mcp-config test' now to validate it — the stored token can")
        print("be superseded by your browser session, so don't wait too long.")

        # Check if legacy credentials exist and offer to clean them up
        legacy_files = []
        config_dir = Path.home() / ".fpl-mcp"
        
        if (config_dir / ".env").exists():
            legacy_files.append(str(config_dir / ".env"))
        if (config_dir / "config.json").exists():
            legacy_files.append(str(config_dir / "config.json"))
            
        if legacy_files:
            print("\nLegacy credential files detected:")
            for file in legacy_files:
                print(f"  - {file}")
            print("\nThese files contain plaintext credentials and are no longer needed.")
            remove_legacy = input("Would you like to remove them? (y/N): ").lower()
            
            if remove_legacy == 'y':
                for file in legacy_files:
                    try:
                        os.remove(file)
                        print(f"Removed: {file}")
                    except Exception as e:
                        print(f"Could not remove {file}: {e}")
        
        print("Configuration successful!")
        return True
        
    except Exception as e:
        print(f"Error saving encrypted credentials: {e}")
        print("You may need to install the cryptography library: pip install cryptography")
        return False

async def test_auth():
    """Test authentication with FPL API"""
    try:
        # Import here to avoid circular imports
        from .fpl.auth_manager import get_auth_manager
        
        auth_manager = get_auth_manager()

        if not auth_manager._refresh_token or not auth_manager.team_id:
            print(
                "Authentication is not configured. "
                "Run 'fpl-mcp-config setup' to add your refresh token and team ID."
            )
            return False

        # /my-team/ rejects requests without a valid X-API-Authorization
        # header, so this proves the API accepts our token end-to-end
        # (/entry/ is public and would succeed even with a bad token).
        team_data = await auth_manager.get_my_team()
        entry_data = await auth_manager.get_entry_data()

        print("Authentication successful!")
        print(f"Team name: {entry_data.get('name', 'Unknown')}")
        print(f"Manager: {entry_data.get('player_first_name', '')} {entry_data.get('player_last_name', '')}")
        print(f"Overall rank: {entry_data.get('summary_overall_rank', 'Unknown')}")
        print(f"Squad picks returned: {len(team_data.get('picks', []))}")
        return True
    except Exception as e:
        print(f"Authentication failed: {e}")
        return False
    finally:
        # Clean up resources
        try:
            await auth_manager.close()
        except:
            pass

def main():
    parser = argparse.ArgumentParser(description="FPL MCP Server Configuration")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    subparsers.add_parser("setup", help="Set up FPL credentials")
    subparsers.add_parser("test", help="Test FPL authentication")

    args = parser.parse_args()
    
    if args.command == "setup":
        setup_credentials()
    elif args.command == "test":
        asyncio.run(test_auth())
    else:
        parser.print_help()

if __name__ == "__main__":
    main()