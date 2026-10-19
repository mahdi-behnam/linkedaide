"""Cross-platform script to configure Git hooks for LinkedAide contributors."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path


def setup_git_hooks() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    githooks_dir = repo_root / ".githooks"

    if not (repo_root / ".git").exists():
        print("⚠️  Not a git repository root. Skipping git hook installation.")
        return

    print("🔧 Configuring LinkedAide Git hooks...")

    # 1. Point Git core.hooksPath to .githooks
    try:
        subprocess.run(
            ["git", "config", "core.hooksPath", ".githooks"],
            cwd=str(repo_root),
            check=True,
            capture_output=True,
            text=True,
        )
        print("✅ Configured git 'core.hooksPath' -> '.githooks'")
    except Exception as err:
        print(f"❌ Failed to set core.hooksPath: {err}", file=sys.stderr)
        sys.exit(1)

    # 2. Ensure hook files have executable permissions on POSIX systems
    if os.name != "nt":
        for hook in ["pre-commit", "pre-push"]:
            hook_file = githooks_dir / hook
            if hook_file.exists():
                curr_mode = hook_file.stat().st_mode
                hook_file.chmod(curr_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print("✅ Ensured executable permissions on .githooks scripts")

    # 3. If pre-commit tool is available, also install pre-commit framework hooks
    try:
        res = subprocess.run(
            [
                "uv",
                "run",
                "pre-commit",
                "install",
                "--hook-type",
                "pre-commit",
                "--hook-type",
                "pre-push",
            ],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        if res.returncode == 0:
            print("✅ Pre-commit framework hooks also registered")
    except Exception:
        pass

    print("\n🎉 Git hooks are fully active!")
    print("   • pre-commit : Runs ruff check --fix, ruff format, and mypy")
    print("   • pre-push   : Runs ruff check, ruff format check, mypy, and unit tests\n")


if __name__ == "__main__":
    setup_git_hooks()
