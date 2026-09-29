# LinkedIn Human-in-the-Loop AI Agent

An enterprise-grade, human-supervised LinkedIn automation agent orchestrating candidate discovery, LLM triage, human approval via Telegram, and verified Playwright browser execution.

## Architecture & Invariants

```text
LinkedIn feed
    ↓
ScoutGraph (Playwright Scraper)
    ↓
LLM Triage (NVIDIA NIM via LangChain)
    ↓
LLM Draft (Structured Pydantic Output)
    ↓
Persist Pending Action (state/pending/)
    ↓
Telegram Approval Request (Inline Buttons)
    ↓
Human Approve / Reject
    ↓
Telegram Relay / GitHub Repository Dispatch
    ↓
ExecuteGraph (Re-validation & Safety Checks)
    ↓
Playwright LinkedIn Action Execution
```

### Core Invariants

1. **Human Approval is Mandatory**: No LinkedIn write action (comment, post) may occur without explicit human authorization via Telegram.
2. **LangGraph Orchestrates Workflows**: Business logic and state transitions are deterministically coordinated using compiled LangGraph state graphs (`ScoutGraph`, `ExecuteGraph`, `HealthCheckGraph`).
3. **LangChain Owns LLM Integration**: Centralized LLM interactions via `ChatNVIDIA` with structured Pydantic schema validation.
4. **Deterministic Safety Enforcement**: Circuit breakers, daily action caps, pending action TTLs, authorized Telegram identity validation, and duplicate-action protection are strictly enforced in code—never solely via prompts.
5. **Durable Repository State**: All application state resides in version-controlled JSON/JSONL records under `state/`.

---

## Repository Structure

```text
.
├── .github/
│   └── workflows/          # GitHub Actions CI/CD and scheduled cron workflows
├── infra/
│   └── telegram-relay-worker/ # Cloudflare Worker relaying Telegram callbacks to GitHub
├── scripts/                # Local CLI utilities (session extraction, webhook setup, dry run)
│   ├── extract_linkedin_session.py
│   ├── register_telegram_webhook.py
│   └── run_scout_dry.py
├── src/
│   └── agent/
│       ├── config.py       # Pydantic Settings configuration
│       ├── errors.py       # Custom exception hierarchy
│       ├── models/         # Pydantic domain & persistence schemas
│       ├── llm/            # LangChain & NVIDIA NIM models, prompts, services
│       ├── graphs/         # LangGraph state graphs (Scout, Execute, HealthCheck)
│       ├── browser/        # Playwright session management, stealth, scraper, executor
│       ├── telegram/       # Telegram bot client and interactive keyboards
│       ├── state/          # GitStateStore persistence manager
│       ├── safety/         # Rate limiter and circuit breaker controls
│       └── orchestration/  # Flow entrypoints
├── state/                  # Durable version-controlled application state
│   ├── pending/            # Consumable pending action records
│   ├── seen_posts.json     # Tracking scraped post IDs to avoid re-evaluation
│   ├── history.jsonl       # Append-only audit log of executed actions
│   └── daily_counters.json # Daily rate-limit counters
├── tests/                  # Unit and integration test suites
├── AGENTS.md               # Coding guidelines and invariants for automated agents
├── SECURITY.md             # Security policy and secret handling rules
└── pyproject.toml          # Project configuration and dependencies
```

---

## Getting Started

### Prerequisites

- Python `>= 3.11`
- [`uv`](https://docs.astral.sh/uv/) package manager
- NVIDIA NIM API Key (`NVIDIA_NIM_API_KEY`)
- Telegram Bot Token (`TELEGRAM_BOT_TOKEN`) & Authorized Chat ID (`TELEGRAM_AUTHORIZED_CHAT_ID`)
- Encrypted LinkedIn Playwright storage state

### Installation

```bash
# Clone the repository
git clone https://github.com/mahdi-behnam/linkedin-hitl-agent.git
cd linkedin-hitl-agent

# Install dependencies and sync virtual environment
uv sync
```

### Quick Start & Configuration

The repository includes a unified CLI (`agent`) with an interactive onboarding wizard and diagnostic suite:

```bash
# 1. Run the interactive setup wizard to configure LLM provider, keys, Telegram, and state backend:
uv run agent setup

# 2. Verify all dependencies, credentials, and API connectivity:
uv run agent doctor

# 3. Extract and encrypt your LinkedIn session:
uv run python scripts/extract_linkedin_session.py

# 4. Test scouting in dry-run mode:
uv run agent scout --dry-run
```

Alternatively, copy `.env.example` directly:
```bash
cp .env.example .env
```
Refer to [`.env.example`](.env.example) for detailed variable documentation.

### CLI Reference

The unified `agent` command provides:

- `uv run agent doctor`: Comprehensive diagnostic suite (Python runtime, Playwright Chromium, configuration, LLM provider, Telegram connectivity, State backend, LinkedIn session).
- `uv run agent setup`: Interactive onboarding wizard guiding provider selection, API keys, Telegram credentials, Fernet encryption key generation, and state persistence.
- `uv run agent scout [--dry-run] [--headed]`: Run feed scraping, LLM triage, comment drafting, and Telegram review delivery.
- `uv run agent execute [--action approve|reject] [--item-id ID]`: Execute an approved or rejected LinkedIn action.
- `uv run agent health`: Read-only session health check canary.

---

## Development & Testing

```bash
# Run test suite
uv run pytest

# Run linter checks
uv run ruff check .

# Check formatting
uv run ruff format --check .

# Type checking
uv run mypy src tests scripts
```

---

## Documentation

Comprehensive guides and technical documentation are available in [`docs/`](docs/):

- **[End-to-End Setup & Deployment Guide](docs/setup-guide.md)**: Step-by-step instructions for Telegram bot setup, LinkedIn session encryption, Cloudflare Worker deployment, and GitHub Actions configuration.
- **[System Architecture & Design](docs/architecture.md)**: Deep dive into LangGraph state machines (`ScoutGraph`, `ExecuteGraph`, `HealthCheckGraph`), LLM triage pipelines, and Git-backed persistence.
- **[Configuration Reference](docs/configuration.md)**: Exhaustive reference of all runtime settings, environment variables, persona tuning, and safety limits.
- **[Operational Troubleshooting](docs/troubleshooting.md)**: Diagnostics for session expiry, circuit breaker recovery (`state/incident.json`), and selector maintenance.

---

## Safety & Security

- **Dry-Run Mode**: Set `DRY_RUN=true` to test the entire scouting, triage, drafting, and Telegram delivery pipeline without performing any live browser write actions on LinkedIn.
- **Bot & Challenge Protection**: If LinkedIn presents a CAPTCHA, checkpoint, or unusual activity challenge, execution halts immediately and trips the circuit breaker.
- **Credential Hygiene**: Authenticated session states and credentials are never stored in plaintext and never committed to Git. See [`SECURITY.md`](SECURITY.md) for full security practices.
- **Legal Disclaimer**: Automated interaction on LinkedIn carries inherent platform risks. See [`DISCLAIMER.md`](DISCLAIMER.md) before deploying.

---

## Contributing

We welcome contributions! Please see [`CONTRIBUTING.md`](CONTRIBUTING.md) for setup instructions, quality checks, and architectural guidelines, and review our [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

---

## License

MIT License. See [LICENSE](LICENSE) for details.
