# src/fpl_mcp/cli.py
import os
import json
import argparse
import getpass
import asyncio
from pathlib import Path

def setup_credentials():
    """Interactive CLI for setting up FPL credentials"""
    print("FPL MCP Server - Credential Setup")
    print("=================================")
    print("This will set up your FPL credentials for use with the MCP server.")
    print("Your credentials will be stored in ~/.fpl-mcp/")
    print()
    
    # Get credentials
    email = input("Enter your FPL email: ")
    password = getpass.getpass("Enter your FPL password: ")
    team_id = input("Enter your FPL team ID: ")
    
    # Validate basic input
    if not email or not password or not team_id:
        print("Error: All fields are required.")
        return False
    
    # Create config directory
    config_dir = Path.home() / ".fpl-mcp"
    config_dir.mkdir(exist_ok=True)
    
    # Ask how to store credentials
    storage_method = input("Store credentials in [1] config.json or [2] .env file? (1/2): ")
    
    if storage_method == "2":
        # Create .env file
        env_path = config_dir / ".env"
        with open(env_path, "w") as f:
            f.write(f"FPL_EMAIL={email}\n")
            f.write(f"FPL_PASSWORD={password}\n")
            f.write(f"FPL_TEAM_ID={team_id}\n")
        
        # Set secure permissions
        os.chmod(env_path, 0o600)  # Only user can read/write
        
        print(f"\nCredentials saved to {env_path}")
        print("Configuration successful!")
        return True
    else:
        # Create config file (default)
        config_path = config_dir / "config.json"
        config = {
            "email": email,
            "password": password,
            "team_id": team_id
        }
        
        try:
            with open(config_path, "w") as f:
                json.dump(config, f)
            
            # Set secure permissions
            os.chmod(config_path, 0o600)  # Only user can read/write
            
            print(f"\nCredentials saved to {config_path}")
            print("Configuration successful!")
            return True
        except Exception as e:
            print(f"Error saving configuration: {e}")
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