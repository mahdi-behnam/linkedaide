"""Unit tests for the unified CLI tool, diagnostic doctor, and setup wizard."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from agent.cli import (
    build_parser,
    main,
    run_doctor,
    run_execute,
    run_health,
    run_ideate,
    run_poll,
    run_scout,
    run_setup,
)
from agent.cli.setup import (
    parse_dotenv_lines,
    read_dotenv_vars,
    update_dotenv_file,
)
from agent.config import Settings
from agent.doctor import (
    CheckResult,
    check_configuration,
    check_linkedin_session,
    check_llm_provider,
    check_playwright_chromium,
    check_python_runtime,
    check_state_backend,
    check_telegram_bot,
    format_check_result,
)
from agent.errors import ConfigError

# =============================================================================
# 1. CLI Parser Dispatch Tests
# =============================================================================


def test_build_parser_doctor() -> None:
    parser = build_parser()
    args = parser.parse_args(["doctor", "--repo-root", "/custom/path"])
    assert args.command == "doctor"
    assert args.repo_root == "/custom/path"


def test_build_parser_setup() -> None:
    parser = build_parser()
    args = parser.parse_args(["setup", "--env-file", ".env.test"])
    assert args.command == "setup"
    assert args.env_file == ".env.test"


def test_build_parser_scout() -> None:
    parser = build_parser()
    args = parser.parse_args(["scout", "--dry-run", "--headed"])
    assert args.command == "scout"
    assert args.dry_run is True
    assert args.headed is True


def test_build_parser_execute() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "execute",
            "--action",
            "approve",
            "--item-id",
            "item1234",
            "--chat-id",
            "987654",
            "--message-id",
            "123",
            "--callback-query-id",
            "cb_999",
        ]
    )
    assert args.command == "execute"
    assert args.action == "approve"
    assert args.item_id == "item1234"
    assert args.chat_id == 987654
    assert args.message_id == 123
    assert args.callback_query_id == "cb_999"


def test_build_parser_health() -> None:
    parser = build_parser()
    args = parser.parse_args(["health", "--repo-root", "/some/root"])
    assert args.command == "health"
    assert args.repo_root == "/some/root"


def test_build_parser_poll() -> None:
    parser = build_parser()
    args = parser.parse_args(["poll", "--timeout", "30", "--once", "--repo-root", "/some/root"])
    assert args.command == "poll"
    assert args.timeout == 30
    assert args.once is True
    assert args.repo_root == "/some/root"


def test_build_parser_ideate() -> None:
    parser = build_parser()
    args = parser.parse_args(["ideate", "--dry-run", "--repo-root", "/some/root"])
    assert args.command == "ideate"
    assert args.dry_run is True
    assert args.repo_root == "/some/root"


def test_main_no_args_exits_cleanly(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "usage: agent" in captured.out


# =============================================================================
# 2. Diagnostic Check Tests
# =============================================================================


def test_check_python_runtime_pass() -> None:
    res = check_python_runtime()
    assert res.status == "PASS"
    assert "Python" in res.message


def test_check_python_runtime_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.version_info", (3, 10, 5))
    res = check_python_runtime()
    assert res.status == "FAIL"
    assert "Python >= 3.11 is required" in res.message


def test_check_playwright_chromium_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_exec = tmp_path / "chrome"
    fake_exec.write_text("fake binary")

    class MockChromium:
        executable_path = str(fake_exec)

    class MockPlaywrightInstance:
        chromium = MockChromium()

    class MockPlaywrightCM:
        def __enter__(self) -> MockPlaywrightInstance:
            return MockPlaywrightInstance()

        def __exit__(self, *args: Any) -> None:
            pass

    monkeypatch.setattr("agent.doctor.checks.sync_playwright", lambda: MockPlaywrightCM())
    res = check_playwright_chromium()
    assert res.status == "PASS"
    assert "Chromium executable found" in res.message


def test_check_playwright_chromium_missing_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    non_existent = tmp_path / "missing_chrome"

    class MockChromium:
        executable_path = str(non_existent)

    class MockPlaywrightInstance:
        chromium = MockChromium()

    class MockPlaywrightCM:
        def __enter__(self) -> MockPlaywrightInstance:
            return MockPlaywrightInstance()

        def __exit__(self, *args: Any) -> None:
            pass

    monkeypatch.setattr("agent.doctor.checks.sync_playwright", lambda: MockPlaywrightCM())
    res = check_playwright_chromium()
    assert res.status == "FAIL"
    assert "not found" in res.message


def test_check_playwright_chromium_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_err() -> None:
        raise RuntimeError("Playwright internal driver error")

    monkeypatch.setattr("agent.doctor.checks.sync_playwright", raise_err)
    res = check_playwright_chromium()
    assert res.status == "FAIL"
    assert "Playwright check failed" in res.message


def test_check_configuration_valid() -> None:
    dummy_settings = Settings(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        telegram_authorized_chat_id=123456789,
        nvidia_nim_api_key="nvapi-testkey",
    )
    res, settings = check_configuration(dummy_settings)
    assert res.status == "PASS"
    assert settings is dummy_settings


def test_check_configuration_load_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_load() -> Settings:
        raise ConfigError("Missing required fields")

    monkeypatch.setattr("agent.doctor.checks.load_settings", fail_load)
    res, settings = check_configuration(None)
    assert res.status == "FAIL"
    assert settings is None
    assert "Configuration validation failed" in res.message


def test_check_llm_provider_nvidia_pass() -> None:
    settings = Settings(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        telegram_authorized_chat_id=123456789,
        llm_provider="nvidia",
        nvidia_nim_api_key="nvapi-valid",
    )
    with patch("agent.llm.models.build_chat_model") as mock_build:
        mock_build.return_value = MagicMock()
        res = check_llm_provider(settings)
        assert res.status == "PASS"
        assert "Provider 'nvidia' configured" in res.message


def test_check_llm_provider_missing_key() -> None:
    # Use object with missing key
    settings = MagicMock(spec=Settings)
    settings.llm_provider = "openai"
    settings.get_api_key_for_provider.return_value = None

    res = check_llm_provider(settings)
    assert res.status == "FAIL"
    assert "Missing API key" in res.message


def test_check_llm_provider_import_error() -> None:
    settings = Settings(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        telegram_authorized_chat_id=123456789,
        llm_provider="nvidia",
        nvidia_nim_api_key="nvapi-valid",
    )
    with patch("agent.llm.models.build_chat_model", side_effect=ImportError("Package not found")):
        res = check_llm_provider(settings)
        assert res.status == "FAIL"
        assert "Missing dependency" in res.message


def test_check_telegram_bot_success() -> None:
    settings = Settings(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        telegram_authorized_chat_id=123456789,
        nvidia_nim_api_key="nvapi-valid",
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "ok": True,
        "result": {"username": "AgentHITLBot", "first_name": "HITL Bot"},
    }

    mock_client = MagicMock(spec=httpx.Client)
    mock_client.get.return_value = mock_resp

    res = check_telegram_bot(settings, client=mock_client)
    assert res.status == "PASS"
    assert "@AgentHITLBot" in res.message


def test_check_telegram_bot_invalid_token() -> None:
    settings = Settings(
        telegram_bot_token="invalid_token",
        telegram_authorized_chat_id=123456789,
        nvidia_nim_api_key="nvapi-valid",
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 401

    mock_client = MagicMock(spec=httpx.Client)
    mock_client.get.return_value = mock_resp

    res = check_telegram_bot(settings, client=mock_client)
    assert res.status == "FAIL"
    assert "Invalid bot token" in res.message


def test_check_telegram_bot_network_error() -> None:
    settings = Settings(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        telegram_authorized_chat_id=123456789,
        nvidia_nim_api_key="nvapi-valid",
    )
    mock_client = MagicMock(spec=httpx.Client)
    mock_client.get.side_effect = httpx.ConnectError("Failed to connect")

    res = check_telegram_bot(settings, client=mock_client)
    assert res.status == "FAIL"
    assert "Network error" in res.message


def test_check_state_backend_local_writable(tmp_path: Path) -> None:
    settings = Settings(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        telegram_authorized_chat_id=123456789,
        nvidia_nim_api_key="nvapi-valid",
        state_backend="git",
        state_dir=Path("state_test"),
    )
    res = check_state_backend(settings, repo_root=tmp_path)
    assert res.status == "PASS"
    assert "State directory writable" in res.message
    assert (tmp_path / "state_test").exists()


def test_check_state_backend_kv_success() -> None:
    settings = Settings(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        telegram_authorized_chat_id=123456789,
        nvidia_nim_api_key="nvapi-valid",
        state_backend="kv",
        cloudflare_account_id="cf_acc_123",
        cloudflare_kv_namespace_id="cf_ns_456",
        cloudflare_api_token="cf_tok_789",
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"success": True, "result": []}

    mock_client = MagicMock(spec=httpx.Client)
    mock_client.get.return_value = mock_resp

    res = check_state_backend(settings, client=mock_client)
    assert res.status == "PASS"
    assert "Connected to Cloudflare KV" in res.message


def test_check_state_backend_kv_failure() -> None:
    settings = Settings(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        telegram_authorized_chat_id=123456789,
        nvidia_nim_api_key="nvapi-valid",
        state_backend="kv",
        cloudflare_account_id="cf_acc_123",
        cloudflare_kv_namespace_id="cf_ns_456",
        cloudflare_api_token="cf_tok_789",
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = "Forbidden"

    mock_client = MagicMock(spec=httpx.Client)
    mock_client.get.return_value = mock_resp

    res = check_state_backend(settings, client=mock_client)
    assert res.status == "FAIL"
    assert "Cloudflare KV returned HTTP 403" in res.message


def test_check_linkedin_session_file_exists(tmp_path: Path) -> None:
    storage_file = tmp_path / "storage_state.json"
    storage_file.write_text('{"cookies": []}')
    settings = Settings(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        telegram_authorized_chat_id=123456789,
        nvidia_nim_api_key="nvapi-valid",
        linkedin_storage_state_path=storage_file,
    )
    res = check_linkedin_session(settings)
    assert res.status == "PASS"
    assert "Decrypted session storage file found" in res.message


def test_check_linkedin_session_encrypted_valid(tmp_path: Path) -> None:
    key = Fernet.generate_key().decode("utf-8")
    f = Fernet(key.encode("utf-8"))
    encrypted_data = f.encrypt(b'{"cookies": []}').decode("utf-8")

    settings = Settings(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        telegram_authorized_chat_id=123456789,
        nvidia_nim_api_key="nvapi-valid",
        linkedin_storage_state_path=tmp_path / "non_existent.json",
        session_encryption_key=SecretStr(key),
        linkedin_session_state_enc=SecretStr(encrypted_data),
    )
    res = check_linkedin_session(settings)
    assert res.status == "PASS"
    assert "Encrypted LinkedIn session verified" in res.message


def test_check_linkedin_session_corrupted_key(tmp_path: Path) -> None:
    bad_key = Fernet.generate_key().decode("utf-8")
    settings = Settings(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        telegram_authorized_chat_id=123456789,
        nvidia_nim_api_key="nvapi-valid",
        linkedin_storage_state_path=tmp_path / "non_existent.json",
        session_encryption_key=SecretStr(bad_key),
        linkedin_session_state_enc=SecretStr("corrupted_base64_payload"),
    )
    res = check_linkedin_session(settings)
    assert res.status == "FAIL"
    assert "Invalid SESSION_ENCRYPTION_KEY or corrupted" in res.message


def test_check_linkedin_session_missing(tmp_path: Path) -> None:
    settings = Settings(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        telegram_authorized_chat_id=123456789,
        nvidia_nim_api_key="nvapi-valid",
        linkedin_storage_state_path=tmp_path / "missing.json",
        session_encryption_key=None,
        linkedin_session_state_enc=None,
    )
    res = check_linkedin_session(settings)
    assert res.status == "WARN"
    assert "not configured" in res.message


def test_format_check_result() -> None:
    pass_res = CheckResult(name="Test", status="PASS", message="Passed ok")
    warn_res = CheckResult(
        name="Test", status="WARN", message="Warning notice", details="Extra info"
    )
    fail_res = CheckResult(name="Test", status="FAIL", message="Failed error")

    assert "🟢 Pass" in format_check_result(pass_res)
    assert "🟡 Warning" in format_check_result(warn_res)
    assert "Extra info" in format_check_result(warn_res)
    assert "🔴 Fail" in format_check_result(fail_res)


# =============================================================================
# 3. Doctor Diagnostics Suite Tests
# =============================================================================


def test_doctor_all_passing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    session_file = tmp_path / "storage_state.json"
    session_file.write_text("{}")
    settings = Settings(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        telegram_authorized_chat_id=123456789,
        nvidia_nim_api_key="nvapi-valid",
        linkedin_storage_state_path=session_file,
    )

    class MockChromium:
        executable_path = str(session_file)

    class MockPlaywrightCM:
        def __enter__(self) -> Any:
            mock_inst = MagicMock()
            mock_inst.chromium = MockChromium()
            return mock_inst

        def __exit__(self, *args: Any) -> None:
            pass

    monkeypatch.setattr("agent.doctor.checks.sync_playwright", lambda: MockPlaywrightCM())
    with patch("agent.llm.models.build_chat_model", return_value=MagicMock()):
        mock_tg_client = MagicMock(spec=httpx.Client)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True, "result": {"username": "agent_bot"}}
        mock_tg_client.get.return_value = mock_resp

        code = run_doctor(
            settings=settings,
            repo_root=tmp_path,
            telegram_client=mock_tg_client,
        )
        assert code == 0


def test_doctor_failing_telegram(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    session_file = tmp_path / "storage_state.json"
    session_file.write_text("{}")
    settings = Settings(
        telegram_bot_token="invalid",
        telegram_authorized_chat_id=123456789,
        nvidia_nim_api_key="nvapi-valid",
        linkedin_storage_state_path=session_file,
    )

    class MockChromium:
        executable_path = str(session_file)

    class MockPlaywrightCM:
        def __enter__(self) -> Any:
            mock_inst = MagicMock()
            mock_inst.chromium = MockChromium()
            return mock_inst

        def __exit__(self, *args: Any) -> None:
            pass

    monkeypatch.setattr("agent.doctor.checks.sync_playwright", lambda: MockPlaywrightCM())
    with patch("agent.llm.models.build_chat_model", return_value=MagicMock()):
        mock_tg_client = MagicMock(spec=httpx.Client)
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_tg_client.get.return_value = mock_resp

        code = run_doctor(
            settings=settings,
            repo_root=tmp_path,
            telegram_client=mock_tg_client,
        )
        assert code == 1


def test_doctor_failing_llm(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    session_file = tmp_path / "storage_state.json"
    session_file.write_text("{}")
    settings = Settings(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        telegram_authorized_chat_id=123456789,
        nvidia_nim_api_key="nvapi-valid",
        linkedin_storage_state_path=session_file,
    )

    class MockChromium:
        executable_path = str(session_file)

    class MockPlaywrightCM:
        def __enter__(self) -> Any:
            mock_inst = MagicMock()
            mock_inst.chromium = MockChromium()
            return mock_inst

        def __exit__(self, *args: Any) -> None:
            pass

    monkeypatch.setattr("agent.doctor.checks.sync_playwright", lambda: MockPlaywrightCM())
    with patch("agent.llm.models.build_chat_model", side_effect=RuntimeError("Model failure")):
        mock_tg_client = MagicMock(spec=httpx.Client)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True, "result": {"username": "agent_bot"}}
        mock_tg_client.get.return_value = mock_resp

        code = run_doctor(
            settings=settings,
            repo_root=tmp_path,
            telegram_client=mock_tg_client,
        )
        assert code == 1


def test_doctor_failing_playwright(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    session_file = tmp_path / "storage_state.json"
    session_file.write_text("{}")
    settings = Settings(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        telegram_authorized_chat_id=123456789,
        nvidia_nim_api_key="nvapi-valid",
        linkedin_storage_state_path=session_file,
    )

    class MockChromium:
        executable_path = str(tmp_path / "does_not_exist_chrome")

    class MockPlaywrightCM:
        def __enter__(self) -> Any:
            mock_inst = MagicMock()
            mock_inst.chromium = MockChromium()
            return mock_inst

        def __exit__(self, *args: Any) -> None:
            pass

    monkeypatch.setattr("agent.doctor.checks.sync_playwright", lambda: MockPlaywrightCM())
    with patch("agent.llm.models.build_chat_model", return_value=MagicMock()):
        mock_tg_client = MagicMock(spec=httpx.Client)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True, "result": {"username": "agent_bot"}}
        mock_tg_client.get.return_value = mock_resp

        code = run_doctor(
            settings=settings,
            repo_root=tmp_path,
            telegram_client=mock_tg_client,
        )
        assert code == 1


# =============================================================================
# 4. Setup Wizard Tests
# =============================================================================


def test_parse_dotenv_lines() -> None:
    content = """# Comment line
FOO=bar
EMPTY_LINE=

export BAZ=qux
# Another comment
"""
    parsed = parse_dotenv_lines(content)
    assert parsed[0] == (None, "# Comment line\n")
    assert parsed[1] == ("FOO", "FOO=bar\n")
    assert parsed[2] == ("EMPTY_LINE", "EMPTY_LINE=\n")
    assert parsed[4] == ("BAZ", "export BAZ=qux\n")


def test_read_dotenv_vars(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        """# Sample
VAR_A=hello
VAR_B="world with spaces"
export VAR_C='single_quoted'
"""
    )
    res = read_dotenv_vars(env_file)
    assert res == {
        "VAR_A": "hello",
        "VAR_B": "world with spaces",
        "VAR_C": "single_quoted",
    }


def test_update_dotenv_file_preserves_unrelated(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        """# Operator comments
EXISTING_VAR=preserve_me
TELEGRAM_BOT_TOKEN=old_token
DRY_RUN=true
"""
    )

    update_dotenv_file(
        env_file,
        {
            "TELEGRAM_BOT_TOKEN": "new_token_123",
            "NEW_VAR": "added_value",
        },
    )

    content = env_file.read_text()
    assert "# Operator comments" in content
    assert "EXISTING_VAR=preserve_me" in content
    assert "DRY_RUN=true" in content
    assert "TELEGRAM_BOT_TOKEN=new_token_123" in content
    assert "NEW_VAR=added_value" in content
    assert "old_token" not in content


def test_setup_interactive_new_env(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"

    user_inputs = [
        "1",  # Provider: 1 -> nvidia
        "nvapi-test-api-key",  # NVIDIA NIM key
        "123456:ABC-telegram-token",  # Telegram bot token
        "987654321",  # Telegram chat ID
        "git",  # State backend: git
    ]
    input_iter = iter(user_inputs)

    def mock_input(prompt: str) -> str:
        return next(input_iter)

    written = run_setup(env_path=env_file, input_func=mock_input, print_func=lambda *a: None)

    assert written["LLM_PROVIDER"] == "nvidia"
    assert written["NVIDIA_NIM_API_KEY"] == "nvapi-test-api-key"
    assert written["TELEGRAM_BOT_TOKEN"] == "123456:ABC-telegram-token"
    assert written["TELEGRAM_AUTHORIZED_CHAT_ID"] == "987654321"
    assert written["STATE_BACKEND"] == "git"
    assert "SESSION_ENCRYPTION_KEY" in written

    # Verify generated Fernet key is valid
    key = written["SESSION_ENCRYPTION_KEY"]
    f = Fernet(key.encode("utf-8"))
    assert f.decrypt(f.encrypt(b"test")) == b"test"

    # Check file contents
    saved = read_dotenv_vars(env_file)
    assert saved["LLM_PROVIDER"] == "nvidia"
    assert saved["TELEGRAM_BOT_TOKEN"] == "123456:ABC-telegram-token"


def test_setup_interactive_kv_backend(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"

    user_inputs = [
        "openai",  # Provider: openai
        "sk-test-openai-key",  # OpenAI API key
        "123456:ABC-telegram-token",  # Telegram bot token
        "987654321",  # Telegram chat ID
        "kv",  # State backend: kv
        "cf_account_123",  # Cloudflare account ID
        "cf_namespace_456",  # Cloudflare KV namespace ID
        "cf_token_789",  # Cloudflare API token
    ]
    input_iter = iter(user_inputs)

    written = run_setup(
        env_path=env_file,
        input_func=lambda p: next(input_iter),
        print_func=lambda *a: None,
    )

    assert written["LLM_PROVIDER"] == "openai"
    assert written["OPENAI_API_KEY"] == "sk-test-openai-key"
    assert written["STATE_BACKEND"] == "kv"
    assert written["CLOUDFLARE_ACCOUNT_ID"] == "cf_account_123"
    assert written["CLOUDFLARE_KV_NAMESPACE_ID"] == "cf_namespace_456"
    assert written["CLOUDFLARE_API_TOKEN"] == "cf_token_789"


# =============================================================================
# 5. Flow Dispatcher Tests
# =============================================================================


def test_run_scout_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        telegram_authorized_chat_id=123456789,
        nvidia_nim_api_key="nvapi-valid",
    )
    monkeypatch.setattr("agent.cli.load_settings", lambda: settings)

    with patch("agent.orchestration.scout_flow.run_scout_flow") as mock_flow:
        mock_flow.return_value = {"status": "completed", "pending_items": []}
        args = argparse.Namespace(dry_run=True, headed=False)
        code = run_scout(args)
        assert code == 0
        mock_flow.assert_called_once()


def test_run_execute_dispatch() -> None:
    with patch("agent.orchestration.execute_flow.run_execute_flow") as mock_flow:
        mock_flow.return_value = {"status": "success"}
        args = argparse.Namespace(
            action="approve",
            item_id="abcd1234",
            chat_id=123456,
            message_id=789,
            callback_query_id="cq_test",
        )
        code = run_execute(args)
        assert code == 0
        mock_flow.assert_called_once_with(
            action="approve",
            item_id="abcd1234",
            telegram_chat_id=123456,
            telegram_message_id=789,
            telegram_callback_query_id="cq_test",
        )


def test_run_health_dispatch() -> None:
    with patch("agent.orchestration.health_check_flow.run_health_check_flow") as mock_flow:
        mock_flow.return_value = {"is_healthy": True}
        args = argparse.Namespace(repo_root=None)
        code = run_health(args)
        assert code == 0
        mock_flow.assert_called_once_with(repo_root=None)


def test_run_poll_dispatch() -> None:
    with patch("agent.orchestration.poll_flow.run_poll_flow") as mock_flow:
        mock_flow.return_value = [{"action": "approve"}]
        args = argparse.Namespace(timeout=15, once=True, repo_root=None)
        code = run_poll(args)
        assert code == 0
        mock_flow.assert_called_once_with(repo_root=None, timeout_seconds=15)


def test_run_ideate_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        telegram_authorized_chat_id=123456789,
        nvidia_nim_api_key="nvapi-valid",
    )
    monkeypatch.setattr("agent.cli.load_settings", lambda: settings)

    with patch("agent.orchestration.ideation_flow.run_ideation_flow") as mock_flow:
        mock_flow.return_value = {"status": "completed", "pending_items": []}
        args = argparse.Namespace(dry_run=True, repo_root=None)
        code = run_ideate(args)
        assert code == 0
        mock_flow.assert_called_once()


# =============================================================================
# 6. Main Entrypoint Dispatch Tests
# =============================================================================


def test_main_doctor_dispatch() -> None:
    with (
        patch("agent.cli.run_doctor", return_value=0) as mock_doc,
        pytest.raises(SystemExit) as exc,
    ):
        main(["doctor"])
    assert exc.value.code == 0
    mock_doc.assert_called_once()


def test_main_setup_dispatch() -> None:
    with patch("agent.cli.run_setup") as mock_set, pytest.raises(SystemExit) as exc:
        main(["setup", "--env-file", ".env.custom"])
    assert exc.value.code == 0
    mock_set.assert_called_once_with(env_path=Path(".env.custom"))


def test_main_poll_dispatch() -> None:
    with patch("agent.cli.run_poll", return_value=0) as mock_poll, pytest.raises(SystemExit) as exc:
        main(["poll", "--once"])
    assert exc.value.code == 0
    mock_poll.assert_called_once()


def test_main_ideate_dispatch() -> None:
    with (
        patch("agent.cli.run_ideate", return_value=0) as mock_ideate,
        pytest.raises(SystemExit) as exc,
    ):
        main(["ideate", "--dry-run"])
    assert exc.value.code == 0
    mock_ideate.assert_called_once()
