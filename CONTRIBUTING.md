# Contributing to Open Assistant

Thanks for your interest in contributing! Here's how to get started.

## Getting started

1. Fork the repo and clone your fork
2. Create a feature branch from `main`
3. Install dependencies: `uv sync`
4. Make your changes
5. Run tests: `uv run pytest`
6. Run the linter: `uv run ruff check . --fix && uv run ruff format .`
7. Push and open a pull request against `main`

## Pull requests

- All PRs require review before merging
- Keep PRs focused — one feature or fix per PR
- Write clear commit messages explaining *why*, not just *what*
- Add tests for new functionality
- Make sure existing tests pass

## Code style

- Python: [Ruff](https://docs.astral.sh/ruff/) handles formatting and linting (config in `pyproject.toml`)
- Line length: 100 characters
- Target: Python 3.10+

## Project structure

```
src/                    # Core assistant runtime
  agent/                # Claude Agent SDK integration
  channels/             # Telegram + WhatsApp handlers
  scheduler/            # Cron task engine
  memory/               # Google Drive memory sync
open_assistant/         # CLI + setup wizard (pip-installable)
baileys-bridge/         # WhatsApp Web sidecar (Node.js)
tests/                  # pytest test suite
```

## Reporting issues

- Use [GitHub Issues](https://github.com/ribeirorod/open-assitant/issues)
- Include steps to reproduce, expected vs actual behavior, and relevant logs

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
