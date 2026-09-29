"""Repository-backed and Cloudflare KV durable state store package."""

from __future__ import annotations

from pathlib import Path

from agent.config import Settings
from agent.errors import ConfigError
from agent.state.base import BaseStateStore
from agent.state.kv_store import CloudflareKVStateStore
from agent.state.store import GitStateStore


def get_state_store(settings: Settings, repo_root: Path) -> BaseStateStore:
    """Return the configured state store backend (Cloudflare KV or Git-as-database).

    Args:
        settings: Application runtime settings.
        repo_root: Root path for repository-backed Git state fallback.

    Returns:
        BaseStateStore: Configured CloudflareKVStateStore or GitStateStore instance.

    Raises:
        ConfigError: If state_backend is 'kv' but required Cloudflare credentials are missing.
    """
    backend = settings.state_backend.lower().strip()
    has_kv_creds = bool(
        settings.cloudflare_account_id
        and settings.cloudflare_kv_namespace_id
        and settings.cloudflare_api_token
    )

    if backend == "kv" or has_kv_creds:
        if not (
            settings.cloudflare_account_id
            and settings.cloudflare_kv_namespace_id
            and settings.cloudflare_api_token
        ):
            raise ConfigError(
                "Cloudflare KV state backend requires CLOUDFLARE_ACCOUNT_ID, "
                "CLOUDFLARE_KV_NAMESPACE_ID, and CLOUDFLARE_API_TOKEN"
            )
        return CloudflareKVStateStore(
            account_id=settings.cloudflare_account_id,
            namespace_id=settings.cloudflare_kv_namespace_id,
            api_token=settings.cloudflare_api_token,
        )

    return GitStateStore(repo_root=repo_root)


__all__ = [
    "BaseStateStore",
    "CloudflareKVStateStore",
    "GitStateStore",
    "get_state_store",
]
