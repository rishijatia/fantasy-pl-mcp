# src/fpl_mcp/fpl/credential_manager.py
import os
import json
import getpass
import platform
import uuid
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

logger = logging.getLogger(__name__)


class CredentialManager:
    """Manages encrypted credential storage for FPL authentication"""

    def __init__(self):
        self._config_dir = Path.home() / ".fpl-mcp"
        self._encrypted_file = self._config_dir / "credentials.enc"
        self._legacy_env_file = self._config_dir / ".env"
        self._legacy_json_file = self._config_dir / "config.json"

        # Ensure config directory exists
        self._config_dir.mkdir(exist_ok=True)

    def _generate_key(self, salt: bytes) -> bytes:
        """Generate encryption key from system-specific data"""
        # Combine multiple system identifiers for key derivation
        try:
            node = uuid.getnode()
            # Check if uuid.getnode() returned a random value (not a valid MAC address)
            if (node >> 40) % 2:
                logger.warning("uuid.getnode() returned a random value; falling back to platform.uname()")
                machine_id = str(platform.uname()).encode()
            else:
                machine_id = str(node).encode()
        except Exception as e:
            logger.error(f"Failed to retrieve machine ID using uuid.getnode(): {e}")
            machine_id = str(platform.uname()).encode()
        username = getpass.getuser().encode()
        home_path = str(Path.home()).encode()
        platform_info = platform.node().encode()

        # Combine all identifiers
        key_material = machine_id + username + home_path + platform_info

        # Derive key using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=600000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(key_material))
        return key

    def _encrypt_data(self, data: Dict[str, str]) -> bytes:
        """Encrypt credential data"""
        # Generate random salt
        salt = os.urandom(16)

        # Generate encryption key
        key = self._generate_key(salt)
        fernet = Fernet(key)

        # Serialize and encrypt data
        json_data = json.dumps(data).encode()
        encrypted_data = fernet.encrypt(json_data)

        # Prepend salt to encrypted data
        return salt + encrypted_data

    def _decrypt_data(self, encrypted_bytes: bytes) -> Dict[str, str]:
        """Decrypt credential data"""
        # Extract salt (first 16 bytes)
        salt = encrypted_bytes[:16]
        encrypted_data = encrypted_bytes[16:]

        # Generate decryption key
        key = self._generate_key(salt)
        fernet = Fernet(key)

        # Decrypt and deserialize data
        decrypted_data = fernet.decrypt(encrypted_data)
        return json.loads(decrypted_data.decode())

    def store_credentials(self, email: str, password: str, team_id: str) -> None:
        """Store encrypted credentials to file"""
        data = {"email": email, "password": password, "team_id": team_id}

        try:
            encrypted_data = self._encrypt_data(data)

            # Write encrypted data to file
            with open(self._encrypted_file, "wb") as f:
                f.write(encrypted_data)

            # Set restrictive file permissions (owner read/write only)
            os.chmod(self._encrypted_file, 0o600)

            logger.info(f"Credentials stored securely in {self._encrypted_file}")

        except Exception as e:
            logger.error(f"Failed to store encrypted credentials: {e}")
            raise

    def load_credentials(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Load credentials from various sources, preferring encrypted storage"""

        # First, try encrypted storage
        if self._encrypted_file.exists():
            try:
                with open(self._encrypted_file, "rb") as f:
                    encrypted_data = f.read()

                data = self._decrypt_data(encrypted_data)
                email = data.get("email")
                password = data.get("password")
                team_id = data.get("team_id")

                if email and password and team_id:
                    logger.info("Loaded credentials from encrypted storage")
                    return email, password, team_id

            except Exception as e:
                logger.error(f"Failed to decrypt credentials: {e}")
                logger.info("Falling back to legacy credential sources")

        # Fall back to legacy sources for backward compatibility
        return self._load_legacy_credentials()

    def _load_legacy_credentials(
        self,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Load credentials from legacy plaintext sources"""
        from dotenv import load_dotenv

        # Check environment variables first
        load_dotenv()
        email = os.getenv("FPL_EMAIL")
        password = os.getenv("FPL_PASSWORD")
        team_id = os.getenv("FPL_TEAM_ID")

        if email and password and team_id:
            logger.info("Loaded credentials from environment variables")
            return email, password, team_id

        # Check legacy .env file
        if self._legacy_env_file.exists():
            load_dotenv(self._legacy_env_file)
            email = os.getenv("FPL_EMAIL")
            password = os.getenv("FPL_PASSWORD")
            team_id = os.getenv("FPL_TEAM_ID")

            if email and password and team_id:
                logger.info(f"Loaded credentials from {self._legacy_env_file}")
                return email, password, team_id

        # Check legacy JSON file
        if self._legacy_json_file.exists():
            try:
                with open(self._legacy_json_file, "r") as f:
                    config = json.load(f)
                    email = config.get("email")
                    password = config.get("password")
                    team_id = config.get("team_id")

                    if email and password and team_id:
                        logger.info(f"Loaded credentials from {self._legacy_json_file}")
                        return email, password, team_id

            except Exception as e:
                logger.error(f"Error loading legacy JSON config: {e}")

        logger.warning("No credentials found in any source")
        return None, None, None

    def migrate_legacy_credentials(self) -> bool:
        """Migrate plaintext credentials to encrypted storage"""
        # Load from legacy sources
        email, password, team_id = self._load_legacy_credentials()

        if not (email and password and team_id):
            logger.info("No legacy credentials found to migrate")
            return False

        # Skip if encrypted credentials already exist
        if self._encrypted_file.exists():
            logger.info("Encrypted credentials already exist, skipping migration")
            return False

        try:
            # Store in encrypted format
            self.store_credentials(email, password, team_id)

            # Optionally remove legacy files (commented out for safety)
            # if self._legacy_env_file.exists():
            #     self._legacy_env_file.unlink()
            # if self._legacy_json_file.exists():
            #     self._legacy_json_file.unlink()

            logger.info("Successfully migrated legacy credentials to encrypted storage")
            logger.info("Legacy credential files preserved for backup")
            return True

        except Exception as e:
            logger.error(f"Failed to migrate legacy credentials: {e}")
            return False

    def has_credentials(self) -> bool:
        """Check if any credentials are available"""
        email, password, team_id = self.load_credentials()
        return bool(email and password and team_id)

    def clear_credentials(self) -> None:
        """Clear encrypted credentials"""
        if self._encrypted_file.exists():
            self._encrypted_file.unlink()
            logger.info("Encrypted credentials cleared")
