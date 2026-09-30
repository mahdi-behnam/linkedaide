"""Deterministic anti-cliché guardrails and stylometric limits.

Architecture Invariants:
- Deterministic safety enforcement: strictly rule-based, no LLM in the loop for scanning.
- Detects banned AI openers, banned buzzwords, sycophantic praise, and stylometric limits.
- Supports deterministic sanitization as clean fallback.
"""

from __future__ import annotations

import re
from typing import ClassVar

from pydantic import BaseModel, Field

# Banned AI openers regex patterns (case-insensitive)
BANNED_OPENER_PATTERNS: tuple[str, ...] = (
    r"^(in\s+today['\u2019]?s\s+(fast-paced|rapidly\s+evolving|modern)\s+(world|landscape|tech))",
    r"^(great\s+(post|read|share|article|insights?)|kudos|spot\s+on|100%\s+this|couldn['\u2019]?t\s+agree\s+more)",
    r"^(fascinating\s+(read|perspective|take)|love\s+this|thanks\s+for\s+sharing)",
    r"^(this\s+is\s+a\s+(game[\s-]changer|must[\s-]read))",
)

# Banned AI buzzwords set (case-insensitive)
BANNED_BUZZWORDS: frozenset[str] = frozenset(
    {
        "delve",
        "game changer",
        "game-changer",
        "tapestry",
        "beacon",
        "testament",
        "paradigm shift",
        "supercharge",
        "harness the power",
        "holistic approach",
        "synergies",
        "in conclusion",
        "furthermore",
        "moreover",
        "it's important to remember",
        "vital role",
        "pivotal",
        "groundbreaking",
        "pleasure to read",
    }
)

# Individual compiled regexes for buzzwords with word boundaries
BUZZWORD_REGEX_MAP: dict[str, re.Pattern[str]] = {
    "delve": re.compile(r"\bdelv(?:e|es|ed|ing)\b", re.IGNORECASE),
    "game changer": re.compile(r"\bgame\s+changer\b", re.IGNORECASE),
    "game-changer": re.compile(r"\bgame-changer\b", re.IGNORECASE),
    "tapestry": re.compile(r"\btapestr(?:y|ies)\b", re.IGNORECASE),
    "beacon": re.compile(r"\bbeacons?\b", re.IGNORECASE),
    "testament": re.compile(r"\btestaments?\b", re.IGNORECASE),
    "paradigm shift": re.compile(r"\bparadigm[\s-]shifts?\b", re.IGNORECASE),
    "supercharge": re.compile(r"\bsupercharg(?:e|es|ed|ing)\b", re.IGNORECASE),
    "harness the power": re.compile(r"\bharness(?:ing)?\s+the\s+power\b", re.IGNORECASE),
    "holistic approach": re.compile(r"\bholistic\s+approach(?:es)?\b", re.IGNORECASE),
    "synergies": re.compile(r"\bsynerg(?:y|ies)\b", re.IGNORECASE),
    "in conclusion": re.compile(r"\bin\s+conclusion\b", re.IGNORECASE),
    "furthermore": re.compile(r"\bfurthermore\b", re.IGNORECASE),
    "moreover": re.compile(r"\bmoreover\b", re.IGNORECASE),
    "it's important to remember": re.compile(
        r"\bit['\u2019]?s\s+important\s+to\s+remember\b|\bit\s+is\s+important\s+to\s+remember\b",
        re.IGNORECASE,
    ),
    "vital role": re.compile(r"\bvital\s+roles?\b", re.IGNORECASE),
    "pivotal": re.compile(r"\bpivotal\b", re.IGNORECASE),
    "groundbreaking": re.compile(r"\bground[\s-]?breaking\b", re.IGNORECASE),
    "pleasure to read": re.compile(r"\bpleasure\s+to\s+read\b", re.IGNORECASE),
}

# Buzzword replacement mapping for deterministic sanitization
BUZZWORD_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bdelv(?:e|es|ed|ing)\s+into\b", re.IGNORECASE), "examine"),
    (re.compile(r"\bdelv(?:e|es|ed|ing)\b", re.IGNORECASE), "explore"),
    (re.compile(r"\bgame[\s-]changer\b", re.IGNORECASE), "significant advancement"),
    (re.compile(r"\btapestr(?:y|ies)\b", re.IGNORECASE), "framework"),
    (re.compile(r"\bbeacons?\b", re.IGNORECASE), "standard"),
    (re.compile(r"\btestaments?\b", re.IGNORECASE), "evidence"),
    (re.compile(r"\bparadigm[\s-]shifts?\b", re.IGNORECASE), "major shift"),
    (re.compile(r"\bsupercharg(?:e|es|ed|ing)\b", re.IGNORECASE), "accelerate"),
    (re.compile(r"\bharness(?:ing)?\s+the\s+power\s+of\b", re.IGNORECASE), "leverage"),
    (re.compile(r"\bharness(?:ing)?\s+the\s+power\b", re.IGNORECASE), "leverage"),
    (re.compile(r"\bholistic\s+approach(?:es)?\b", re.IGNORECASE), "comprehensive approach"),
    (re.compile(r"\bsynerg(?:y|ies)\b", re.IGNORECASE), "efficiencies"),
    (re.compile(r"\bin\s+conclusion\b,?", re.IGNORECASE), ""),
    (re.compile(r"\bfurthermore\b,?", re.IGNORECASE), ""),
    (re.compile(r"\bmoreover\b,?", re.IGNORECASE), ""),
    (
        re.compile(
            r"\bit['\u2019]?s\s+important\s+to\s+remember(?:\s+that)?\b",
            re.IGNORECASE,
        ),
        "note that",
    ),
    (
        re.compile(
            r"\bit\s+is\s+important\s+to\s+remember(?:\s+that)?\b",
            re.IGNORECASE,
        ),
        "note that",
    ),
    (re.compile(r"\bvital\s+roles?\b", re.IGNORECASE), "key role"),
    (re.compile(r"\bpivotal\b", re.IGNORECASE), "critical"),
    (re.compile(r"\bground[\s-]?breaking\b", re.IGNORECASE), "notable"),
    (re.compile(r"\bpleasure\s+to\s+read\b", re.IGNORECASE), ""),
)

# Regex matching emojis (including grapheme clusters with ZWJ and modifiers)
EMOJI_REGEX: re.Pattern[str] = re.compile(
    r"(?:"
    r"[\U0001F600-\U0001F64F]"
    r"|[\U0001F300-\U0001F5FF]"
    r"|[\U0001F680-\U0001F6FF]"
    r"|[\U0001F1E0-\U0001F1FF]"
    r"|[\U0001F900-\U0001F9FF]"
    r"|[\U0001FA00-\U0001FAFF]"
    r"|[\U00002700-\U000027BF]"
    r"|[\U00002600-\U000026FF]"
    r"|[\U00002300-\U000023FF]"
    r"|[\U00002B50]"
    r")"
    r"(?:[\U0001F3FB-\U0001F3FF]|\uFE0F)?"
    r"(?:\u200D"
    r"(?:[\U0001F600-\U0001F64F]|[\U0001F300-\U0001F5FF]|[\U0001F680-\U0001F6FF]|"
    r"[\U0001F900-\U0001F9FF]|[\U0001FA00-\U0001FAFF]|[\U00002700-\U000027BF]|"
    r"[\U00002600-\U000026FF]|[\U00002300-\U000023FF])"
    r"(?:[\U0001F3FB-\U0001F3FF]|\uFE0F)?)*"
)

# Patterns detecting pure uncritical sycophantic praise or agreement
SYCOPHANTIC_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"^(?:i\s+)?(?:completely|totally|strongly|wholeheartedly|couldn['\u2019]?t|could\s+not)\s+agree\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:this\s+is\s+)?(?:so\s+true|spot\s+on|100%\s+(?:this|true|accurate|agree)|so\s+well\s+said|brilliantly\s+said|so\s+accurate)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:well\s+said|nailed\s+it|you\s+nailed\s+it|couldn['\u2019]?t\s+have\s+said\s+it\s+better)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:great|awesome|excellent|fantastic|wonderful|brilliant|insightful)\s+(?:post|read|share|article|insights?|take|perspective|write-?up)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:love|loved)\s+this(?:\s+(?:post|read|take|perspective|insights?))?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:thanks|thank\s+you)\s+for\s+(?:sharing|posting|this)\b",
        re.IGNORECASE,
    ),
    re.compile(r"^kudos\b", re.IGNORECASE),
    re.compile(
        r"^(?:such\s+an?\s+)?(?:insightful|great|valuable|inspiring|fantastic)\s+(?:post|read|share|perspective|reminder)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:agree|agreed)(?:[!.,;]|\s+100%|\s+with\s+this|\s+with\s+you)?$",
        re.IGNORECASE,
    ),
)


class ScanResult(BaseModel):
    """Result of an anti-cliché safety scan."""

    passed: bool = Field(description="Whether the text passed all anti-cliché guardrails")
    violations: list[str] = Field(
        default_factory=list,
        description="List of detected anti-cliché and stylometric violations",
    )
    cleaned_text: str | None = Field(
        default=None,
        description="Deterministically cleaned text if salvageable, or None if unsalvageable",
    )


class AntiClicheScanner:
    """Deterministic anti-cliché scanner for LinkedIn comments."""

    MAX_EMOJIS: ClassVar[int] = 1
    MAX_EXCLAMATIONS: ClassVar[int] = 1

    def __init__(
        self,
        *,
        banned_openers: tuple[str, ...] | list[str] = BANNED_OPENER_PATTERNS,
        banned_buzzwords: frozenset[str] | set[str] = BANNED_BUZZWORDS,
        max_emojis: int = MAX_EMOJIS,
        max_exclamations: int = MAX_EXCLAMATIONS,
    ) -> None:
        self._raw_openers = tuple(banned_openers)
        self._compiled_openers = [
            re.compile(pattern, re.IGNORECASE) for pattern in self._raw_openers
        ]
        self._banned_buzzwords = frozenset(banned_buzzwords)
        self._max_emojis = max_emojis
        self._max_exclamations = max_exclamations

    def scan(self, text: str) -> ScanResult:
        """Scan comment text for banned openers, buzzwords, sycophancy, and stylometric limits.

        Args:
            text: Raw or drafted comment text.

        Returns:
            ScanResult containing passed status, violations list, and cleaned text candidate.
        """
        violations: list[str] = []
        raw_text = text.strip() if text else ""
        if not raw_text:
            return ScanResult(
                passed=False,
                violations=["Comment text is empty or contains only whitespace."],
                cleaned_text=None,
            )

        # 1. Banned AI openers check
        stripped_target = re.sub(r"^[\"'\u201c\u201d\u2018\u2019*#_>\s]+", "", raw_text)
        for pattern, compiled in zip(self._raw_openers, self._compiled_openers, strict=False):
            match = compiled.search(stripped_target)
            if match:
                matched_snippet = match.group(0).strip()
                violations.append(
                    f"Banned AI opener detected: '{matched_snippet}' (matches pattern: {pattern})"
                )

        # 2. Sycophantic first sentence check
        first_sentence = self._extract_first_sentence(raw_text)
        if self._is_sycophantic(first_sentence):
            violations.append(
                f"Sycophantic first sentence detected (pure praise or agreement without new information): '{first_sentence}'"
            )

        # 3. Banned AI buzzwords set (case-insensitive)
        for buzzword in sorted(self._banned_buzzwords):
            pattern = BUZZWORD_REGEX_MAP.get(buzzword)
            if pattern is None:
                pattern = re.compile(r"\b" + re.escape(buzzword) + r"\b", re.IGNORECASE)
            if pattern.search(raw_text):
                violations.append(f"Banned AI buzzword detected: '{buzzword}'")

        # 4. Stylometric limit: emojis
        emojis_found = EMOJI_REGEX.findall(raw_text)
        if len(emojis_found) > self._max_emojis:
            violations.append(
                f"Emoji limit exceeded: found {len(emojis_found)} emojis (maximum allowed is {self._max_emojis})"
            )

        # 5. Stylometric limit: exclamation marks
        exclamation_count = raw_text.count("!") + raw_text.count("！")
        if exclamation_count > self._max_exclamations:
            violations.append(
                f"Exclamation mark limit exceeded: found {exclamation_count} exclamation marks (maximum allowed is {self._max_exclamations})"
            )

        passed = len(violations) == 0
        cleaned_text = raw_text if passed else self.sanitize(raw_text)

        return ScanResult(
            passed=passed,
            violations=violations,
            cleaned_text=cleaned_text,
        )

    def sanitize(self, text: str) -> str | None:
        """Deterministically sanitize text by stripping banned openers, buzzwords, and excess punctuation.

        Args:
            text: Text to sanitize.

        Returns:
            Sanitized string if substantive content remains, or None if hollow/empty.
        """
        if not text or not text.strip():
            return None

        cleaned = text.strip()

        # 1. Strip leading markdown quotes/headers
        leading_decorations = re.match(r"^[\"'\u201c\u201d\u2018\u2019*#_>\s]+", cleaned)
        prefix_len = len(leading_decorations.group(0)) if leading_decorations else 0
        search_target = cleaned[prefix_len:]

        # 2. Strip banned opener if present
        for compiled in self._compiled_openers:
            m = compiled.search(search_target)
            if m:
                rest = search_target[m.end() :]
                search_target = re.sub(r"^[!?,;:\-\s]+", "", rest)
                break

        # 3. Strip sycophantic first sentence if still present at the beginning
        sycophantic_opener_match = re.match(
            r"^(?:(?:i\s+)?(?:completely|totally|strongly|wholeheartedly|couldn['\u2019]?t|could\s+not)\s+agree|spot\s+on|well\s+said|nailed\s+it|100%\s+this|thanks\s+for\s+sharing|thank\s+you\s+for\s+sharing|love\s+this|kudos)[!.,;\s]+",
            search_target,
            re.IGNORECASE,
        )
        if sycophantic_opener_match:
            search_target = search_target[sycophantic_opener_match.end() :]

        cleaned = search_target.strip()

        # 4. Enforce exclamation mark limit: keep at most 1
        parts = cleaned.split("!")
        if len(parts) > 2:
            cleaned = parts[0] + "!" + ".".join(parts[1:])

        # 5. Enforce emoji limit: keep at most 1
        emoji_matches = list(EMOJI_REGEX.finditer(cleaned))
        if len(emoji_matches) > 1:
            chars: list[str] = []
            last_end = 0
            for idx, match in enumerate(emoji_matches):
                if idx == 0:
                    continue  # Keep the first emoji
                chars.append(cleaned[last_end : match.start()])
                last_end = match.end()
            chars.append(cleaned[last_end:])
            cleaned = "".join(chars)

        # 6. Neutralize / replace buzzwords
        for pat, repl in BUZZWORD_REPLACEMENTS:
            cleaned = pat.sub(repl, cleaned)

        # 7. Normalize whitespace, remove leading orphan punctuation, and capitalize
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        cleaned = re.sub(r"^[!?,;:\-\s]+", "", cleaned).strip()
        if cleaned:
            cleaned = cleaned[0].upper() + cleaned[1:]

        # If no substantive alphanumeric text remains, return None
        if not cleaned or not re.search(r"[a-zA-Z0-9]", cleaned):
            return None

        return cleaned

    @staticmethod
    def _extract_first_sentence(text: str) -> str:
        """Extract the first sentence from a comment string."""
        cleaned = text.strip()
        match = re.search(r"^(.*?[.!?\n])", cleaned)
        if match:
            return match.group(1).strip()
        return cleaned

    @staticmethod
    def _is_sycophantic(sentence: str) -> bool:
        """Check whether a sentence is pure uncritical praise or agreement."""
        s = sentence.strip().rstrip("!.,;").strip()
        for pat in SYCOPHANTIC_PATTERNS:
            if pat.search(s):
                return True
        return False
