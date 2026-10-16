# LinkedAide — Human-in-the-Loop AI Agent for LinkedIn

<p align="center">
  <img src="assets/logo.png" alt="LinkedAide" width="480" />
</p>

An enterprise-grade, human-supervised LinkedIn automation agent orchestrating candidate discovery, LLM triage, personalized comment drafting, thought leadership post ideation, Telegram human approval, and verified Playwright browser execution.

<p align="center">
  <a href="https://github.com/mahdi-behnam/linkedaide/releases/latest">
    <img src="https://img.shields.io/badge/Download%20Desktop%20App-Latest%20Release-0077B5?style=for-the-badge&logo=electron&logoColor=white" alt="Download Desktop App" />
  </a>
  <a href="https://github.com/mahdi-behnam/linkedaide/releases">
    <img src="https://img.shields.io/github/v/release/mahdi-behnam/linkedaide?style=for-the-badge&color=2ea44f&label=Version" alt="Latest Version" />
  </a>
</p>

<p align="center">
  <b>Direct Downloads:</b>&nbsp;
  <a href="https://github.com/mahdi-behnam/linkedaide/releases/latest/download/LinkedAide-Setup.exe">🪟 Windows (.exe)</a> &nbsp;•&nbsp;
  <a href="https://github.com/mahdi-behnam/linkedaide/releases/latest/download/LinkedAide.dmg">🍏 macOS (.dmg)</a> &nbsp;•&nbsp;
  <a href="https://github.com/mahdi-behnam/linkedaide/releases/latest/download/LinkedAide.AppImage">🐧 Linux (.AppImage)</a>
</p>

---

## ⚡ Quickstart for New Operators

LinkedAide pairs your own private cloud runner with a cross-platform desktop control panel:

```text
1. Fork Repository  ──>  2. Download Desktop App  ──>  3. Connect Your Secrets
```

1. **Fork this Repository**: Click **[Fork](https://github.com/mahdi-behnam/linkedaide/fork)** at the top right to create your private copy for running GitHub Actions workflows.
2. **Download the Desktop App**: Grab the installer for your OS ([Windows](https://github.com/mahdi-behnam/linkedaide/releases/latest/download/LinkedAide-Setup.exe) / [macOS](https://github.com/mahdi-behnam/linkedaide/releases/latest/download/LinkedAide.dmg) / [Linux](https://github.com/mahdi-behnam/linkedaide/releases/latest/download/LinkedAide.AppImage)).
3. **Configure Settings**: Open Desktop **Settings**, enter your GitHub username & repository name, paste your GitHub PAT (with `workflow` and `repo` permissions), and add your API keys.
4. **Customize Your Voice**: Copy [`persona/profile.example.yaml`](persona/profile.example.yaml) to `persona/profile.yaml` to tailor the LLM to your personal industry expertise and stances.
5. **Keep Up to Date (1-Click Sync)**: Whenever a new version is released, open your forked repository on GitHub, click **Sync fork** ▾, and select **Update branch** to instantly keep your cloud runner in sync with your desktop app.

👉 See the complete **[Setup Guide](docs/setup-guide.md)** for detailed instructions on extracting your encrypted session, syncing forks, and setting up Telegram approval cards.

---

## What This Assistant Does & How It Helps

This agent helps you build and maintain a strong, consistent, high-value LinkedIn presence while keeping you in complete control:

- 🔍 **Automated Feed Intelligence**: Periodically monitors your LinkedIn feed for high-signal posts matching your specific focus areas and industry topics.
- 🎯 **Intelligent Relevance Triage**: Filters out noise, viral reposts, and low-signal fluff so you only engage in meaningful, substantive conversations.
- ✍️ **Contextual Comment Drafting**: Uses modern LLMs (NVIDIA NIM, OpenAI, Anthropic, Gemini, Groq, Ollama) and your custom persona to craft authentic, insightful comments that add value to the author's post.
- 💡 **Thought Leadership Post Ideation**: Proactively brainstorms and drafts original, standalone posts tailored to your technical domain and perspective.
- 📱 **1-Click Human Supervision via Telegram**: Delivers clean review cards with **Approve**, **Edit**, and **Reject** buttons directly to your phone. Nothing is ever published to LinkedIn without your explicit sign-off.
- 🛡️ **Safe, Deterministic Automation**: Submits approved actions through a stealthy Playwright browser session with daily limits, circuit breakers, anti-bot safeguards, and full audit logs.

---

## Architecture & Lifecycle

```text
LinkedIn Feed / Topics
        ↓
    ScoutGraph (Playwright Scraper)
        ↓
    LLM Triage (Relevance Filtering)
        ↓
    LLM Draft (Contextual Comment / Idea Generation)
        ↓
    Persist Pending Action (Cloudflare KV or state/pending/)
        ↓
    Telegram Review Card (Inline Buttons: Approve / Edit / Reject)
        ↓
    Operator Action on Phone
        ↓
    Execution Pathway:
    ┌──────────────────────────────────┬──────────────────────────────────┐
    │ Mode A: 24/7 Cloud Automation    │ Mode B: Local Operator Mode      │
    │ Telegram Webhook → Cloudflare    │ Long-polling listener            │
    │ Worker Relay → GitHub Dispatch   │ (uv run agent poll)              │
    │ → ExecuteGraph (GitHub Actions)  │ → ExecuteGraph (Local runner)    │
    └──────────────────────────────────┴──────────────────────────────────┘
        ↓
    Safety & Re-Validation (TTL, daily caps, session check, anti-bot)
        ↓
    Playwright Verified Execution (Live LinkedIn submission + DOM confirmation)
```

### Core Invariants

1. **Human Approval is Mandatory**: No LinkedIn write action (comment, post) may occur without explicit human authorization via Telegram.
2. **LangGraph Orchestrates Workflows**: Business logic and state transitions are deterministically coordinated using compiled LangGraph state graphs (`ScoutGraph`, `ExecuteGraph`, `IdeationGraph`, `HealthCheckGraph`).
3. **LangChain Owns LLM Integration**: Centralized LLM interactions via LangChain chat abstractions with structured Pydantic schema validation across supported providers.
4. **Deterministic Safety Enforcement**: Circuit breakers, daily action caps, pending action TTLs, authorized Telegram identity validation, and duplicate-action protection are strictly enforced in code—never solely via prompts.
5. **Durable State Persistence**: State is persisted either remotely via Cloudflare KV (eliminating Git merge conflicts and keeping drafts private in CI) or locally via Git/JSON state records under `state/`.

---

## Repository Structure

```text
.
├── .github/
│   └── workflows/             # Scheduled cron & event-driven GitHub Actions workflows
├── desktop/                   # Cross-platform Electron desktop control panel (React + TypeScript)
│   ├── electron/              # Electron main process, IPC handlers, tray manager, local runner
│   └── src/                   # React UI (Approval Queue, Studio, Outreach, Calendar, Analytics)
├── infra/
│   └── telegram-relay-worker/    # Cloudflare Worker relaying Telegram callbacks to GitHub
├── scripts/                   # Local operator utilities
│   ├── extract_linkedin_session.py  # Interactive browser login & session encrypter
│   ├── generate_secrets.py          # Cryptographic Fernet & webhook secret generator
│   ├── register_telegram_webhook.py # Telegram Bot webhook registration utility
│   └── run_scout_dry.py             # Standalone local dry-run script
├── src/
│   └── agent/
│       ├── cli/               # Unified CLI tool (setup, doctor, scout, ideate, thread-monitor, outreach)
│       ├── doctor/            # Diagnostic health check suite
│       ├── config/            # Pydantic Settings configuration & provider defaults
│       ├── errors.py          # Custom exception hierarchy
│       ├── models/            # Pydantic domain & persistence schemas
│       ├── llm/               # LangChain models, prompts, structured output service
│       ├── graphs/            # LangGraph state machines (Scout, Execute, Ideate, Health, Thread)
│       ├── browser/           # Playwright session management, stealth, scraper, executor
│       ├── telegram/          # Telegram bot client, review keyboards, draft editor
│       ├── state/             # StateStore backends (Cloudflare KV & GitStateStore)
│       ├── safety/            # Daily rate limiters and circuit breaker controls
│       └── orchestration/     # Flow runners (scout, ideate, poll, execute, health, thread, outreach)
├── state/                     # Local fallback storage (seen posts, history, pending drafts)
├── tests/                     # Comprehensive unit and integration test suites
├── docs/                      # In-depth architectural and operational guides
├── AGENTS.md                  # Development guidelines and coding invariants
├── SECURITY.md                # Security policy and credential handling rules
└── pyproject.toml             # Project dependencies and CLI entrypoints
```

---

## Getting Started

### Prerequisites

Ensure you have the following ready before setting up:

1. **Python `>= 3.11`** and the [`uv`](https://docs.astral.sh/uv/) package manager.
2. **Telegram Bot Token & Chat ID**:
   - Create a bot via [`@BotFather`](https://t.me/BotFather) on Telegram to get your `TELEGRAM_BOT_TOKEN`.
   - Get your numeric user ID via [`@userinfobot`](https://t.me/userinfobot) on Telegram for `TELEGRAM_AUTHORIZED_CHAT_ID`.
3. **LLM Provider API Key**:
   - NVIDIA NIM API key (`NVIDIA_NIM_API_KEY`) by default, or an API key for OpenAI, Anthropic Claude, Google Gemini, Groq, or local Ollama.
4. **Active LinkedIn Account**.
5. **Computer with a Graphical Browser**: Needed once to log into LinkedIn interactively and extract your session cookies.
6. _(Optional for 24/7 Cloud Automation)_: A GitHub repository and a free [Cloudflare](https://dash.cloudflare.com/) account.

---

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/mahdi-behnam/linkedaide.git
cd linkedaide

# 2. Install base dependencies (includes NVIDIA NIM integration)
uv sync

# (Optional) If you plan to use OpenAI, Anthropic, Gemini, Groq, or Ollama:
uv sync --extra all-providers

# 3. Install Playwright Chromium browser binary (Required)
uv run playwright install chromium
```

---

### Quick Start (4-Step Setup)

The repository provides an interactive onboarding wizard and diagnostic suite via the unified `agent` command:

```bash
# Step 1: Run the interactive setup wizard to configure your LLM provider, API keys,
# Telegram bot credentials, Fernet encryption key, and state backend:
uv run agent setup

# Step 2: Extract and encrypt your LinkedIn session (opens an interactive browser window
# for you to log in and pass 2FA, then safely encrypts cookies):
uv run python scripts/extract_linkedin_session.py

# Step 3: Run the diagnostic doctor to verify all credentials, APIs, and browser readiness:
uv run agent doctor

# Step 4: Test feed scouting safely in dry-run mode (generates real drafts in Telegram
# without performing any live writes on LinkedIn):
uv run agent scout --dry-run
```

_Tip: You can also inspect or copy [`.env.example`](.env.example) directly for manual configuration._

---

## Moving Forward: Choosing Your Operational Mode

Once you have completed the Quick Start, choose how you want the agent to operate:

### Mode A: Automated 24/7 in the Cloud (Recommended Production Setup)

In this mode, the agent runs entirely hands-free in the cloud:

1. **Scheduled Feed Scouting**: GitHub Actions (`scout.yml`) runs automatically on weekdays (e.g. 08:00, 13:00, 18:00 UTC) to discover relevant posts and deliver review cards to your phone.
2. **Scheduled Post Ideation**: GitHub Actions (`ideation.yml`) runs daily at 09:00 UTC to draft original standalone post ideas for your approval.
3. **1-Click Mobile Approval**: When you tap **Approve** in Telegram, your free Cloudflare Worker relay receives the webhook and triggers GitHub Actions (`execute.yml`) to publish the comment or post securely.
4. **Session Canary**: A scheduled health check (`session-health-check.yml`) warns you before session cookies expire.

👉 **To deploy Mode A, follow our step-by-step [End-to-End Setup & Deployment Guide](docs/setup-guide.md)** for Cloudflare Worker deployment and GitHub Secrets configuration.

---

### Mode B: Zero-Cloud Local Operator Mode

If you prefer to run everything locally on your own machine without Cloudflare Workers or GitHub Actions:

```bash
# 1. Scout your LinkedIn feed and deliver draft comment proposals to Telegram:
uv run agent scout

# 2. Brainstorm and draft original thought leadership post ideas:
uv run agent ideate

# 3. Start the local approval listener:
uv run agent poll
```

The `agent poll` command long-polls Telegram for your approval button clicks, draft edits, and operator commands, executing approved actions directly on your machine.

---

## Interactive Telegram Features

When suggestions arrive in Telegram, you have full control right from your chat:

- **Approve / Reject**: Dedicated buttons for comments, standalone posts, discussion replies, and connection requests.
- **Interactive Draft Edits**: Reply directly to any card with revised text to instantly update the draft in Cloudflare KV.
- **AI Tone Regeneration**: Reply with a tone name (or `/tone <name>`) to regenerate comments on the fly using edge LLM inference (`contrarian`, `data_driven`, `concise`, `inquisitive`, `supportive`).
- **Operator C2 Commands**:
  - `/status`: Real-time system operational state, circuit breaker health, and daily quota counts.
  - `/pending`: Summary list of all items currently awaiting review with excerpt previews.
  - `/stats`: Daily execution counters and all-time approval rate metrics.
  - `/pause`: Temporarily suspends automated feed scouting and action dispatching.
  - `/resume`: Unpauses and resumes scheduled workflows.
  - `/clear_incident`: Manually resets a tripped circuit breaker.
  - `/help`: Complete operator command and syntax guide.

---

## Desktop Control Panel & Advanced Subsystems

The repository includes a modern Electron desktop application in [`desktop/`](desktop/) that acts as your local command center:

- ⚡ **Real-Time Approval Queue**: Review drafted comments with live character countdowns, tone quick-pills (_Technical_, _Inquisitive_, _Contrarian_, _Concise_), and instant approval.
- 🔍 **⌘K Spotlight Command Palette**: Instant keyboard-driven navigation across all views and quick actions (pause/resume agent, toggle theme) with real-time fuzzy search.
- 🧭 **Tab Navigation History**: Browser-style history stack with functional back and forward buttons in the top control bar.
- 🩺 **Diagnostic Doctor Runner**: Direct execution of the full Python CLI `agent doctor` diagnostic suite from the desktop app with an embedded terminal output log viewer.
- ⌨️ **Power-User Keyboard Shortcuts**: Blazing fast triage with `[A]` (Approve), `[R]` (Reject), `[E]` (Edit), `[T]` (Cycle Tone), and `Cmd+Enter` (Submit).
- 🎙️ **Voice Audio Dictation**: Dictate custom revisions directly into comment and post drafts with native speech-to-text.
- ✍️ **Post Composer Studio & Visual Calendar**: Draft original LinkedIn thought leadership posts with above-the-fold cutoff indicators, rich tone rewriting, durable Cloudflare R2 media uploads (images and carousel PDFs), and scheduled publishing calendar synchronized across Cloudflare Workers KV and local storage.
- 🤝 **Connection Outreach Studio**: Automatically discover 2nd-degree connection candidates from qualifying feed posts, personalize 300-character invitation notes with tone assistance, and approve invitations subject to daily safety caps.
- 💬 **Multi-Turn Thread Reply Monitoring**: Automatically inspect active discussion threads where you commented, triage incoming replies with LLM intelligence, draft high-value follow-ups, and deliver Telegram cards for human sign-off.
- 🔔 **System Tray & WebSocket Sync**: Live <50ms push updates via Cloudflare Worker WebSockets with native OS desktop notifications and background polling fallback.

### 📥 1-Click Standalone Download (Recommended)

No Node.js, Python, or terminal setup required. Download the latest installer for your operating system directly from [GitHub Releases](https://github.com/mahdi-behnam/linkedaide/releases/latest):

| Platform       | Recommended Installer                                                                                                                                  | Alternative Format                                                                                                                                        |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 🪟 **Windows** | [**Download `LinkedAide-Setup.exe`**](https://github.com/mahdi-behnam/linkedaide/releases/latest/download/LinkedAide-Setup.exe) (NSIS Installer)       | [Download `LinkedAide-Portable.exe`](https://github.com/mahdi-behnam/linkedaide/releases/latest/download/LinkedAide-Portable.exe) (Standalone executable) |
| 🍏 **macOS**   | [**Download `LinkedAide.dmg`**](https://github.com/mahdi-behnam/linkedaide/releases/latest/download/LinkedAide.dmg) (Universal: Apple Silicon & Intel) | [Download `LinkedAide.zip`](https://github.com/mahdi-behnam/linkedaide/releases/latest/download/LinkedAide.zip)                                           |
| 🐧 **Linux**   | [**Download `LinkedAide.AppImage`**](https://github.com/mahdi-behnam/linkedaide/releases/latest/download/LinkedAide.AppImage) (Self-contained binary)  | [Download `LinkedAide.deb`](https://github.com/mahdi-behnam/linkedaide/releases/latest/download/LinkedAide.deb) (Debian / Ubuntu)                         |

> [!TIP]
> **Verification & Checksums**: Each release automatically attaches an aggregated `SHA256SUMS.txt` manifest on the [Releases](https://github.com/mahdi-behnam/linkedaide/releases/latest) page so you can verify the cryptographic integrity of your downloaded package.

<details>
<summary><b>ℹ️ First-Time Launch: Bypassing Unsigned App Warnings (SmartScreen / Gatekeeper)</b></summary>

Because LinkedAide is a free and open-source project, binaries are distributed without costly proprietary enterprise signing certificates. Your operating system may display a standard security prompt on first launch:

- **macOS**: Right-click (or `Ctrl`+click) `LinkedAide.app` in `/Applications` and select **Open** → Click **Open** in the confirmation dialog. (Alternatively, open _System Settings → Privacy & Security_ and click _Open Anyway_).
- **Windows**: Click **More info** on the blue Windows SmartScreen popup, then click **Run anyway**.
- **Linux**: Ensure the downloaded AppImage is executable before launching: `chmod +x LinkedAide.AppImage`.
</details>

_(Prefer to build, customize, or run from source? Check out [Building the Desktop App from Source](docs/setup-guide.md#building-the-desktop-app-from-source-developers))._

---

## Unified CLI Reference

The `agent` CLI provides access to all agent workflows:

| Command                                                          | Description                                                                             |
| ---------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `uv run agent setup`                                             | Interactive onboarding wizard for keys, providers, Telegram, and state.                 |
| `uv run agent doctor`                                            | Diagnostic suite testing Python, Chromium, settings, LLM, Telegram, and session.        |
| `uv run agent scout [--dry-run] [--headed]`                      | Scrapes feed, triages relevance, drafts comments, and sends Telegram cards.             |
| `uv run agent ideate [--dry-run]`                                | Generates original standalone post ideas based on your focus areas.                     |
| `uv run agent thread-monitor [--headed]`                         | Inspects active comment threads for new replies and drafts follow-up responses.         |
| `uv run agent outreach [--list] [--review]`                      | Manages 2nd-degree connection outreach queue, reviews candidates, and executes invites. |
| `uv run agent poll [--timeout SEC] [--once]`                     | Local listener polling Telegram for approvals, edits, and operator commands.            |
| `uv run agent execute [--action approve\|reject] [--item-id ID]` | Executes an approved or rejected LinkedIn action.                                       |
| `uv run agent health`                                            | Runs a read-only session validity and challenge check.                                  |

---

## Development & Testing

```bash
# Run unit and integration tests
uv run pytest

# Run fast CLI tests
uv run pytest tests/unit/test_cli.py

# Linting checks
uv run ruff check .

# Formatting checks
uv run ruff format --check .

# Static type checking
uv run mypy src tests scripts
```

---

## Documentation Directory

Deep dive into system details and operational guides in [`docs/`](docs/):

- **[End-to-End Setup & Deployment Guide](docs/setup-guide.md)**: Cloudflare Worker relay, Telegram webhook registration, and GitHub Actions CI/CD setup.
- **[Configuration Reference](docs/configuration.md)**: Full reference for all settings, LLM provider options, persona tuning, and safety limits.
- **[System Architecture & Design](docs/architecture.md)**: Detailed breakdown of LangGraph state graphs (`ScoutGraph`, `ExecuteGraph`, `IdeationGraph`), schemas, and invariants.
- **[Operational Troubleshooting](docs/troubleshooting.md)**: Recovery from challenge pages, session refresh, circuit breaker resets (`state/incident.json`), and DOM selector maintenance.

---

## Safety & Security

- **Dry-Run Mode**: Set `DRY_RUN=true` to test feed scraping, triage, drafting, and Telegram review cards with zero live write actions on LinkedIn.
- **Anti-Bot & Challenge Detection**: If LinkedIn serves a CAPTCHA, checkpoint, or unusual activity challenge, execution halts immediately and trips the circuit breaker to protect your account.
- **Zero Credential Commits**: Session cookies are encrypted with AES-256 Fernet keys. Plaintext session data and `.env` credentials are strictly excluded from version control. See [`SECURITY.md`](SECURITY.md).
- **Platform Disclaimer**: Automated platform interaction carries inherent terms-of-service risks. See [`DISCLAIMER.md`](DISCLAIMER.md).

---

## License

MIT License. See [LICENSE](LICENSE) for details.
