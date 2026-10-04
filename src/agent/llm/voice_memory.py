"""Persona Voice Vector Memory and Dynamic Few-Shot Retrieval.

Architecture Invariants:
- Loads operator profile, style guide, and writing samples from persona/ directory.
- Falls back safely to deterministic defaults if files are absent or unreadable.
- Retrieves top-k authentic writing samples using semantic embeddings or normalized token similarity.
- Formats operator persona, style constraints, and few-shot examples for prompt injection.
- Indexes executed comments into memory for continuous few-shot learning.
"""

from __future__ import annotations

import json
import logging
import math
import re
from pathlib import Path
from typing import Any

import yaml
from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)

from agent.llm.voice_defaults import (
    DEFAULT_PROFILE,
    DEFAULT_STYLE_GUIDE,
    DEFAULT_WRITING_SAMPLES,
    STOPWORDS,
    cosine_similarity,
    tokenize,
)


class VoiceMemoryStore:
    """Operator Persona Voice Memory Store with dynamic few-shot retrieval."""

    def __init__(
        self,
        persona_dir: Path | str | None = None,
        *,
        embeddings: Embeddings | None = None,
    ) -> None:
        """Initialize VoiceMemoryStore.

        Args:
            persona_dir: Path to the persona directory containing profile.yaml,
                style_guide.md, and writing_samples.json.
            embeddings: Optional LangChain Embeddings provider for dense semantic similarity.
        """
        self._persona_dir = self._resolve_persona_dir(persona_dir)
        self._embeddings = embeddings

        self._profile: dict[str, Any] = DEFAULT_PROFILE.copy()
        self._style_guide: str = DEFAULT_STYLE_GUIDE
        self._base_writing_samples: list[dict[str, Any]] = [
            s.copy() for s in DEFAULT_WRITING_SAMPLES
        ]
        self._dynamic_samples: list[dict[str, Any]] = []

        self._sample_embeddings: list[list[float]] | None = None

        self._load_persona_corpus()

    @property
    def profile(self) -> dict[str, Any]:
        """Operator profile dictionary."""
        return self._profile

    @property
    def style_guide(self) -> str:
        """Operator style guide content."""
        return self._style_guide

    @property
    def writing_samples(self) -> list[dict[str, Any]]:
        """All writing samples combining base corpus and dynamically indexed samples."""
        return self._base_writing_samples + self._dynamic_samples

    def _resolve_persona_dir(self, persona_dir: Path | str | None) -> Path | None:
        """Resolve the path to the persona directory."""
        if persona_dir is not None:
            p = Path(persona_dir).resolve()
            return p

        # Check working directory
        cwd_persona = Path.cwd() / "persona"
        if cwd_persona.is_dir():
            return cwd_persona

        # Check repository root walking up from this file
        current = Path(__file__).resolve().parent
        for parent in [current, *current.parents]:
            candidate = parent / "persona"
            if candidate.is_dir():
                return candidate
            if (parent / "pyproject.toml").is_file():
                candidate = parent / "persona"
                return candidate

        return None

    def _load_persona_corpus(self) -> None:
        """Load operator profile, style guide, and writing samples from disk."""
        if not self._persona_dir or not self._persona_dir.exists():
            logger.info("Persona directory not found or unreadable; using built-in safe defaults.")
            self._init_embeddings_cache()
            return

        # 1. Load profile.yaml
        profile_path = self._persona_dir / "profile.yaml"
        if profile_path.is_file():
            try:
                with profile_path.open("r", encoding="utf-8") as f:
                    loaded = yaml.safe_load(f)
                    if isinstance(loaded, dict) and loaded:
                        self._profile = loaded
                        logger.debug("Loaded operator profile from %s", profile_path)
            except Exception as e:
                logger.warning(
                    "Failed to load profile.yaml from %s: %s; using default.", profile_path, e
                )

        # 2. Load style_guide.md
        style_path = self._persona_dir / "style_guide.md"
        if style_path.is_file():
            try:
                with style_path.open("r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        self._style_guide = content
                        logger.debug("Loaded operator style guide from %s", style_path)
            except Exception as e:
                logger.warning(
                    "Failed to load style_guide.md from %s: %s; using default.", style_path, e
                )

        # 3. Load writing_samples.json
        samples_path = self._persona_dir / "writing_samples.json"
        if samples_path.is_file():
            try:
                with samples_path.open("r", encoding="utf-8") as f:
                    loaded_samples = json.load(f)
                    if isinstance(loaded_samples, list) and loaded_samples:
                        self._base_writing_samples = loaded_samples
                        logger.debug(
                            "Loaded %d writing samples from %s", len(loaded_samples), samples_path
                        )
            except Exception as e:
                logger.warning(
                    "Failed to load writing_samples.json from %s: %s; using default.",
                    samples_path,
                    e,
                )

        self._init_embeddings_cache()

    def _init_embeddings_cache(self) -> None:
        """Pre-compute embeddings for writing samples if dense embeddings are configured."""
        if self._embeddings is None:
            self._sample_embeddings = None
            return

        texts: list[str] = [
            f"{s.get('topic', '')} {' '.join(s.get('tags', []))} {s.get('sample', '')}"
            for s in self.writing_samples
        ]
        try:
            self._sample_embeddings = self._embeddings.embed_documents(texts)
        except Exception as e:
            logger.warning(
                "Dense embeddings initialization failed: %s; falling back to token similarity.", e
            )
            self._sample_embeddings = None

    def retrieve_samples(self, query: str, top_k: int = 2) -> list[dict[str, Any]]:
        """Retrieve the top-k most relevant writing samples for a given query/post topic.

        Args:
            query: The post text, topic, or query string.
            top_k: Number of samples to retrieve (default: 2).

        Returns:
            List of top-k writing sample dictionaries.
        """
        all_samples = self.writing_samples
        if not all_samples:
            return []

        if top_k <= 0:
            return []

        # 1. If dense embeddings are available and initialized, use cosine similarity
        if self._embeddings is not None and self._sample_embeddings is not None:
            try:
                query_emb = self._embeddings.embed_query(query)
                scored = [
                    (cosine_similarity(query_emb, emb), s)
                    for emb, s in zip(self._sample_embeddings, all_samples, strict=False)
                ]
                scored.sort(key=lambda x: x[0], reverse=True)
                return [s for _, s in scored[:top_k]]
            except Exception as e:
                logger.warning("Dense embedding retrieval failed: %s; using token similarity.", e)

        # 2. Normalized token similarity matching
        query_tokens = tokenize(query)
        if not query_tokens:
            return all_samples[:top_k]

        # Calculate document frequency for IDF weighting across corpus
        doc_count = len(all_samples)
        token_doc_counts: dict[str, int] = {}
        for s in all_samples:
            sample_text = (
                f"{s.get('topic', '')} {' '.join(s.get('tags', []))} "
                f"{s.get('context', '')} {s.get('sample', '')}"
            )
            unique_sample_tokens = set(tokenize(sample_text))
            for t in unique_sample_tokens:
                token_doc_counts[t] = token_doc_counts.get(t, 0) + 1

        def idf(token: str) -> float:
            df = token_doc_counts.get(token, 0)
            return math.log(1.0 + (doc_count - df + 0.5) / (df + 0.5))

        scored_samples: list[tuple[float, dict[str, Any]]] = []
        for s in all_samples:
            topic_tokens = set(tokenize(s.get("topic", "")))
            tags_tokens = {t.lower() for t in s.get("tags", [])}
            context_tokens = set(tokenize(s.get("context", "")))
            body_tokens = set(tokenize(s.get("sample", "")))

            score = 0.0
            for q in query_tokens:
                term_idf = idf(q)
                if q in tags_tokens:
                    score += 5.0 * term_idf
                if q in topic_tokens:
                    score += 3.0 * term_idf
                if q in context_tokens:
                    score += 2.0 * term_idf
                if q in body_tokens:
                    score += 1.0 * term_idf

            scored_samples.append((score, s))

        # Sort descending by score
        scored_samples.sort(key=lambda x: x[0], reverse=True)

        # If highest score > 0, return top-k matches
        if scored_samples[0][0] > 0.0:
            return [s for _, s in scored_samples[:top_k]]

        # Otherwise fallback to top default samples
        return all_samples[:top_k]

    def format_operator_bio(self) -> str:
        """Format the operator bio, domains, and stances into a structured block."""
        name = self._profile.get("name", "Principal Software Engineer")
        role = self._profile.get("role", "Principal Software Engineer")
        bio = self._profile.get("bio", "")
        core_domains = self._profile.get("core_domains", [])
        stances = self._profile.get("contrarian_engineering_stances", [])
        opinions = self._profile.get("non_negotiable_opinions", [])

        lines: list[str] = [
            f"Operator: {name}",
            f"Role: {role}",
        ]
        if bio:
            lines.append(f"Bio: {bio}")
        if core_domains:
            domains_str = (
                ", ".join(core_domains) if isinstance(core_domains, list) else str(core_domains)
            )
            lines.append(f"Core Domains: {domains_str}")
        if stances and isinstance(stances, list):
            lines.append("Contrarian Engineering Stances:")
            for stance in stances:
                lines.append(f"- {stance}")
        if opinions and isinstance(opinions, list):
            lines.append("Non-Negotiable Opinions:")
            for opinion in opinions:
                lines.append(f"- {opinion}")

        return "\n".join(lines)

    def format_few_shot_examples(self, samples: list[dict[str, Any]]) -> str:
        """Format writing samples into a clean few-shot demonstrations block."""
        if not samples:
            return "No specific few-shot examples available."

        formatted_blocks: list[str] = []
        for idx, sample in enumerate(samples, 1):
            topic = sample.get("topic", "Technical insight")
            context = sample.get("context", "")
            comment = sample.get("sample", "")

            block_lines: list[str] = [
                f"### Example {idx} (Topic: {topic})",
            ]
            if context:
                block_lines.append(f"Context: {context}")
            block_lines.append(f'Approved Comment:\n"{comment}"')
            formatted_blocks.append("\n".join(block_lines))

        return "\n\n".join(formatted_blocks)

    def get_voice_context(self, post_text: str, top_k: int = 2) -> dict[str, Any]:
        """Retrieve voice context including operator bio, style guidelines, and dynamic few-shot examples.

        Args:
            post_text: The LinkedIn post text or topic to ground the retrieval.
            top_k: Number of writing samples to retrieve (default: 2).

        Returns:
            Dictionary with keys 'operator_bio', 'style_guidelines', and 'few_shot_examples'.
        """
        relevant_samples = self.retrieve_samples(post_text, top_k=top_k)

        return {
            "operator_bio": self.format_operator_bio(),
            "style_guidelines": self._style_guide.strip(),
            "few_shot_examples": self.format_few_shot_examples(relevant_samples),
        }

    def index_executed_comment(
        self,
        item_id: str,
        comment_text: str,
        post_excerpt: str = "",
    ) -> None:
        """Append an operator-approved comment from execution history into voice memory.

        Enables continuous few-shot learning by making past approved comments searchable.

        Args:
            item_id: Unique action or history item ID.
            comment_text: Approved comment text.
            post_excerpt: Optional excerpt or topic of the post commented on.
        """
        cleaned_text = comment_text.strip()
        if not cleaned_text:
            return

        new_entry: dict[str, Any] = {
            "id": f"executed-{item_id}",
            "topic": post_excerpt[:120].strip() if post_excerpt else "Executed technical comment",
            "tags": ["executed-history", "approved"],
            "context": post_excerpt.strip(),
            "sample": cleaned_text,
            "source": "history",
        }
        self._dynamic_samples.append(new_entry)

        # Update dense embeddings cache if present
        if self._embeddings is not None and self._sample_embeddings is not None:
            try:
                emb_text = f"{new_entry['topic']} executed-history {cleaned_text}"
                emb = self._embeddings.embed_documents([emb_text])[0]
                self._sample_embeddings.append(emb)
            except Exception as e:
                logger.warning("Failed to embed newly indexed executed comment: %s", e)


__all__ = [
    "DEFAULT_PROFILE",
    "DEFAULT_STYLE_GUIDE",
    "DEFAULT_WRITING_SAMPLES",
    "STOPWORDS",
    "VoiceMemoryStore",
    "cosine_similarity",
    "tokenize",
]
