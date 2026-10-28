# AGENTS.md

## Purpose & Architecture Overview

LinkedAide (v1.8.2) is an enterprise-grade, human-in-the-loop (HITL) LinkedIn AI assistant and automation system built with:

- **Python (>=3.11)** with [`uv`](https://docs.astral.sh/uv/) for dependency and virtual environment management.
- **LangChain**: Multi-provider LLM integration (NVIDIA NIM default, OpenAI, Anthropic Claude, Google Gemini, Groq, Ollama), structured Pydantic schema validation, multimodal vision analysis, and voice vector memory with dynamic few-shot learning.
- **LangGraph**: Deterministic workflow orchestration across 5 compiled state machines (`ScoutGraph`, `ExecuteGraph`, `HealthCheckGraph`, `IdeationGraph`, `ThreadMonitorGraph`).
- **Playwright**: Stealth LinkedIn browser automation featuring 4-tier self-healing selectors, behavioral biometrics, session keeper, and residential proxy gateway routing.
- **Dual-Channel HITL Authorization**: Telegram Bot (inline cards, tone studio, C2 commands) and Desktop Cockpit (`desktop/` — Electron + React + TypeScript + Apple HIG / Things 3 UI).
- **Edge Relay & Realtime Hub**: Cloudflare Worker (`infra/edge-relay`) with Workers KV, R2 media vault, and WebSocket push hub for instant desktop synchronization.
- **State & Config Persistence**: Authoritative Cloudflare Workers KV (`STATE_BACKEND=kv`) with local Git/JSON fallback (`STATE_BACKEND=git`).
- **Automation Execution**: Scheduled and event-driven GitHub Actions cloud runners (`.github/workflows/`) alongside local desktop runner execution.

This file defines the mandatory operating rules for AI coding agents working in this repository. Technical specifications in [`docs/architecture.md`](docs/architecture.md) and [`docs/configuration.md`](docs/configuration.md) are the primary architectural references.

---

## 1. Core Architecture Invariants

These constraints are non-negotiable architectural invariants:

### 1.1 Human Approval is Mandatory
No LinkedIn write action (comment, original post, thread reply, connection outreach, reaction) may ever occur without explicit human authorization.
- **Workflow Order**: Discovery/Scouting → LLM Triage → LLM Draft → Persist Pending Action → Human Approval (Telegram or Desktop Queue) → Authorized Dispatch → Deterministic Safety Re-validation → Playwright Verified Write.
- Never add autonomous loops or ReAct agents that independently invoke LinkedIn write tools.

### 1.2 LangGraph Orchestrates Workflows
All business workflow control belongs in compiled LangGraph state machines:
- `ScoutGraph`: Feed scraping, relevance triage, contextual comment drafting, and pending suggestion persistence.
- `ExecuteGraph`: Validates approved actions against daily caps and TTLs, verifies live target availability, executes browser writes, logs history, and reports outcome.
- `HealthCheckGraph`: Session validity canary, proactive session expiration warnings, and breaker tripping.
- `IdeationGraph`: Thought leadership post brainstorming, dynamic hook generation, and post idea staging.
- `ThreadMonitorGraph`: Deep multi-turn comment thread monitoring, reply triage, and follow-up draft suggestions.

CLI and orchestration modules (`src/agent/orchestration/`) must remain thin wrappers: load configuration, construct runtime dependencies, invoke compiled graphs, and handle process exit codes.

### 1.3 LangChain Owns Structured LLM Operations
- Centralize model creation through the factory in [`src/agent/llm/models.py`](src/agent/llm/models.py) (`_build_chat_model`).
- Support multiple providers dynamically via `Settings.llm_provider` (`nvidia`, `openai`, `anthropic`, `gemini`, `groq`, `ollama`, `openai-compatible`).
- All LLM outputs must be validated Pydantic models (`TriageResult`, `CommentDraft`, `PostIdea`, `ThreadReplyCandidate`). Never parse raw markdown or free-form strings directly into business logic.
- Maintain two-stage evaluation: high-speed triage first; draft generation only for qualifying items.
- Maintain anti-cliche deterministic guardrails ([`src/agent/safety/anti_cliche.py`](src/agent/safety/anti_cliche.py)) to prevent generic AI commentary.

### 1.4 Deterministic Safety Policy
Safety policies are strictly enforced in deterministic Python code ([`src/agent/safety/`](src/agent/safety/)), never in LLM prompts:
- **Rate Limits & Caps**: Daily caps on comments (`MAX_COMMENTS_PER_DAY`), posts (`MAX_POSTS_PER_DAY`), and connection requests (`MAX_CONNECTIONS_PER_DAY`) via `RateLimiter`.
- **Pending Action TTL**: Pending actions expire after `PENDING_ACTION_TTL_HOURS` (default 12h) to avoid commenting on stale discussions.
- **Circuit Breaker**: Trips immediately on bot challenge detection, session expiration, or consecutive failures (`CircuitBreaker`). When active, all automated operations abort.
- **Idempotency**: Duplicate dispatches for already-executed or rejected item IDs are safely ignored.

### 1.5 State Persistence (Cloudflare KV & Git Fallback)
All durable state operations must use `BaseStateStore` ([`src/agent/state/store.py`](src/agent/state/store.py)):
- **Cloudflare KV (`CloudflareKVStateStore`)**: Primary production backend (`STATE_BACKEND=kv`). Prevents Git merge conflicts, keeps pending drafts and audit history private, and enables fast-path Telegram rejections directly at the edge.
- **GitStateStore**: Local offline development fallback (`STATE_BACKEND=git`).
- **Keys/Structure**: `pending:{id}`, `seen_posts`, `history`, `daily_counters`, `incident`, `paused`, `connection_queue`, `scheduled_posts`, `active_threads`, `scout_schedule`, and centralized KV runtime `config:runtime`.
- Local `state/` directory is git-ignored to prevent accidental commits of local operational state.

---

## 2. Repository Layout

```text
linkedaide/
├── .github/workflows/          # CI, scout, execute, ideation, monitor, and release workflows
├── desktop/                    # Cross-platform Electron + React desktop cockpit
│   ├── electron/               # Main process, IPC handlers, Fernet crypto, session vault, tray
│   ├── src/                    # React UI: Approval Queue, Outreach Queue, Composer, Calendar
│   └── tests/                  # Desktop TypeScript and React component test suites
├── docs/                       # Architecture, configuration, setup, and troubleshooting guides
├── infra/
│   └── edge-relay/             # Cloudflare Worker: Telegram webhook, API, WS push hub, R2 vault
├── persona/                    # User voice configuration, style guides, writing samples
├── scripts/                    # Session extraction, secret generation, webhook registration
├── src/agent/
│   ├── browser/                # Playwright automation, selectors, biometrics, stealth, actions
│   ├── cli/                    # Unified CLI (doctor, setup, scout, execute, ideate, outreach, config)
│   ├── config/                 # Pydantic Settings, KV config loader, validators, constants
│   ├── doctor/                 # Environment and dependency diagnostic suite
│   ├── errors.py               # Custom exception hierarchy
│   ├── graphs/                 # LangGraph state machines (Scout, Execute, Health, Ideate, Thread)
│   ├── llm/                    # Models factory, prompts, chains, voice memory, multimodal vision
│   ├── models/                 # Pydantic domain models (actions, browser, dispatch, llm, state)
│   ├── orchestration/          # Flow entrypoints and runners for graphs and CLI
│   ├── safety/                 # Rate limiter, circuit breaker, anti-cliche guardrail
│   ├── state/                  # StateStore abstractions (KV store, Git store, base)
│   └── telegram/               # Telegram bot client, keyboards, command handler, draft editor
└── tests/                      # Python unit and integration test suites
```

---

## 3. Browser Automation & Anti-Bot Rules

1. **Isolation**: Only `src/agent/browser/` may interact with Playwright or LinkedIn DOM. Graph nodes and LLM services must never import Playwright or execute DOM queries.
2. **4-Tier Self-Healing Selectors**: Always use `SelectorEngine` ([`src/agent/browser/selectors.py`](src/agent/browser/selectors.py)) with primary data attributes, semantic fallbacks, ARIA roles, and fuzzy DOM recovery.
3. **Behavioral Biometrics**: Incorporate humanized mouse trajectories, realistic typing cadence with typo simulation, and randomized dwell intervals ([`src/agent/browser/biometrics.py`](src/agent/browser/biometrics.py)).
4. **Session Security**: Session cookies (`LINKEDIN_SESSION_STATE_ENC`) are decrypted only into ephemeral runner memory and wiped in `finally` blocks. Never log cookies, tokens, or auth headers.
5. **Fatal Challenge Detection**: If a CAPTCHA, checkpoint, or security gate is encountered, immediately raise `BotDetectionError`, trip the circuit breaker, and halt. **Never attempt to bypass CAPTCHAs or platform security checks.**
6. **No Ambiguous Retries**: Never retry a submission write if the outcome is uncertain. Inspect the DOM to confirm success; if unconfirmed, record failure and fail closed.

---

## 4. Human Approval & Review Interfaces

### 4.1 Telegram Bot & Relay Worker
- Telegram webhook runs on Cloudflare Workers ([`infra/edge-relay`](infra/edge-relay)).
- Only `TELEGRAM_AUTHORIZED_CHAT_ID` is authorized to trigger actions.
- Callback data must contain only compact action codes (`ac`, `rc`, `ap`, `rp`, etc.) and opaque item IDs. Never pass secrets or executable payload in callbacks.
- Supports interactive draft revisions via message reply and tone adjustment menus.
- Operator C2 commands: `/status`, `/pending`, `/pause`, `/resume`, `/clear_incident`, `/stats`, `/help`.

### 4.2 Desktop Application Cockpit
- Built with Electron, React, and Tailwind CSS using Apple HIG and Things 3 aesthetic tokens.
- Supports Dual Execution Modes: Cloud Mode (Cloudflare KV + GitHub Actions) and Local Mode (local Python execution).
- Features: Approval Queue with AI tone rewriter, Outreach Queue for connections, 2-Pane Post Composer Studio with Carousel PDF preview, Content Calendar, Session Vault with embedded authentication, and ⌘K Command Palette.

---

## 5. Configuration & Centralized Settings

All runtime configuration is managed via `Settings` ([`src/agent/config/settings.py`](src/agent/config/settings.py)) using `pydantic-settings`:
- **Centralized Cloudflare KV**: In production (`STATE_BACKEND=kv`), operational settings and credentials live in Cloudflare KV (`config:runtime`), keeping runners, worker, and desktop synchronized.
- **CLI Configuration Tool**: Manage remote settings with `uv run agent config show` and `uv run agent config set <key> <val>`.
- **Environment Fallback**: Supported via `.env` and environment variables. **Never read or edit `.env` without explicit user permission.**
- Validate configuration once near process startup; never sprinkle `os.getenv()` across modules.

---

## 6. Common Development Commands

### Python Environment & CLI
```bash
# Environment sync
uv sync --all-groups

# Unified Agent CLI
uv run agent doctor                       # Run diagnostic health check suite
uv run agent setup                        # Interactive onboarding wizard
uv run agent scout [--dry-run] [--headed] # Run feed scout workflow
uv run agent execute --action approve --item-id <id> # Execute approved action
uv run agent ideate [--dry-run]           # Run post ideation workflow
uv run agent monitor [--headed]           # Run thread reply monitoring
uv run agent outreach --limit 5           # Run connection outreach flow
uv run agent config show                  # Display remote KV configuration

# Testing & Static Analysis
uv run ruff check .                       # Linting check
uv run ruff check --fix .                 # Auto-fix linting issues
uv run ruff format --check .              # Format check
uv run ruff format .                      # Format code
uv run mypy src tests scripts             # Static type checking
uv run pytest                             # Full test suite
uv run pytest tests/unit/test_schemas.py  # Targeted unit test
```

### Cloudflare Worker (`infra/edge-relay`)
```bash
cd infra/edge-relay
npm ci
npm run typecheck
npm test
npm run deploy                            # Deploy worker to Cloudflare
```

### Desktop App (`desktop`)
```bash
cd desktop
npm ci
npm run typecheck
npm test
npm run build                             # Build desktop bundle
npm run dev                               # Start Vite dev server
```

---

## 7. Git Commit Policy & Quality Standards

1. **Commit Readiness**:
   Before committing, verify that all pre-flight checks pass:
   - `uv run ruff check .`
   - `uv run ruff format --check .`
   - `uv run mypy src tests scripts`
   - Relevant unit tests (`uv run pytest`)
2. **Conventional Commits**:
   Format: `<type>(<scope>): <short imperative description>`
   - Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`
   - Scopes: `llm`, `graphs`, `browser`, `desktop`, `telegram`, `relay`, `state`, `safety`, `config`, `models`, `cli`, `doctor`
   - Non-trivial commits must include an explanatory body separated by a blank line.
3. **Commit Invariants**:
   - Never commit `.env`, credentials, secrets, or storage-state files.
   - Never commit local `state/` runtime records (`seen_posts.json`, `history.jsonl`, `pending/`).
   - Do NOT push or commit any code unless explicitly requested by the user.
   - Do NOT remove or modify existing code comments unless the associated code logic changes.
   - Avoid monolithic files; keep modules small, modular, and single-purpose.

---

## 8. Safety & Platform Risk Guardrails

- **Dry-Run Integrity**: `DRY_RUN=true` must guarantee zero LinkedIn write actions while allowing scouting, LLM triage, drafting, and Telegram review cards.
- **Fail Closed**: Ambiguous browser responses, missing approvals, schema failures, or expired TTLs must always fail closed (abort or reject) rather than guess.
- **Platform Boundaries**: Never attempt to bypass CAPTCHAs, email checkpoints, or platform enforcement. Respect platform rate limits and preserve humanized delays.
- **Central Principle**:
  > *LLMs propose and draft. Humans authorize. Deterministic code validates. Automation executes only when authorized and safe.*
