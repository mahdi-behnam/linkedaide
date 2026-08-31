# Telegram Relay Worker

Cloudflare Worker that receives Telegram callback queries and converts them into GitHub Actions `repository_dispatch` events for Human-in-the-Loop LinkedIn approvals.

## Configuration Secrets

Configure these secrets via `wrangler secret put <NAME>`:

- `TELEGRAM_WEBHOOK_SECRET` — Arbitrary high-entropy secret string matched in `X-Telegram-Bot-Api-Secret-Token`
- `TELEGRAM_BOT_TOKEN` — Telegram Bot Token
- `TELEGRAM_AUTHORIZED_CHAT_ID` — Numeric Telegram chat/user ID authorized to approve
- `GITHUB_DISPATCH_PAT` — GitHub Personal Access Token (Fine-Grained `Contents: Read and write` or Classic `repo` scope)
- `GITHUB_REPO_OWNER` — GitHub username or organization
- `GITHUB_REPO_NAME` — Repository name

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
