# Operational Troubleshooting & Diagnostics Guide

This guide details common operational scenarios, diagnostic steps, and recovery procedures for the LinkedIn Human-in-the-Loop (HITL) AI Agent.

---

## Quick Diagnostic Checklist

| Symptom | Likely Cause | Recommended Action |
|---|---|---|
| Workflows skip immediately with "System Paused" | Circuit breaker active or `AGENT_PAUSED=true` | Check for `state/incident.json` or review `AGENT_PAUSED` repo variable. |
| Telegram suggestions stop arriving | Feed had no matching posts, or session expired | Check GitHub Actions logs for `Scout` job or run `Session Health Check`. |
| Approval button clicked in Telegram, but action never executes | Relay webhook secret mismatch or expired GitHub PAT | Check Cloudflare Worker logs and inspect GitHub `repository_dispatch` events. |
| Desktop App displays "Worker API Error (500): NVIDIA_NIM_API_KEY is not configured" | Missing `NVIDIA_NIM_API_KEY` secret in Cloudflare Worker | Run `npx wrangler secret put NVIDIA_NIM_API_KEY` in `infra/telegram-relay-worker` or add in Cloudflare Dashboard. |
| Workflow fails with `BotDetectionError` | LinkedIn displayed CAPTCHA or checkpoint | Halt automated runs, log in manually via browser to clear challenge, and reset breaker. |

---

## 1. LinkedIn Session Expiration & Renewal

### Symptoms
- `SessionExpiredError` in workflow logs.
- Weekly `LinkedIn Session Health Check` workflow fails.
- Telegram alert: `⚠️ LinkedIn session has expired or is invalid.`

### Recovery Procedure
1. On your local machine, run the interactive session extractor:
   ```bash
   uv run python scripts/extract_linkedin_session.py
   ```
2. Log into LinkedIn in the opened browser window and complete any verification prompts.
3. Copy the output values:
   - `SESSION_ENCRYPTION_KEY`
   - `LINKEDIN_SESSION_STATE_ENC`
4. Update these secrets in GitHub:
   - Navigate to **GitHub Repo** -> **Settings** -> **Secrets and variables** -> **Actions**.
   - Update `SESSION_ENCRYPTION_KEY` and `LINKEDIN_SESSION_STATE_ENC`.
5. Trigger the **LinkedIn Session Health Check** workflow manually in GitHub Actions to verify connectivity.

---

## 2. Circuit Breaker Recovery (`state/incident.json`)

### Mechanism
When the agent detects a CAPTCHA, checkpoint, security challenge, or repeated critical browser errors, it trips the circuit breaker by writing `state/incident.json`. While this file exists, all automated workflows immediately exit without touching LinkedIn.

### Recovery Procedure
1. **Inspect Incident Record**:
   View `state/incident.json` in the repository or local clone to understand the error reason, timestamp, and context:
   ```bash
   cat state/incident.json
   ```
2. **Verify Account Status Manually**:
   Open a standard web browser and log into LinkedIn manually. Ensure your account is in good standing and not presenting a verification challenge.
3. **Reset the Circuit Breaker**:
   Delete the incident file, commit the change, and push to main:
   ```bash
   git rm state/incident.json
   git commit -m "chore(safety): clear circuit breaker incident"
   git push origin main
   ```
4. Run the **LinkedIn Session Health Check** workflow to confirm normal operations have resumed.

---

## 3. LinkedIn DOM Selector Drift

### Symptoms
- `SelectorDriftError` or timeout errors during `Scout` feed scraping or `Execute` comment posting.
- Scraper returns 0 posts even though your LinkedIn feed has active content.

### Diagnostic Procedure
1. **Enable Debug Artifacts**:
   When a workflow fails, GitHub Actions automatically uploads Playwright screenshots and traces under workflow artifacts (`scout-debug-<run-id>` or `execute-debug-<run-id>`).
2. Download the artifact and inspect the failure screenshot in `debug/screenshots/`.
3. If LinkedIn modified its feed DOM structure or CSS class names:
   - Update the relevant selector in [`src/agent/browser/scraper.py`](../src/agent/browser/scraper.py) or [`src/agent/browser/executor.py`](../src/agent/browser/executor.py).
   - Capture a sanitized HTML snippet and update test fixtures in [`tests/fixtures/linkedin_feed_snapshots/`](../tests/fixtures/linkedin_feed_snapshots/).
   - Run browser unit tests locally:
     ```bash
     uv run pytest tests/unit/test_scraper.py tests/unit/test_executor.py
     ```

---

## 4. Telegram Relay & Cloudflare Worker Issues

### 1. Telegram Webhook Returns Error
If clicking **Approve** or **Reject** in Telegram results in an error alert:
- Check Cloudflare Worker real-time logs:
  ```bash
  cd infra/telegram-relay-worker
  npx wrangler tail
  ```
- **HTTP 401 Unauthorized**: The `TELEGRAM_WEBHOOK_SECRET` header sent by Telegram does not match the secret in Cloudflare Worker. Re-register the webhook:
  ```bash
  uv run python scripts/register_telegram_webhook.py \
    --worker-url <WORKER_URL> \
    --secret-token <TELEGRAM_WEBHOOK_SECRET> \
    --bot-token <TELEGRAM_BOT_TOKEN>
  ```
- **HTTP 403 Forbidden**: The callback sender's Telegram ID does not match `TELEGRAM_AUTHORIZED_CHAT_ID`.

### 2. GitHub Dispatch Fails (Worker logs HTTP 401/404 on dispatch)
- Ensure `GITHUB_DISPATCH_PAT` in Cloudflare has sufficient permissions to trigger `repository_dispatch`:
  - **Fine-Grained PAT**: `Repository permissions` -> **Contents: Read and write**.
  - **Classic PAT**: **`repo`** scope.
- Verify `GITHUB_REPO_OWNER` and `GITHUB_REPO_NAME` match your repository exactly.

### 3. Desktop App Tone Rewrite Fails with `NVIDIA_NIM_API_KEY is not configured`
**Symptoms:**  
When clicking an AI tone quick-pill (*Technical*, *Inquisitive*, *Contrarian*, *Shorter & Punchier*) or *Regenerate* in the Desktop App's **Approval Queue** or **Connection Outreach Studio**, a red banner appears:  
`Error invoking remote method 'api:rewriteDraft': Error: Worker API Error (500 Internal Server Error): NVIDIA_NIM_API_KEY is not configured`

**Cause:**  
The Desktop App delegates draft rewriting to the Cloudflare Worker's `/api/rewrite` endpoint, which calls NVIDIA NIM on the edge. This requires `NVIDIA_NIM_API_KEY` to be set as an encrypted secret directly in your Cloudflare Worker environment.

**Resolution:**  
1. **Via Wrangler CLI:**
   ```bash
   cd infra/telegram-relay-worker
   npx wrangler secret put NVIDIA_NIM_API_KEY
   ```
   Paste your NVIDIA NIM API key (`nvapi-...`).
2. **Via Cloudflare Dashboard:**
   - Go to [Cloudflare Dashboard](https://dash.cloudflare.com/) &rarr; **Compute (Workers & Pages)**.
   - Select your worker (`linkedin-agent-telegram-relay`).
   - Go to **Settings** &rarr; **Variables and Secrets** &rarr; click **Add** under Secrets.
   - Enter variable name `NVIDIA_NIM_API_KEY`, paste your `nvapi-...` value, and click **Deploy**.

---

## 5. Local Dry-Run Testing & Debugging

You can test the entire pipeline locally without modifying live LinkedIn state:

### Run Scout in Dry-Run Mode
```bash
# Set DRY_RUN in environment
export DRY_RUN=true
uv run python -m agent.orchestration.scout_flow
```
Or use the standalone test script:
```bash
uv run python scripts/run_scout_dry.py
```

### Run Unit Tests
```bash
# Run all tests
uv run pytest -v

# Run only safety tests
uv run pytest tests/unit/test_safety.py

# Run graph integration tests
uv run pytest tests/integration/graphs/
```

---

## 6. Custom Exception Hierarchy Reference

```text
AgentError
├── ConfigError                  # Configuration validation failure
├── NIMError                     # NVIDIA NIM provider error
│   ├── NIMSchemaValidationError # Response failed Pydantic validation
│   ├── NIMRateLimitError        # HTTP 429 Rate limit exceeded
│   └── NIMTimeoutError          # Request timeout exceeded
├── SessionError                 # LinkedIn authentication issue
│   ├── SessionExpiredError      # Session cookies invalid/expired
│   └── BotDetectionError        # CAPTCHA / checkpoint detected (Fatal)
├── ScrapeError                  # Scraper failure
│   └── SelectorDriftError       # DOM elements not found
├── ExecutionError               # Action execution failure
│   ├── PostNoLongerAvailableError # Target post was deleted
│   ├── StaleApprovalError       # Pending action expired past TTL
│   └── DuplicateActionError     # Action already executed or consumed
├── StateStoreError              # Repository state I/O error
└── TelegramAPIError             # Telegram notification/edit failure
```
