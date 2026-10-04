"""Unit tests for connection queue, scheduled posts, and active threads state persistence."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agent.models import (
    ActiveThreadRecord,
    ConnectionCandidate,
    MediaAttachment,
    ScheduledPost,
)
from agent.state.kv_store import CloudflareKVStateStore
from agent.state.store import GitStateStore


class TestGitStateStoreFeatures:
    """Test connection queue, scheduled posts, and active threads in GitStateStore."""

    def test_connection_queue_operations(self, tmp_path: Path) -> None:
        store = GitStateStore(tmp_path)
        assert store.load_connection_queue() == []

        cand1 = ConnectionCandidate(
            id="cand_1",
            profile_url="https://linkedin.com/in/user1",
            target_name="User One",
            note_text="Hello User One",
        )
        store.add_connection_candidate(cand1)
        queue = store.load_connection_queue()
        assert len(queue) == 1
        assert queue[0].id == "cand_1"

        retrieved = store.read_connection_candidate("cand_1")
        assert retrieved is not None
        assert retrieved.target_name == "User One"

        store.update_connection_status("cand_1", "approved", note_text="Updated note")
        updated = store.read_connection_candidate("cand_1")
        assert updated is not None
        assert updated.status == "approved"
        assert updated.note_text == "Updated note"
        assert updated.approved_at is not None

        # Increment connection count
        counters = store.increment_connection_count()
        assert counters.connections_sent == 1
        counters2 = store.increment_connection_count()
        assert counters2.connections_sent == 2

    def test_scheduled_posts_operations(self, tmp_path: Path) -> None:
        store = GitStateStore(tmp_path)
        assert store.list_scheduled_posts() == []

        post = ScheduledPost(
            id="sch_1",
            headline="Post Headline",
            post_text="Content text here",
            status="scheduled",
            media=[
                MediaAttachment(
                    media_type="image",
                    file_name="pic.png",
                    file_url="https://r2/pic.png",
                    slide_count=1,
                )
            ],
            topic_pillar="AI",
        )
        store.save_scheduled_post(post)

        posts = store.list_scheduled_posts()
        assert len(posts) == 1
        assert posts[0].id == "sch_1"
        assert posts[0].headline == "Post Headline"

        read_post = store.read_scheduled_post("sch_1")
        assert read_post is not None
        assert read_post.post_text == "Content text here"

        deleted = store.delete_scheduled_post("sch_1")
        assert deleted is True
        assert store.read_scheduled_post("sch_1") is None
        assert store.list_scheduled_posts() == []

    def test_active_threads_operations(self, tmp_path: Path) -> None:
        store = GitStateStore(tmp_path)
        assert store.list_active_threads() == []

        thread = ActiveThreadRecord(
            id="th_100",
            post_url="https://linkedin.com/post/100",
            post_urn="urn:li:post:100",
            our_comment_urn="urn:li:comment:100",
            our_comment_text="Top-level comment",
            post_author="Author Name",
            status="active",
        )
        store.save_active_thread(thread)

        threads = store.list_active_threads()
        assert len(threads) == 1
        assert threads[0].id == "th_100"

        store.update_thread_status("th_100", "resolved")
        threads_after = store.list_active_threads()
        assert len(threads_after) == 1
        assert threads_after[0].status == "resolved"


class TestCloudflareKVStateStoreFeatures:
    """Test connection queue, scheduled posts, and active threads in CloudflareKVStateStore."""

    @pytest.fixture
    def mock_kv_store(self) -> CloudflareKVStateStore:
        store = CloudflareKVStateStore(
            account_id="test_acc",
            namespace_id="test_ns",
            api_token="test_tok",
        )
        kv_data: dict[str, str] = {}

        def mock_get(key: str) -> str | None:
            return kv_data.get(key)

        def mock_put(key: str, value: str) -> None:
            kv_data[key] = value

        def mock_delete(key: str) -> bool:
            return kv_data.pop(key, None) is not None

        def mock_list(prefix: str = "") -> list[str]:
            return [k for k in kv_data if k.startswith(prefix)]

        store._get_value = MagicMock(side_effect=mock_get)  # type: ignore[method-assign]
        store._put_value = MagicMock(side_effect=mock_put)  # type: ignore[method-assign]
        store._delete_key = MagicMock(side_effect=mock_delete)  # type: ignore[method-assign]
        store._list_keys = MagicMock(side_effect=mock_list)  # type: ignore[method-assign]
        return store

    def test_kv_connection_queue_operations(self, mock_kv_store: CloudflareKVStateStore) -> None:
        assert mock_kv_store.load_connection_queue() == []

        cand = ConnectionCandidate(
            id="cand_kv_1",
            profile_url="https://linkedin.com/in/kvuser",
            target_name="KV User",
        )
        mock_kv_store.add_connection_candidate(cand)
        queue = mock_kv_store.load_connection_queue()
        assert len(queue) == 1
        assert queue[0].id == "cand_kv_1"

        mock_kv_store.update_connection_status("cand_kv_1", "approved")
        cand_updated = mock_kv_store.read_connection_candidate("cand_kv_1")
        assert cand_updated is not None
        assert cand_updated.status == "approved"

    def test_kv_scheduled_posts_operations(self, mock_kv_store: CloudflareKVStateStore) -> None:
        assert mock_kv_store.list_scheduled_posts() == []

        post = ScheduledPost(
            id="kv_post_1",
            headline="KV Post",
            post_text="KV Post Text",
            status="scheduled",
        )
        mock_kv_store.save_scheduled_post(post)
        assert len(mock_kv_store.list_scheduled_posts()) == 1
        assert mock_kv_store.read_scheduled_post("kv_post_1") is not None

        deleted = mock_kv_store.delete_scheduled_post("kv_post_1")
        assert deleted is True
        assert mock_kv_store.read_scheduled_post("kv_post_1") is None

    def test_kv_active_threads_operations(self, mock_kv_store: CloudflareKVStateStore) -> None:
        assert mock_kv_store.list_active_threads() == []

        thread = ActiveThreadRecord(
            id="kv_th_1",
            post_url="https://linkedin.com/post/kv",
            post_urn="urn:li:post:kv",
            our_comment_urn="urn:li:comment:kv",
            our_comment_text="KV text",
            post_author="Author",
            status="active",
        )
        mock_kv_store.save_active_thread(thread)
        mock_kv_store.update_thread_status("kv_th_1", "resolved")
        threads_after = mock_kv_store.list_active_threads()
        assert len(threads_after) == 1
        assert threads_after[0].status == "resolved"
