# Configuration Reference Guide

All runtime settings in LinkedAide are loaded and strictly validated via `pydantic-settings` in [`src/agent/config/settings.py`](../src/agent/config/settings.py).

Settings can be provided via environment variables, a local `.env` file, or GitHub Actions Secrets / Variables.

---

## Complete Settings Reference

| Environment Variable                                      | Type                  | Default                                                                                                                                                        | Secret? | Description                                                                                                                                   |
| --------------------------------------------------------- | --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | :-----: | --------------------------------------------------------------------------------------------------------------------------------------------- |
| **LLM Provider & API Keys**                               |                       |                                                                                                                                                                |         |                                                                                                                                               |
| `LLM_PROVIDER`                                            | `string`              | `nvidia`                                                                                                                                                       |   No    | Selected LLM provider: `nvidia`, `openai`, `anthropic`, `gemini`, `groq`, `ollama`, or `openai-compatible`.                                   |
| `NVIDIA_NIM_API_KEY`                                      | `string`              | _(Required if nvidia)_                                                                                                                                         | **Yes** | NVIDIA NIM API key (`nvapi-...`).                                                                                                             |
| `OPENAI_API_KEY`                                          | `string`              | `None` _(Required if openai)_                                                                                                                                  | **Yes** | OpenAI API key (`sk-...`).                                                                                                                    |
| `ANTHROPIC_API_KEY`                                       | `string`              | `None` _(Required if anthropic)_                                                                                                                               | **Yes** | Anthropic API key (`sk-ant-...`).                                                                                                             |
| `GEMINI_API_KEY`                                          | `string`              | `None` _(Required if gemini)_                                                                                                                                  | **Yes** | Google Gemini API key (`AIza...`). `GOOGLE_API_KEY` also accepted as alias.                                                                   |
| `GROQ_API_KEY`                                            | `string`              | `None` _(Required if groq)_                                                                                                                                    | **Yes** | Groq API key (`gsk_...`).                                                                                                                     |
| `OLLAMA_BASE_URL`                                         | `string`              | `http://localhost:11434`                                                                                                                                       |   No    | Base URL for local or remote Ollama server.                                                                                                   |
| **Model Selection & Parameters**                          |                       |                                                                                                                                                                |         |                                                                                                                                               |
| `LLM_MODEL_PRIMARY` / `NIM_MODEL_PRIMARY`                 | `string`              | Provider default _(e.g. `meta/llama-3.3-70b-instruct`, `gpt-4o`, `claude-3-5-sonnet-latest`, `gemini-2.0-flash`, `llama-3.3-70b-versatile`, `llama3.2`)_ |   No    | Primary LLM model for comment and post drafting.                                                                                              |
| `LLM_MODEL_FALLBACK` / `NIM_MODEL_FALLBACK`               | `string`              | Provider default _(e.g. `openai/gpt-oss-20b`, `gpt-4o-mini`, `claude-3-5-haiku-latest`, `gemini-1.5-flash`, `llama-3.1-8b-instant`, `llama3.2`)_               |   No    | Fallback LLM model if primary encounters rate limit or provider error.                                                                        |
| `LLM_MODEL_TRIAGE` / `NIM_MODEL_TRIAGE`                   | `string`              | `None` _(uses provider triage default or primary)_                                                                                                             |   No    | Optional lightweight LLM dedicated exclusively to fast post triage.                                                                           |
| `NIM_TEMPERATURE`                                         | `float` (`0.0`-`2.0`) | `0.2`                                                                                                                                                          |   No    | Sampling temperature for LLM text generation.                                                                                                 |
| `NIM_TOP_P`                                               | `float` (`0.0`-`1.0`) | `None`                                                                                                                                                         |   No    | Optional nucleus sampling probability.                                                                                                        |
| `NIM_TIMEOUT_SECONDS`                                     | `float` (`>= 1.0`)    | `60.0`                                                                                                                                                         |   No    | Request timeout for LLM API calls in seconds.                                                                                                 |
| `NIM_MAX_TOKENS`                                          | `int` (`>= 1`)        | `1024`                                                                                                                                                         |   No    | Maximum token limit per generation response.                                                                                                  |
| `NIM_BASE_URL`                                            | `string`              | `None`                                                                                                                                                         |   No    | Custom base URL for private NIM or custom OpenAI-compatible endpoints.                                                                        |
| `NIM_MAX_CONCURRENCY`                                     | `int` (`>= 1`)        | `4`                                                                                                                                                            |   No    | Maximum concurrent requests to the LLM provider.                                                                                              |
| **Telegram Bot**                                          |                       |                                                                                                                                                                |         |                                                                                                                                               |
| `TELEGRAM_BOT_TOKEN`                                      | `string`              | _(Required)_                                                                                                                                                   | **Yes** | Telegram bot token obtained from `@BotFather`.                                                                                                |
| `TELEGRAM_AUTHORIZED_CHAT_ID`                             | `int`                 | _(Required)_                                                                                                                                                   | **Yes** | Numeric Telegram user/chat ID permitted to approve actions.                                                                                   |
| **LinkedIn Session & Security**                           |                       |                                                                                                                                                                |         |                                                                                                                                               |
| `SESSION_ENCRYPTION_KEY`                                  | `string`              | `None`                                                                                                                                                         | **Yes** | Fernet 32-byte url-safe base64 encryption key.                                                                                                |
| `LINKEDIN_SESSION_STATE_ENC`                              | `string`              | `None`                                                                                                                                                         | **Yes** | Base64-encoded encrypted Playwright session state string.                                                                                     |
| `LINKEDIN_STORAGE_STATE_PATH`                             | `Path`                | `storage_state.json`                                                                                                                                           |   No    | Path to runner-local decrypted storage state.                                                                                                 |
| **Persona & Content Customization**                       |                       |                                                                                                                                                                |         |                                                                                                                                               |
| `USER_FOCUS_AREAS`                                        | `list[str]`           | `[]`                                                                                                                                                           |   No    | Comma-separated list or JSON array of domain topics to evaluate.                                                                              |
| `SCOUT_TARGET_URLS`                                       | `list[str]`           | `[]`                                                                                                                                                           |   No    | Explicit LinkedIn feed URLs to scout (e.g. hashtag feeds, creator activity URLs).                                                             |
| `TARGET_HASHTAGS`                                         | `list[str]`           | `[]`                                                                                                                                                           |   No    | Specific LinkedIn hashtags to scout (e.g. `['python', 'ai', '#agentic']`).                                                                    |
| `USER_PERSONA`                                            | `string`              | `""`                                                                                                                                                           |   No    | Professional background and tone guidelines for drafting.                                                                                     |
| `MAX_COMMENT_WORDS`                                       | `int` (`10`-`200`)    | `80`                                                                                                                                                           |   No    | Target maximum word count for drafted comments.                                                                                               |
| **Safety & Rate Limits**                                  |                       |                                                                                                                                                                |         |                                                                                                                                               |
| `MAX_COMMENTS_PER_DAY`                                    | `int` (`>= 0`)        | `5`                                                                                                                                                            |   No    | Hard daily maximum for approved LinkedIn comments.                                                                                            |
| `MAX_POSTS_PER_DAY`                                       | `int` (`>= 0`)        | `1`                                                                                                                                                            |   No    | Hard daily maximum for original LinkedIn posts.                                                                                               |
| `MAX_CONNECTIONS_PER_DAY`                                 | `int` (`>= 0`)        | `10`                                                                                                                                                           |   No    | Hard daily maximum for approved LinkedIn connection requests.                                                                                 |
| `MAX_SUGGESTIONS_PER_RUN`                                 | `int` (`>= 1`)        | `3`                                                                                                                                                            |   No    | Maximum suggestions sent to Telegram per scout run.                                                                                           |
| `PENDING_ACTION_TTL_HOURS`                                | `int` (`>= 1`)        | `12`                                                                                                                                                           |   No    | Time-to-live in hours before pending approvals expire.                                                                                        |
| `AGENT_PAUSED`                                            | `bool`                | `false`                                                                                                                                                        |   No    | Global kill switch: when `true`, all workflows pause immediately.                                                                             |
| `DRY_RUN`                                                 | `bool`                | `false`                                                                                                                                                        |   No    | When `true`, mocks live LinkedIn writes and logs intended actions.                                                                            |
| **Logging & Storage**                                     |                       |                                                                                                                                                                |         |                                                                                                                                               |
| `LOG_LEVEL`                                               | `string`              | `INFO`                                                                                                                                                         |   No    | Python logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`).                                                                                   |
| `STATE_DIR`                                               | `Path`                | `state`                                                                                                                                                        |   No    | Path to directory containing version-controlled JSON state (used by `STATE_BACKEND=git`).                                                     |
| **State Persistence & Cloudflare KV / R2**                |                       |                                                                                                                                                                |         |                                                                                                                                               |
| `STATE_BACKEND`                                           | `string`              | `git` _(Local)_ / `kv` _(CI)_                                                                                                                                  |   No    | Durable state backend: `kv` (Cloudflare Workers KV) or `git` (Git-as-database).                                                               |
| `CLOUDFLARE_ACCOUNT_ID`                                   | `string`              | `None`                                                                                                                                                         | **Yes** | 32-character Cloudflare Account ID (Required when `STATE_BACKEND=kv`).                                                                        |
| `CLOUDFLARE_KV_NAMESPACE_ID`                              | `string`              | `None`                                                                                                                                                         | **Yes** | 32-character Workers KV Namespace ID for `LINKEDIN_AGENT_KV` (Required when `STATE_BACKEND=kv`).                                              |
| `CLOUDFLARE_API_TOKEN`                                    | `string`              | `None`                                                                                                                                                         | **Yes** | Cloudflare API Token with `Account.Workers KV Storage: Edit` permission (Required when `STATE_BACKEND=kv`).                                   |
| `WORKER_URL`                                              | `string`              | `None`                                                                                                                                                         |   No    | Base URL of deployed Cloudflare Worker relay (e.g. `https://relay.your-subdomain.workers.dev`).                                               |
| `DESKTOP_API_SECRET`                                      | `string`              | `None`                                                                                                                                                         | **Yes** | API secret authenticating desktop client requests and R2 screenshot uploads.                                                                  |
| **Cloudflare Relay Worker (infra/telegram-relay-worker)** |                       |                                                                                                                                                                |         |                                                                                                                                               |
| `TELEGRAM_WEBHOOK_SECRET`                                 | `string`              | _(Required)_                                                                                                                                                   | **Yes** | Shared secret token verified via `X-Telegram-Bot-Api-Secret-Token`. Generate with `uv run python scripts/generate_secrets.py --type webhook`. |
| `GITHUB_DISPATCH_PAT`                                     | `string`              | _(Required)_                                                                                                                                                   | **Yes** | GitHub PAT with `repo` / `Contents: Read and write` permissions to trigger `repository_dispatch`.                                             |
| `GITHUB_REPO_OWNER`                                       | `string`              | _(Required)_                                                                                                                                                   |   No    | GitHub username or organization name.                                                                                                         |
| `GITHUB_REPO_NAME`                                        | `string`              | _(Required)_                                                                                                                                                   |   No    | GitHub repository name (e.g. `linkedaide`).                                                                                                   |
| `NVIDIA_NIM_API_KEY`                                      | `string`              | _(Required for Desktop App)_                                                                                                                                   | **Yes** | NVIDIA NIM API key (`nvapi-...`) allowing the worker's `/api/rewrite` endpoint to rewrite drafts into different tones.                        |
| `LLM_BASE_URL`                                            | `string`              | `https://integrate.api.nvidia.com/v1`                                                                                                                          |   No    | Custom base URL if using a custom endpoint or proxy for Worker LLM calls.                                                                     |

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
