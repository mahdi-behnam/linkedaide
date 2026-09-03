"""Circuit breaker state management."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent.config import Settings


def is_halted(repo_root: Path, settings: Settings) -> tuple[bool, str | None]:
    """Check if the system is halted due to manual pause or active incident.

    Args:
        repo_root: Absolute path to the repository root directory.
        settings: Application settings instance.

    Returns:
        tuple[bool, str | None]: (True, reason) if halted, otherwise (False, None).
    """
    if settings.agent_paused:
        return True, "Agent is paused via AGENT_PAUSED configuration"

    paused_file = repo_root / "state" / "paused.json"
    if paused_file.exists():
        return True, "Agent is paused via remote operator command (state/paused.json present)"

    incident_file = repo_root / "state" / "incident.json"
    if incident_file.exists():
        try:
            data = json.loads(incident_file.read_text(encoding="utf-8"))
            reason = data.get("reason", "Circuit breaker active (incident.json present)")
            return True, f"Circuit breaker tripped: {reason}"
        except Exception:
            return True, "Circuit breaker tripped: incident.json present"

    return False, None


def trip_breaker(repo_root: Path, reason: str, context: dict[str, Any] | None = None) -> None:
    """Trip the circuit breaker by persisting state/incident.json.

    Idempotent: preserve the earliest incident timestamp if file already exists.

    Args:
        repo_root: Absolute path to the repository root directory.
        reason: Description of the fatal error or challenge detected.
        context: Optional dictionary containing error details, DOM diagnostics, etc.
    """
    incident_file = repo_root / "state" / "incident.json"
    incident_file.parent.mkdir(parents=True, exist_ok=True)

    now_iso = datetime.now(UTC).isoformat()
    created_at = now_iso

    if incident_file.exists():
        try:
            existing_data = json.loads(incident_file.read_text(encoding="utf-8"))
            created_at = existing_data.get("created_at", now_iso)
        except Exception:
            pass

    payload = {
        "created_at": created_at,
        "tripped_at": now_iso,
        "reason": reason,
        "context": context or {},
    }

    temp_path = incident_file.with_suffix(".tmp")
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp_path.replace(incident_file)
