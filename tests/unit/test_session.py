"""Unit tests for storage state symmetric encryption and decryption."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import SecretStr

from agent.browser.session import (
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
        _env_file=None,
    )
    with pytest.raises(SessionError, match="LinkedIn session state not found"):
        ensure_session_file(settings)
