# Telegram Relay Worker

Cloudflare Worker that receives Telegram callback queries and converts them into GitHub Actions `repository_dispatch` events for Human-in-the-Loop LinkedIn approvals.

## Configuration Secrets

Configure these secrets via `wrangler secret put <NAME>`:

- `TELEGRAM_WEBHOOK_SECRET` — High-entropy secret string matched in `X-Telegram-Bot-Api-Secret-Token`. Auto-generate with `uv run python scripts/generate_secrets.py --type webhook`.
- `TELEGRAM_BOT_TOKEN` — Telegram Bot Token from `@BotFather`
- `TELEGRAM_AUTHORIZED_CHAT_ID` — Numeric Telegram chat/user ID authorized to approve (from `@userinfobot`)
- `GITHUB_DISPATCH_PAT` — GitHub Personal Access Token (Fine-Grained `Contents: Read and write` or Classic `repo` scope)
- `GITHUB_REPO_OWNER` — GitHub username or organization (e.g. `your-username`)
- `GITHUB_REPO_NAME` — Repository name (e.g. `linkedaide`)
- `DESKTOP_API_SECRET` — High-entropy secret authenticating Desktop Control Panel requests and WebSocket subscriptions
- `NVIDIA_NIM_API_KEY` — NVIDIA NIM API Key (`nvapi-...`) used by `/api/rewrite` to power live comment draft tone adjustments and regeneration in the Desktop App
- `LLM_BASE_URL` — _(Optional)_ Base URL for custom LLM endpoint (defaults to `https://integrate.api.nvidia.com/v1`)

## Dynamic Model Resolution & Configuration API

- **Dynamic Model Resolution**: The worker's `/api/rewrite` endpoint dynamically queries Cloudflare KV key `config:runtime` for `nim_model_primary`. When you update the primary model via `uv run agent config set nim_model_primary <model>` or the Desktop App, the worker uses the new model immediately without requiring redeployment.
- **Configuration API (`/api/config`)**: Authenticated GET and PUT endpoints (protected by `DESKTOP_API_SECRET`) allow the Desktop Control Panel and clients to inspect and update runtime operational configuration directly in Cloudflare KV.

## Deployment

```bash
npm install
npx wrangler deploy
```

Then register the webhook with Telegram:

```bash
uv run python scripts/register_telegram_webhook.py \
  --worker-url https://<your-worker>.workers.dev \
  --secret-token <TELEGRAM_WEBHOOK_SECRET> \
  --bot-token <TELEGRAM_BOT_TOKEN>
```
