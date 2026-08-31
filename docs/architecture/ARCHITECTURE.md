# Developer Documentation & Architecture

## 1. System Overview

**LeetCodeBot** is a Python Discord bot that makes discussing LeetCode problems easier by giving each problem its own forum thread. It is built on `discord.py` and organises its features into extensions ("cogs").

Problem data is fetched from LeetCode's GraphQL API, stored in a SQLite database through SQLAlchemy's async engine, and kept in an in-memory cache in front of both.

## 2. Directory Structure

| Path       | Contents                                                                                                                    |
| ---------- | --------------------------------------------------------------------------------------------------------------------------- |
| `main.py`  | Entry point. The `LeetCodeBot` subclass, migrations, signal handling, shutdown.                                             |
| `cogs/`    | Slash and text commands, one module per area: `leetcode`, `admin`, `general`, `help`, `debug`, `migration`, `problem_list`. |
| `core/`    | The managers holding the business logic and the caches: `leetcode_api`, `leetcode_problem`, `problem_threads`.              |
| `db/`      | SQLAlchemy models and the session manager.                                                                                  |
| `alembic/` | Schema migrations. One file per change under `alembic/versions/`.                                                           |
| `models/`  | Plain dataclasses and enums, e.g. `ProblemDifficulty`. Not ORM models.                                                      |
| `view/`    | `discord.ui` components. Currently the generic pagination view.                                                             |
| `utils/`   | Helpers shared across cogs: checks, error handlers, embed builders, transformers.                                           |
| `graphql/` | The `.graphql` query files sent to LeetCode, loaded at startup.                                                             |
| `config/`  | `constants.py` (tunables and ids), `secrets.py` (reads `.env`), `logger.py`.                                                |
| `tests/`   | The pytest suite.                                                                                                           |

`core/` holds no Discord-facing code and `cogs/` holds no business logic; a cog fetches through a manager and renders the result.

## 3. Main Logic Flow

### Startup Sequence

1. `config/secrets.py` loads `.env` at import time and raises if `BOT_TOKEN` is missing.
2. `main()` configures logging, then constructs `LeetCodeBot`, which creates the async engine.
3. `run_migrations()` applies any outstanding alembic revisions. This happens **before** the bot connects, so a failed migration is a failed startup rather than a bot answering commands against a schema it does not match.
4. `bot.start()` triggers `setup_hook()`, which builds the `aiohttp` session and the managers, loads the GraphQL queries, loads every module in `cogs/`, and warms the problem, thread and tag caches.
5. `on_ready()` copies the global commands to `MY_GUILD` and syncs the tree.

### Shutdown Sequence

`SIGINT` and `SIGTERM` cancel the main task, which leaves the `async with bot:` block. `LeetCodeBot.close()` then tears down the gateway, the `aiohttp` session and the database engine in that order. Disposing the engine matters: aiosqlite's connection worker is a non-daemon thread, so an undisposed engine keeps the interpreter alive after `asyncio.run()` returns. A second `Ctrl+C` is ignored so it cannot interrupt the teardown halfway.

### Error Handling

There are no per-cog error handlers. `utils/error_handlers.py` defines `ErrorHandlingTree`, passed as `tree_cls`, which handles every app command error, and `handle_command_error`, which `LeetCodeBot.on_command_error` delegates to for text commands. Both split errors into ones worth showing the user and ones that are bugs, and reply ephemerally.

### LeetCode Commands

See [Main Features](./main-feature.md).

## 4. Development Setup

See the [Development Guide](../index.md).

```bash
uv sync
cp .env.example .env    # then fill in BOT_TOKEN
uv run main.py
```
