"""Persistent docked ReplyKeyboardMarkup builders for operator navigation.

Architecture Invariants:
- Zero-typing mobile navigation: High-frequency operational actions accessible via persistent dock.
- Non-interfering: Uses Telegram's resize_keyboard=True and is_persistent=True.
- Fail-safe: Plain text commands remain 100% supported alongside docked buttons.
"""

from __future__ import annotations

from typing import Any

# Standard emoji button labels for the persistent bottom dock
DOCK_LABEL_STATUS = "📊 Status"
DOCK_LABEL_PENDING = "📋 Pending Queue"
DOCK_LABEL_STATS = "📈 Stats"
DOCK_LABEL_PAUSE = "⏸️ Pause"
DOCK_LABEL_RESUME = "▶️ Resume"
DOCK_LABEL_HOME = "🏠 Home Menu"
DOCK_LABEL_HELP = "❓ Help"

# Mapping from button text to command name
DOCK_BUTTON_COMMAND_MAP: dict[str, str] = {
    DOCK_LABEL_STATUS: "status",
    DOCK_LABEL_PENDING: "pending",
    DOCK_LABEL_STATS: "stats",
    DOCK_LABEL_PAUSE: "pause",
    DOCK_LABEL_RESUME: "resume",
    DOCK_LABEL_HOME: "home",
    DOCK_LABEL_HELP: "help",
    "🏠 Home": "home",
    "⏸️ Pause / Resume": "pause",
}


def build_docked_reply_keyboard(
    is_paused: bool = False,
    input_placeholder: str | None = "Tap a button or type /help...",
) -> dict[str, Any]:
    """Construct persistent reply keyboard markup for mobile C2 navigation.

    Args:
        is_paused: Current paused state of the agent to toggle Pause / Resume button.
        input_placeholder: Optional placeholder text for chat input field (max 64 chars).

    Returns:
        dict[str, Any]: Telegram ReplyKeyboardMarkup dictionary.
    """
    pause_button_text = DOCK_LABEL_RESUME if is_paused else DOCK_LABEL_PAUSE
    markup: dict[str, Any] = {
        "keyboard": [
            [{"text": DOCK_LABEL_STATUS}, {"text": DOCK_LABEL_PENDING}],
            [{"text": pause_button_text}, {"text": DOCK_LABEL_STATS}],
            [{"text": DOCK_LABEL_HOME}, {"text": DOCK_LABEL_HELP}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }
    if input_placeholder:
        markup["input_field_placeholder"] = input_placeholder[:64]
    return markup
