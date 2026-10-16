# Contributing to LinkedIn HITL AI Agent

Thank you for your interest in contributing! We welcome contributions, bug fixes, enhancements, and documentation improvements.

Please take a moment to review this document to ensure a smooth and productive collaboration.

---

## Code of Conduct

By participating in this project, you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md). Please treat all contributors and maintainers with respect and courtesy.

---

## Architectural Invariants (Non-Negotiable)

When contributing code, you must respect the core invariants of this project:

1. **Human Approval is Mandatory**: No LinkedIn write action (commenting, posting, reacting) may occur without explicit, authenticated approval via Telegram. Never introduce an autonomous path or ReAct loop that directly executes browser writes.
2. **Deterministic Safety Policy**: Safety rules (TTL expiration, daily caps, authorized chat ID verification, circuit breakers) must be enforced in deterministic Python code—never solely through LLM prompts.
3. **Zero Plaintext Credentials**: Never commit cookies, decrypted storage states, API keys, tokens, or `.env` files.
4. **LangGraph Workflow Orchestration**: Business logic and state transitions belong inside typed LangGraph state graphs (`ScoutGraph`, `ExecuteGraph`, `HealthCheckGraph`).
5. **Durable Repository State**: All persistence operates via version-controlled JSON/JSONL records under `state/`.

For a full breakdown of agent and architectural rules, see [AGENTS.md](AGENTS.md) and [docs/architecture.md](docs/architecture.md).

---

## Development Environment Setup

### Prerequisites

- **Python**: `>= 3.14`
- **Package Manager**: [`uv`](https://docs.astral.sh/uv/) (Astral's fast Python package manager)
- **Git**

### Installation Steps

1. **Fork and clone the repository:**

   ```bash
   git clone https://github.com/<your-username>/linkedaide.git
   cd linkedaide
   ```

2. **Set up the virtual environment and install dependencies:**

   ```bash
   uv sync
   ```

3. **Install Playwright browser binaries (for browser testing):**

   ```bash
   uv run playwright install chromium
   ```

4. **Configure your local environment:**
   ```bash
   cp .env.example .env
   ```
   _Note: For local unit testing, real credentials are not required as all external services (NVIDIA NIM, Telegram, LinkedIn) are mocked in tests._

---

## Running Quality Checks

Before submitting any code changes or opening a pull request, ensure all checks pass locally:

### 1. Run Unit and Integration Tests

```bash
uv run pytest
```

To run tests with coverage reporting:

```bash
uv run pytest --cov=agent --cov-report=term-missing
```

### 2. Linting and Code Formatting

We use [Ruff](https://docs.astral.sh/ruff/) for fast linting and code formatting:

```bash
# Check for lint errors
uv run ruff check .

# Automatically fix fixable lint issues
uv run ruff check --fix .

# Verify code formatting
uv run ruff format --check .

# Format code
uv run ruff format .
```

### 3. Static Type Checking

We enforce strict typing with `mypy` across source, test, and script directories:

```bash
uv run mypy src tests scripts
```

---

## Testing Guidelines

- **Mock External Calls**: Unit tests must never make real network requests to LinkedIn, Telegram, GitHub, or NVIDIA NIM endpoints.
- **Fixture-Based Browser Tests**: Scraper and executor tests should use saved static HTML fixtures under `tests/fixtures/linkedin_feed_snapshots/` rather than live LinkedIn pages.
- **Graph Coverage**: When adding or modifying LangGraph nodes or conditional edges, write tests verifying both terminal graph states and side-effect expectations.

---

## Commit Guidelines

We adhere to [Conventional Commits](https://www.conventionalcommits.org/):

```text
<type>(<scope>): <short imperative description>
```

### Common Types:

- `feat`: A new feature or capability.
- `fix`: A bug fix.
- `refactor`: Code restructuring without changing external behavior.
- `test`: Adding or improving tests.
- `docs`: Documentation updates.
- `chore`: Tooling, dependency, or repository maintenance.
- `ci`: GitHub Actions or CI/CD updates.

### Recommended Scopes:

`graphs`, `llm`, `browser`, `telegram`, `state`, `safety`, `config`, `models`, `actions`, `relay`.

### Examples:

```text
feat(graphs): add structured retry handling to scout triage
fix(browser): update selector fallback for feed post authors
test(safety): add tests for circuit breaker incident serialization
docs(setup): clarify Telegram webhook registration steps
```

---

## Pull Request Process

1. **Create a branch**: Use a descriptive branch name (e.g., `feat/improve-triage-prompt` or `fix/circuit-breaker-path`).
2. **Implement changes**: Keep commits focused and atomic.
3. **Verify checks**: Run tests, linter, formatting, and type checks locally.
4. **Inspect Git status**: Ensure no `.env`, decrypted session files, or unwanted files in `state/` are staged.
5. **Open Pull Request**: Fill out the [Pull Request Template](.github/PULL_REQUEST_TEMPLATE.md) and describe your changes, testing steps, and rationale.
