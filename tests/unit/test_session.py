"""Unit tests for storage state symmetric encryption and decryption."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from pydantic import SecretStr

from agent.browser.session import (
    check_session_expiry,
    decrypt_storage_state,
    encrypt_storage_state,
    ensure_session_file,
    generate_encryption_key,
)
from agent.config import Settings
from agent.errors import SessionError


def test_encryption_roundtrip(tmp_path: Path) -> None:
    key = generate_encryption_key()
    sample_storage_state = {
        "cookies": [{"name": "li_at", "value": "secret_cookie_val", "domain": ".linkedin.com"}],
        "origins": [],
    }
    raw_bytes = json.dumps(sample_storage_state).encode("utf-8")

    # Encrypt
    encrypted_token = encrypt_storage_state(raw_bytes, key)
    assert isinstance(encrypted_token, str)
    assert len(encrypted_token) > 20

    # Decrypt
    out_file = tmp_path / "decrypted_state.json"
    result_path = decrypt_storage_state(encrypted_token, SecretStr(key), out_file)
    assert result_path.exists()

    decrypted_data = json.loads(result_path.read_text(encoding="utf-8"))
    assert decrypted_data["cookies"][0]["value"] == "secret_cookie_val"


def test_decrypt_with_invalid_key(tmp_path: Path) -> None:
    valid_key = generate_encryption_key()
    wrong_key = generate_encryption_key()
    raw_bytes = b'{"cookies": []}'

    encrypted_token = encrypt_storage_state(raw_bytes, valid_key)
    out_file = tmp_path / "should_fail.json"

    with pytest.raises(SessionError, match="Session decryption failed"):
        decrypt_storage_state(encrypted_token, wrong_key, out_file)


def test_decrypt_empty_token_raises(tmp_path: Path) -> None:
    key = generate_encryption_key()
    out_file = tmp_path / "empty.json"

    with pytest.raises(SessionError, match="Empty or missing"):
        decrypt_storage_state("", key, out_file)


def test_ensure_session_file_existing(tmp_path: Path) -> None:
    existing_file = tmp_path / "storage_state.json"
    existing_file.write_text('{"cookies": []}', encoding="utf-8")

    settings = Settings(
        nvidia_nim_api_key=SecretStr("key"),
        telegram_bot_token=SecretStr("tok"),
        telegram_authorized_chat_id=123,
        linkedin_storage_state_path=existing_file,
    )
    result = ensure_session_file(settings)
    assert result == existing_file.resolve()


def test_ensure_session_file_auto_decrypt(tmp_path: Path) -> None:
    key = generate_encryption_key()
    raw_bytes = b'{"cookies": [{"name": "li_at", "value": "xyz"}]}'
    encrypted_token = encrypt_storage_state(raw_bytes, key)

    out_file = tmp_path / "auto_decrypted.json"
    assert not out_file.exists()

    settings = Settings(
        nvidia_nim_api_key=SecretStr("key"),
        telegram_bot_token=SecretStr("tok"),
        telegram_authorized_chat_id=123,
        session_encryption_key=SecretStr(key),
        linkedin_session_state_enc=SecretStr(encrypted_token),
        linkedin_storage_state_path=out_file,
    )
    result = ensure_session_file(settings)
    assert result.exists()
    assert b"xyz" in result.read_bytes()


def test_ensure_session_file_missing_raises(tmp_path: Path) -> None:
    non_existing = tmp_path / "missing.json"
    settings = Settings(
        nvidia_nim_api_key=SecretStr("key"),
        telegram_bot_token=SecretStr("tok"),
        telegram_authorized_chat_id=123,
        session_encryption_key=None,
        linkedin_session_state_enc=None,
        linkedin_storage_state_path=non_existing,
    )
    with pytest.raises(SessionError, match="LinkedIn session state not found"):
        ensure_session_file(settings)


def test_check_session_expiry_missing_or_invalid(tmp_path: Path) -> None:
    # Non-existent file
    res = check_session_expiry(tmp_path / "nonexistent.json")
    assert res["has_cookie"] is False
    assert res["is_expiring_soon"] is False

    # Corrupted JSON
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("not-json", encoding="utf-8")
    assert check_session_expiry(corrupt)["has_cookie"] is False

    # Missing li_at cookie
    no_li_at = tmp_path / "no_li_at.json"
    no_li_at.write_text(
        '{"cookies": [{"name": "other_cookie", "expires": 12345}]}', encoding="utf-8"
    )
    assert check_session_expiry(no_li_at)["has_cookie"] is False


def test_check_session_expiry_valid_and_expiring_soon(tmp_path: Path) -> None:
    now = time.time()
    # Expiring in 2 days (<= 3 days threshold)
    two_days_later = now + (2 * 86400)
    data = {"cookies": [{"name": "li_at", "value": "auth-val", "expires": two_days_later}]}
    file_path = tmp_path / "expiring.json"
    file_path.write_text(json.dumps(data), encoding="utf-8")

    res = check_session_expiry(file_path, warning_days=3)
    assert res["has_cookie"] is True
    assert res["is_expiring_soon"] is True
    assert 1.9 <= res["days_remaining"] <= 2.1

    # Safe future (10 days later)
    ten_days_later = now + (10 * 86400)
    data_safe = {"cookies": [{"name": "li_at", "value": "auth-val", "expires": ten_days_later}]}
    file_safe = tmp_path / "safe.json"
    file_safe.write_text(json.dumps(data_safe), encoding="utf-8")

    res_safe = check_session_expiry(file_safe, warning_days=3)
    assert res_safe["has_cookie"] is True
    assert res_safe["is_expiring_soon"] is False
    assert 9.9 <= res_safe["days_remaining"] <= 10.1


def test_check_session_expiry_milliseconds_timestamp() -> None:
    now_ms = time.time() * 1000
    one_day_ms = now_ms + (1 * 86400 * 1000)
    data = {"cookies": [{"name": "li_at", "value": "auth-val", "expires": one_day_ms}]}
    res = check_session_expiry(data, warning_days=3)
    assert res["has_cookie"] is True
    assert res["is_expiring_soon"] is True
    assert 0.9 <= res["days_remaining"] <= 1.1
