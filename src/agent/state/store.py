"""Repository-backed durable Git state store ("git-as-database")."""

from __future__ import annotations

import json
import subprocess
import time
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from agent.errors import StateStoreError
from agent.models.schemas import DailyCounters, HistoryEntry, PendingAction, PostRecord


class GitStateStore:
    """Manages reading, writing, and atomic committing of durable repository state."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.state_dir = self.repo_root / "state"
        self.pending_dir = self.state_dir / "pending"
        self.seen_posts_path = self.state_dir / "seen_posts.json"
        self.history_path = self.state_dir / "history.jsonl"
        self.daily_counters_path = self.state_dir / "daily_counters.json"
        self.incident_path = self.state_dir / "incident.json"

        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Ensure state directories exist."""
        self.pending_dir.mkdir(parents=True, exist_ok=True)

    def _atomic_write_json(self, target_path: Path, data: Any, indent: int = 2) -> None:
        """Write JSON data to a target path atomically via a temporary file."""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = target_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(data, indent=indent, default=str), encoding="utf-8")
        temp_path.replace(target_path)

    # -------------------------------------------------------------------------
    # Pending Actions
    # -------------------------------------------------------------------------

    def write_pending(self, item: PendingAction) -> Path:
        """Write a pending action to state/pending/{item_id}.json."""
        target_path = self.pending_dir / f"{item.item_id}.json"
        payload = item.model_dump(mode="json")
        self._atomic_write_json(target_path, payload)
        return target_path

    def read_pending(self, item_id: str) -> PendingAction | None:
        """Read a pending action by item_id. Returns None if not found."""
        target_path = self.pending_dir / f"{item_id}.json"
        if not target_path.exists():
            return None
        try:
            raw = json.loads(target_path.read_text(encoding="utf-8"))
            return PendingAction.model_validate(raw)
        except Exception as err:
            raise StateStoreError(f"Failed to read pending action {item_id}: {err}") from err

    def delete_pending(self, item_id: str) -> bool:
        """Delete a pending action file. Returns True if deleted, False if not found."""
        target_path = self.pending_dir / f"{item_id}.json"
        if target_path.exists():
            target_path.unlink()
            return True
        return False

    def list_pending(self) -> list[PendingAction]:
        """List all current pending actions sorted by creation time."""
        results: list[PendingAction] = []
        if not self.pending_dir.exists():
            return results

        for file_path in self.pending_dir.glob("*.json"):
            if file_path.name.startswith("."):
                continue
            try:
                raw = json.loads(file_path.read_text(encoding="utf-8"))
                results.append(PendingAction.model_validate(raw))
            except Exception:
                continue

        results.sort(key=lambda x: x.created_at)
        return results

    # -------------------------------------------------------------------------
    # History (JSONL Append-Only)
    # -------------------------------------------------------------------------

    def append_history(self, entry: HistoryEntry) -> None:
        """Append an outcome entry to state/history.jsonl."""
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        payload = entry.model_dump(mode="json")
        line = json.dumps(payload, default=str) + "\n"
        with self.history_path.open("a", encoding="utf-8") as f:
            f.write(line)

    def read_history(self, limit: int | None = None) -> list[HistoryEntry]:
        """Read history entries from state/history.jsonl."""
        if not self.history_path.exists():
            return []

        entries: list[HistoryEntry] = []
        lines = self.history_path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
                entries.append(HistoryEntry.model_validate(raw))
            except Exception:
                continue

        if limit is not None and limit > 0:
            return entries[-limit:]
        return entries

    # -------------------------------------------------------------------------
    # Seen Posts Hashes
    # -------------------------------------------------------------------------

    def load_seen_hashes(self, ttl_days: int = 30) -> set[str]:
        """Load and prune seen post content hashes.

        Args:
            ttl_days: Number of days to retain hashes before pruning.

        Returns:
            set[str]: Set of valid content hashes.
        """
        if not self.seen_posts_path.exists():
            return set()

        try:
            data = json.loads(self.seen_posts_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return set()
        except Exception:
            return set()

        now = datetime.now(UTC)
        valid_hashes: dict[str, str] = {}
        result_set: set[str] = set()

        for content_hash, timestamp_str in data.items():
            try:
                ts = datetime.fromisoformat(timestamp_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                if (now - ts).total_seconds() <= (ttl_days * 86400):
                    valid_hashes[content_hash] = timestamp_str
                    result_set.add(content_hash)
            except Exception:
                continue

        # If entries were pruned, persist updated state
        if len(valid_hashes) != len(data):
            self._atomic_write_json(self.seen_posts_path, valid_hashes)

        return result_set

    def save_seen_hashes(self, hashes: dict[str, str]) -> None:
        """Save a dictionary of content_hash -> iso_timestamp to seen_posts.json."""
        self._atomic_write_json(self.seen_posts_path, hashes)

    def record_seen_posts(self, posts: list[PostRecord]) -> set[str]:
        """Record newly seen posts with current timestamp and return updated hash set."""
        seen_map: dict[str, str] = {}
        if self.seen_posts_path.exists():
            try:
                raw = json.loads(self.seen_posts_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    seen_map = raw
            except Exception:
                pass

        now_iso = datetime.now(UTC).isoformat()
        for p in posts:
            seen_map[p.content_hash] = now_iso

        self._atomic_write_json(self.seen_posts_path, seen_map)
        return set(seen_map.keys())

    # -------------------------------------------------------------------------
    # Daily Counters
    # -------------------------------------------------------------------------

    def load_daily_counters(self, today: date | None = None) -> DailyCounters:
        """Load daily counters, automatically rolling over to 0 if stored date != today."""
        target_date = today or datetime.now(UTC).date()
        target_date_str = target_date.isoformat()

        if self.daily_counters_path.exists():
            try:
                raw = json.loads(self.daily_counters_path.read_text(encoding="utf-8"))
                if raw.get("date") == target_date_str:
                    return DailyCounters.model_validate(raw)
            except Exception:
                pass

        # Date rollover or missing: reset counters to 0 for target_date
        fresh_counters = DailyCounters(
            date=target_date_str,
            comments_executed=0,
            posts_executed=0,
            suggestions_sent=0,
        )
        self.save_daily_counters(fresh_counters)
        return fresh_counters

    def save_daily_counters(self, counters: DailyCounters) -> None:
        """Save daily counters to daily_counters.json."""
        payload = counters.model_dump(mode="json")
        self._atomic_write_json(self.daily_counters_path, payload)

    def increment_comment_count(self, today: date | None = None) -> DailyCounters:
        """Increment daily comment count by 1 and return updated counters."""
        counters = self.load_daily_counters(today)
        updated = DailyCounters(
            date=counters.date,
            comments_executed=counters.comments_executed + 1,
            posts_executed=counters.posts_executed,
            suggestions_sent=counters.suggestions_sent,
        )
        self.save_daily_counters(updated)
        return updated

    def increment_post_count(self, today: date | None = None) -> DailyCounters:
        """Increment daily post count by 1 and return updated counters."""
        counters = self.load_daily_counters(today)
        updated = DailyCounters(
            date=counters.date,
            comments_executed=counters.comments_executed,
            posts_executed=counters.posts_executed + 1,
            suggestions_sent=counters.suggestions_sent,
        )
        self.save_daily_counters(updated)
        return updated

    def increment_suggestion_count(
        self, count: int = 1, today: date | None = None
    ) -> DailyCounters:
        """Increment daily suggestions sent count and return updated counters."""
        counters = self.load_daily_counters(today)
        updated = DailyCounters(
            date=counters.date,
            comments_executed=counters.comments_executed,
            posts_executed=counters.posts_executed,
            suggestions_sent=counters.suggestions_sent + count,
        )
        self.save_daily_counters(updated)
        return updated

    # -------------------------------------------------------------------------
    # Git Persistence
    # -------------------------------------------------------------------------

    def commit_and_push(
        self,
        message: str,
        push: bool = False,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        remote: str | None = None,
        branch: str | None = None,
    ) -> bool:
        """Stage state/ directory and commit state changes with rebase resilience.

        Args:
            message: Git commit message.
            push: Whether to push to remote (default False, used in CI workflows).
            max_retries: Maximum number of push/rebase retry attempts (default 3).
            backoff_factor: Exponential backoff base delay in seconds (default 0.5).
            remote: Optional remote name (default None -> git tracking upstream).
            branch: Optional branch name (default None -> current branch).

        Returns:
            bool: True if changes were committed, False if working tree had no state diff.

        Raises:
            StateStoreError: If git command fails or rebase encounters an unresolvable conflict.
        """
        try:
            # Stage state directory
            subprocess.run(
                ["git", "add", "state/"],
                cwd=str(self.repo_root),
                check=True,
                capture_output=True,
                text=True,
            )

            # Check if there is a diff staged
            diff_check = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=str(self.repo_root),
                capture_output=True,
            )

            # Returncode 0 means no diff, 1 means diff present
            if diff_check.returncode == 0:
                return False

            # Commit locally to preserve state in git database
            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=str(self.repo_root),
                check=True,
                capture_output=True,
                text=True,
            )

            if not push:
                return True

            # Prepare push and pull commands
            push_cmd = ["git", "push"]
            pull_cmd = ["git", "pull", "--rebase"]
            if remote:
                push_cmd.append(remote)
                pull_cmd.append(remote)
                if branch:
                    push_cmd.append(branch)
                    pull_cmd.append(branch)

            for attempt in range(1, max_retries + 1):
                try:
                    subprocess.run(
                        push_cmd,
                        cwd=str(self.repo_root),
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    return True
                except subprocess.CalledProcessError as push_err:
                    err_msg = push_err.stderr.strip() if push_err.stderr else str(push_err)

                    if attempt >= max_retries:
                        raise StateStoreError(
                            f"Git push failed after {max_retries} attempts: {err_msg}"
                        ) from push_err

                    # Attempt pull --rebase
                    try:
                        subprocess.run(
                            pull_cmd,
                            cwd=str(self.repo_root),
                            check=True,
                            capture_output=True,
                            text=True,
                        )
                    except subprocess.CalledProcessError as rebase_err:
                        # Abort rebase to guarantee clean repository state
                        subprocess.run(
                            ["git", "rebase", "--abort"],
                            cwd=str(self.repo_root),
                            capture_output=True,
                        )
                        rebase_err_msg = (
                            rebase_err.stderr.strip() if rebase_err.stderr else str(rebase_err)
                        )
                        raise StateStoreError(
                            f"Git pull --rebase failed during push retry (attempt {attempt}/{max_retries}): {rebase_err_msg}"
                        ) from rebase_err

                    # Exponential backoff delay
                    if backoff_factor > 0:
                        time.sleep(backoff_factor * (2 ** (attempt - 1)))

            return True

        except subprocess.CalledProcessError as err:
            err_msg = err.stderr.strip() if err.stderr else str(err)
            raise StateStoreError(f"Git commit/push failed: {err_msg}") from err
        except StateStoreError:
            raise
        except Exception as err:
            raise StateStoreError(f"Unexpected git state error: {err}") from err
