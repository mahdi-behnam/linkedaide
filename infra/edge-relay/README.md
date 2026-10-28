# Edge Relay

Cloudflare Worker that handles Telegram webhooks, Desktop Cockpit REST API and WebSocket push events, edge post scheduling, and converts approval actions into GitHub Actions `repository_dispatch` events for Human-in-the-Loop LinkedIn automation.

## Configuration Secrets

Set the essential secrets via `wrangler secret put <NAME>`:

- `TELEGRAM_WEBHOOK_SECRET` — High-entropy secret string matched in `X-Telegram-Bot-Api-Secret-Token`. Auto-generate with `uv run python scripts/generate_secrets.py --type webhook`.
- `GITHUB_DISPATCH_PAT` — GitHub Personal Access Token (Fine-Grained `Contents: Read and write` or Classic `repo` scope).
- `GITHUB_REPO_OWNER` — GitHub username or organization (e.g. `your-username`).
- `GITHUB_REPO_NAME` — Repository name (e.g. `linkedaide`).
- `DESKTOP_API_SECRET` — High-entropy secret authenticating Desktop Control Panel requests, REST API endpoints, and WebSocket subscriptions.

### Dynamic KV Resolution (Optional Worker Secrets)

The worker dynamically inherits the following credentials and parameters from Cloudflare KV key `config:runtime` (managed via the Desktop Control Panel or CLI):

- `TELEGRAM_BOT_TOKEN` — Dynamic fallback: if omitted from worker secrets, resolved from KV `config:runtime`.
- `TELEGRAM_AUTHORIZED_CHAT_ID` — Dynamic fallback: if omitted from worker secrets, resolved from KV `config:runtime`.
- `NVIDIA_NIM_API_KEY` — Dynamic fallback: powers `/api/rewrite` edge tone adjustments, resolved from KV `config:runtime`.
- `LLM_BASE_URL` / `NIM_BASE_URL` — Dynamic fallback: custom LLM endpoint (defaults to `https://integrate.api.nvidia.com/v1`).
- `NIM_MODEL_PRIMARY` / `LLM_MODEL_PRIMARY` — Dynamic model resolution (defaults to `nvidia/nemotron-3-ultra-550b-a55b`).

> [!NOTE]
> `SESSION_ENCRYPTION_KEY` is **not** required for the Cloudflare Worker relay. The worker does not run Playwright or touch LinkedIn session cookies.

## API Endpoints for Desktop Control Panel

- **Configuration API (`/api/config`)**: Authenticated `GET` and `PUT` endpoints (protected by `DESKTOP_API_SECRET`) allowing the Desktop App to read and atomically update operational settings and credentials in Cloudflare KV.
- **Telegram Gateway Verification (`/api/telegram/verify`)**: Validates a bot token against Telegram's `getMe` API, returning bot username, display name, and bot ID.
- **Proxy Latency Test (`/api/proxy/test`)**: Tests residential or datacenter proxy connectivity and roundtrip latency.
- **Tone Rewrite API (`/api/rewrite`)**: On-the-fly edge comment draft rewriting into various tones (`technical`, `inquisitive`, `contrarian`, `concise`, etc.).
- **Real-Time WebSocket (`/api/ws`)**: Sub-50ms live synchronization of pending actions, approvals, and system state directly to the Desktop App.

## Deployment

### Automated CI/CD (Recommended)

LinkedAide includes an automated GitHub Actions deployment workflow (`.github/workflows/deploy-relay.yml`). Whenever changes under `infra/edge-relay/**` are merged or pushed to `main`, GitHub Actions automatically:
1. Runs TypeScript type checking (`npm run typecheck`).
2. Runs the test suite (`npm test`).
3. Deploys the worker using `cloudflare/wrangler-action`.

**Requirements**:
Add `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` to your GitHub Repository Secrets (see `docs/setup-guide.md`).

You can also trigger a deployment manually at any time from the **Actions** tab in GitHub via **Deploy Cloudflare Edge Relay** → **Run workflow**.

### Manual Deployment

For initial provisioning or local development:

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
