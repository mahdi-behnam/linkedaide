## Description
<!-- Provide a concise description of the changes introduced by this pull request. -->

## Related Issues
<!-- Link to any open issues addressed by this PR: e.g. Fixes #123 -->

## Type of Change
- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking addition adhering to HITL invariants)
- [ ] Refactoring / code cleanup (no behavior changes)
- [ ] Documentation update
- [ ] CI/CD or build infrastructure update

## Quality & Safety Checklist
- [ ] **Tests**: All unit and integration tests pass (`uv run pytest`).
- [ ] **Linting & Formatting**: Clean with `uv run ruff check .` and `uv run ruff format --check .`.
- [ ] **Type Checking**: Clean with `uv run mypy src tests scripts`.
- [ ] **HITL Invariant**: Human approval is strictly maintained for any LinkedIn write action.
- [ ] **Deterministic Safety**: Rate limits, TTL checks, circuit breakers, and sender authentication are preserved.
- [ ] **No Secrets**: Verified that no cookies, storage states, API keys, or `.env` files are included in the diff.
- [ ] **Durable State**: Verified that no local `state/` artifacts are accidentally committed.

## Testing Steps
<!-- Describe how reviewers can verify these changes. -->
1. Run `...`
2. Expected output `...`
