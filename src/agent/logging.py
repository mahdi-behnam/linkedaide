"""Centralized logging configuration supporting console and persistent file output."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path


def is_running_under_pytest() -> bool:
    """Return True if execution is running inside a pytest test session."""
    return "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ


def setup_logging(
    log_level: str = "INFO",
    log_dir: Path | None = None,
    log_filename: str = "agent.log",
    disable_file_logging: bool | None = None,
) -> None:
    """Configure unified logging to both stdout and a persistent log file in debug/logs/.

    Args:
        log_level: Log level string ('DEBUG', 'INFO', 'WARNING', 'ERROR').
        log_dir: Directory where log files are stored (default: debug/logs).
        log_filename: Name of the log file (default: agent.log).
        disable_file_logging: Explicitly enable/disable file logging. If None, file logging is
            automatically disabled when running under test runners (pytest).
    """
    level = getattr(logging, log_level.upper(), logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Determine if file logging should be active
    should_log_to_file = True
    if disable_file_logging is not None:
        should_log_to_file = not disable_file_logging
    elif is_running_under_pytest() and log_dir is None:
        # Default behavior under pytest: disable disk log writes unless a specific log_dir is passed
        should_log_to_file = False

    if should_log_to_file:
        target_dir = Path(log_dir or "debug/logs").resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        log_file_path = target_dir / log_filename

        # Configure FileHandler if not already present
        has_file_handler = any(
            isinstance(h, logging.FileHandler)
            and getattr(h, "baseFilename", None) == str(log_file_path)
            for h in root_logger.handlers
        )
        if not has_file_handler:
            file_handler = logging.FileHandler(str(log_file_path), encoding="utf-8", mode="a")
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

    # Configure StreamHandler for console output if not already present
    has_stream_handler = any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        for h in root_logger.handlers
    )
    if not has_stream_handler:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(level)
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)
