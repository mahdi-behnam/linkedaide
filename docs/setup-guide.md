# End-to-End Setup & Deployment Guide

This guide walks you through setting up the LinkedIn Human-in-the-Loop (HITL) AI Agent from scratch, including credential extraction, Telegram bot configuration, Cloudflare Worker relay deployment, and GitHub Actions orchestration.

---

## Architecture Overview

```text
┌────────────────┐     ┌──────────────┐     ┌────────────────┐
│  GitHub Cron   │ ──> │  ScoutGraph  │ ──> │ Telegram Bot   │
│  (scout.yml)   │     │ (Scrape+NIM) │     │ (Human Review) │
└────────────────┘     └──────────────┘     └───────┬────────┘
                                                    │ [Approve / Reject]
                                                    ▼
┌────────────────┐     ┌──────────────┐     ┌────────────────┐
│  ExecuteGraph  │ <── │ GitHub Event │ <── │  Cloudflare    │
│  (Playwright)  │     │ (execute.yml)│     │  Relay Worker  │
└────────────────┘     └──────────────┘     └────────────────┘
```

---

## Prerequisites

Before starting, ensure you have:
- A workstation with **Python `>= 3.14`** and [`uv`](https://docs.astral.sh/uv/) installed.
- [Node.js](https://nodejs.org/) `>= 18` (for deploying Cloudflare Worker with Wrangler).
- An active [LinkedIn](https://www.linkedin.com) account.
- An [NVIDIA NIM](https://build.nvidia.com/) API account and API key.
- A [Telegram](https://telegram.org/) account.
- A [Cloudflare](https://dash.cloudflare.com/) account (free tier is sufficient).
- A GitHub repository hosting this codebase.

---

## Step 1: NVIDIA NIM Setup

1. Log into the [NVIDIA API Catalog](https://build.nvidia.com/).
2. Navigate to your desired model (e.g., `meta/llama-3.3-70b-instruct`).
3. Generate and copy your API key (starts with `nvapi-`).

---

## Step 2: Telegram Bot Setup

1. **Create the Bot:**
   - Open Telegram and message [`@BotFather`](https://t.me/BotFather).
   - Send `/newbot`, choose a name and username for your bot.
   - Copy the generated `TELEGRAM_BOT_TOKEN` (e.g., `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`).

2. **Retrieve Your Telegram Chat / User ID:**
   - Message [`@userinfobot`](https://t.me/userinfobot) or [`@IDBot`](https://t.me/myidbot) on Telegram.
   - Copy your numeric ID (e.g., `987654321`). This becomes `TELEGRAM_AUTHORIZED_CHAT_ID`.

3. **Start the Bot:**
   - Send `/start` to your newly created bot to open a direct message thread.

---

## Step 3: LinkedIn Session Extraction & Encryption

To allow Playwright to access your LinkedIn feed without logging in with raw credentials during each run, extract and symmetrically encrypt your authenticated browser storage state:

1. **Run the interactive extraction utility on your local machine:**
   ```bash
   uv run python scripts/extract_linkedin_session.py
   ```

2. **Complete Login:**
   - A Chromium browser window will open to `https://www.linkedin.com/login`.
   - Log in using your LinkedIn credentials, complete 2FA, and pass any security challenges.
   - Once the script detects the authenticated session cookie (`li_at`), it automatically captures the session state, closes the browser, and encrypts the payload using Fernet AES.

3. **Record Generated Credentials:**
   The script outputs two sensitive strings:
   - `SESSION_ENCRYPTION_KEY`: A 32-byte url-safe base64 Fernet encryption key.
   - `LINKEDIN_SESSION_STATE_ENC`: The base64-encoded encrypted storage state string.

> [!CAUTION]
> Treat both `SESSION_ENCRYPTION_KEY` and `LINKEDIN_SESSION_STATE_ENC` as high-security credentials. Never commit them to version control.

---

## Step 4: Deploy Cloudflare Telegram Relay Worker

When you click **Approve** or **Reject** in Telegram, the Telegram Bot API sends a webhook payload. The Cloudflare Worker validates this callback and triggers GitHub Actions via a `repository_dispatch` event.

### 1. Create a GitHub Personal Access Token (PAT)
- Go to GitHub -> **Settings** -> **Developer Settings** -> **Personal Access Tokens**.
- Configure token permissions to enable triggering `repository_dispatch` events:
  - **Fine-Grained PAT**: Target your `linkedin-hitl-agent` repo, select `Repository permissions` -> **Contents: Read and write**.
  - **Classic PAT**: Select the **`repo`** scope.
- Copy the generated token (`GITHUB_DISPATCH_PAT`).

### 2. Deploy Worker via Wrangler
```bash
cd infra/telegram-relay-worker
npm install
npx wrangler deploy
```
Note your deployed worker URL (e.g., `https://telegram-relay-worker.<your-subdomain>.workers.dev`).

### 3. Configure Worker Secrets
Set the required secrets in Cloudflare:
```bash
# Webhook secret to verify requests originate from Telegram
npx wrangler secret put TELEGRAM_WEBHOOK_SECRET

# Telegram bot token
npx wrangler secret put TELEGRAM_BOT_TOKEN

# Numeric authorized chat ID
npx wrangler secret put TELEGRAM_AUTHORIZED_CHAT_ID

# GitHub PAT created above
npx wrangler secret put GITHUB_DISPATCH_PAT

# GitHub username or organization name
npx wrangler secret put GITHUB_REPO_OWNER

# GitHub repository name (e.g., linkedin-hitl-agent)
npx wrangler secret put GITHUB_REPO_NAME
```

### 4. Register Telegram Webhook
From the root of the project, run the registration script:
```bash
uv run python scripts/register_telegram_webhook.py \
  --worker-url https://telegram-relay-worker.<your-subdomain>.workers.dev \
  --secret-token <YOUR_TELEGRAM_WEBHOOK_SECRET> \
  --bot-token <YOUR_TELEGRAM_BOT_TOKEN>
```

---

## Step 5: Configure GitHub Repository Secrets & Variables

Go to your repository on GitHub: **Settings** -> **Secrets and variables** -> **Actions**.

### 1. Repository Secrets (`Secrets` tab)
| Secret Name | Value Description |
|---|---|
| `NVIDIA_NIM_API_KEY` | Your NVIDIA NIM API key (`nvapi-...`) |
| `TELEGRAM_BOT_TOKEN` | Your Telegram Bot Token |
| `TELEGRAM_AUTHORIZED_CHAT_ID` | Your numeric Telegram user ID |
| `SESSION_ENCRYPTION_KEY` | Fernet AES encryption key from Step 3 |
| `LINKEDIN_SESSION_STATE_ENC` | Encrypted session state token from Step 3 |

### 2. Repository Variables (`Variables` tab)
| Variable Name | Example Value | Description |
|---|---|---|
| `NIM_MODEL_PRIMARY` | `meta/llama-3.3-70b-instruct` | Primary model for comment drafting |
| `NIM_MODEL_FALLBACK` | `meta/llama-3.1-8b-instruct` | Fallback model if primary rate-limits |
| `USER_FOCUS_AREAS` | `["AI Agents", "Python", "Distributed Systems"]` | Topics of interest for triage |
| `MAX_COMMENTS_PER_DAY` | `5` | Hard limit on daily approved comments |
| `MAX_POSTS_PER_DAY` | `1` | Hard limit on daily original LinkedIn posts |
| `MAX_SUGGESTIONS_PER_RUN` | `3` | Maximum suggestions sent to Telegram per scout run |
| `PENDING_ACTION_TTL_HOURS` | `12` | Approval expiration window |
| `AGENT_PAUSED` | `false` | Global kill switch (`true` pauses all runs) |
| `DRY_RUN` | `false` | When `true`, avoids actual LinkedIn writes |

---

## Step 6: Verify End-to-End Execution

1. **Test Session Health Check:**
   - In GitHub Actions, select the **LinkedIn Session Health Check** workflow and click **Run workflow**.
   - Verify that it logs into LinkedIn without triggering challenge screens.

2. **Trigger Dry-Run Scout:**
   - Select **LinkedIn Feed Scout** workflow -> **Run workflow** -> Set `dry_run = true`.
   - Check your Telegram bot: you should receive suggestions with interactive inline buttons!

3. **Test Approval Flow:**
   - Click **Approve** on a Telegram suggestion.
   - Observe the **LinkedIn Execute Action** workflow trigger via `repository_dispatch`.
   - The Telegram message will update in-place to show execution status!
