# Security Policy

## Reporting Security Issues

If you discover a security vulnerability or sensitive information leak in this repository, please do not open a public GitHub issue. Instead, report it privately to the repository owner.

---

## Secret & Credential Management Rules

This repository automates sensitive actions and handles session credentials. The following rules are mandatory:

### 1. Zero Plaintext Credentials in Repository
- Never commit `.env`, `.pem`, `.key`, or credentials of any kind.
- API keys (`NVIDIA_NIM_API_KEY`, `TELEGRAM_BOT_TOKEN`, `GITHUB_PAT`) must strictly reside in environment variables or GitHub Repository Secrets.

### 2. Browser Storage State Protection
- Authenticated Playwright storage states (`storage_state.json`, `auth/`) contain active LinkedIn session cookies. They must **never** be committed in plaintext or uploaded as unsecured artifacts.
- When stored remotely, session states must be symmetrically encrypted with Fernet AES using `SESSION_ENCRYPTION_KEY`.
- Decrypted session files must only exist in ephemeral local paths and must be wiped after execution.

### 3. Redaction and Logging
- Never output secrets, cookies, session tokens, or authorization headers into stdout, stderr, or CI job logs.
- Sanitize exception context before recording errors.

### 4. Human Authorization Boundary
- The Telegram bot represents the human authorization boundary.
- All approval interactions strictly verify the sender's Telegram user ID against `TELEGRAM_AUTHORIZED_CHAT_ID`.
- Telegram callback data must never contain secrets, tokens, or raw executable commands.

### 5. Automated Safety Safeguards
- **Circuit Breaker**: If bot detection, CAPTCHA, or abnormal account status is detected, the agent trips a circuit breaker (`state/incident.json`) and halts all write actions until manual operator intervention.
- **Daily Action Caps**: Strict deterministic caps (`MAX_COMMENTS_PER_DAY`, `MAX_POSTS_PER_DAY`) are enforced independently of model instructions.
