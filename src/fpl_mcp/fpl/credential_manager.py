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


def extract_refresh_token(pasted: str) -> str:
    """Accept either a bare refresh token or a full oidc.user JSON blob."""
    pasted = pasted.strip()
    if pasted.startswith("{"):
        try:
            return json.loads(pasted).get("refresh_token", "") or ""
        except json.JSONDecodeError:
            return ""
    return pasted


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

    def store_credentials(self, refresh_token: str, team_id: str) -> None:
        """Store encrypted credentials to file.

        FPL now authenticates via PingOne OIDC, so the durable secret is the
        OIDC refresh token rather than an email/password pair.
        """
        data = {"refresh_token": refresh_token, "team_id": team_id}

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

    def update_refresh_token(self, refresh_token: str) -> None:
        """Persist a rotated refresh token, keeping the stored team_id.

        PingOne rotates refresh tokens on use; persisting the new one keeps the
        next run from being locked out.
        """
        _, team_id = self.load_credentials()
        if not team_id:
            logger.warning("Cannot persist rotated refresh token: no team_id stored")
            return
        self.store_credentials(refresh_token, team_id)

    def load_credentials(self) -> Tuple[Optional[str], Optional[str]]:
        """Load credentials, preferring encrypted storage.

        Returns a (refresh_token, team_id) tuple.
        """

        # First, try encrypted storage
        if self._encrypted_file.exists():
            try:
                with open(self._encrypted_file, "rb") as f:
                    encrypted_data = f.read()

                data = self._decrypt_data(encrypted_data)
                refresh_token = data.get("refresh_token")
                team_id = data.get("team_id")

                if refresh_token and team_id:
                    logger.info("Loaded credentials from encrypted storage")
                    return refresh_token, team_id

                # Encrypted file predates the OIDC migration (email/password).
                if data.get("email") or data.get("password"):
                    logger.warning(
                        "Stored credentials use the retired email/password login; "
                        "please re-run 'fpl-mcp-config setup' with a refresh token."
                    )

            except Exception as e:
                logger.error(f"Failed to decrypt credentials: {e}")
                logger.info("Falling back to legacy credential sources")

        # Fall back to legacy sources for backward compatibility
        return self._load_legacy_credentials()

    def _load_legacy_credentials(
        self,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Load credentials from legacy plaintext sources.

        Only the refresh token and team id are usable now; any email/password
        found here can no longer authenticate against PingOne.
        """
        from dotenv import load_dotenv

        # Check environment variables first
        load_dotenv()
        refresh_token = os.getenv("FPL_REFRESH_TOKEN")
        team_id = os.getenv("FPL_TEAM_ID")

        if refresh_token and team_id:
            logger.info("Loaded credentials from environment variables")
            return refresh_token, team_id

        # Check legacy .env file
        if self._legacy_env_file.exists():
            load_dotenv(self._legacy_env_file)
            refresh_token = os.getenv("FPL_REFRESH_TOKEN")
            team_id = os.getenv("FPL_TEAM_ID")

            if refresh_token and team_id:
                logger.info(f"Loaded credentials from {self._legacy_env_file}")
                return refresh_token, team_id

        # Check legacy JSON file
        if self._legacy_json_file.exists():
            try:
                with open(self._legacy_json_file, "r") as f:
                    config = json.load(f)
                    refresh_token = config.get("refresh_token")
                    team_id = config.get("team_id")

                    if refresh_token and team_id:
                        logger.info(f"Loaded credentials from {self._legacy_json_file}")
                        return refresh_token, team_id

            except Exception as e:
                logger.error(f"Error loading legacy JSON config: {e}")

        logger.warning("No credentials found in any source")
        return None, None

    def migrate_legacy_credentials(self) -> bool:
        """Migrate plaintext refresh-token credentials to encrypted storage"""
        # Load from legacy sources
        refresh_token, team_id = self._load_legacy_credentials()

        if not (refresh_token and team_id):
            logger.info("No legacy credentials found to migrate")
            return False

        # Skip if encrypted credentials already exist
        if self._encrypted_file.exists():
            logger.info("Encrypted credentials already exist, skipping migration")
            return False

        try:
            # Store in encrypted format
            self.store_credentials(refresh_token, team_id)

            logger.info("Successfully migrated legacy credentials to encrypted storage")
            logger.info("Legacy credential files preserved for backup")
            return True

        except Exception as e:
            logger.error(f"Failed to migrate legacy credentials: {e}")
            return False

    def has_credentials(self) -> bool:
        """Check if any credentials are available"""
        refresh_token, team_id = self.load_credentials()
        return bool(refresh_token and team_id)

    def clear_credentials(self) -> None:
        """Clear encrypted credentials"""
        if self._encrypted_file.exists():
            self._encrypted_file.unlink()
            logger.info("Encrypted credentials cleared")
