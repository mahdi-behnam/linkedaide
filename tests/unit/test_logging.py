"""Unit tests for centralized logging setup."""

from __future__ import annotations

import logging
from pathlib import Path

from agent.logging import setup_logging


def test_setup_logging_creates_file_handler(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    setup_logging(
        log_level="DEBUG",
        log_dir=log_dir,
        log_filename="test_agent.log",
        disable_file_logging=False,
    )

    test_logger = logging.getLogger("test_logger")
    test_logger.info("Hello test log file")

    log_file = log_dir / "test_agent.log"
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "Hello test log file" in content


def test_setup_logging_suppresses_file_under_pytest() -> None:
    # Under pytest with default log_dir=None, file handler should not be created
    setup_logging(log_level="INFO")
    root_logger = logging.getLogger()
    debug_handlers = [
        h
        for h in root_logger.handlers
        if isinstance(h, logging.FileHandler) and "debug" in getattr(h, "baseFilename", "")
    ]
    # No file handler targeting default debug/logs/agent.log should be added
    assert len(debug_handlers) == 0
