# Contributing to ModelHop

Thank you for your interest in contributing to ModelHop! This document provides guidelines and information for contributors.

## Getting Started

### Prerequisites

- Python 3.8 or higher
- pip or poetry for package management
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
4. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

## Development Guidelines

### Code Style

- We use `black` for code formatting
- We use `ruff` for linting
- Line length: 100 characters
- Run formatters before committing:
  ```bash
  black modelhop/
  ruff check modelhop/ --fix
  ```

### Testing

- Write tests for new features and bug fixes
- Run the test suite:
  ```bash
  pytest
  ```
- Aim for clear, readable tests
- Mock external API calls in tests

### Commit Messages

- Use clear, descriptive commit messages
- Start with a verb in imperative mood (e.g., "Add", "Fix", "Update")
- Keep the first line under 72 characters
- Reference issue numbers when applicable (e.g., "Fix #42")

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
2. Make your changes and commit them
3. Push to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```
4. Open a Pull Request on GitHub
5. Fill out the PR template with:
   - Description of changes
   - Related issues
   - Testing performed
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

- Use GitHub Issues for bug reports and feature requests
- Include as much detail as possible
- For bugs: steps to reproduce, expected vs actual behavior
- For features: use case and proposed solution

## Questions?

Open a discussion on GitHub Discussions or ask in an issue.

Thank you for contributing to ModelHop! 🐸
