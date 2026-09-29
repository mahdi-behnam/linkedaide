# End-to-End Setup & Deployment Guide

This guide walks you through setting up the LinkedIn Human-in-the-Loop (HITL) AI Agent from scratch, including automated secret generation, credential extraction, Telegram bot configuration, Cloudflare Worker relay deployment, and GitHub Actions orchestration.

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

## Credentials & Secrets Directory

Before proceeding, here is a quick map of all secrets used in the system, where they come from, and where they are placed:

| Secret / Variable Name | What It Is & Where It Comes From | Where It Is Configured |
|---|---|---|
| `NVIDIA_NIM_API_KEY` | API key from [NVIDIA API Catalog](https://build.nvidia.com/) (`nvapi-...`). | Local `.env`, GitHub Secrets |
| `TELEGRAM_BOT_TOKEN` | Bot token created via [`@BotFather`](https://t.me/BotFather). | Local `.env`, GitHub Secrets, Cloudflare Worker Secret |
| `TELEGRAM_AUTHORIZED_CHAT_ID` | Your numeric Telegram User ID retrieved from [`@userinfobot`](https://t.me/userinfobot). | Local `.env`, GitHub Secrets, Cloudflare Worker Secret |
| `SESSION_ENCRYPTION_KEY` | 32-byte Fernet key generated via `scripts/generate_secrets.py`. | Local `.env`, GitHub Secrets |
| `LINKEDIN_SESSION_STATE_ENC` | Encrypted LinkedIn cookies extracted via `scripts/extract_linkedin_session.py`. | Local `.env`, GitHub Secrets |
| `TELEGRAM_WEBHOOK_SECRET` | Custom random secret generated via `scripts/generate_secrets.py` (used by Telegram to sign webhooks and verified by Cloudflare Worker). | Cloudflare Worker Secret, Telegram Webhook Registration |
| `GITHUB_DISPATCH_PAT` | GitHub Personal Access Token created by you (with `repo` / `Contents: Read and write` permissions). | Cloudflare Worker Secret |
| `GITHUB_REPO_OWNER` | Your GitHub username or organization name. | Cloudflare Worker Secret |
| `GITHUB_REPO_NAME` | Your GitHub repository name (e.g., `linkedin-hitl-agent`). | Cloudflare Worker Secret |

---

## Prerequisites

Ensure you have installed:
- **Python `>= 3.11`** and [`uv`](https://docs.astral.sh/uv/) package manager.
- [Node.js](https://nodejs.org/) `>= 18` (for deploying the Cloudflare Worker via Wrangler).
- An active [LinkedIn](https://www.linkedin.com) account.
- An [NVIDIA NIM](https://build.nvidia.com/) API account and API key.
- A [Telegram](https://telegram.org/) account.
- A [Cloudflare](https://dash.cloudflare.com/) account (free tier is sufficient).
- A GitHub repository hosting this codebase.

---

## Fast-Track Onboarding: Interactive CLI Setup & Doctor

To accelerate setup, use the unified CLI tool to configure credentials and diagnose your environment:

### 1. Interactive Setup Wizard
Run the setup wizard to interactively configure your LLM provider, enter API keys, connect your Telegram bot, choose state persistence, and generate cryptographic encryption keys:

```bash
uv run agent setup
```

The wizard will:
- Guide you through selecting your LLM provider (`nvidia`, `openai`, `anthropic`, `gemini`, `groq`, `ollama`) and saving the relevant API key.
- Guide your Telegram reviewer bot setup (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_AUTHORIZED_CHAT_ID`).
- Guide your state persistence choice (Cloudflare KV for production vs Git/Local for dev).
- Automatically generate a 32-byte Fernet `SESSION_ENCRYPTION_KEY` if missing.
- Safely write and update `.env` without overwriting unrelated variables.

### 2. Diagnostic Health Check ("Doctor")
Run the diagnostic suite at any time to verify system integrity and connectivity across all subsystems:

```bash
uv run agent doctor
```

The diagnostic suite checks and reports a checklist (🟢 Pass, 🟡 Warning, 🔴 Fail):
- **Python Runtime**: Confirms Python `>= 3.11`.
- **Playwright Chromium**: Checks that Chromium is installed and executable.
- **Configuration**: Validates loaded settings from `.env` and environment variables.
- **LLM Provider**: Tests model instantiation for the selected provider.
- **Telegram Bot**: Calls `getMe` via HTTP to verify bot token and display bot handle.
- **State Backend**: Verifies Cloudflare KV namespace access via REST API, or checks local `state/` directory write access.
- **LinkedIn Session**: Verifies that `storage_state.json` or encrypted credentials exist and are decryptable.

---

## Step 1: Generate Cryptographic Secrets

The repository includes a secret generation script to produce the required cryptographic keys:

```bash
uv run python scripts/generate_secrets.py
```

This generates:
1. `SESSION_ENCRYPTION_KEY`: A 32-byte Fernet AES key used to encrypt and decrypt browser session cookies.
2. `TELEGRAM_WEBHOOK_SECRET`: A high-entropy URL-safe token used to secure webhook communication between Telegram and your Cloudflare Worker.

> [!TIP]
> Keep the terminal output handy — you will paste these values into your `.env`, Cloudflare Worker, and GitHub Repository Secrets in the following steps.

---

## Step 2: NVIDIA NIM Setup

1. Log into the [NVIDIA API Catalog](https://build.nvidia.com/).
2. Select your desired primary model (e.g., `nvidia/nemotron-3-super-120b-a12b`).
3. Generate and copy your API key (starts with `nvapi-`). This is your `NVIDIA_NIM_API_KEY`.

---

## Step 3: Telegram Bot Setup

1. **Create the Reviewer Bot:**
   - Open Telegram and message [`@BotFather`](https://t.me/BotFather).
   - Send `/newbot`, choose a name and username for your bot.
   - Copy the generated `TELEGRAM_BOT_TOKEN` (e.g., `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`).

2. **Retrieve Your Numeric Telegram User ID:**
   - Message [`@userinfobot`](https://t.me/userinfobot) or [`@IDBot`](https://t.me/myidbot) on Telegram.
   - Copy your numeric ID (e.g., `987654321`). This becomes `TELEGRAM_AUTHORIZED_CHAT_ID`.
   - *Security invariant: Only messages from this ID will be permitted to approve or reject actions.*

3. **Start a Conversation with Your Bot:**
   - Open your new bot in Telegram and click **Start** (or send `/start`) to initiate a direct message thread.

---

## Step 4: LinkedIn Session Extraction & Encryption

To allow browser automation to securely access your LinkedIn feed without storing raw passwords:

1. **Run the interactive session extractor:**
   ```bash
   uv run python scripts/extract_linkedin_session.py
   ```

2. **Log in interactively:**
   - A Chromium browser window will open to `https://www.linkedin.com/login`.
   - Log into your LinkedIn account and pass any 2FA or CAPTCHA challenges.
   - Once login is detected (via the `li_at` cookie), the script automatically captures storage state, encrypts it using `SESSION_ENCRYPTION_KEY` (either read from your `.env` or generated automatically on the fly), and closes the browser.

3. **Record Generated Output:**
   The script outputs both credentials directly to your terminal:
   - `SESSION_ENCRYPTION_KEY`: The 32-byte Fernet key used to encrypt the payload.
   - `LINKEDIN_SESSION_STATE_ENC`: The base64-encoded encrypted storage state string.

   Save both values to your local `.env` file and GitHub Repository Secrets.

> [!CAUTION]
> Treat `SESSION_ENCRYPTION_KEY` and `LINKEDIN_SESSION_STATE_ENC` as confidential credentials. Never commit them to git.

---

## Step 5: Deploy Cloudflare Telegram Relay Worker

When you click **Approve** or **Reject** in Telegram, Telegram sends an HTTP webhook callback. A lightweight Cloudflare Worker validates the request and triggers GitHub Actions via a `repository_dispatch` event.

### Understanding `TELEGRAM_WEBHOOK_SECRET`
- **What is it?** It is a custom secret string (generated in Step 1) shared between Telegram and your Cloudflare Worker.
- **Why is it needed?** Telegram attaches this secret in the `X-Telegram-Bot-Api-Secret-Token` HTTP header on every webhook call. The Cloudflare Worker verifies the header before taking any action. If the header is missing or incorrect, it returns `401 Unauthorized`. This prevents arbitrary internet traffic from triggering GitHub Actions workflows.

### 1. Create a GitHub Personal Access Token (PAT)
To allow the Cloudflare Worker to trigger GitHub Actions:
- Go to GitHub -> **Settings** -> **Developer Settings** -> **Personal Access Tokens**.
- Create a token with dispatch permissions:
  - **Fine-Grained PAT**: Target repository `linkedin-hitl-agent`, select `Repository permissions` -> **Contents: Read and write**.
  - **Classic PAT**: Select the **`repo`** scope.
- Copy the token (`GITHUB_DISPATCH_PAT`).

### 2. Deploy the Worker
```bash
cd infra/telegram-relay-worker
npm install
npx wrangler deploy
```
Copy the deployed worker URL (e.g., `https://telegram-relay-worker.<your-subdomain>.workers.dev`).

### 3. Set Worker Secrets in Cloudflare
Set the 6 required secrets in Cloudflare via Wrangler:
```bash
# 1. Custom webhook secret (generated in Step 1)
npx wrangler secret put TELEGRAM_WEBHOOK_SECRET

# 2. Telegram bot token (from Step 3)
npx wrangler secret put TELEGRAM_BOT_TOKEN

# 3. Authorized numeric Telegram chat ID (from Step 3)
npx wrangler secret put TELEGRAM_AUTHORIZED_CHAT_ID

# 4. GitHub PAT (from Step 5.1)
npx wrangler secret put GITHUB_DISPATCH_PAT

# 5. GitHub account/organization name (e.g. your-username)
npx wrangler secret put GITHUB_REPO_OWNER

# 6. Repository name (e.g. linkedin-hitl-agent)
npx wrangler secret put GITHUB_REPO_NAME
```

### 4. Register the Webhook with Telegram
Return to the project root directory and run the registration utility:
```bash
uv run python scripts/register_telegram_webhook.py \
  --worker-url https://telegram-relay-worker.<your-subdomain>.workers.dev \
  --secret-token <YOUR_TELEGRAM_WEBHOOK_SECRET> \
  --bot-token <YOUR_TELEGRAM_BOT_TOKEN>
```
You should see: `Webhook registered successfully`.

---

## Step 6: Configure GitHub Repository Secrets & Variables

In your GitHub repository, navigate to **Settings** -> **Secrets and variables** -> **Actions**.

### 1. Repository Secrets (`Secrets` tab)
Add the following 5 secrets:

| Secret Name | Value |
|---|---|
| `NVIDIA_NIM_API_KEY` | NVIDIA NIM API key (`nvapi-...`) from Step 2 |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token from Step 3 |
| `TELEGRAM_AUTHORIZED_CHAT_ID` | Numeric Telegram user ID from Step 3 |
| `SESSION_ENCRYPTION_KEY` | Fernet AES encryption key from Step 1 |
| `LINKEDIN_SESSION_STATE_ENC` | Encrypted session state token from Step 4 |

### 2. Repository Variables (`Variables` tab)
Configure operational preferences:

| Variable Name | Default / Example Value | Description |
|---|---|---|
| `NIM_MODEL_PRIMARY` | `nvidia/nemotron-3-super-120b-a12b` | Primary model for drafting comments/posts |
| `NIM_MODEL_FALLBACK` | `openai/gpt-oss-20b` | Fallback model if primary encounters errors |
| `USER_FOCUS_AREAS` | `["AI Agents", "Python", "Distributed Systems"]` | Topics of interest for post triage |
| `USER_PERSONA` | `Principal AI Engineer sharing technical insights...` | Custom tone and background prompt |
| `MAX_COMMENTS_PER_DAY` | `5` | Hard safety limit on approved comments posted daily |
| `MAX_POSTS_PER_DAY` | `1` | Hard safety limit on daily original posts |
| `MAX_SUGGESTIONS_PER_RUN` | `3` | Maximum suggestions sent to Telegram per scout run |
| `PENDING_ACTION_TTL_HOURS` | `12` | Approval expiration window (hours) |
| `AGENT_PAUSED` | `false` | Global pause switch (`true` stops all workflows) |
| `DRY_RUN` | `false` | Set `true` to disable real LinkedIn writes |

---

## Step 7: Local `.env` Setup (Optional for Local Development)

If you want to run tests or dry-run flows locally on your workstation:
1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Populate the values with your credentials from Steps 1–4.

---

## Step 8: Verify End-to-End Execution

### 1. Session Health Check
- Go to GitHub -> **Actions** -> **LinkedIn Session Health Check** -> click **Run workflow**.
- Confirm that the workflow validates your encrypted LinkedIn session without encountering challenge pages.

### 2. Test Dry-Run Scout Flow
- Go to GitHub -> **Actions** -> **LinkedIn Feed Scout** -> click **Run workflow** (leave `dry_run = true`).
- Check your Telegram bot: you will receive formatted suggestion cards with **Approve** and **Reject** buttons.

### 3. Test Human Approval Relay
- Click **Approve** on a suggestion in Telegram.
- Verify:
  1. The Telegram message updates with an immediate confirmation status.
  2. GitHub Actions triggers the **LinkedIn Execute Action** workflow via `repository_dispatch`.
  3. The action executes successfully (or simulates execution in dry-run mode).

---

## Operator Scripts Reference

The `scripts/` directory provides utilities for setup and maintenance:

| Command | Purpose |
|---|---|
| `uv run python scripts/generate_secrets.py` | Generates `SESSION_ENCRYPTION_KEY` and `TELEGRAM_WEBHOOK_SECRET`. |
| `uv run python scripts/extract_linkedin_session.py` | Opens interactive browser to log into LinkedIn and extracts encrypted session state. |
| `uv run python scripts/register_telegram_webhook.py --worker-url ... --secret-token ...` | Registers Cloudflare Worker webhook URL and secret with Telegram Bot API. |
| `uv run python scripts/register_telegram_webhook.py --delete` | Removes Telegram webhook (useful if switching to local polling mode). |
| `uv run python scripts/run_scout_dry.py` | Executes a local dry-run of the Scout workflow on your machine. |
