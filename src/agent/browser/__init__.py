"""Browser automation package for LinkedIn scraping and execution."""

from agent.browser.biometrics import BiometricController
from agent.browser.executor import ActionExecutor
from agent.browser.scraper import FeedScraper
from agent.browser.session import decrypt_storage_state, encrypt_storage_state
from agent.browser.session_keeper import refresh_and_persist_session
from agent.browser.stealth import (
    detect_challenge_page,
    humanized_scroll,
    humanized_type,
    new_stealth_context,
)
from agent.browser.telemetry import capture_dom_telemetry, sanitize_dom_tree

__all__ = [
    "ActionExecutor",
    "BiometricController",
    "FeedScraper",
    "capture_dom_telemetry",
    "sanitize_dom_tree",
    "decrypt_storage_state",
    "encrypt_storage_state",
    "detect_challenge_page",
    "humanized_scroll",
    "humanized_type",
    "new_stealth_context",
    "refresh_and_persist_session",
]

