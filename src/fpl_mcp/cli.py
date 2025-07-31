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

def main():
    parser = argparse.ArgumentParser(description="FPL MCP Server Configuration")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Setup command
    setup_parser = subparsers.add_parser("setup", help="Set up FPL credentials")
    
    # Test command
    test_parser = subparsers.add_parser("test", help="Test FPL authentication")
    
    # Parse args
    args = parser.parse_args()
    
    if args.command == "setup":
        setup_credentials()
    elif args.command == "test":
        asyncio.run(test_auth())
    else:
        parser.print_help()

if __name__ == "__main__":
    main()