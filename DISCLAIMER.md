# Legal & Platform Disclaimer

## Important Notice

This repository and its associated software (**"the Project"**) is an open-source project intended strictly for **educational, personal research, and development purposes**.

### 1. No Affiliation with LinkedIn

This project is **not affiliated with, endorsed by, sponsored by, or associated with LinkedIn Corporation or Microsoft Corporation** in any way. "LinkedIn" is a registered trademark of LinkedIn Corporation.

### 2. Terms of Service & Platform Policies

Automating interactions on LinkedIn using browser automation frameworks (such as Playwright) may violate [LinkedIn's User Agreement](https://www.linkedin.com/legal/user-agreement) and [Professional Community Policies](https://www.linkedin.com/legal/professional-community-policies), specifically provisions concerning unauthorized automation, scraping, or botting.

By using this software, you acknowledge and agree that:
- You assume **sole and complete responsibility** for any actions taken by this agent on your LinkedIn account.
- The authors and contributors of this project accept **no liability** for any account restrictions, temporary checkpoints, permanent bans, data loss, or damages arising from the use or misuse of this software.
- You are responsible for ensuring your usage complies with all applicable platform policies, terms of service, and local legal regulations.

### 3. Human-in-the-Loop & Safe Automation Principles

This project is intentionally designed with strict safety boundaries:
- **Mandatory Human Approval**: Every write action (comment, post) requires explicit, authenticated human authorization via Telegram before execution.
- **Deterministic Action Caps**: The software enforces hard daily posting and commenting limits independently of LLM reasoning.
- **Immediate Circuit Breaking**: If any bot challenge, CAPTCHA, or verification checkpoint is detected, execution halts immediately and trips a safety circuit breaker.

Do not modify or disable these safety invariants. Bypassing human verification or disabling rate limits increases the likelihood of platform enforcement against your account.
