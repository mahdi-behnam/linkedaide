"""Playwright storage_state encryption and decryption at rest."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr

from agent.errors import SessionError


def generate_encryption_key() -> str:
    """Generate a fresh URL-safe base64 32-byte Fernet key."""
    return Fernet.generate_key().decode("utf-8")


def encrypt_storage_state(raw_json: bytes, key: SecretStr | str) -> str:
    """Encrypt raw storage_state JSON bytes.

    Args:
        raw_json: Raw bytes of Playwright storage_state.json.
        key: Fernet key (SecretStr or string).

    Returns:
        str: Base64-encoded ciphertext string.
    """
    key_str = key.get_secret_value() if isinstance(key, SecretStr) else key
    try:
        f = Fernet(key_str.encode("utf-8") if isinstance(key_str, str) else key_str)
        token = f.encrypt(raw_json)
        return token.decode("utf-8")
    except Exception as err:
        raise SessionError(f"Failed to encrypt storage state: {err}") from err


def decrypt_storage_state(ciphertext_b64: str, key: SecretStr | str, out_path: Path) -> Path:
    """Decrypt base64 ciphertext and write to out_path with restricted permissions.

    Args:
        ciphertext_b64: Base64-encoded encrypted token string.
        key: Fernet key (SecretStr or string).
        out_path: Path where decrypted storage_state.json should be written.

    Returns:
        Path: The path to the decrypted file.

    Raises:
        SessionError: If decryption fails due to invalid key, corrupted token, or IO failure.
    """
    if not ciphertext_b64 or not ciphertext_b64.strip():
        raise SessionError("Empty or missing LinkedIn session ciphertext")

    key_str = key.get_secret_value() if isinstance(key, SecretStr) else key
    if not key_str or not key_str.strip():
        raise SessionError("Empty or missing session encryption key")

    try:
        f = Fernet(key_str.strip().encode("utf-8"))
        decrypted_bytes = f.decrypt(ciphertext_b64.strip().encode("utf-8"))
    except InvalidToken as err:
        raise SessionError(
            "Session decryption failed: Invalid encryption key or corrupted session data"
        ) from err
    except Exception as err:
        raise SessionError(f"Unexpected session decryption failure: {err}") from err

    try:
        out_path = Path(out_path).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(decrypted_bytes)

        # Set restrictive permissions on POSIX runners
        if os.name != "nt":
            try:
                os.chmod(out_path, 0o600)
            except OSError:
                pass

        return out_path
    except Exception as err:
        raise SessionError(f"Failed to write decrypted session file to {out_path}: {err}") from err


def ensure_session_file(settings: Any) -> Path:
    """Ensure a valid decrypted storage_state.json exists on disk, auto-decrypting if needed.

    Args:
        settings: Settings instance containing storage state path and encryption keys.

    Returns:
        Path: Path to decrypted storage_state.json.

    Raises:
        SessionError: If no valid session file exists and credentials cannot decrypt one.
    """
    target_path = Path(settings.linkedin_storage_state_path).resolve()
    if target_path.exists() and target_path.stat().st_size > 0:
        return target_path

    # Attempt auto-decryption if ciphertext and key are present in settings
    enc_token = getattr(settings, "linkedin_session_state_enc", None)
    enc_key = getattr(settings, "session_encryption_key", None)

    if enc_token and enc_key:
        token_str = (
            enc_token.get_secret_value() if isinstance(enc_token, SecretStr) else str(enc_token)
        )
        key_str = enc_key.get_secret_value() if isinstance(enc_key, SecretStr) else str(enc_key)
        if token_str and key_str and token_str.strip() and key_str.strip():
            return decrypt_storage_state(token_str.strip(), key_str.strip(), target_path)

    raise SessionError(
        f"LinkedIn session state not found at '{settings.linkedin_storage_state_path}' and "
        "LINKEDIN_SESSION_STATE_ENC / SESSION_ENCRYPTION_KEY are not configured. "
        "Please run 'uv run python scripts/extract_linkedin_session.py' to extract and save your session."
    )


def main() -> None:
    """CLI entrypoint for decrypting session state in CI workflows."""
    parser = argparse.ArgumentParser(description="Decrypt LinkedIn Playwright storage state")
    subparsers = parser.add_subparsers(dest="command")

    decrypt_parser = subparsers.add_parser("decrypt", help="Decrypt session state")
    decrypt_parser.add_argument(
        "--out", required=True, help="Output path for decrypted storage_state.json"
    )

    args = parser.parse_args()

    if args.command == "decrypt":
        key = os.environ.get("SESSION_ENCRYPTION_KEY")
        ciphertext = os.environ.get("LINKEDIN_SESSION_STATE_ENC")

        if not key or not ciphertext:
            print(
                "Error: Missing SESSION_ENCRYPTION_KEY or LINKEDIN_SESSION_STATE_ENC env vars",
                file=sys.stderr,
            )
            sys.exit(1)

        try:
            out_file = decrypt_storage_state(ciphertext, key, Path(args.out))
            print(f"Decrypted session written to {out_file}")
        except Exception as err:
            print(f"Session decryption error: {err}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
