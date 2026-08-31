# AGENTS.md

## Purpose

This repository implements a human-in-the-loop LinkedIn agent using:

- Python
- LangChain for model integration, prompting, and structured output
- LangGraph for deterministic workflow orchestration
- NVIDIA NIM as the LLM provider
- Playwright for LinkedIn browser automation
- Telegram for human approval
- GitHub Actions for scheduled and event-driven execution
- Repository-backed JSON/JSONL files for durable application state

This file defines the operating rules for coding agents working in this repository.

The implementation plan / technical specification is the source of truth for product behavior and architecture. When this file and the implementation plan appear to conflict, preserve the implementation plan unless the change request explicitly updates the architecture.

---

## 1. Core Architecture Invariants

These are architectural constraints, not suggestions.

### 1.1 Human approval is mandatory

No LinkedIn write action may happen solely because an LLM, LangChain chain, LangGraph node, scheduler, or browser component decided to do it.

The required lifecycle is:

```text
LinkedIn feed
    ↓
ScoutGraph
    ↓
LLM triage
    ↓
LLM draft
    ↓
persist pending action
    ↓
Telegram approval request
    ↓
human Approve / Reject
    ↓
repository_dispatch
    ↓
ExecuteGraph
    ↓
re-validation + safety checks
    ↓
Playwright write action
```

Never introduce an autonomous path that bypasses Telegram approval.

Do not add a ReAct-style agent that can independently choose or invoke LinkedIn write tools.

### 1.2 LangGraph orchestrates workflows

Business workflow control belongs in LangGraph graphs.

Use explicit graph nodes, conditional edges, and typed graph state for workflow transitions.

Primary graphs:

- `ScoutGraph`
- `ExecuteGraph`
- `HealthCheckGraph`

Optional fallback flow:

- polling-based approval execution if the Telegram relay is not used

CLI/orchestration modules should remain thin. They should:

1. load configuration,
2. construct runtime dependencies,
3. invoke the appropriate compiled graph,
4. translate terminal failures into process exit behavior.

Do not move workflow branching back into large procedural `run_*()` functions.

### 1.3 LangChain owns LLM integration

Use LangChain abstractions for:

- NVIDIA NIM chat model construction,
- prompt templates,
- structured output parsing,
- Pydantic-backed response schemas,
- model invocation,
- model fallback where appropriate.

Prefer `ChatNVIDIA` for NVIDIA NIM integration.

LLM-facing code should remain behind a narrow service boundary such as `LLMService`.

The rest of the application should consume validated domain objects, not raw model response payloads.

### 1.4 LLMs do not own safety policy

Deterministic code must enforce:

- approval status,
- pending-action TTL,
- daily posting/comment caps,
- authorized Telegram identity,
- circuit breaker state,
- duplicate-action protection,
- bot/challenge detection,
- dry-run behavior.

Never encode these protections only in prompts.

### 1.5 Repository state is durable application state

The `state/` directory is intentionally version-controlled.

Do not add `state/` to `.gitignore`.

Expected state includes:

```text
state/
├── pending/
├── seen_posts.json
├── history.jsonl
├── daily_counters.json
└── incident.json
```

`state/incident.json` should normally be absent. Its presence means the circuit breaker is active.

Do not replace repository-backed state with Redis, Postgres, SQLite, a LangGraph production checkpointer, or another persistence system unless the implementation plan is explicitly being revised.

### 1.6 LangGraph checkpoints are not the approval database

The Telegram approval boundary spans separate GitHub Actions runs.

Persist cross-run approval state using the repository state model.

Do not assume an in-memory LangGraph checkpointer survives between GitHub Actions jobs.

Do not introduce LangGraph `interrupt()` as the primary Telegram approval mechanism unless a persistent checkpointer and thread lifecycle are intentionally designed and approved.

---

## 2. Repository Layout

Keep responsibilities separated roughly as follows:

```text
src/agent/
├── config.py
├── errors.py
├── models/
│   └── schemas.py
├── llm/
│   ├── models.py
│   ├── prompts.py
│   └── service.py
├── graphs/
│   ├── state.py
│   ├── scout_graph.py
│   ├── execute_graph.py
│   └── health_graph.py
├── browser/
│   ├── session.py
│   ├── stealth.py
│   ├── scraper.py
│   └── executor.py
├── telegram/
│   ├── client.py
│   └── keyboards.py
├── state/
│   └── store.py
├── safety/
│   ├── rate_limiter.py
│   └── circuit_breaker.py
└── orchestration/
    ├── scout_flow.py
    ├── execute_flow.py
    ├── poll_flow.py
    └── health_check_flow.py
```

The exact filenames may evolve, but preserve these boundaries:

- `models/`: domain and persistence schemas
- `llm/`: LangChain/NIM concerns
- `graphs/`: LangGraph workflow definitions
- `browser/`: Playwright-only concerns
- `telegram/`: Telegram API/UI concerns
- `state/`: durable repository state
- `safety/`: deterministic policy enforcement
- `orchestration/`: process entrypoints and dependency wiring

Avoid circular dependencies between these areas.

---

## 3. LangGraph Conventions

### 3.1 Use typed state

Every graph must use an explicit typed state definition.

Do not pass arbitrary untyped dictionaries between nodes.

Graph state should contain serializable workflow data such as:

- identifiers,
- validated domain models,
- decision flags,
- lists of candidate items,
- error/status information,
- paths or references to persisted records.

Runtime clients such as browser objects, Telegram clients, state stores, and model clients should not be serialized into graph state.

Pass runtime dependencies using the graph runtime/context mechanism or construct them outside the graph and inject them cleanly.

### 3.2 Nodes should have one responsibility

Prefer small nodes such as:

```text
check_halted
load_state
scrape_feed
filter_seen
triage_posts
draft_comments
rank_candidates
persist_pending
send_telegram_suggestions
```

and:

```text
load_pending
validate_request
check_ttl
handle_rejection
check_daily_cap
verify_session
verify_target
execute_linkedin_action
persist_outcome
notify_outcome
```

A graph node should perform one coherent transition and return only the state updates it owns.

### 3.3 Keep routing deterministic

Conditional edges should be based on validated state, not free-form LLM prose.

Good:

```python
if state["triage"].recommendation == "comment":
    return "draft"
return "skip"
```

Bad:

```python
if "probably engage" in raw_model_text:
    ...
```

### 3.4 Fail closed

When a graph encounters ambiguous or invalid state, prefer:

```text
skip item
reject execution
record failure
notify operator
halt when safety-sensitive
```

Never guess a missing approval, malformed model result, or uncertain browser outcome.

### 3.5 Do not hide side effects

Nodes that perform external side effects must have obvious names.

For example:

- `persist_pending`
- `send_telegram_suggestion`
- `post_linkedin_comment`
- `edit_telegram_outcome`

Do not bury network or browser writes inside generic nodes such as `process_item`.

---

## 4. LangChain / NVIDIA NIM Conventions

### 4.1 Model construction

Centralize model construction.

Do not instantiate `ChatNVIDIA` throughout the codebase.

Use configuration values for:

- primary model,
- fallback model,
- temperature,
- token limits,
- concurrency,
- request timeout.

Never hardcode production API keys or model credentials.

### 4.2 Structured output is required

Triage and generation outputs must be validated Pydantic models.

Expected domain models include:

- `TriageResult`
- `CommentDraft`
- `PostIdea`

Prefer LangChain structured-output support rather than manual JSON string parsing.

Never let raw LLM strings directly drive graph routing or persisted pending actions.

### 4.3 Preserve two-stage evaluation

For feed posts, retain the two-stage pattern:

```text
new post
  ↓
triage
  ↓ only when worth engaging
comment generation
```

Do not generate comments for every scraped post and filter afterward.

### 4.4 Preserve explicit failure semantics

The LLM layer must distinguish at least:

- schema validation failure,
- rate limit exhaustion,
- timeout,
- provider/server failure.

Retry only transient failures.

Schema repair should remain bounded.

Fallback should remain bounded.

Do not create unbounded retry loops.

If both primary and fallback fail for an item, skip that item and continue unless a broader safety condition requires halting the run.

### 4.5 Prompts are controlled artifacts

Keep prompts centralized under `agent/llm/prompts.py` or equivalent.

Do not scatter large prompt strings through graph nodes.

When changing prompts:

1. preserve the structured-output contract,
2. preserve the anti-generic-comment constraints,
3. add or update tests,
4. avoid changing unrelated workflow behavior.

---

## 5. Browser Automation Rules

### 5.1 Treat Playwright writes as high-risk side effects

The browser layer is the only layer that may interact directly with LinkedIn.

Graph and LLM modules must not contain selectors or Playwright calls.

### 5.2 Never retry ambiguous writes

A navigation timeout may receive one bounded retry where explicitly allowed.

A submission with an uncertain outcome must not be retried blindly.

If it is unclear whether LinkedIn accepted a comment or post:

1. inspect/verify the DOM,
2. record the failure,
3. do not submit the same content again automatically.

This prevents duplicate comments or posts.

### 5.3 Challenge detection is fatal

If a CAPTCHA, checkpoint, unusual-activity page, or equivalent bot challenge is detected:

- raise `BotDetectionError`,
- trip the circuit breaker,
- stop the workflow,
- do not retry,
- do not continue to the next action.

Never add code intended to bypass CAPTCHAs, checkpoints, access controls, or platform enforcement.

### 5.4 Session state is sensitive

Authenticated Playwright storage state must never be committed.

Files matching patterns such as these belong in `.gitignore`:

```text
*storage_state*.json
*storage-state*.json
playwright/.auth/
```

Decrypted session files should live only in an ephemeral runner path.

Never log cookies, authentication headers, session tokens, or decrypted storage-state content.

---

## 6. Telegram Approval Rules

The Telegram bot represents the human authorization boundary.

Only the configured authorized chat/user may approve or reject actions.

Authorization must be checked in more than one layer when practical.

`callback_data` should contain only a compact action code and opaque item identifier.

Never place:

- drafted comment text,
- access tokens,
- LinkedIn session data,
- secrets,
- arbitrary executable instructions

inside Telegram callback data.

After an item reaches a terminal state, remove its inline keyboard.

A missing pending item must be treated as already handled or invalid, not recreated from callback contents.

---

## 7. Safety and Idempotency

Before every LinkedIn write, verify all applicable conditions:

1. system is not paused,
2. circuit breaker is not active,
3. callback sender is authorized,
4. pending item exists,
5. pending item is still within TTL,
6. requested action matches the pending record,
7. daily cap is not exceeded,
8. LinkedIn session is valid,
9. target post still exists when commenting,
10. no challenge page is present.

Only then may the browser write occur.

After a successful write:

1. confirm success in the DOM,
2. persist history,
3. update counters,
4. delete/consume the pending item,
5. commit state,
6. update the Telegram message.

Design all execution paths to tolerate duplicate `repository_dispatch` events safely.

---

## 8. Dry-Run Semantics

`DRY_RUN=true` must guarantee zero LinkedIn write actions.

Dry run may still perform:

- configuration loading,
- repository state reads,
- feed scraping,
- LLM triage,
- LLM drafting,
- Telegram suggestion delivery,
- approval relay testing,
- target-page navigation,
- screenshots,
- logging of the action that would have occurred.

Dry run must not:

- submit a comment,
- publish a LinkedIn post,
- accidentally invoke a browser helper that performs a write.

When adding new write-capable behavior, explicitly test its dry-run path.

---

## 9. Error Handling

Use the repository's custom exception hierarchy rather than generic exceptions at architectural boundaries.

Expected categories include:

```text
AgentError
├── ConfigError
├── NIMError
│   ├── NIMSchemaValidationError
│   ├── NIMRateLimitError
│   └── NIMTimeoutError
├── SessionError
│   ├── SessionExpiredError
│   └── BotDetectionError
├── ScrapeError
│   └── SelectorDriftError
├── ExecutionError
│   ├── PostNoLongerAvailableError
│   ├── StaleApprovalError
│   └── DuplicateActionError
├── StateStoreError
└── TelegramAPIError
```

Do not catch `Exception` and silently continue.

If a broad catch is required at a process boundary:

- log sanitized context,
- preserve the original exception,
- return a failing exit code when appropriate.

Never swallow `BotDetectionError`.

---

## 10. Configuration

All runtime configuration must flow through the central settings model.

Use `pydantic-settings`.

Secrets must come from environment variables / GitHub Secrets.

Non-secret operational configuration should come from repository variables where practical.

Typical configuration includes:

```text
NVIDIA_NIM_API_KEY
NIM_MODEL_PRIMARY
NIM_MODEL_FALLBACK
TELEGRAM_BOT_TOKEN
TELEGRAM_AUTHORIZED_CHAT_ID
SESSION_ENCRYPTION_KEY
LINKEDIN_SESSION_STATE_ENC
USER_FOCUS_AREAS
MAX_COMMENTS_PER_DAY
MAX_POSTS_PER_DAY
MAX_SUGGESTIONS_PER_RUN
PENDING_ACTION_TTL_HOURS
AGENT_PAUSED
DRY_RUN
```

Do not call `os.getenv()` throughout application modules.

Load and validate settings once near the process boundary.

---

## 11. State Store Rules

All repository-backed persistence should go through `GitStateStore` or its successor abstraction.

Do not write directly to `state/*.json` from unrelated modules.

Persist Pydantic/domain models rather than ad hoc dictionaries where possible.

State writes should be atomic from the application's perspective.

A git push conflict must fail loudly; do not silently discard state.

Never mutate history retroactively.

`history.jsonl` is append-only.

Pending records are consumable workflow records.

---

## 12. GitHub Actions Rules

All workflows that can access LinkedIn should share the same concurrency group.

The goal is at most one active LinkedIn browser session at a time.

Do not enable `cancel-in-progress` for an execution that may already have performed an external side effect.

Keep workflow permissions minimal.

Do not expose the relay's GitHub dispatch PAT to normal GitHub Actions jobs.

Do not upload decrypted browser session files as artifacts.

Debug artifacts may contain sensitive account information; keep retention short.

---


## 13. Git Commit Policy

Coding agents are expected to create commits during implementation when they have
completed a coherent, independently understandable unit of work.

Commit frequency is based on logical change boundaries, not elapsed time or file
count.

### 13.1 Commit frequency

Do not commit after every edited file.

Do not wait until an entire multi-phase implementation is complete before making
the first commit.

Prefer one commit per coherent change, such as:

- one implementation-plan phase,
- one independently testable subsystem within a large phase,
- one bug fix,
- one refactor with no intended behavior change,
- one dependency/configuration change,
- one documentation-only change.

A small phase may be a single commit.

A large phase may contain several commits when its parts are independently
meaningful. For example:

```text
feat(llm): add NVIDIA NIM model factory
feat(llm): add structured triage and drafting chains
test(llm): cover fallback and schema repair behavior
```

Do not split a tightly coupled implementation into artificial micro-commits merely
to increase commit count.

The guiding rule is:

> Commit whenever a coherent unit of work is complete, tested, and could reasonably
> be reviewed or reverted independently.

### 13.2 Commit readiness

Before creating a commit:

1. inspect `git status`,
2. inspect the staged and unstaged diff,
3. ensure no secrets, credentials, session files, or unrelated artifacts are included,
4. run the relevant focused tests,
5. ensure the change is internally coherent.

For a phase-completion commit, also run the broader applicable test/lint suite.

Do not knowingly commit broken code unless the user explicitly requests a WIP
checkpoint.

Do not create empty commits unless the user explicitly requests one.

### 13.3 Staging rules

Do not blindly use `git add .` or `git add -A` without first inspecting repository
status and understanding what will be staged.

Prefer staging only files belonging to the current logical change.

Never use `git add -f` to bypass `.gitignore` for:

- `.env` files,
- credentials,
- API keys,
- LinkedIn storage state,
- decrypted session data,
- debug captures containing sensitive information.

The `state/` directory is intentionally version-controlled, but runtime mutations
under `state/` must not be included in ordinary development commits unless the
current task specifically requires changing committed state fixtures, initial state
files, or state-related test data.

For example, do not accidentally commit local or dry-run mutations to:

```text
state/pending/
state/seen_posts.json
state/history.jsonl
state/daily_counters.json
state/incident.json
```

Always inspect these files before staging them.

### 13.4 Commit message format

Use Conventional Commits:

```text
<type>(<scope>): <short imperative description>
```

Preferred types:

- `feat` — new behavior or capability
- `fix` — bug fix
- `refactor` — structural change without intended behavior change
- `test` — test-only changes
- `docs` — documentation-only changes
- `chore` — tooling, dependencies, repository maintenance
- `ci` — GitHub Actions / CI changes

Recommended scopes include:

- `llm`
- `graphs`
- `browser`
- `telegram`
- `state`
- `safety`
- `config`
- `models`
- `actions`
- `relay`
- `tests`
- `docs`
- `deps`

Examples:

```text
feat(graphs): implement scout graph routing
feat(llm): add structured NVIDIA NIM chains
fix(execute): reject expired pending approvals
test(graphs): cover duplicate dispatch handling
ci(actions): add scout workflow
docs(agents): define commit policy
chore(deps): add langchain and langgraph
```

Use the imperative mood and describe what the commit does.

Keep the subject concise and specific.

Do not use vague messages such as:

```text
updates
changes
fix stuff
wip
more work
phase 2
```

The commit should be understandable without reading the diff.

### 13.5 Commit boundaries

Each commit should contain one primary concern.

Do not mix unrelated cleanup, formatting, dependency upgrades, documentation
rewrites, and feature work into the same commit.

If a refactor is required before implementing a feature, prefer separate commits
when each change is independently valid:

```text
refactor(graphs): extract shared graph runtime context
feat(graphs): add execute approval routing
```

rather than combining both into an opaque large commit.

Formatting changes caused directly by edited files may remain in the same commit.

Avoid opportunistic repository-wide cleanup during a focused feature task.

### 13.6 Implementation-plan phase boundaries

When working from `docs/IMPLEMENTATION_PLAN.md`, treat phase boundaries as natural
checkpoint boundaries.

At the end of a completed phase:

1. run the phase Definition of Done,
2. run relevant tests and linting,
3. review `git status` and the full diff,
4. verify no sensitive or runtime-only files are included,
5. commit the completed phase or its final coherent unit,
6. report the resulting commit hash and commit message in the task summary when
   commits were created.

Do not bundle unrelated work from the next implementation phase into the current
phase's final commit.

Do not force exactly one commit per phase. Use multiple commits when a large phase
contains independently understandable and testable units.

### 13.7 Existing history

Do not rewrite repository history unless the user explicitly requests it.

Specifically, do not:

- amend commits that existed before the current task,
- interactive-rebase shared history,
- reset published commits,
- squash existing commits,
- force-push,
- delete branches or tags.

Do not discard or rewrite commits merely to make the history look cleaner.

If a new commit needs a correction, prefer a follow-up commit unless the current
task explicitly permits amending a commit created during the same task and doing
so cannot affect shared history.

### 13.8 Pushing

Creating a local commit and pushing it are separate operations.

Do not push commits to a remote repository unless:

- the user explicitly requested a push, or
- the task/environment explicitly states that pushing is part of the workflow.

Never force-push unless explicitly instructed.

Never change the configured remote destination without explicit instruction.

### 13.9 User-authored changes

Never discard, overwrite, reset, revert, or silently include changes that appear
to have been made by the user merely because they are unrelated to the current
task.

If unrelated user changes are present:

1. leave them untouched,
2. leave them unstaged,
3. stage only files belonging to the current task.

If user changes overlap with files required for the task, preserve them and work
around them where possible. Do not use destructive Git commands to obtain a clean
working tree.

### 13.10 Commit reporting

When commits are created during a task, include a concise commit summary in the
final response.

Example:

```text
3f2a61c feat(graphs): implement scout graph routing
971bd27 test(graphs): cover scout routing and failure paths
```

Do not claim a commit was created unless `git commit` actually succeeded.


## 14. Testing Requirements

Every meaningful change should include tests at the lowest appropriate level.

### 14.1 Unit tests

Unit-test:

- Pydantic schemas,
- configuration validation,
- prompt/model structured output,
- retry/fallback behavior,
- graph routing,
- Telegram authorization,
- callback parsing,
- rate limits,
- TTL behavior,
- circuit breaker behavior,
- state transitions.

### 14.2 Graph tests

Test graphs as graphs.

At minimum, cover:

#### Scout

- halted system,
- no new posts,
- ignored post,
- qualifying post,
- LLM failure for one item,
- suggestion cap,
- dry run.

#### Execute

- approve,
- reject,
- missing pending item,
- expired item,
- unauthorized request,
- daily cap reached,
- post missing,
- successful execution,
- ambiguous execution failure,
- bot challenge,
- duplicate dispatch.

Assert both:

- terminal graph state,
- expected side effects / absence of side effects.

### 14.3 Browser tests

Do not depend on live LinkedIn for normal CI.

Use saved HTML fixtures and local static pages for:

- scraper selectors,
- login detection,
- challenge detection,
- post existence checks,
- success-confirmation behavior.

Live-account validation belongs in controlled manual dry-run testing.

### 14.4 No real external calls in unit tests

Mock:

- NVIDIA NIM,
- Telegram,
- GitHub API,
- LinkedIn network access.

Tests must never post to a real LinkedIn account.

---

## 15. Code Quality

Prefer:

- Python type hints everywhere,
- Pydantic models at boundaries,
- small async functions,
- dependency injection,
- explicit return types,
- deterministic routing,
- narrow interfaces,
- structured logging,
- descriptive names.

Avoid:

- global mutable clients,
- hidden network calls,
- deep inheritance,
- untyped dictionaries passed across layers,
- giant orchestration functions,
- duplicated retry logic,
- duplicated config loading,
- framework abstractions that hide safety-critical behavior.

Use comments to explain why a constraint exists, not to restate obvious code.

---

## 16. Dependency Management

Use `uv`.

Commit:

```text
pyproject.toml
uv.lock
```

Do not manually edit `uv.lock`.

When changing dependencies:

```bash
uv add <package>
uv remove <package>
uv lock
uv sync
```

Keep LangChain/LangGraph dependencies explicit rather than relying on large umbrella installs where a narrower package is sufficient.

After dependency changes, run the full test suite.

---

## 17. Common Development Commands

Use the repository's actual configured commands if they differ.

Typical commands:

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Local dry run:

```bash
uv run python scripts/run_scout_dry.py
```

Orchestration entrypoints:

```bash
uv run python -m agent.orchestration.scout_flow
uv run python -m agent.orchestration.execute_flow
uv run python -m agent.orchestration.health_check_flow
```

Before finishing a code change, run the relevant focused tests and then the full unit suite where practical.

---

## 18. Security Rules

Never commit:

- `.env`,
- API keys,
- bot tokens,
- GitHub PATs,
- encryption keys,
- decrypted LinkedIn session state,
- cookies,
- raw credentials,
- private debug captures containing credentials.

Never print secrets in logs.

Redact secrets from exception context.

Do not weaken sender authorization, TTL checks, daily caps, idempotency controls, or the circuit breaker merely to make a test pass.

Security-sensitive tests should test the failure path, not only the happy path.

---

## 19. Platform-Risk Boundary

This repository automates interaction with LinkedIn through a browser.

Human approval does not make browser automation compliant with LinkedIn's terms.

Do not represent anti-detection techniques as making the automation safe, invisible, or compliant.

Do not add features designed to defeat CAPTCHAs, checkpoints, account restrictions, or other access controls.

If LinkedIn presents an enforcement or verification challenge, halt and require manual operator intervention.

---

## 20. Scope Guardrails

Unless a task explicitly changes product scope, do not add:

- automated connection requests,
- automated DMs,
- automated profile visits,
- automatic likes,
- multi-account support,
- multi-tenant support,
- autonomous approval,
- autonomous retry of failed LinkedIn writes,
- CAPTCHA solving,
- browser-fingerprint evasion intended to bypass platform controls.

Keep v1 focused on:

- scouting feed posts,
- triaging candidates,
- drafting comments/post ideas,
- human approval,
- bounded execution,
- audit/state tracking.

---

## 21. Making Architectural Changes

Before changing any of these, update the technical specification as part of the same change:

- approval mechanism,
- persistence model,
- LangGraph graph boundaries,
- LLM provider,
- browser automation strategy,
- GitHub Actions trigger model,
- Telegram relay architecture,
- daily caps,
- circuit breaker behavior,
- state schemas.

Do not silently introduce a second architecture beside the documented one.

If a requested change conflicts with an invariant, surface the conflict clearly in the PR/change summary.

---

## 22. Pull Request / Change Completion Checklist

Before considering a change complete, verify:

- [ ] behavior matches the implementation plan,
- [ ] HITL approval cannot be bypassed,
- [ ] safety rules remain deterministic,
- [ ] graph routing is explicit and tested,
- [ ] LLM outputs are schema-validated,
- [ ] no secret/session data is committed,
- [ ] dry-run performs no LinkedIn writes,
- [ ] duplicate execution remains safe,
- [ ] challenge detection still halts the system,
- [ ] tests cover new success and failure paths,
- [ ] `uv run pytest` passes,
- [ ] linting passes,
- [ ] documentation/config examples are updated when required.

---

## 23. Agent Working Style

When modifying this repository:

1. Read the relevant implementation-plan section before editing code.
2. Inspect existing schemas, graph state, and tests before adding new abstractions.
3. Make the smallest coherent change that satisfies the task.
4. Preserve safety checks even when they appear redundant.
5. Prefer extending an existing service or graph node over creating a parallel path.
6. Add tests with the implementation.
7. Do not perform unrelated cleanup in the same change.
8. Mention assumptions or architecture deviations explicitly in the final change summary.
9. Never claim a live LinkedIn action was tested unless it actually was.
10. Never execute a real LinkedIn write as part of automated testing.

The central design principle is:

> LLMs may recommend and draft. Humans authorize. Deterministic code validates. Only then may automation execute.
