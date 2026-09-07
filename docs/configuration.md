# Configuration Reference Guide

All runtime settings in the LinkedIn Human-in-the-Loop (HITL) AI Agent are loaded and strictly validated via `pydantic-settings` in [`src/agent/config.py`](../src/agent/config.py).

Settings can be provided via environment variables, a local `.env` file, or GitHub Actions Secrets / Variables.

---

## Complete Settings Reference

| Environment Variable | Type | Default | Secret? | Description |
|---|---|---|:---:|---|
| **NVIDIA NIM LLM** | | | | |
| `NVIDIA_NIM_API_KEY` | `string` | *(Required)* | **Yes** | NVIDIA NIM API key (`nvapi-...`). |
| `NIM_MODEL_PRIMARY` | `string` | `nvidia/nemotron-3-super-120b-a12b` | No | Primary LLM model for comment and post drafting. |
| `NIM_MODEL_FALLBACK` | `string` | `openai/gpt-oss-20b` | No | Fallback LLM model if primary encounters rate limit or provider error. |
| `NIM_MODEL_TRIAGE` | `string` | `None` (uses primary) | No | Optional lightweight LLM dedicated exclusively to fast post triage. |
| `NIM_TEMPERATURE` | `float` (`0.0`-`2.0`) | `0.2` | No | Sampling temperature for LLM text generation. |
| `NIM_TOP_P` | `float` (`0.0`-`1.0`) | `None` | No | Optional nucleus sampling probability. |
| `NIM_TIMEOUT_SECONDS` | `float` (`>= 1.0`) | `60.0` | No | Request timeout for NIM API calls in seconds. |
| `NIM_MAX_TOKENS` | `int` (`>= 1`) | `1024` | No | Maximum token limit per generation response. |
| `NIM_BASE_URL` | `string` | `None` | No | Custom base URL for private or self-hosted NIM endpoints. |
| `NIM_MAX_CONCURRENCY` | `int` (`>= 1`) | `4` | No | Maximum concurrent requests to NVIDIA NIM. |
| **Telegram Bot** | | | | |
| `TELEGRAM_BOT_TOKEN` | `string` | *(Required)* | **Yes** | Telegram bot token obtained from `@BotFather`. |
| `TELEGRAM_AUTHORIZED_CHAT_ID` | `int` | *(Required)* | **Yes** | Numeric Telegram user/chat ID permitted to approve actions. |
| **LinkedIn Session & Security** | | | | |
| `SESSION_ENCRYPTION_KEY` | `string` | `None` | **Yes** | Fernet 32-byte url-safe base64 encryption key. |
| `LINKEDIN_SESSION_STATE_ENC` | `string` | `None` | **Yes** | Base64-encoded encrypted Playwright session state string. |
| `LINKEDIN_STORAGE_STATE_PATH` | `Path` | `storage_state.json` | No | Path to runner-local decrypted storage state. |
| **Persona & Content Customization** | | | | |
| `USER_FOCUS_AREAS` | `list[str]` | `[]` | No | Comma-separated list or JSON array of domain topics to evaluate. |
| `USER_PERSONA` | `string` | `""` | No | Professional background and tone guidelines for drafting. |
| `MAX_COMMENT_WORDS` | `int` (`10`-`200`) | `80` | No | Target maximum word count for drafted comments. |
| **Safety & Rate Limits** | | | | |
| `MAX_COMMENTS_PER_DAY` | `int` (`>= 0`) | `5` | No | Hard daily maximum for approved LinkedIn comments. |
| `MAX_POSTS_PER_DAY` | `int` (`>= 0`) | `1` | No | Hard daily maximum for original LinkedIn posts. |
| `MAX_SUGGESTIONS_PER_RUN` | `int` (`>= 1`) | `3` | No | Maximum suggestions sent to Telegram per scout run. |
| `PENDING_ACTION_TTL_HOURS` | `int` (`>= 1`) | `12` | No | Time-to-live in hours before pending approvals expire. |
| `AGENT_PAUSED` | `bool` | `false` | No | Global kill switch: when `true`, all workflows pause immediately. |
| `DRY_RUN` | `bool` | `false` | No | When `true`, mocks live LinkedIn writes and logs intended actions. |
| **Logging & Storage** | | | | |
| `LOG_LEVEL` | `string` | `INFO` | No | Python logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `STATE_DIR` | `Path` | `state` | No | Path to directory containing version-controlled JSON state. |
| **Cloudflare Relay Worker (infra/telegram-relay-worker)** | | | | |
| `TELEGRAM_WEBHOOK_SECRET` | `string` | *(Required)* | **Yes** | Shared secret token verified via `X-Telegram-Bot-Api-Secret-Token`. Generate with `uv run python scripts/generate_secrets.py --type webhook`. |
| `GITHUB_DISPATCH_PAT` | `string` | *(Required)* | **Yes** | GitHub PAT with `repo` / `Contents: Read and write` permissions to trigger `repository_dispatch`. |
| `GITHUB_REPO_OWNER` | `string` | *(Required)* | No | GitHub username or organization name. |
| `GITHUB_REPO_NAME` | `string` | *(Required)* | No | GitHub repository name (e.g. `linkedin-hitl-agent`). |

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

### 2. Tuning Model Concurrency & Performance
- For high-throughput feeds, configure `NIM_MODEL_TRIAGE="openai/gpt-oss-20b"` for fast initial screening, while retaining `NIM_MODEL_PRIMARY="nvidia/nemotron-3-super-120b-a12b"` for comment drafting.
- Adjust `NIM_MAX_CONCURRENCY=4` to balance throughput with NIM rate limits.

### 3. Adjusting Safety Caps
- For cautious account growth, keep `MAX_COMMENTS_PER_DAY=3` to `5`.
- Set `PENDING_ACTION_TTL_HOURS=12` to ensure comments are posted while discussions are still fresh.
