"""URL utilities and hashtag mapping for LinkedIn scraping."""

from __future__ import annotations

import urllib.parse


def clean_hashtag(hashtag: str) -> str:
    """Strip leading '#' and whitespace, validating non-empty."""
    clean = hashtag.strip().lstrip("#").strip()
    if not clean or set(clean).issubset({"#", " "}):
        raise ValueError(f"Invalid empty hashtag: {hashtag!r}")
    return clean


def hashtag_to_feed_url(hashtag: str) -> str:
    """Convert a hashtag or keyword into a LinkedIn hashtag feed URL.

    Handles leading '#', leading/trailing whitespace, full URLs, and URL encoding.

    Examples:
        'python' -> 'https://www.linkedin.com/feed/hashtag/?keywords=python'
        '#Python' -> 'https://www.linkedin.com/feed/hashtag/?keywords=python'
        '#ai_agents' -> 'https://www.linkedin.com/feed/hashtag/?keywords=ai_agents'
        'https://www.linkedin.com/feed/hashtag/?keywords=custom' -> 'https://www.linkedin.com/feed/hashtag/?keywords=custom'

    Raises:
        ValueError: If hashtag is empty or contains only whitespace/hashes.
    """
    clean = hashtag.strip()
    if clean.lower().startswith(("http://", "https://")):
        return clean
    clean = clean.lstrip("#").strip()
    if not clean or set(clean).issubset({"#", " "}):
        raise ValueError(f"Invalid empty hashtag: {hashtag!r}")
    encoded = urllib.parse.quote_plus(clean.lower())
    return f"https://www.linkedin.com/feed/hashtag/?keywords={encoded}"
