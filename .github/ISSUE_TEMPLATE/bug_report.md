---
name: Bug Report
about: Create a report to help us improve the agent
title: '[BUG]: '
labels: ['bug', 'triage']
assignees: ''
---

## Describe the Bug
A clear and concise description of what the bug is.

## Steps to Reproduce
Steps to reproduce the behavior:
1. Run flow: `...` (e.g. `uv run python -m agent.orchestration.scout_flow`)
2. Environment config / settings used: `...`
3. See error in logs.

## Expected Behavior
A clear and concise description of what you expected to happen.

## Reproduction in Dry-Run Mode
- [ ] Reproducible with `DRY_RUN=true`
- [ ] Only occurs during live execution

## Sanitized Logs / Stack Trace
```text
<!-- Paste relevant sanitized logs here. DO NOT include session tokens, cookies, or API keys! -->
```

## Environment & System Information
- **OS**: [e.g. Ubuntu 24.04, Windows 11, macOS 14]
- **Python Version**: [e.g. 3.14.0]
- **uv Version**: [e.g. 0.5.0]
- **Execution Mode**: [e.g. GitHub Actions, Local CLI, Docker]
- **LLM Model**: [e.g. meta/llama-3.3-70b-instruct]

## Additional Context
Add any other context about the problem here (e.g. selector changes on LinkedIn, Telegram webhook responses, etc.).
