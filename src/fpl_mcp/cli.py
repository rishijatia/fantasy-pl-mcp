# src/fpl_mcp/cli.py
import os
import json
import argparse
import getpass
import asyncio
from pathlib import Path

def setup_credentials():
    """Interactive CLI for setting up FPL credentials with encryption"""
    print("FPL MCP Server - Credential Setup")
    print("=================================")
    print("This will set up your FPL credentials for use with the MCP server.")
    print("Your credentials will be encrypted and stored securely in ~/.fpl-mcp/")
    print()
    
    # Get credentials
    email = input("Enter your FPL email: ")
    password = getpass.getpass("Enter your FPL password: ")
    team_id = input("Enter your FPL team ID: ")
    
    # Validate basic input
    if not email or not password or not team_id:
        print("Error: All fields are required.")
        return False
    
    try:
        # Import credential manager
        from .fpl.credential_manager import CredentialManager
        
        # Initialize credential manager and store credentials
        credential_manager = CredentialManager()
        credential_manager.store_credentials(email, password, team_id)
        
        print("\nCredentials encrypted and saved successfully!")
        print("Your password is now stored securely using encryption.")
        
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
        entry_data = await auth_manager.get_entry_data()
        
        print("Authentication successful!")
        print(f"Team name: {entry_data.get('name', 'Unknown')}")
        print(f"Manager: {entry_data.get('player_first_name', '')} {entry_data.get('player_last_name', '')}")
        print(f"Overall rank: {entry_data.get('summary_overall_rank', 'Unknown')}")
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

def login(redirect_url=None):
    """Interactive OAuth2 (PKCE) sign-in against the Premier League IdP.

    If redirect_url is given, finish a sign-in started by an earlier run using
    the stored PKCE verifier instead of beginning a new one.
    """
    from .fpl.oauth import (
        OAuthError,
        build_authorize_url,
        clear_pending_login,
        describe_token,
        exchange_code,
        generate_pkce_pair,
        generate_state,
        load_pending_login,
        parse_redirect_url,
        save_pending_login,
        token_subject,
    )
    from .fpl.auth_manager import get_auth_manager

    # --- Completing a previously started sign-in -------------------------
    if redirect_url:
        pending = load_pending_login()
        if not pending:
            print("No sign-in is in progress. Run 'fpl-mcp-config login' first.")
            return False
        verifier = pending.get("code_verifier")
        state = pending.get("state")
        try:
            code = parse_redirect_url(redirect_url, expected_state=state)
        except OAuthError as e:
            print(f"\nError: {e}")
            return False
        return _finish_login(code, verifier)

    # --- Starting a new sign-in ------------------------------------------
    verifier, challenge = generate_pkce_pair()
    state = generate_state()
    auth_url = build_authorize_url(challenge, state)

    # Persist before printing: the code is worthless without this verifier.
    save_pending_login(verifier, state)

    print("\nFPL sign-in")
    print("=" * 60)
    print("\n1. Open this URL in your browser and sign in as normal:\n")
    print(auth_url)
    print("\n2. You will land on a plain-text robots.txt page. That is expected -")
    print("   it is deliberately a page with no JavaScript, so nothing can strip")
    print("   the code. The address bar will end with '?code=...'.")
    print("\n3. Copy that entire URL and paste it below.")
    print("\n   (If you lose this prompt, you can finish later with:")
    print("    fpl-mcp-config login --complete \"<the URL>\")\n")

    try:
        import webbrowser
        if webbrowser.open(auth_url):
            print("(A browser window should have opened for you.)\n")
    except Exception:
        pass

    try:
        pasted = input("Redirected URL: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled. Finish later with: fpl-mcp-config login --complete \"<URL>\"")
        return False

    try:
        code = parse_redirect_url(pasted, expected_state=state)
    except OAuthError as e:
        print(f"\nError: {e}")
        print("The sign-in URL is still valid - retry with:")
        print('  fpl-mcp-config login --complete "<URL>"')
        return False

    return _finish_login(code, verifier)


def _finish_login(code, verifier):
    """Exchange an authorization code for tokens and store them."""
    from .fpl.oauth import (
        OAuthError, clear_pending_login, describe_token, exchange_code, token_subject,
    )
    from .fpl.auth_manager import get_auth_manager

    print("\nExchanging authorization code for tokens...")
    try:
        tokens = exchange_code(code, verifier)
    except OAuthError as e:
        print(f"\nError: {e}")
        print("\nAuthorization codes are single-use and short-lived. Run")
        print("'fpl-mcp-config login' again to get a fresh one.")
        return False

    get_auth_manager().store_oauth_tokens(tokens)
    clear_pending_login()

    who = token_subject(tokens)
    print("\nSigned in successfully.")
    if who:
        print(f"  Account:       {who}")
    print(f"  Token status:  {describe_token(tokens)}")
    if tokens.get("refresh_token"):
        print("  Refresh token: stored - future calls renew automatically.")
    else:
        print("  Refresh token: NOT issued - you will need to log in again later.")
    print("\nTokens are encrypted in ~/.fpl-mcp/tokens.enc (permissions 0600).")
    return True


def logout():
    """Discard stored OAuth tokens."""
    from .fpl.credential_manager import CredentialManager

    cm = CredentialManager()
    if not cm.has_tokens():
        print("No stored tokens to remove.")
        return True
    cm.clear_tokens()
    print("Stored OAuth tokens removed.")
    return True


def main():
    parser = argparse.ArgumentParser(description="FPL MCP Server Configuration")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Setup command
    setup_parser = subparsers.add_parser("setup", help="Set up FPL credentials")
    
    # Test command
    test_parser = subparsers.add_parser("test", help="Test FPL authentication")

    # Login command
    login_parser = subparsers.add_parser(
        "login", help="Sign in to FPL via browser (OAuth2 + PKCE)"
    )
    login_parser.add_argument(
        "--complete",
        metavar="URL",
        help="Finish a sign-in started earlier, using the redirected URL",
    )

    # Logout command
    logout_parser = subparsers.add_parser(
        "logout", help="Remove stored OAuth tokens"
    )
    
    # Parse args
    args = parser.parse_args()
    
    if args.command == "setup":
        setup_credentials()
    elif args.command == "test":
        asyncio.run(test_auth())
    elif args.command == "login":
        login(redirect_url=getattr(args, "complete", None))
    elif args.command == "logout":
        logout()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()