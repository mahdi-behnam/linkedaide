"""Diagnostic check runner and result data structures for doctor command."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx

from agent.config import Settings

CheckStatus = Literal["PASS", "WARN", "FAIL"]


@dataclass
class CheckResult:
    """Diagnostic check result."""

    name: str
    status: CheckStatus
    message: str
    details: str | None = None


def format_check_result(result: CheckResult) -> str:
    """Format check result with rich status symbol."""
    symbol = {
        "PASS": "🟢 Pass",
        "WARN": "🟡 Warning",
        "FAIL": "🔴 Fail",
    }[result.status]
    output = f"  [{symbol}] {result.name}: {result.message}"
    if result.details:
        output += f"\n         {result.details}"
    return output


def run_doctor(
    args: argparse.Namespace | None = None,
    settings: Settings | None = None,
    repo_root: Path | None = None,
    telegram_client: httpx.Client | None = None,
    kv_client: httpx.Client | None = None,
) -> int:
    """Run full diagnostic test suite and print rich status checklist.

    Returns:
        int: 0 if all checks pass or only warnings; 1 if any check fails.
    """
    from agent.doctor.checks import (
        check_configuration,
        check_git_hooks,
        check_linkedin_session,
        check_llm_provider,
        check_node_runtime,
        check_playwright_chromium,
        check_python_runtime,
        check_state_backend,
        check_telegram_bot,
    )

    root = repo_root or (
        Path(args.repo_root) if args and getattr(args, "repo_root", None) else None
    )

    print("\n=== LinkedAide Doctor Diagnostics ===\n")

    results: list[CheckResult] = []

    # 1. Python runtime
    results.append(check_python_runtime())

    # 2. Node.js & TypeScript runtime
    results.append(check_node_runtime(repo_root=root))

    # 3. Git hooks configuration
    results.append(check_git_hooks(repo_root=root))

    # 4. Playwright Chromium
    results.append(check_playwright_chromium())

    # 5. Configuration validation
    cfg_result, resolved_settings = check_configuration(settings)
    results.append(cfg_result)

    # 6. LLM provider check
    results.append(check_llm_provider(resolved_settings))

    # 7. Telegram bot check
    results.append(check_telegram_bot(resolved_settings, client=telegram_client))

    # 8. State backend check
    results.append(check_state_backend(resolved_settings, repo_root=root, client=kv_client))

    # 9. LinkedIn session check
    results.append(check_linkedin_session(resolved_settings))

    # Display checklist
    for res in results:
        print(format_check_result(res))

    passed_count = sum(1 for r in results if r.status == "PASS")
    warn_count = sum(1 for r in results if r.status == "WARN")
    fail_count = sum(1 for r in results if r.status == "FAIL")

    print(f"\nResult: {passed_count} passed, {warn_count} warning(s), {fail_count} failed.")

    if fail_count > 0:
        print("🔴 Diagnostics failed. Please resolve the errors highlighted above.\n")
        return 1
    if warn_count > 0:
        print("🟡 Diagnostics completed with warnings. System is operational with caveats.\n")
        return 0
    print("🟢 All systems operational!\n")
    return 0
