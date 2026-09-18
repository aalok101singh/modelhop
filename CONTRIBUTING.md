# 🐸 Contributing to ModelHop (v1.1)

Thank you for your interest in contributing to ModelHop! This document covers
everything you need to get a green build.

## Getting Started

### Prerequisites

- Python 3.9 or higher
- pip for package management
- Git

### Setup

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/your-username/modelhop.git
   cd modelhop
   ```
3. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
4. Install with all test dependencies (the `server` extra is required —
   serve/SDK integration tests import it):
   ```bash
   pip install -e ".[dev,server,cache,secrets,anthropic]"
   ```

## Development Guidelines

### Code Style

- We use `black` for formatting (line length 100) and `ruff` for linting.
- CI checks **both** `modelhop/` and `tests/`. Run before pushing:
  ```bash
  black --check modelhop/ tests/
  ruff check modelhop/ tests/
  ```

### Testing

- Write tests for new features and bug fixes; mock external API calls.
- The suite is **hermetic**: an autouse fixture strips live API keys and
  neutralizes `.env` reloads, so tests never touch the network. Never depend
  on a real key, a repo-root `.env`, or `modelhop.yaml` — use `tmp_path` and
  `monkeypatch` for filesystem isolation.
- Full gate (what CI enforces):
  ```bash
  python -m pytest --tb=short -q --cov=modelhop --cov-report=term --cov-fail-under=60
  python -m pytest -q -W error::ResourceWarning
  ```
- Coverage gate is 60%; keep user-facing behavior covered and the suite
  warning-free.

### API Compatibility

- Public SDK/API changes must be **additive-only** (new optional fields and
  params with safe defaults). Never rename, remove, or retype existing
  fields — downstream agents depend on them.

### Commit Messages

- Use clear, descriptive commit messages.
- Start with a verb in imperative mood (e.g., "Add", "Fix", "Update").
- Keep the first line under 72 characters.
- Reference issue numbers when applicable (e.g., "Fix #42").

Example:
```
Add Groq provider fallback

- Implement automatic fallback to next provider on failure
- Add retry logic with exponential backoff
- Fixes #42
```

### Pull Request Process

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make your changes and commit them (never commit `.env`, `modelhop.yaml`,
   or runtime data files — all are gitignored).
3. Push to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```
4. Open a Pull Request on GitHub.
5. Fill out the PR template with:
   - Description of changes
   - Related issues
   - Testing performed (gate output: tests passed, coverage %, lint clean)
   - Checklist items

### What to Contribute

We welcome contributions in these areas:

- **Bug fixes**: Check open issues for bugs
- **New providers**: Add support for more LLM providers
- **Tests**: Improve test coverage
- **Documentation**: Improve docs, add examples
- **Features**: New routing strategies, cost optimization

### Code of Conduct

Please follow our [Code of Conduct](CODE_OF_CONDUCT.md) in all interactions.

## Reporting Issues

- Use GitHub Issues for bug reports and feature requests.
- Include as much detail as possible.
- For bugs: steps to reproduce, expected vs actual behavior.
  `modelhop providers` output (failure reasons, keys redacted) helps a lot.
- For features: use case and proposed solution.

## Questions?

Open a discussion on GitHub Discussions or ask in an issue.

Thank you for contributing to ModelHop! 🐸
