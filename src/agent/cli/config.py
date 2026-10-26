"""CLI management tool for centralized Cloudflare KV configuration and secrets.

Provides commands to view, update, and initialize remote operational configuration
and encrypted secrets in Cloudflare KV.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from pydantic import SecretStr

from agent.config.kv_loader import (
    CONFIG_KV_KEY,
    SECRETS_KV_KEY,
    clear_kv_config_cache,
    decrypt_secrets_payload,
    encrypt_secrets_payload,
    fetch_kv_raw_value,
    put_kv_raw_value,
)
from agent.config.settings import load_settings
from agent.errors import ConfigError


def _get_bootstrap_credentials() -> tuple[str, str, str, str]:
    """Retrieve bootstrap credentials from process environment or local settings."""
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID") or os.environ.get("cloudflare_account_id")
    namespace_id = os.environ.get("CLOUDFLARE_KV_NAMESPACE_ID") or os.environ.get(
        "cloudflare_kv_namespace_id"
    )
    api_token = os.environ.get("CLOUDFLARE_API_TOKEN") or os.environ.get("cloudflare_api_token")
    enc_key = os.environ.get("SESSION_ENCRYPTION_KEY") or os.environ.get("session_encryption_key")

    # If any is missing from direct env, check loaded local settings fallback
    if not (account_id and namespace_id and api_token and enc_key):
        try:
            local_cfg = load_settings()
            account_id = account_id or getattr(local_cfg, "cloudflare_account_id", None)
            namespace_id = namespace_id or getattr(local_cfg, "cloudflare_kv_namespace_id", None)
            if not api_token and getattr(local_cfg, "cloudflare_api_token", None):
                tok = local_cfg.cloudflare_api_token
                api_token = tok.get_secret_value() if isinstance(tok, SecretStr) else tok
            if not enc_key and getattr(local_cfg, "session_encryption_key", None):
                k = local_cfg.session_encryption_key
                enc_key = k.get_secret_value() if isinstance(k, SecretStr) else k
        except Exception:
            pass

    if not account_id:
        raise ConfigError("Missing CLOUDFLARE_ACCOUNT_ID")
    if not namespace_id:
        raise ConfigError("Missing CLOUDFLARE_KV_NAMESPACE_ID")
    if not api_token:
        raise ConfigError("Missing CLOUDFLARE_API_TOKEN")
    if not enc_key:
        raise ConfigError("Missing SESSION_ENCRYPTION_KEY")

    return account_id, namespace_id, api_token, enc_key


def _mask_secret(val: Any) -> str:
    """Mask secret value for terminal output."""
    s = str(val).strip()
    if not s:
        return "<empty>"
    if len(s) <= 8:
        return "****"
    return f"{s[:4]}...{s[-4:]}"


def _parse_value(value_str: str) -> Any:
    """Attempt parsing a string as JSON or primitive before storing."""
    v = value_str.strip()
    if v.lower() == "true":
        return True
    if v.lower() == "false":
        return False
    if v.isdigit():
        return int(v)
    try:
        return json.loads(v)
    except Exception:
        return v


def run_config_show(args: argparse.Namespace) -> int:
    """Display current Cloudflare KV configuration and secrets."""
    try:
        account_id, namespace_id, api_token, enc_key = _get_bootstrap_credentials()
    except ConfigError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    print("=" * 64)
    print(f"Cloudflare KV Configuration (Namespace: {namespace_id})")
    print("=" * 64)

    # 1. Operational Config
    print("\n[Operational Settings] (Key: config:runtime)")
    raw_config = fetch_kv_raw_value(account_id, namespace_id, api_token, CONFIG_KV_KEY)
    if not raw_config:
        print("  ⚠️  config:runtime is not initialized in Cloudflare KV.")
    else:
        try:
            cfg = json.loads(raw_config)
            for k in sorted(cfg.keys()):
                print(f"  {k:30} : {cfg[k]}")
        except Exception as err:
            print(f"  Error parsing config:runtime: {err}")

    # 2. Encrypted Secrets Vault
    print("\n[Encrypted Secrets Vault] (Key: secrets:vault_enc)")
    raw_secrets = fetch_kv_raw_value(account_id, namespace_id, api_token, SECRETS_KV_KEY)
    if not raw_secrets:
        print("  ⚠️  secrets:vault_enc is not initialized in Cloudflare KV.")
    else:
        try:
            secrets = decrypt_secrets_payload(raw_secrets, enc_key)
            for k in sorted(secrets.keys()):
                print(f"  {k:30} : {_mask_secret(secrets[k])}")
        except Exception as err:
            print(f"  Error decrypting secrets:vault_enc: {err}")

    print("\n" + "=" * 64)
    return 0


def run_config_set(args: argparse.Namespace) -> int:
    """Update a single operational configuration key in KV."""
    key = args.key.strip()
    value = _parse_value(args.value)

    try:
        account_id, namespace_id, api_token, _ = _get_bootstrap_credentials()
        raw_config = fetch_kv_raw_value(account_id, namespace_id, api_token, CONFIG_KV_KEY)
        config_data = json.loads(raw_config) if raw_config else {}
        config_data[key] = value

        put_kv_raw_value(
            account_id, namespace_id, api_token, CONFIG_KV_KEY, json.dumps(config_data, indent=2)
        )
        clear_kv_config_cache()
        print(f"✅ Successfully updated '{key}' = {value} in Cloudflare KV ('{CONFIG_KV_KEY}')")
        return 0
    except Exception as err:
        print(f"❌ Failed to update '{key}': {err}", file=sys.stderr)
        return 1


def run_config_set_secret(args: argparse.Namespace) -> int:
    """Encrypt and store a secret in the Cloudflare KV secrets vault."""
    key = args.key.strip()
    value = args.value.strip()

    try:
        account_id, namespace_id, api_token, enc_key = _get_bootstrap_credentials()
        raw_secrets = fetch_kv_raw_value(account_id, namespace_id, api_token, SECRETS_KV_KEY)
        secrets_data = decrypt_secrets_payload(raw_secrets, enc_key) if raw_secrets else {}
        secrets_data[key] = value

        encrypted = encrypt_secrets_payload(secrets_data, enc_key)
        put_kv_raw_value(account_id, namespace_id, api_token, SECRETS_KV_KEY, encrypted)
        clear_kv_config_cache()
        print(
            f"✅ Successfully encrypted and updated secret '{key}' in Cloudflare KV ('{SECRETS_KV_KEY}')"
        )
        return 0
    except Exception as err:
        print(f"❌ Failed to set secret '{key}': {err}", file=sys.stderr)
        return 1


def run_config_init_from_env(args: argparse.Namespace) -> int:
    """Read current local settings and initialize config:runtime & secrets:vault_enc in KV."""
    print("Reading local configuration and secrets...")
    try:
        settings = load_settings()
        account_id, namespace_id, api_token, enc_key = _get_bootstrap_credentials()
    except Exception as err:
        print(f"Initialization error: {err}", file=sys.stderr)
        return 1

    # Extract operational parameters
    operational_keys = [
        "llm_provider",
        "nim_model_primary",
        "nim_model_fallback",
        "nim_model_triage",
        "nim_model_vision",
        "nim_temperature",
        "nim_top_p",
        "nim_timeout_seconds",
        "nim_max_tokens",
        "nim_base_url",
        "user_focus_areas",
        "scout_target_urls",
        "target_hashtags",
        "user_persona",
        "max_comment_words",
        "max_comments_per_day",
        "max_posts_per_day",
        "max_connections_per_day",
        "max_suggestions_per_run",
        "pending_action_ttl_hours",
        "enable_pre_comment_reaction",
        "default_reaction_type",
        "scout_scroll_screens",
        "candidate_pool_multiplier",
        "min_triage_confidence",
        "agent_paused",
        "dry_run",
    ]

    config_data: dict[str, Any] = {}
    for k in operational_keys:
        val = getattr(settings, k, None)
        if val is not None:
            config_data[k] = val

    # Extract secret parameters
    secret_keys = [
        "nvidia_nim_api_key",
        "openai_api_key",
        "anthropic_api_key",
        "gemini_api_key",
        "groq_api_key",
        "telegram_bot_token",
        "telegram_authorized_chat_id",
        "desktop_api_secret",
        "worker_url",
        "residential_proxy_url",
    ]

    secrets_data: dict[str, Any] = {}
    for k in secret_keys:
        val = getattr(settings, k, None)
        if val is not None:
            if isinstance(val, SecretStr):
                secrets_data[k] = val.get_secret_value()
            else:
                secrets_data[k] = str(val)

    print(f"Pushing {len(config_data)} operational settings to '{CONFIG_KV_KEY}'...")
    put_kv_raw_value(
        account_id, namespace_id, api_token, CONFIG_KV_KEY, json.dumps(config_data, indent=2)
    )

    print(f"Encrypting and pushing {len(secrets_data)} secrets to '{SECRETS_KV_KEY}'...")
    encrypted = encrypt_secrets_payload(secrets_data, enc_key)
    put_kv_raw_value(account_id, namespace_id, api_token, SECRETS_KV_KEY, encrypted)

    clear_kv_config_cache()
    print("✅ Centralized Cloudflare KV configuration & secrets vault successfully initialized!")
    return 0


def add_config_subparsers(subparsers: argparse._SubParsersAction[Any]) -> None:
    """Add 'config' subcommands to main CLI parser."""
    config_parser = subparsers.add_parser(
        "config",
        help="Manage centralized Cloudflare KV configuration and encrypted secrets",
    )
    config_sub = config_parser.add_subparsers(dest="config_command", required=True)

    # show
    config_sub.add_parser("show", help="Display remote KV configuration and secrets")

    # set <key> <value>
    set_parser = config_sub.add_parser("set", help="Set an operational configuration value in KV")
    set_parser.add_argument("key", help="Configuration parameter name (e.g. nim_model_primary)")
    set_parser.add_argument("value", help="Configuration value")

    # set-secret <key> <value>
    secret_parser = config_sub.add_parser(
        "set-secret", help="Encrypt and store a secret in the KV vault"
    )
    secret_parser.add_argument("key", help="Secret parameter name (e.g. nvidia_nim_api_key)")
    secret_parser.add_argument("value", help="Secret plaintext value")

    # init-from-env
    config_sub.add_parser(
        "init-from-env",
        help="Initialize remote KV config and secrets vault from current local environment",
    )


def run_config_cli(args: argparse.Namespace) -> int:
    """Dispatch config subcommand."""
    cmd = getattr(args, "config_command", None)
    if cmd == "show":
        return run_config_show(args)
    if cmd == "set":
        return run_config_set(args)
    if cmd == "set-secret":
        return run_config_set_secret(args)
    if cmd == "init-from-env":
        return run_config_init_from_env(args)
    return 1
