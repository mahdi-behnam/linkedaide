"""Cloudflare KV centralized configuration and encrypted secrets loader.

Implements strict, fail-closed loading of operational configuration and
Fernet-encrypted secrets directly from Cloudflare KV.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import quote

import httpx
from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr

from agent.errors import ConfigError

logger = logging.getLogger("agent.config.kv_loader")

CONFIG_KV_KEY = "config:runtime"
SECRETS_KV_KEY = "secrets:vault_enc"

# Cache KV config across Settings() instantiations within the same process
_KV_CONFIG_CACHE: dict[str, Any] | None = None


def encrypt_secrets_payload(payload: dict[str, Any], encryption_key: SecretStr | str) -> str:
    """Encrypt a dictionary of secrets into a Fernet base64 ciphertext string."""
    key_str = (
        encryption_key.get_secret_value()
        if isinstance(encryption_key, SecretStr)
        else encryption_key
    )
    if not key_str:
        raise ConfigError("Cannot encrypt secrets: SESSION_ENCRYPTION_KEY is empty")
    try:
        f = Fernet(key_str.encode("utf-8") if isinstance(key_str, str) else key_str)
        raw_bytes = json.dumps(payload).encode("utf-8")
        return f.encrypt(raw_bytes).decode("utf-8")
    except Exception as err:
        raise ConfigError(f"Failed to encrypt secrets vault: {err}") from err


def decrypt_secrets_payload(ciphertext_b64: str, encryption_key: SecretStr | str) -> dict[str, Any]:
    """Decrypt a Fernet base64 ciphertext string into a dictionary of secrets."""
    key_str = (
        encryption_key.get_secret_value()
        if isinstance(encryption_key, SecretStr)
        else encryption_key
    )
    if not key_str:
        raise ConfigError("Cannot decrypt secrets: SESSION_ENCRYPTION_KEY is missing or empty")
    try:
        f = Fernet(key_str.strip().encode("utf-8") if isinstance(key_str, str) else key_str)
        raw_bytes = f.decrypt(ciphertext_b64.strip().encode("utf-8"))
        data = json.loads(raw_bytes.decode("utf-8"))
        if not isinstance(data, dict):
            raise ConfigError("Decrypted secrets vault payload is not a valid JSON dictionary")
        return data
    except InvalidToken as err:
        raise ConfigError(
            "Secrets decryption failed: Invalid SESSION_ENCRYPTION_KEY or corrupted vault data"
        ) from err
    except Exception as err:
        raise ConfigError(f"Failed to decrypt secrets vault: {err}") from err


def fetch_kv_raw_value(
    account_id: str,
    namespace_id: str,
    api_token: str,
    key: str,
    client: httpx.Client | None = None,
    timeout: float = 10.0,
) -> str | None:
    """Retrieve raw string value for key from Cloudflare KV via REST API.

    Returns None if key is not found (404).
    """
    safe_key = quote(key, safe=":")
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}"
        f"/storage/kv/namespaces/{namespace_id}/values/{safe_key}"
    )
    headers = {
        "Authorization": f"Bearer {api_token}",
        "User-Agent": "LinkedIn-Agent-ConfigLoader/1.0",
    }

    try:
        if client is not None:
            resp = client.get(url, headers=headers, timeout=timeout)
        else:
            with httpx.Client(timeout=timeout) as c:
                resp = c.get(url, headers=headers)

        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            raise ConfigError(
                f"Cloudflare KV GET '{key}' failed with HTTP {resp.status_code}: {resp.text}"
            )
        return resp.text
    except httpx.HTTPError as err:
        raise ConfigError(f"Network error reading Cloudflare KV key '{key}': {err}") from err


def put_kv_raw_value(
    account_id: str,
    namespace_id: str,
    api_token: str,
    key: str,
    value: str,
    client: httpx.Client | None = None,
    timeout: float = 10.0,
) -> None:
    """Put raw string value for key into Cloudflare KV via REST API."""
    safe_key = quote(key, safe=":")
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}"
        f"/storage/kv/namespaces/{namespace_id}/values/{safe_key}"
    )
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
        "User-Agent": "LinkedIn-Agent-ConfigLoader/1.0",
    }

    try:
        if client is not None:
            resp = client.put(url, headers=headers, content=value, timeout=timeout)
        else:
            with httpx.Client(timeout=timeout) as c:
                resp = c.put(url, headers=headers, content=value)

        if resp.status_code >= 400:
            raise ConfigError(
                f"Cloudflare KV PUT '{key}' failed with HTTP {resp.status_code}: {resp.text}"
            )
    except httpx.HTTPError as err:
        raise ConfigError(f"Network error writing Cloudflare KV key '{key}': {err}") from err


def load_central_kv_settings(
    account_id: str | None,
    namespace_id: str | None,
    api_token: str | None,
    encryption_key: SecretStr | str | None,
    strict: bool = False,
    force_refresh: bool = False,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Load configuration and secrets from Cloudflare KV.

    In strict mode (production / CI when STATE_BACKEND=kv):
    - Raises ConfigError if config:runtime is missing or incomplete.
    - Decrypts secrets:vault_enc and raises ConfigError if missing or invalid.
    """
    global _KV_CONFIG_CACHE

    if _KV_CONFIG_CACHE is not None and not force_refresh:
        return _KV_CONFIG_CACHE

    if not account_id or not namespace_id or not api_token:
        if strict:
            raise ConfigError(
                "Strict KV configuration requires CLOUDFLARE_ACCOUNT_ID, "
                "CLOUDFLARE_KV_NAMESPACE_ID, and CLOUDFLARE_API_TOKEN to be set."
            )
        logger.debug("Cloudflare credentials not provided; skipping central KV configuration.")
        return {}

    logger.info(
        "Loading centralized configuration from Cloudflare KV namespace %s...", namespace_id
    )

    # 1. Fetch operational configuration (plain JSON)
    raw_config = fetch_kv_raw_value(
        account_id, namespace_id, api_token, CONFIG_KV_KEY, client=client
    )
    if not raw_config:
        if strict:
            raise ConfigError(
                f"Missing required Cloudflare KV key '{CONFIG_KV_KEY}'. "
                "Run 'python -m agent.cli.config init-from-env' to initialize remote configuration."
            )
        config_data: dict[str, Any] = {}
    else:
        try:
            parsed = json.loads(raw_config)
            if not isinstance(parsed, dict):
                raise ValueError("Payload is not a JSON dictionary")
            config_data = parsed
        except Exception as err:
            raise ConfigError(f"Malformed JSON in Cloudflare KV '{CONFIG_KV_KEY}': {err}") from err

    # 2. Strict validation of required operational configuration
    if strict:
        if "nim_model_primary" not in config_data and "llm_model_primary" not in config_data:
            raise ConfigError(
                f"Missing required setting 'nim_model_primary' in Cloudflare KV '{CONFIG_KV_KEY}'. "
                "Run 'python -m agent.cli.config set nim_model_primary <value>' to configure it."
            )

    # 3. Fetch and decrypt secrets vault
    raw_secrets_enc = fetch_kv_raw_value(
        account_id, namespace_id, api_token, SECRETS_KV_KEY, client=client
    )
    secrets_data: dict[str, Any] = {}
    if raw_secrets_enc:
        if not encryption_key:
            raise ConfigError(
                f"Found encrypted secrets vault in KV '{SECRETS_KV_KEY}' but SESSION_ENCRYPTION_KEY "
                "is not provided to decrypt it."
            )
        secrets_data = decrypt_secrets_payload(raw_secrets_enc, encryption_key)
    elif strict:
        raise ConfigError(
            f"Missing required Cloudflare KV secrets vault '{SECRETS_KV_KEY}'. "
            "Run 'python -m agent.cli.config init-from-env' to populate encrypted secrets."
        )

    # Combine config and secrets (secrets override or supply provider keys)
    combined: dict[str, Any] = {**config_data, **secrets_data}
    _KV_CONFIG_CACHE = combined
    return combined


def clear_kv_config_cache() -> None:
    """Clear in-memory cached KV configuration."""
    global _KV_CONFIG_CACHE
    _KV_CONFIG_CACHE = None
