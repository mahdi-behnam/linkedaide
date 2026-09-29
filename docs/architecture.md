# System Architecture & Technical Design

This document details the architectural design, workflow state machines, persistence model, and safety mechanisms of the LinkedIn Human-in-the-Loop (HITL) AI Agent.

---

## 1. System Overview

The system bridges scheduled autonomous discovery with strict human supervisory control:

```mermaid
flowchart TD
    subgraph Scheduled Discovery [1. Discovery & Triage]
        Cron[GitHub Cron / Scout Workflow] --> ScoutGraph[ScoutGraph]
        ScoutGraph -->|Scrape Feed| Scraper[Playwright Stealth Scraper]
        Scraper -->|Extract Posts| Triage[LLM Triage NIM]
        Triage -->|Qualifying Posts| Draft[LLM Comment Drafter NIM]
        Draft -->|Persist| PendingStore[state/pending/<item_id>.json]
        PendingStore -->|Notify| TelegramBot[Telegram Suggestion Message]
    end

    subgraph Human Boundary [2. Authorization Boundary]
        TelegramBot -->|Inline Buttons| Operator((Human Operator))
        Operator -->|Click Approve / Reject| RelayWorker[Cloudflare Relay Worker]
        RelayWorker -->|repository_dispatch| GitHubActions[GitHub Actions Runner]
    end

    subgraph Execution [3. Deterministic Execution]
        GitHubActions --> ExecuteGraph[ExecuteGraph]
        ExecuteGraph -->|Validate Safety & Cap| SafetyEngine[Deterministic Safety Layer]
        SafetyEngine -->|Valid| Executor[Playwright Action Executor]
        Executor -->|Write Comment| LinkedInDOM[LinkedIn Live DOM]
        Executor -->|Log Result| StateStore[state/history.jsonl & daily_counters.json]
        StateStore -->|Edit Message| TelegramUpdate[Telegram Outcome Update]
    end
```

---

## 2. Core Architectural Invariants

1. **Human Approval is Mandatory**: No LinkedIn write action (commenting, posting, reacting) may occur without explicit authorization from the configured Telegram user.
2. **LangGraph Workflow Orchestration**: Business logic and branching transitions are orchestrated via deterministic LangGraph state graphs.
3. **LangChain for Structured LLM Operations**: All model interactions are centralized through `LLMService` using LangChain and NVIDIA NIM, with strict Pydantic schema validation.
4. **Deterministic Safety Policy**: Rate limits, daily caps, approval TTLs, circuit breakers, and sender checks are implemented in code—never entrusted solely to LLM prompts.
5. **Durable Repository State**: All application state resides in version-controlled JSON/JSONL records in `state/`.

---

## 3. Workflow State Machines (LangGraph)

The application defines three compiled LangGraph state machines:

### 3.1 ScoutGraph
Orchestrates feed ingestion, LLM evaluation, and suggestion delivery:

```mermaid
stateDiagram-v2
    [*] --> check_halted
    check_halted --> load_seen: System Active
    check_halted --> [*]: System Paused / Tripped
    load_seen --> scrape_feed
    scrape_feed --> triage_batch: Posts Scraped
    scrape_feed --> [*]: No Posts / Scrape Error
    triage_batch --> draft_batch: Qualifying Candidates Found
    triage_batch --> [*]: No Qualifying Posts
    draft_batch --> rank_and_build_pending
    rank_and_build_pending --> persist_state
    persist_state --> send_telegram_suggestions
    send_telegram_suggestions --> [*]
```

### 3.2 ExecuteGraph
Executes human approval or rejection events received via `repository_dispatch`:

```mermaid
stateDiagram-v2
    [*] --> check_halted
    check_halted --> load_pending: System Active
    check_halted --> [*]: System Paused
    load_pending --> notify_already_handled: Pending Missing
    load_pending --> handle_rejection: Action == Reject
    load_pending --> validate_request: Action == Approve
    notify_already_handled --> [*]
    handle_rejection --> [*]
    validate_request --> verify_target: Valid & Within Caps/TTL
    validate_request --> handle_failure: Expired / Cap Exceeded / Unauthorized
    verify_target --> execute_browser_action: Session OK & Post Exists
    verify_target --> handle_failure: Session Invalid / Post Deleted
    execute_browser_action --> persist_success: Success
    execute_browser_action --> handle_failure: Execution Failed
    persist_success --> notify_success
    notify_success --> [*]
    handle_failure --> [*]
```

### 3.3 HealthCheckGraph
A lightweight canary workflow that runs periodically to verify LinkedIn session validity without performing feed scraping or LLM calls:

```mermaid
stateDiagram-v2
    [*] --> check_halted
    check_halted --> verify_session: System Active
    check_halted --> [*]: System Paused
    verify_session --> [*]: Health Checked (Alerts & Trips Breaker if Expired/Challenge)
```

---

## 4. LLM Service & Structured Output

LLM integration is managed by `LLMService` in `src/agent/llm/service.py`:

- **Provider**: NVIDIA NIM via LangChain (`ChatNVIDIA`).
- **Two-Stage Evaluation**:
  1. **Triage**: High-speed, cost-effective evaluation of scraped posts against configured `USER_FOCUS_AREAS` and `USER_PERSONA`. Produces a structured `TriageResult` (`recommendation: "comment" | "ignore"`, `confidence`, `reasoning`, `risk_flags`).
  2. **Drafting**: Deep generation producing `CommentDraft` with strict anti-generic constraints, specific professional insights, and character length bounds.
- **Resilience & Fallback**:
  - Primary model: `nvidia/nemotron-3-super-120b-a12b`
  - Fallback model: `openai/gpt-oss-20b`
  - Automatic fallback on rate-limits (HTTP 429), timeouts, or provider 5xx errors.

---

## 5. Durable State Persistence Model (Cloudflare KV & Git Fallback)

State persistence is abstracted via `BaseStateStore` (`src/agent/state/base.py`) with two implementations:

### 5.1 Cloudflare KV State Backend (`CloudflareKVStateStore`)
The primary production backend (`STATE_BACKEND=kv`). State records are persisted in a private Cloudflare Workers KV namespace via the REST API (`api.cloudflare.com/client/v4`):

- `pending:{item_id}` -> JSON string of `PendingAction`
- `seen_posts` -> JSON map of `content_hash -> iso timestamp`
- `history` -> JSON array of `HistoryEntry` audit logs
- `daily_counters` -> JSON of `DailyCounters` (auto-rollover on UTC date boundary)
- `incident` -> JSON of circuit breaker incident record (or 404 when normal)
- `paused` -> JSON of remote operator pause state

**Architectural Advantages of Cloudflare KV:**
- **Zero Git Merge Conflicts**: Eliminates concurrent push collisions between scheduled scout runs and approval dispatches.
- **Privacy on Public Repositories**: Keeps pending drafts, evaluated post excerpts, and operator history private inside Cloudflare KV rather than committed to a public Git repository.
- **Fast-Path Rejections**: The Cloudflare Telegram relay worker directly updates KV upon operator rejection, removing the need to spin up a GitHub Actions runner (saving CI minutes).
- **Clean Git History**: Prevents thousands of automated `chore(state): ... [skip ci]` commits from polluting git history.

### 5.2 Git-as-Database Fallback (`GitStateStore`)
Used for local offline development and testing (`STATE_BACKEND=git`):
- `state/pending/{item_id}.json`
- `state/seen_posts.json`
- `state/history.jsonl`
- `state/daily_counters.json`
- `state/incident.json`
- `state/paused.json`

The local `state/` directory is in `.gitignore` to prevent committing operational state when working locally.

---

## 6. Browser Automation & Stealth

The browser layer (`src/agent/browser/`) is the sole subsystem that interacts with LinkedIn:

- **Playwright Chromium**: Executes in headless mode with realistic viewport configurations, randomized natural delay jitter, and stealth navigator property overrides.
- **Ephemeral Session Decryption**: The encrypted storage state (`LINKEDIN_SESSION_STATE_ENC`) is decrypted into memory/runner-local temporary storage during execution and deleted in `finally` blocks.
- **No Autonomous Writes**: Scraper only reads from DOM; Executor only writes when an explicit, verified `ExecuteGraph` step instructs it.
- **Challenge Detection**: Automatically detects CAPTCHAs, email verification checkpoints, or security gates, instantly raising `BotDetectionError` and halting the workflow.

---

## 7. Deterministic Safety & Policy Enforcement

Safety rules are enforced by independent modules (`src/agent/safety/`):

1. **Daily Action Limiter (`RateLimiter`)**: Strictly limits comments and posts per day based on `daily_counters.json`.
2. **Approval TTL**: Pending suggestions expire after `PENDING_ACTION_TTL_HOURS` (default: 12 hours) to avoid executing stale commentary on old feed discussions.
3. **Idempotency & Duplicate Protection**: Each pending item has an 8-character hex hash. Once executed or rejected, the pending file is consumed and deleted; duplicate `repository_dispatch` events are safely ignored.
4. **Circuit Breaker (`CircuitBreaker`)**: Tripped immediately upon detection of bot challenges, session invalidation, or consecutive failure thresholds. When active, all subsequent runs abort immediately until manually reset.
5. **Dry-Run Mode**: Setting `DRY_RUN=true` executes full scraping, triage, drafting, and Telegram suggestion delivery, but mocks out DOM submission.
