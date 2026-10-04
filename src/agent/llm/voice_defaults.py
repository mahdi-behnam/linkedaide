"""Default persona settings, style guides, writing samples, and lexical similarity utilities."""

from __future__ import annotations

import math
import re
from typing import Any

STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "about",
        "above",
        "after",
        "again",
        "against",
        "all",
        "am",
        "an",
        "and",
        "any",
        "are",
        "aren",
        "as",
        "at",
        "be",
        "because",
        "been",
        "before",
        "being",
        "below",
        "between",
        "both",
        "but",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "doing",
        "down",
        "during",
        "each",
        "few",
        "for",
        "from",
        "further",
        "had",
        "has",
        "have",
        "having",
        "he",
        "her",
        "here",
        "hers",
        "herself",
        "him",
        "himself",
        "his",
        "how",
        "i",
        "if",
        "in",
        "into",
        "is",
        "isn",
        "it",
        "its",
        "itself",
        "just",
        "me",
        "more",
        "most",
        "my",
        "myself",
        "no",
        "nor",
        "not",
        "now",
        "of",
        "off",
        "on",
        "once",
        "only",
        "or",
        "other",
        "our",
        "ours",
        "ourselves",
        "out",
        "over",
        "own",
        "s",
        "same",
        "she",
        "should",
        "so",
        "some",
        "such",
        "t",
        "than",
        "that",
        "the",
        "their",
        "theirs",
        "them",
        "themselves",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "through",
        "to",
        "too",
        "under",
        "until",
        "up",
        "very",
        "was",
        "wasn",
        "we",
        "were",
        "weren",
        "what",
        "when",
        "where",
        "which",
        "while",
        "who",
        "whom",
        "why",
        "will",
        "with",
        "you",
        "your",
        "yours",
        "yourself",
        "yourselves",
    }
)

DEFAULT_PROFILE: dict[str, Any] = {
    "name": "Principal Software Engineer",
    "role": "Principal Software Engineer & Distributed Systems Architect",
    "bio": (
        "Principal Software Engineer specializing in enterprise AI architectures, "
        "deterministic distributed systems, high-throughput state machines, and human-in-the-loop workflows."
    ),
    "core_domains": [
        "enterprise AI",
        "distributed systems",
        "determinism & reliability engineering",
        "state stores & persistent memory",
        "human-in-the-loop agentic workflows",
    ],
    "contrarian_engineering_stances": [
        "Autonomous ReAct loops without human boundaries are dangerous toy architectures for production.",
        "Deterministic state machines and durable event logs always beat opaque prompt-chained agent memory in production systems.",
        "LLMs should never own safety or access policy; deterministic code and gatekeepers must strictly enforce system invariants.",
    ],
    "non_negotiable_opinions": [
        "Never execute autonomous writes to production external APIs without an explicit human authorization boundary.",
        "Fail-closed safety defaults are mandatory across all agentic execution paths.",
        "No generic praise or superficial influencer platitudes in technical discourse.",
    ],
}

DEFAULT_STYLE_GUIDE: str = """# Persona Style Guide & Voice Constraints

## Voice & Demeanor
- Principal Software Engineer & Distributed AI Architect.
- Authoritative, collegial, intellectually curious, incisive, and pragmatic.

## Core Tone Rules
1. Technical Depth Over Generalities: Reference concrete architectural primitives, failure modes, and trade-offs.
2. Zero Fluff: Never open with generic praise (e.g., 'Great post', '100% agree'). Start immediately with technical insight.
3. Direct, Punchy Sentences: High information density, active declarative prose, no corporate buzzwords.
4. Realistic Trade-Off Analysis: Balance critique with concrete production realities and operational costs.
"""

DEFAULT_WRITING_SAMPLES: list[dict[str, Any]] = [
    {
        "id": "def-01",
        "topic": "distributed systems and consensus",
        "tags": ["distributed-systems", "consensus", "raft", "paxos"],
        "context": "Discussion on distributed consensus complexity and Raft vs Paxos in production databases.",
        "sample": (
            "Raft is easier to reason about on paper, but the operational edge cases around joint consensus "
            "and leader heartbeats under network partitions are where teams get burned. In production, leader "
            "lease renewals with monotonic clocks save you from split-brain scenarios far more reliably than "
            "trusting NTP sync across nodes."
        ),
    },
    {
        "id": "def-02",
        "topic": "agentic workflows and human-in-the-loop",
        "tags": ["agentic-workflows", "hitl", "safety", "ai-agents"],
        "context": "Debate regarding fully autonomous AI agents performing production actions versus human-in-the-loop boundaries.",
        "sample": (
            "Autonomous ReAct loops executing external side effects without an approval gate are an operational "
            "nightmare waiting to happen. The sweet spot is asynchronous human-in-the-loop: let the agent draft "
            "and triage at scale, but keep deterministic code enforcing rate limits, circuit breakers, and interactive "
            "human sign-off before hitting third-party APIs."
        ),
    },
    {
        "id": "def-03",
        "topic": "vector memory and hybrid search",
        "tags": ["vector-search", "rag", "embeddings", "retrieval"],
        "context": "Evaluating whether vector search alone is sufficient for enterprise RAG and memory retrieval.",
        "sample": (
            "Dense embeddings excel at broad topical recall, but pure cosine similarity fails miserably on exact "
            "identifiers, temporal recency, and domain-specific acronyms. Hybrid retrieval pairing BM25 lexical search "
            "with dense vectors and metadata pre-filtering consistently cuts hallucinations by 40% in enterprise corpora."
        ),
    },
]


def tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase alphanumeric tokens excluding common stopwords."""
    words = re.findall(r"[a-zA-Z0-9_\-]+", text.lower())
    return [w for w in words if len(w) > 1 and w not in STOPWORDS]


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two numeric vectors."""
    if len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=True))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
