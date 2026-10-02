import React from "react";
import {
  Lightning,
  Sparkle,
  Clock,
  CheckCircle,
  PencilSimple,
  IconProps,
} from "../icons";

export interface HookArchetype {
  id: string;
  name: string;
  tagline: string;
  icon: React.ComponentType<IconProps>;
  templates: Record<string, string>;
}

export const HOOK_ARCHETYPES: HookArchetype[] = [
  {
    id: "contrarian",
    name: "Contrarian Stance",
    tagline: "Challenge prevailing industry consensus with conviction",
    icon: Lightning,
    templates: {
      "Agent Architecture":
        "Most engineering teams are building agent workflows completely wrong:\n\nThey rely on autonomous ReAct loops instead of deterministic state machines.",
      "Distributed Systems":
        "Database-backed state stores are often overkill for agent pipelines:\n\nPrivate edge KV namespaces provide sub-40ms latency without commit storms.",
      "AI Safety & Guardrails":
        "Prompt-based safety filters do not work in production:\n\nDeterministic code gates and human verification are the only real safety invariant.",
      "System Design":
        "Microservices for LLM agents introduce unnecessary operational friction:\n\nA compact, typed workflow engine outperforms distributed graphs 10x.",
      General:
        "The prevailing approach to this problem is fundamentally backwards:\n\nHere is why the consensus fails when scaled to production.",
    },
  },
  {
    id: "data_shock",
    name: "Data Shock",
    tagline: "Anchor attention with a surprising, counter-intuitive statistic",
    icon: Sparkle,
    templates: {
      "Agent Architecture":
        "93% of LLM production incidents are not hallucination errors:\n\nThey are state leakage, race conditions, and unverified side effects.",
      "Distributed Systems":
        "Over 80% of automated CI failures in multi-agent repos stem from git merge conflicts in state files.",
      "AI Safety & Guardrails":
        "Only 6% of enterprise AI prototypes survive into production without human approval loops.",
      "System Design":
        "74% of API latency in agentic systems is spent waiting for un-cached model round-trips.",
      General:
        "87% of teams struggle with this specific bottleneck in production:\n\nHere is the exact data breakdown and how we addressed it.",
    },
  },
  {
    id: "micro_story",
    name: "Micro-Story Teardown",
    tagline: "Hook readers with a vivid, high-stakes incident narrative",
    icon: Clock,
    templates: {
      "Agent Architecture":
        "Last Tuesday at 2 AM, our production agent halted mid-execution:\n\nHere is the exact architectural flaw that triggered the incident, and how we resolved it in 15 minutes.",
      "Distributed Systems":
        "We watched our state synchronization deadlock across three regions simultaneously.\n\nThe culprit? A 3-line retry loop with no jitter.",
      "AI Safety & Guardrails":
        "A client almost published an unreviewed autonomous comment to 500k followers.\n\nOur Telegram HITL approval circuit tripped just in time. Here is the postmortem.",
      "System Design":
        "We spent three weeks chasing an intermittent agent bug.\n\nThe root cause was surprisingly simple, and it changed how we design all state stores.",
      General:
        "Three days ago, a small edge case brought down our primary pipeline:\n\nHere is the step-by-step postmortem and the key takeaway.",
    },
  },
  {
    id: "framework",
    name: "Counter-Intuitive Framework",
    tagline: "Introduce a surprising mental model that reframes the problem",
    icon: CheckCircle,
    templates: {
      "Agent Architecture":
        "The fastest way to scale autonomous systems is to make human approval mandatory:\n\nHere is the 3-layer architecture we use to guarantee zero unintended side effects.",
      "Distributed Systems":
        "To increase automation velocity, you must slow down write executions.\n\nHere is the dual-queue rate limiting framework that protects our accounts.",
      "AI Safety & Guardrails":
        "Zero-trust session vaults: Why browser session cookies should never touch CI/CD runner logs.\n\nHere is our Fernet encryption architecture.",
      "System Design":
        "The Inverted Pipeline pattern: How to design workflows where the model proposes but deterministic code executes.",
      General:
        "The 3-stage validation framework that eliminated 99% of our deployment regressions:\n\n1. State isolation\n2. Deterministic triage\n3. Dom-verified execution",
    },
  },
  {
    id: "synthesis",
    name: "Curated Synthesis",
    tagline: "Condense deep research or extensive production experience",
    icon: PencilSimple,
    templates: {
      "Agent Architecture":
        "I analyzed 50 enterprise agent deployments over the last 6 months:\n\n4 non-negotiable architectural patterns emerged across every successful system.",
      "Distributed Systems":
        "After auditing 12 high-throughput edge architectures, here are the 5 lessons on state persistence nobody talks about.",
      "AI Safety & Guardrails":
        "We tested 1,000 edge cases against human-in-the-loop agents:\n\nThese 3 safety invariants prevented 100% of unauthorized platform actions.",
      "System Design":
        "A comprehensive teardown of production LLM orchestration engines: LangGraph, Temporal, and custom state machines compared.",
      General:
        "After 200 hours of performance tuning and production benchmarks:\n\nHere are the top 5 takeaways you can apply to your stack today.",
    },
  },
];

export const TOPIC_PILLARS = [
  "Agent Architecture",
  "Distributed Systems",
  "AI Safety & Guardrails",
  "System Design",
  "General",
];
