# Configuration Reference Guide

All runtime settings in LinkedAide are loaded and strictly validated via `pydantic-settings` in [`src/agent/config/settings.py`](../src/agent/config/settings.py).

LinkedAide uses a **centralized, fail-closed configuration architecture** backed by Cloudflare Workers KV (`STATE_BACKEND=kv`). Operational settings and provider credentials live authoritatively in Cloudflare KV (`config:runtime`), keeping your GitHub Actions runners, Cloudflare Worker relay, and Desktop app in lockstep with zero manual dashboard synchronization. (An optional AES-256 encrypted vault `secrets:vault_enc` is also supported for CLI secret encryption).

---

## Centralized Cloudflare KV Configuration (Production Mode)

When using Cloudflare KV (`STATE_BACKEND=kv`, the default in production and CI):

1. **Bootstrap Credentials (Configured Once in GitHub Secrets & `.env`):**
   Only the essential bootstrap credentials remain in your local `.env` and GitHub Secrets:
   - `CLOUDFLARE_ACCOUNT_ID`
   - `CLOUDFLARE_KV_NAMESPACE_ID`
   - `CLOUDFLARE_API_TOKEN`
   - `SESSION_ENCRYPTION_KEY` (Required by runners to decrypt LinkedIn session cookies)
   - `LINKEDIN_SESSION_STATE_ENC` (Encrypted LinkedIn session state)
2. **Authoritative Cloudflare KV Store (`config:runtime` in KV):**
   Stores all operational runtime parameters (active LLM models, rate limits, focus areas, persona, hyperparameters) and credentials (LLM provider keys, Telegram bot token, chat ID, residential proxy URL) in your private Cloudflare Workers KV namespace.
3. **Desktop App as Unified Control Plane:**
   All configuration settings and credentials can be inspected and updated directly through the Desktop App Settings UI with Apple HIG-aligned native controls and automatic remote KV synchronization.
4. **Strict Fail-Closed Policy:**
   If a required operational setting or credential is missing from KV in production, the agent halts with a descriptive `ConfigError` indicating the missing key.

### Managing Remote Configuration via CLI

The unified `agent config` command lets you inspect, update, and manage your remote Cloudflare KV configuration directly:

```bash
# Display all operational settings and masked secrets currently stored in Cloudflare KV:
uv run agent config show

# Update an operational setting (e.g. when changing or switching a model):
uv run agent config set nim_model_primary nvidia/nemotron-3-ultra-550b-a55b
uv run agent config set max_comments_per_day 10
uv run agent config set user_focus_areas '["AI Agents", "Python", "Distributed Systems"]'

# Encrypt and store an API key or secret in the KV vault:
uv run agent config set-secret nvidia_nim_api_key nvapi-your-new-key
uv run agent config set-secret openai_api_key sk-your-key

# One-time migration: Push current local settings and secrets into Cloudflare KV:
uv run agent config init-from-env
```

---

## Complete Settings Reference

| Environment Variable                                      | Type                  | Default                                                                                                                                                        | Storage Location (Production KV Mode) | Description                                                                                                                                   |
| --------------------------------------------------------- | --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------: | --------------------------------------------------------------------------------------------------------------------------------------------- |
| **LLM Provider & API Keys**                               |                       |                                                                                                                                                                |                                        |                                                                                                                                               |
| `LLM_PROVIDER`                                            | `string`              | `nvidia`                                                                                                                                                       |            `config:runtime`            | Selected LLM provider: `nvidia`, `openai`, `anthropic`, `gemini`, `groq`, `ollama`, or `openai-compatible`.                                   |
| `NVIDIA_NIM_API_KEY`                                      | `string`              | _(Required if nvidia)_                                                                                                                                         |            `config:runtime`            | NVIDIA NIM API key (`nvapi-...`). Also powers edge draft tone rewrites in the Desktop App.                                                   |
| `OPENAI_API_KEY`                                          | `string`              | `None` _(Required if openai)_                                                                                                                                  |            `config:runtime`            | OpenAI API key (`sk-...`).                                                                                                                    |
| `ANTHROPIC_API_KEY`                                       | `string`              | `None` _(Required if anthropic)_                                                                                                                               |            `config:runtime`            | Anthropic API key (`sk-ant-...`).                                                                                                             |
| `GEMINI_API_KEY`                                          | `string`              | `None` _(Required if gemini)_                                                                                                                                  |            `config:runtime`            | Google Gemini API key (`AIza...`). `GOOGLE_API_KEY` also accepted as alias.                                                                   |
| `GROQ_API_KEY`                                            | `string`              | `None` _(Required if groq)_                                                                                                                                    |            `config:runtime`            | Groq API key (`gsk_...`).                                                                                                                     |
| `OLLAMA_BASE_URL`                                         | `string`              | `http://localhost:11434`                                                                                                                                       |            `config:runtime`            | Base URL for local or remote Ollama server.                                                                                                   |
| **Model Selection & Parameters**                          |                       |                                                                                                                                                                |                                        |                                                                                                                                               |
| `LLM_MODEL_PRIMARY` / `NIM_MODEL_PRIMARY`                 | `string`              | Provider default _(e.g. `nvidia/nemotron-3-ultra-550b-a55b`, `gpt-4o`, `claude-3-5-sonnet-latest`, `gemini-2.0-flash`, `llama-3.3-70b-versatile`, `llama3.2`)_ |            `config:runtime`            | Primary LLM model for comment and post drafting.                                                                                              |
| `LLM_MODEL_FALLBACK` / `NIM_MODEL_FALLBACK`               | `string`              | Provider default _(e.g. `openai/gpt-oss-20b`, `gpt-4o-mini`, `claude-3-5-haiku-latest`, `gemini-1.5-flash`, `llama-3.1-8b-instant`, `llama3.2`)_               |            `config:runtime`            | Fallback LLM model if primary encounters rate limit or provider error.                                                                        |
| `LLM_MODEL_TRIAGE` / `NIM_MODEL_TRIAGE`                   | `string`              | `None` _(uses provider triage default or primary)_                                                                                                             |            `config:runtime`            | Optional lightweight LLM dedicated exclusively to fast post triage.                                                                           |
| `NIM_MODEL_VISION`                                        | `string`              | `meta/llama-3.2-11b-vision-instruct`                                                                                                                           |            `config:runtime`            | Dedicated multimodal vision model for inspecting images and infographics in LinkedIn posts.                                                   |
| `NIM_TEMPERATURE`                                         | `float` (`0.0`-`2.0`) | `0.2`                                                                                                                                                          |            `config:runtime`            | Sampling temperature for LLM text generation.                                                                                                 |
| `NIM_TOP_P`                                               | `float` (`0.0`-`1.0`) | `None`                                                                                                                                                         |            `config:runtime`            | Optional nucleus sampling probability.                                                                                                        |
| `NIM_TIMEOUT_SECONDS`                                     | `float` (`>= 1.0`)    | `60.0`                                                                                                                                                         |            `config:runtime`            | Request timeout for LLM API calls in seconds.                                                                                                 |
| `NIM_MAX_TOKENS`                                          | `int` (`>= 1`)        | `1024`                                                                                                                                                         |            `config:runtime`            | Maximum token limit per generation response.                                                                                                  |
| `NIM_BASE_URL`                                            | `string`              | `None`                                                                                                                                                         |            `config:runtime`            | Custom base URL for private NIM or custom OpenAI-compatible endpoints.                                                                        |
| `NIM_MAX_CONCURRENCY`                                     | `int` (`>= 1`)        | `4`                                                                                                                                                            |            `config:runtime`            | Maximum concurrent requests to the LLM provider.                                                                                              |
| **Telegram Bot Gateway**                                  |                       |                                                                                                                                                                |                                        |                                                                                                                                               |
| `TELEGRAM_BOT_TOKEN`                                      | `string`              | _(Required)_                                                                                                                                                   |            `config:runtime`            | Telegram bot token obtained from `@BotFather`. Verified live in Desktop App.                                                                  |
| `TELEGRAM_AUTHORIZED_CHAT_ID`                             | `int`                 | _(Required)_                                                                                                                                                   |            `config:runtime`            | Numeric Telegram user/chat ID permitted to approve actions.                                                                                   |
| **LinkedIn Session & Security**                           |                       |                                                                                                                                                                |                                        |                                                                                                                                               |
| `SESSION_ENCRYPTION_KEY`                                  | `string`              | `None`                                                                                                                                                         |      **Bootstrap (`.env` / Secret)**   | Fernet 32-byte url-safe base64 encryption key (decrypts storage state in headless runner).                                                     |
| `LINKEDIN_SESSION_STATE_ENC`                              | `string`              | `None`                                                                                                                                                         |      **Bootstrap (`.env` / Secret)**   | Base64-encoded encrypted Playwright session state string.                                                                                     |
| `LINKEDIN_STORAGE_STATE_PATH`                             | `Path`                | `storage_state.json`                                                                                                                                           |             Runner local               | Path to runner-local decrypted storage state.                                                                                                 |
| **Persona & Content Customization**                       |                       |                                                                                                                                                                |                                        |                                                                                                                                               |
| `USER_FOCUS_AREAS`                                        | `list[str]`           | `[]`                                                                                                                                                           |            `config:runtime`            | Comma-separated list or JSON array of domain topics to evaluate.                                                                              |
| `SCOUT_TARGET_URLS`                                       | `list[str]`           | `[]`                                                                                                                                                           |            `config:runtime`            | Explicit LinkedIn feed URLs to scout (e.g. hashtag feeds, creator activity URLs).                                                             |
| `TARGET_HASHTAGS`                                         | `list[str]`           | `[]`                                                                                                                                                           |            `config:runtime`            | Specific LinkedIn hashtags to scout (e.g. `['python', 'ai', '#agentic']`).                                                                    |
| `USER_PERSONA`                                            | `string`              | `""`                                                                                                                                                           |            `config:runtime`            | Professional background and tone guidelines for drafting.                                                                                     |
| `MAX_COMMENT_WORDS`                                       | `int` (`10`-`200`)    | `80`                                                                                                                                                           |            `config:runtime`            | Target maximum word count for drafted comments.                                                                                               |
| `ENABLE_PRE_COMMENT_REACTION`                             | `bool`                | `false`                                                                                                                                                        |            `config:runtime`            | Automatically submit a reaction to target post before publishing comment.                                                                     |
| `DEFAULT_REACTION_TYPE`                                   | `string`              | `like`                                                                                                                                                         |            `config:runtime`            | Default reaction type (`like`, `celebrate`, `support`, `love`, `insightful`, `curious`).                                                       |
| **Safety & Rate Limits**                                  |                       |                                                                                                                                                                |                                        |                                                                                                                                               |
| `MAX_COMMENTS_PER_DAY`                                    | `int` (`>= 0`)        | `5`                                                                                                                                                            |            `config:runtime`            | Hard daily maximum for approved LinkedIn comments.                                                                                            |
| `MAX_POSTS_PER_DAY`                                       | `int` (`>= 0`)        | `1`                                                                                                                                                            |            `config:runtime`            | Hard daily maximum for original LinkedIn posts.                                                                                               |
| `MAX_CONNECTIONS_PER_DAY`                                 | `int` (`>= 0`)        | `10`                                                                                                                                                           |            `config:runtime`            | Hard daily maximum for approved LinkedIn connection requests.                                                                                 |
| `MAX_SUGGESTIONS_PER_RUN`                                 | `int` (`>= 1`)        | `3`                                                                                                                                                            |            `config:runtime`            | Maximum suggestions sent to Telegram per scout run.                                                                                           |
| `PENDING_ACTION_TTL_HOURS`                                | `int` (`>= 1`)        | `12`                                                                                                                                                           |            `config:runtime`            | Time-to-live in hours before pending approvals expire.                                                                                        |
| `AGENT_PAUSED`                                            | `bool`                | `false`                                                                                                                                                        |            `config:runtime`            | Global kill switch: when `true`, all workflows pause immediately.                                                                             |
| `DRY_RUN`                                                 | `bool`                | `false`                                                                                                                                                        |        CLI Flag / `config:runtime`     | When `true`, mocks live LinkedIn writes and logs intended actions.                                                                            |
| **Network & Diagnostics**                                 |                       |                                                                                                                                                                |                                        |                                                                                                                                               |
| `RESIDENTIAL_PROXY_URL`                                   | `string`              | `None`                                                                                                                                                         |       `config:runtime` / `.env`        | Optional HTTP/SOCKS5 proxy endpoint (`http://user:pass@host:port`) for stealth feed scraping.                                                 |
| `LOG_LEVEL`                                               | `string`              | `INFO`                                                                                                                                                         |       `config:runtime` / `.env`        | Diagnostics and execution log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`).                                                                |
| `STATE_DIR`                                               | `Path`                | `state`                                                                                                                                                        |                  `.env`                | Path to directory containing version-controlled JSON state (used when `STATE_BACKEND=git`).                                                    |
| **State Persistence & Cloudflare KV / R2**                |                       |                                                                                                                                                                |                                        |                                                                                                                                               |
| `STATE_BACKEND`                                           | `string`              | `kv` _(CI & Prod)_ / `git` _(Local)_                                                                                                                           |      **Bootstrap (`.env` / Secret)**   | Durable state backend: `kv` (Cloudflare Workers KV) or `git` (Git-as-database).                                                               |
| `CLOUDFLARE_ACCOUNT_ID`                                   | `string`              | `None`                                                                                                                                                         |      **Bootstrap (`.env` / Secret)**   | 32-character Cloudflare Account ID (Required when `STATE_BACKEND=kv`).                                                                        |
| `CLOUDFLARE_KV_NAMESPACE_ID`                              | `string`              | `None`                                                                                                                                                         |      **Bootstrap (`.env` / Secret)**   | 32-character Workers KV Namespace ID for `LINKEDIN_AGENT_KV` (Required when `STATE_BACKEND=kv`).                                              |
| `CLOUDFLARE_API_TOKEN`                                    | `string`              | `None`                                                                                                                                                         |      **Bootstrap (`.env` / Secret)**   | Cloudflare API Token with `Account.Workers KV Storage: Edit` permission (Required when `STATE_BACKEND=kv`).                                   |
| `WORKER_URL`                                              | `string`              | `None`                                                                                                                                                         |            `config:runtime`            | Base URL of deployed Cloudflare Worker relay (e.g. `https://relay.your-subdomain.workers.dev`).                                               |
| `DESKTOP_API_SECRET`                                      | `string`              | `None`                                                                                                                                                         |       Worker Secret / Desktop          | High-entropy API secret authenticating desktop client requests, WebSocket subscriptions, and R2 uploads.                                      |
| **Cloudflare Edge Relay (infra/edge-relay)** |                       |                                                                                                                                                                |                                        |                                                                                                                                               |
| `TELEGRAM_WEBHOOK_SECRET`                                 | `string`              | _(Required)_                                                                                                                                                   |             Worker Secret              | Shared secret token verified via `X-Telegram-Bot-Api-Secret-Token`. Generate with `uv run python scripts/generate_secrets.py --type webhook`. |
| `GITHUB_DISPATCH_PAT`                                     | `string`              | _(Required)_                                                                                                                                                   |             Worker Secret              | GitHub PAT with `repo` / `Contents: Read and write` permissions to trigger `repository_dispatch`.                                             |
| `GITHUB_REPO_OWNER`                                       | `string`              | _(Required)_                                                                                                                                                   |             Worker Secret              | GitHub username or organization name.                                                                                                         |
| `GITHUB_REPO_NAME`                                        | `string`              | _(Required)_                                                                                                                                                   |             Worker Secret              | GitHub repository name (e.g. `linkedaide`).                                                                                                   |
| `NVIDIA_NIM_API_KEY`                                      | `string`              | _(Optional override)_                                                                                                                                          |       Worker Secret / KV fallback      | NIM API key. If omitted in Worker secrets, dynamically resolved from KV `config:runtime`.                                                     |
| `TELEGRAM_BOT_TOKEN`                                      | `string`              | _(Optional override)_                                                                                                                                          |       Worker Secret / KV fallback      | Bot token. If omitted in Worker secrets, dynamically resolved from KV `config:runtime`.                                                       |
| `TELEGRAM_AUTHORIZED_CHAT_ID`                             | `int`                 | _(Optional override)_                                                                                                                                          |       Worker Secret / KV fallback      | Chat ID. If omitted in Worker secrets, dynamically resolved from KV `config:runtime`.                                                         |
| `LLM_BASE_URL`                                            | `string`              | `https://integrate.api.nvidia.com/v1`                                                                                                                          |             Worker Secret              | Custom base URL if using a custom endpoint or proxy for Worker LLM calls.                                                                     |

---

## Operational Tuning Guide

### 1. Persona & Focus Area Tuning

The agent tailors its triage decisions and comment drafts based on `USER_FOCUS_AREAS` and `USER_PERSONA`:

```ini
# Comma-separated string format:
USER_FOCUS_AREAS="AI Agents, Python, Distributed Systems, Software Architecture, LLM Engineering"

# Persona prompt injection:
USER_PERSONA="Principal AI Systems Engineer sharing technical insights, architecture patterns, and practical experience. Tone is concise, collegial, and evidence-driven. Avoid generic praise and buzzwords."
```

### 2. Multi-Provider LLM Setup

The agent natively supports multiple LLM providers: **NVIDIA NIM**, **OpenAI**, **Anthropic**, **Google Gemini**, **Groq**, **Ollama**, and **OpenAI-compatible** endpoints.

#### Installing Optional Provider SDKs

Install provider integrations using `uv`:

```bash
# OpenAI or OpenAI-compatible (Together, vLLM, OpenRouter)
uv add langchain-openai

# Anthropic Claude
uv add langchain-anthropic

# Google Gemini
uv add langchain-google-genai

# Groq
uv add langchain-groq

# Ollama (local)
uv add langchain-ollama

# Or install all providers
uv sync --extra all-providers
```

#### Provider Examples

**1. OpenAI:**

```ini
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
# Defaults: primary=gpt-4o, fallback=gpt-4o-mini, triage=gpt-4o-mini
```

**2. Anthropic:**

```ini
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
# Defaults: primary=claude-3-5-sonnet-latest, fallback=claude-3-5-haiku-latest, triage=claude-3-5-haiku-latest
```

**3. Google Gemini:**

```ini
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIzaSy...
# Defaults: primary=gemini-2.0-flash, fallback=gemini-1.5-flash, triage=gemini-1.5-flash
```

**4. Groq:**

```ini
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...
# Defaults: primary=llama-3.3-70b-versatile, fallback=llama-3.1-8b-instant, triage=llama-3.1-8b-instant
```

**5. Ollama (Local):**

```ini
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
# Defaults: primary=llama3.2, fallback=llama3.2, triage=llama3.2
```

**6. Custom OpenAI-Compatible (Together AI, vLLM, OpenRouter):**

```ini
LLM_PROVIDER=openai-compatible
NIM_BASE_URL=https://api.together.xyz/v1
OPENAI_API_KEY=your-together-api-key
LLM_MODEL_PRIMARY=meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo
LLM_MODEL_FALLBACK=meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo
```

### 3. Tuning Model Concurrency & Performance

- For high-throughput feeds, configure `LLM_MODEL_TRIAGE` to a fast model (e.g. `gpt-4o-mini`, `gemini-1.5-flash`, `llama-3.1-8b-instant`) for fast initial screening, while retaining a higher capability model for drafting.
- Adjust `NIM_MAX_CONCURRENCY=4` to balance throughput with provider rate limits.

### 4. Adjusting Safety Caps

- For cautious account growth, keep `MAX_COMMENTS_PER_DAY=3` to `5`.
- Set `PENDING_ACTION_TTL_HOURS=12` to ensure comments are posted while discussions are still fresh.

### 5. Telegram Webhook C2 & Interactive Editing

The Cloudflare Worker relay supports direct operator commands and interactive draft revision:

| Command           | Syntax / Usage               | Description                                                                                   |
| ----------------- | ---------------------------- | --------------------------------------------------------------------------------------------- |
| `/status`         | `/status`                    | View system state, circuit breaker health, and daily quota counts.                            |
| `/pending`        | `/pending`                   | List actions currently awaiting review with preview snippets.                                 |
| `/stats`          | `/stats`                     | View today's counts and historical execution vs rejection stats.                              |
| `/pause`          | `/pause`                     | Temporarily halt automated feed scouting and action dispatching.                              |
| `/resume`         | `/resume`                    | Resume automated operations and scouting schedules.                                           |
| `/clear_incident` | `/clear_incident`            | Reset tripped circuit breaker and restore operations.                                         |
| `/help`           | `/help`                      | Display command syntax and interactive editing guidance.                                      |
| `/edit`           | `/edit <item_id> <new text>` | Replace draft text for a pending suggestion card.                                             |
| `/tone`           | `/tone <item_id> <tone>`     | Rewrite draft using AI (`contrarian`, `data_driven`, `concise`, `inquisitive`, `supportive`). |

**Interactive Card Replies:**
Operators can reply directly to any Telegram suggestion card:

- Reply with plain text to overwrite the draft text with your custom edit.
- Reply with a tone name (or `/tone <name>`) to invoke edge LLM rewriting and update the card live.

---

## 6. Desktop Control Panel Settings Architecture

The Desktop App (`desktop/`) serves as the visual control plane for LinkedAide. It connects directly to your deployed Cloudflare Worker (`/api/config`) and synchronizes all operational configuration and provider credentials with Cloudflare Workers KV (`config:runtime`) as the single source of truth.

### Settings Cards & Controls

1. **Telegram Approval & Bot Gateway (`TelegramApprovalCard.tsx`)**:
   - **Bot Token** (`TELEGRAM_BOT_TOKEN`): Your Telegram bot API token from `@BotFather`.
   - **Authorized Chat ID** (`TELEGRAM_AUTHORIZED_CHAT_ID`): Numeric Telegram user ID permitted to approve actions.
   - **Verify Bot Connection Action**: Calls the Cloudflare Worker `/api/telegram/verify` endpoint, which queries Telegram's `getMe` API. Instantly displays bot status, username (`@YourBot`), bot ID, and network latency badge before saving.

2. **AI Provider & Model Intelligence (`NimIntelligenceCard.tsx`)**:
   - **Active Provider**: Select among `NVIDIA NIM`, `OpenAI`, `Anthropic`, `Google Gemini`, `Groq`, `Ollama`, or `OpenAI-Compatible`.
   - **Context-Aware API Key**: Automatically switches input label and placeholder to match the selected provider (`nvapi-...`, `sk-...`, `AIza...`, `gsk_...`).
   - **Primary Model** (`LLM_MODEL_PRIMARY` / `NIM_MODEL_PRIMARY`): Defaults to `nvidia/nemotron-3-ultra-550b-a55b` for NVIDIA NIM. Dropdown provides curated high-capability models with custom entry option.
   - **Fallback Model** (`LLM_MODEL_FALLBACK` / `NIM_MODEL_FALLBACK`): Defaults to `openai/gpt-oss-20b` for NVIDIA NIM. Engaged automatically if primary encounters rate limits or transient errors.
   - **Specialized Roles**:
     - **Triage Model** (`NIM_MODEL_TRIAGE`): Lightweight, cost-effective model dedicated to fast initial feed screening.
     - **Vision Model** (`NIM_MODEL_VISION`): Multimodal model (default `meta/llama-3.2-11b-vision-instruct`) for analyzing image and infographic attachments in LinkedIn posts.
   - **Inference Hyperparameters**:
     - **Temperature**: Precision slider (`0.0` - `2.0`, step `0.05`, default `0.20`).
     - **Max Tokens**: Token cap slider (`128` - `4096`, step `64`, default `1024`).
     - **Request Timeout**: Timeout in seconds (`5` - `300s`, default `60s`).
     - **Custom Base URL** (`NIM_BASE_URL`): Custom inference endpoint for private NIM, vLLM, Ollama, or OpenRouter deployments.

3. **Rate Limits & Safety Caps (`SafetyLimitsCard.tsx`)**:
   - **Daily Comment Limit** (`MAX_COMMENTS_PER_DAY`): Default `5`.
   - **Daily Post Limit** (`MAX_POSTS_PER_DAY`): Default `1`.
   - **Daily Connection Limit** (`MAX_CONNECTIONS_PER_DAY`): Default `10`.
   - **Suggestions Per Run** (`MAX_SUGGESTIONS_PER_RUN`): Default `3`.
   - **Pending Action TTL** (`PENDING_ACTION_TTL_HOURS`): Default `12` hours.
   - **Pre-Comment Reaction**: Enable/disable automatic reactions and configure default reaction type (`like`, `celebrate`, `support`, `love`, `insightful`, `curious`).

4. **Targeting & Persona Tuning (`TargetingPersonaCard.tsx`)**:
   - **Focus Areas** (`USER_FOCUS_AREAS`): Tag-based topic entry scored during post triage.
   - **Scout Target URLs** (`SCOUT_TARGET_URLS`): Explicit LinkedIn URLs to scout.
   - **Target Hashtags** (`TARGET_HASHTAGS`): Specific hashtags to monitor.
   - **Persona Instructions** (`USER_PERSONA`): Background and tone guidance.
   - **Comment Word Limit** (`MAX_COMMENT_WORDS`): Max length constraint (default `80`).

5. **System & Network Diagnostics (`SystemDiagnosticsCard.tsx`)**:
   - **Residential Proxy Tunnel URL** (`RESIDENTIAL_PROXY_URL`): Optional proxy endpoint (`http://user:pass@host:port`) with a **Test Proxy** button that tests tunnel latency through the Cloudflare Worker.
   - **System Diagnostics Log Level** (`LOG_LEVEL`): Segmented control for `DEBUG`, `INFO`, `WARNING`, and `ERROR`.
   - **Single Source of Truth**: Eliminates local secret vault files (`vault.enc`). Configuration changes are committed directly to Cloudflare KV (`config:runtime`) and immediately shared across cloud runners, the Telegram relay worker, and the desktop app.
