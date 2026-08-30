"""Unit tests for storage state symmetric encryption and decryption."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import SecretStr

from agent.browser.session import (
    decrypt_storage_state,
    encrypt_storage_state,
    generate_encryption_key,
)
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
