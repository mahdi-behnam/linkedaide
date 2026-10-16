# End-to-End Setup & Deployment Guide

This guide walks you through setting up LinkedAide from scratch, including automated secret generation, credential extraction, Telegram bot configuration, Cloudflare Worker relay deployment, and GitHub Actions orchestration.

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

| Secret / Variable Name        | What It Is & Where It Comes From                                                                                                                  | Where It Is Configured                                                                            |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `NVIDIA_NIM_API_KEY`          | API key from [NVIDIA API Catalog](https://build.nvidia.com/) (`nvapi-...`).                                                                       | Local `.env`, GitHub Secrets, Cloudflare Worker Secret _(powers Desktop App draft tone rewrites)_ |
| `TELEGRAM_BOT_TOKEN`          | Bot token created via [`@BotFather`](https://t.me/BotFather).                                                                                     | Local `.env`, GitHub Secrets, Cloudflare Worker Secret                                            |
| `TELEGRAM_AUTHORIZED_CHAT_ID` | Your numeric Telegram User ID retrieved from [`@userinfobot`](https://t.me/userinfobot).                                                          | Local `.env`, GitHub Secrets, Cloudflare Worker Secret                                            |
| `SESSION_ENCRYPTION_KEY`      | 32-byte Fernet key generated via `scripts/generate_secrets.py`.                                                                                   | Local `.env`, GitHub Secrets                                                                      |
| `LINKEDIN_SESSION_STATE_ENC`  | Encrypted LinkedIn cookies extracted via `scripts/extract_linkedin_session.py`.                                                                   | Local `.env`, GitHub Secrets                                                                      |
| `TELEGRAM_WEBHOOK_SECRET`     | Custom random secret generated via `scripts/generate_secrets.py` (used by Telegram to sign webhooks and verified by Cloudflare Worker).           | Cloudflare Worker Secret, Telegram Webhook Registration                                           |
| `GITHUB_DISPATCH_PAT`         | GitHub Personal Access Token created by you (with `repo` / `Contents: Read and write` permissions).                                               | Cloudflare Worker Secret                                                                          |
| `GITHUB_REPO_OWNER`           | Your GitHub username or organization name.                                                                                                        | Cloudflare Worker Secret                                                                          |
| `GITHUB_REPO_NAME`            | Your GitHub repository name (e.g., `linkedaide`).                                                                                                 | Cloudflare Worker Secret                                                                          |
| `DESKTOP_API_SECRET`          | High-entropy URL-safe token generated via `scripts/generate_secrets.py` (or `uv run agent setup`) to authenticate Desktop app & Worker API calls. | Local `.env`, Cloudflare Worker Secret, Desktop App Settings                                      |
| `CLOUDFLARE_ACCOUNT_ID`       | Your 32-character Cloudflare Account ID (found on Cloudflare dashboard URL or Workers overview).                                                  | Local `.env`, GitHub Secrets                                                                      |
| `CLOUDFLARE_KV_NAMESPACE_ID`  | 32-character Workers KV Namespace ID for `LINKEDIN_AGENT_KV` (generated via Wrangler).                                                            | Local `.env`, GitHub Secrets, `wrangler.toml`                                                     |
| `CLOUDFLARE_API_TOKEN`        | Cloudflare API Token with `Account.Workers KV Storage: Edit` permission to allow GitHub Actions to read/write state in KV.                        | Local `.env`, GitHub Secrets                                                                      |

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
3. `DESKTOP_API_SECRET`: A high-entropy URL-safe token used to authenticate the Desktop Control Panel and local CLI against your Cloudflare Worker API.

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
   - _Security invariant: Only messages from this ID will be permitted to approve or reject actions._

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
  - **Fine-Grained PAT**: Target repository `linkedaide`, select `Repository permissions` -> **Contents: Read and write**.
  - **Classic PAT**: Select the **`repo`** scope.
- Copy the token (`GITHUB_DISPATCH_PAT`).

### 2. Provision Cloudflare Storage (KV & Optional R2)

```bash
cd infra/telegram-relay-worker
npm install
```

#### A. Create Workers KV Namespace (Mandatory — 100% Free, No Credit Card Needed)

Workers KV stores your agent's state (pending actions, history, counters) safely in Cloudflare without requiring a credit card:

```bash
npx wrangler kv namespace create LINKEDIN_AGENT_KV
```

Wrangler will output a configuration snippet with your unique 32-character hexadecimal `id`, for example:

```toml
[[kv_namespaces]]
binding = "LINKEDIN_AGENT_KV"
id = "a1b2c3d4e5f6071829304a5b6c7d8e9f"
```

Open `infra/telegram-relay-worker/wrangler.toml` and replace the placeholder `id = "linkedin_agent_kv_namespace"` with your generated 32-character `id`.

> [!IMPORTANT]
> **Cloudflare KV Credentials for GitHub Actions (`STATE_BACKEND=kv`)**
>
> Because GitHub Actions executes the Scout and Execute flows in the cloud, it connects to your Cloudflare KV namespace via Cloudflare's REST API. Make sure to note down and generate the following 3 values:
>
> 1. **`CLOUDFLARE_ACCOUNT_ID`**: Found in your [Cloudflare Dashboard](https://dash.cloudflare.com/) URL (`https://dash.cloudflare.com/<ACCOUNT_ID>`) or on any Worker's overview page in the right-hand sidebar.
> 2. **`CLOUDFLARE_KV_NAMESPACE_ID`**: The 32-character ID generated from `npx wrangler kv namespace create LINKEDIN_AGENT_KV` above (also visible under **Workers & Pages** &rarr; **KV** in the Cloudflare dashboard).
> 3. **`CLOUDFLARE_API_TOKEN`**: Create an API token so GitHub Actions can read/write KV state:
>    - In Cloudflare Dashboard, click your profile icon (top right) &rarr; **My Profile** &rarr; **API Tokens**.
>    - Click **Create Token** &rarr; scroll to bottom &rarr; **Create Custom Token** &rarr; click **Get started**.
>    - **Token Name**: `LinkedIn Agent KV Access`
>    - **Permissions**: **Account** &rarr; **Workers KV Storage** &rarr; **Edit**
>    - **Account Resources**: **Include** &rarr; **All accounts** (or your specific account)
>    - Click **Continue to summary** &rarr; **Create Token**, then copy the token value.
>
> You will add these 3 values as repository secrets in **Step 6**.

---

#### B. Cloudflare R2 Media Vault (Completely Optional)

> [!NOTE]
> **Do you need Cloudflare R2?**
>
> - **No, R2 is completely optional.**
> - Cloudflare requires entering a payment method / credit card to activate R2 (even though R2 includes a free 10 GB/month tier).
> - If you **do not want to provide a credit card**, simply **skip R2**. In `infra/telegram-relay-worker/wrangler.toml`, the `[[r2_buckets]]` section is already commented out by default. Execution audit screenshots will automatically be saved locally on your workstation instead.
> - You can proceed directly to **Step 3 (Deploy the Worker)**!

**If you DO want Cloudflare R2 (for cloud-hosted proof screenshots):**

1. Log into your [Cloudflare Dashboard](https://dash.cloudflare.com/).
2. In the left navigation menu, go to **Storage & Databases** &rarr; **R2** (or click **R2**).
3. Click **"Enable R2"** / **"Get Started"** (this requires a payment method on file).
4. Run:
   ```bash
   npx wrangler r2 bucket create linkedin-agent-media
   ```
5. In `infra/telegram-relay-worker/wrangler.toml`, uncomment the `[[r2_buckets]]` block:
   ```toml
   [[r2_buckets]]
   binding = "SCREENSHOTS_BUCKET"
   bucket_name = "linkedin-agent-media"
   ```

### 3. Deploy the Worker

```bash
npx wrangler deploy
```

Copy the deployed worker URL (e.g., `https://telegram-relay-worker.<your-subdomain>.workers.dev`).

### 4. Set Worker Secrets in Cloudflare

Set the required secrets in Cloudflare via Wrangler:

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

# 6. Repository name (e.g. linkedaide)
npx wrangler secret put GITHUB_REPO_NAME

# 7. Desktop API Secret (from Step 1 — for desktop app realtime sync & API access)
npx wrangler secret put DESKTOP_API_SECRET

# 8. NVIDIA NIM API Key (from Step 2 — powers AI draft rewriting & tone adjustments in Desktop Control Panel)
npx wrangler secret put NVIDIA_NIM_API_KEY
```

> [!IMPORTANT]
> **Why does the Cloudflare Worker need `NVIDIA_NIM_API_KEY`?**
> The Desktop Control Panel features on-the-fly AI draft rewriting (Technical, Inquisitive, Contrarian, Shorter) and comment regeneration directly from the **Approval Queue** tab. These fast LLM rewrite requests are processed directly on the Cloudflare Worker edge using NVIDIA NIM. If this secret is missing, clicking tone pills in the desktop app will fail with `Worker API Error (500 Internal Server Error): NVIDIA_NIM_API_KEY is not configured`.

### 5. Register the Webhook with Telegram

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

Add the following repository secrets (8 secrets total when using Cloudflare KV):

| Secret Name                   | Value                                                                | Required For                    |
| ----------------------------- | -------------------------------------------------------------------- | ------------------------------- |
| `NVIDIA_NIM_API_KEY`          | NVIDIA NIM API key (`nvapi-...`) from Step 2                         | All workflows                   |
| `TELEGRAM_BOT_TOKEN`          | Telegram Bot Token from Step 3                                       | All workflows                   |
| `TELEGRAM_AUTHORIZED_CHAT_ID` | Numeric Telegram user ID from Step 3                                 | All workflows                   |
| `SESSION_ENCRYPTION_KEY`      | Fernet AES encryption key from Step 1                                | All workflows                   |
| `LINKEDIN_SESSION_STATE_ENC`  | Encrypted session state token from Step 4                            | All workflows                   |
| `CLOUDFLARE_ACCOUNT_ID`       | 32-character Cloudflare Account ID from Step 5.2.A                   | Cloud mode (`STATE_BACKEND=kv`) |
| `CLOUDFLARE_KV_NAMESPACE_ID`  | 32-character KV namespace ID (`LINKEDIN_AGENT_KV`) from Step 5.2.A   | Cloud mode (`STATE_BACKEND=kv`) |
| `CLOUDFLARE_API_TOKEN`        | Cloudflare API Token with Workers KV Edit permission from Step 5.2.A | Cloud mode (`STATE_BACKEND=kv`) |

> [!NOTE]
> **Why does GitHub Actions need Cloudflare KV secrets?**
> In production (`STATE_BACKEND=kv`), GitHub Actions runs the Scout and Execute workflows on remote runners and synchronizes pending posts, seen items, and daily counters directly with your Cloudflare KV namespace using Cloudflare's REST API. This keeps the Telegram Relay Worker, Desktop App, and GitHub Actions completely in sync with zero Git merge conflicts.
> _(If you want to run completely without Cloudflare KV in GitHub Actions, set `STATE_BACKEND=git` under Repository Variables below to fall back to Git-as-Database)._

### 2. Repository Variables (`Variables` tab)

Configure operational preferences:

| Variable Name              | Default / Example Value                               | Description                                         |
| -------------------------- | ----------------------------------------------------- | --------------------------------------------------- |
| `NIM_MODEL_PRIMARY`        | `nvidia/nemotron-3-super-120b-a12b`                   | Primary model for drafting comments/posts           |
| `NIM_MODEL_FALLBACK`       | `openai/gpt-oss-20b`                                  | Fallback model if primary encounters errors         |
| `USER_FOCUS_AREAS`         | `["AI Agents", "Python", "Distributed Systems"]`      | Topics of interest for post triage                  |
| `USER_PERSONA`             | `Principal AI Engineer sharing technical insights...` | Custom tone and background prompt                   |
| `MAX_COMMENTS_PER_DAY`     | `5`                                                   | Hard safety limit on approved comments posted daily |
| `MAX_POSTS_PER_DAY`        | `1`                                                   | Hard safety limit on daily original posts           |
| `MAX_SUGGESTIONS_PER_RUN`  | `3`                                                   | Maximum suggestions sent to Telegram per scout run  |
| `PENDING_ACTION_TTL_HOURS` | `12`                                                  | Approval expiration window (hours)                  |
| `AGENT_PAUSED`             | `false`                                               | Global pause switch (`true` stops all workflows)    |
| `DRY_RUN`                  | `false`                                               | Set `true` to disable real LinkedIn writes          |

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

## Step 9: Launch & Configure the Desktop Control Panel

The repository includes a modern Electron desktop control panel. It provides real-time approval queues, power-user keyboard shortcuts (`[A]` approve, `[R]` reject, `[E]` edit, `[T]` cycle tone), a visual post composer, calendar planner, connection outreach studio, voice audio dictation, system tray background notifications, and live audit telemetry.

### 1. Download or Run the Desktop App

#### Option A: Download Standalone Installer (Recommended)

You do not need to install Node.js, run terminal commands, or compile anything. Simply download the ready-to-run installer for your operating system:

- 🪟 **Windows**: [Download `linkedaide-Setup.exe`](https://github.com/mahdi-behnam/linkedaide/releases) (or portable `.exe`)
- 🍏 **macOS**: [Download `linkedaide.dmg`](https://github.com/mahdi-behnam/linkedaide/releases)
- 🐧 **Linux**: [Download `linkedaide.AppImage`](https://github.com/mahdi-behnam/linkedaide/releases) (or `.deb`)

Install and launch the application, then proceed directly to **Connect the Desktop App** below.

#### Option B: Build and Run from Source (Developers)

_Looking to develop, modify, or run the desktop app directly from code? See [Building the Desktop App from Source](#building-the-desktop-app-from-source-developers)._

---

### 2. Connect the Desktop App to Your Cloudflare Worker

1. In the Desktop App, click **Settings** (gear icon in the sidebar).
2. Configure your connection:
   - **Cloudflare Worker URL**: Enter your deployed worker URL from Step 5 (e.g., `https://linkedin-agent-telegram-relay.<your-subdomain>.workers.dev`).
   - **Desktop API Secret**: Paste the `DESKTOP_API_SECRET` you generated in Step 1.
3. Click **"Save Settings"** and then **"Test Connection"**.
   - You should see a green checkmark indicating successful authentication and latency (<100ms).

---

## Step 10: Day-to-Day Workflow — What Happens Next?

Once setup is complete, your agent runs automatically 24/7. Here is what to expect and how to interact with it:

### 1. Automated Schedule (GitHub Actions)

The agent operates on automated cron schedules in GitHub Actions without requiring your computer to stay on:

- **Feed Scouting (`scout.yml`)**: Runs automatically on weekdays (08:00, 13:00, 18:00 UTC).
  - Inspects your LinkedIn feed for high-relevance posts matching your `USER_FOCUS_AREAS`.
  - Triages posts and generates high-value, authentic draft comments.
  - Pushes draft cards to Telegram and your Desktop Queue simultaneously via WebSocket.
- **Thought Leadership Ideation (`ideation.yml`)**: Runs daily at 09:00 UTC.
  - Brainstorms and drafts original standalone posts matching your domain perspective.
- **Session Canary (`session-health-check.yml`)**: Runs daily at 06:00 UTC.
  - Silently confirms that your encrypted session cookies are valid and alerts you on Telegram before expiration.

### 2. How to Review & Approve Drafts

You have two synchronized ways to supervise the agent:

- **From Your Phone (Telegram)**:
  - You will receive a message with the post excerpt and proposed draft.
  - Click **Approve** &rarr; Cloudflare Worker immediately triggers GitHub Actions (`execute.yml`) to post the comment.
  - Click **Edit** &rarr; Reply with your customized text, then approve your revised draft.
  - Click **Reject** &rarr; Discards the suggestion and logs it.
- **From Your Computer (Desktop Control Panel)**:
  - System tray notification alerts you when new suggestions are scouted.
  - Switch to the **Approval Queue**:
    - Press `[A]` to Approve, `[R]` to Reject, `[E]` to Edit, or `[T]` to cycle tone pills (_Technical_, _Inquisitive_, _Contrarian_, _Concise_).
    - Use voice dictation (microphone icon) to dictate custom comment modifications.
    - Press `Cmd+Enter` (or `Ctrl+Enter`) to submit.

### 3. Triggering Manual Runs On-Demand

You don't have to wait for the scheduled crons:

- **From Desktop App**: Click **"Trigger Scout Now"** in the Dashboard or right-click the system tray icon.
- **From GitHub Actions**: Go to **Actions** &rarr; **LinkedIn Feed Scout** &rarr; **Run workflow** (set `dry_run: false` for live execution).
- **From Local CLI**: Run `uv run agent scout` (or `uv run agent scout --dry-run`).

---

## Operator Scripts Reference

The `scripts/` directory provides utilities for setup and maintenance:

| Command                                                                                  | Purpose                                                                                  |
| ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `uv run python scripts/generate_secrets.py`                                              | Generates `SESSION_ENCRYPTION_KEY`, `TELEGRAM_WEBHOOK_SECRET`, and `DESKTOP_API_SECRET`. |
| `uv run python scripts/extract_linkedin_session.py`                                      | Opens interactive browser to log into LinkedIn and extracts encrypted session state.     |
| `uv run python scripts/register_telegram_webhook.py --worker-url ... --secret-token ...` | Registers Cloudflare Worker webhook URL and secret with Telegram Bot API.                |
| `uv run python scripts/register_telegram_webhook.py --delete`                            | Removes Telegram webhook (useful if switching to local polling mode).                    |
| `uv run python scripts/run_scout_dry.py`                                                 | Executes a local dry-run of the Scout workflow on your machine.                          |

---

## Building the Desktop App from Source (Developers)

If you are a developer looking to inspect, customize, or contribute to the desktop application, you can build and run it locally from source code.

### Prerequisites

- **Node.js**: v18.0.0 or higher (Node v20 LTS or v22+ recommended)
- **npm**: v9.0.0 or higher

### 1. Install Dependencies

Navigate to the `desktop/` directory and install the packages:

```bash
cd desktop
npm install
```

> **Automated Self-Healing Setup**:
> The repository includes an automated verification script (`scripts/ensure-electron.cjs`) hooked into `postinstall` and `prestart`. If modern npm blocks postinstall download scripts, the script automatically searches your local cache (`%LOCALAPPDATA%\electron\Cache` or `~/.cache/electron`), unpacks the binary, cleans Windows carriage returns (`\r\n`) in `path.txt`, and links `dist/electron.exe` properly so you never run into missing binary errors.

### 2. Run in Development Mode

To preview and develop the React frontend with Vite fast refresh:

```bash
npm run dev
```

### 3. Build & Launch the Desktop App

To compile the TypeScript Electron main process, bundle the React frontend, and launch the application:

```bash
# Compile and package bundles:
npm run package

# Launch the desktop control panel:
npm start
```

### 4. Package Standalone Installers

To generate standalone platform installers (`.exe`, `.dmg`, `.AppImage`) locally:

```bash
# Package for your current operating system:
npm run dist

# Or build platform-specific targets:
npm run dist:win    # Windows installer (.exe) & portable executable
npm run dist:mac    # macOS disk image (.dmg) & zip
npm run dist:linux  # Linux AppImage & .deb package
```

The compiled binaries are generated in `desktop/dist-electron/`.

---

## Keeping Your Fork Up to Date (1-Click Sync)

When upstream releases new versions, bug fixes, or updated DOM selectors for LinkedIn layout changes, your desktop application will auto-update. To ensure your cloud runner workflows on GitHub Actions stay in lockstep with the desktop app:

1. Open your forked repository on GitHub (`https://github.com/<your-username>/linkedaide`).
2. Directly below the repository navigation bar, check GitHub's sync status banner:
   > *"This branch is X commit(s) behind mahdi-behnam/linkedaide:main."*
3. Click **Sync fork** ▾ and select **Update branch**.

GitHub will immediately fast-forward your cloud runner workflows and backend logic to match the latest upstream release—no Git commands, terminal, or local cloning required!
