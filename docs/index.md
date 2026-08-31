# Development Guide

## Setting Up Your Development Environment

This project uses [uv](https://github.com/astral-sh/uv) as the python package manager. Make sure it is installed.

This project uses [Rapptz/discord.py: An API wrapper for Discord written in Python.](https://github.com/Rapptz/discord.py) for interacting with the Discord API.

Install the dependencies:

```bash
uv sync
```

That creates a virtual environment at `.venv`. You do not need to activate it — `uv run <command>` uses it automatically.

Copy `.env.example` to `.env` and fill it in:

| Variable       | Purpose                                                 |
| -------------- | ------------------------------------------------------- |
| `BOT_TOKEN`    | Your Discord bot token. Required.                       |
| `DATABASE_URL` | SQLAlchemy URL, e.g. `sqlite+aiosqlite:///./db/test.db` |
| `DEBUG`        | `True` turns on debug logging and SQL echo              |

`config/secrets.py` reads these at import and raises if `BOT_TOKEN` is missing.

### Creating a Discord Bot

There are tons of tutorials online on how to create a discord bot and get its token, here is a quick one:

[Creating a Discord Bot in Python - GeeksforGeeks](https://www.geeksforgeeks.org/python/discord-bot-in-python/)

TL;DR: Go to discord developer portal, create a new application, add a bot to it, copy the token and invite the bot to your server.

### Configuring the Bot

Take a look at `config/constants.py`. `MY_GUILD` is the test guild the command tree is synced to on startup, and `DEV_ID` is the Discord user id allowed to run the developer-only commands in `cogs/debug.py`. Both ship with the maintainer's ids and need replacing.

`command_prefix` sets the prefix for the text commands; everything user-facing is a slash command.

## Running the Bot Locally

```bash
uv run main.py
```

The bot applies any outstanding database migrations, then connects to Discord. Stop it with `Ctrl+C`; it shuts the gateway, the HTTP session and the database engine down in order.

## The Database

SQLite by default, accessed through SQLAlchemy's async engine. The schema is managed by [alembic](https://alembic.sqlalchemy.org/) and migrations run automatically at startup, so a fresh clone needs no manual setup step.

See [Database](./database.md) for the commands, how to change the schema, and what to do with a database created before alembic was adopted.

## Testing

The test suite uses `pytest` with `pytest-asyncio` in auto mode, so async tests need no `@pytest.mark.asyncio` marker.

```bash
uv run pytest
uv run pytest tests/test_migrations.py    # just the schema drift guard
```

`tests/conftest.py` provides the fixtures: an in-memory SQLite engine with the schema created, and the session and manager objects wired to it. `tests/test_migrations.py` is the exception — it needs a file-based database, so it builds one under `tmp_path`.

Tests run in CI on every pull request.

## Linting and Formatting

```bash
uv run ruff format .
uv run ruff check .
```

Both run in CI and must be clean before a pull request can merge.

## Editor Setup

After `uv sync`, point your editor's Python interpreter at `.venv/bin/python`.

- **VSCode**: usually detects `.venv` on its own. If not, `Ctrl+Shift+P` → `Python: Select Interpreter`.
- **Zed**: detects `.venv` automatically; install the Ruff extension for inline lint and format-on-save.
- **Neovim**: `basedpyright` (or `pyright`) plus `ruff` via your LSP setup.

## Architecture Overview

Please refer to the [Architecture Documentation](./architecture/ARCHITECTURE.md).
