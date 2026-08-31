# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

A Discord bot that gives each LeetCode problem its own forum thread. Python 3.13, `discord.py`, SQLAlchemy async over SQLite, managed with `uv`.

## Commands

```bash
uv run main.py                          # run the bot (applies migrations first)
uv run pytest                           # full suite
uv run pytest tests/test_error_handlers.py::test_a_bug_has_no_user_facing_message
uv run ruff format . && uv run ruff check .
uv run zensical build --clean           # build the docs site
```

`pytest-asyncio` runs in auto mode, so async tests need no `@pytest.mark.asyncio`.

Schema work — see `docs/database.md` for the full flow:

```bash
uv run alembic revision --autogenerate -m "what changed"   # a draft; read it
uv run alembic upgrade head
uv run alembic check                    # exits 255 when models and migrations disagree
```

CI gates every PR on four jobs, all required: `Run Pytest`, `Ruff`, `Alembic`, `Build Docs`.

## Layered structure

`cogs/` holds Discord glue only, `core/` holds business logic and the caches, `utils/` holds pure helpers. A cog fetches through a manager and renders the result; managers never touch `discord`. When logic in a cog is worth testing, move it to `utils/` rather than testing through the cog — see `utils/thread_titles.py`.

## Things that will bite you

**`config/secrets.py` resolves `BOT_TOKEN` at import.** Any import chain reaching it needs a configured environment. This has broken CI twice. Two defences are in place and must stay:

- Cogs import `main` only under `if TYPE_CHECKING:`, with the annotation **quoted**. Python 3.13 evaluates function annotations at definition time, so an unquoted `async def setup(bot: LeetCodeBot)` raises `NameError` on import and the extension silently fails to load.
- The repository-root `conftest.py` sets fake values before pytest collects anything.

**Never add a per-cog error handler.** `utils/error_handlers.py` owns both command families — `ErrorHandlingTree` (passed as `tree_cls`) for app commands, `handle_command_error` for prefix commands. `CommandTree._call` runs a cog handler *and* `on_error`, so a cog-level handler produces two replies.

**Never wrap an exception in bare `Exception`.** Everything downstream dispatches on type: thirteen `isinstance` checks in `error_handlers.py`, and `except FetchError` / `except ProblemNotFound` in `utils/handle_leetcode_interation.py`. `raise Exception(f"...: {e}") from e` flattens all of it, and `from e` already prints the original message. Re-raise bare, or raise a typed exception from `utils/custom_exceptions.py`. A user-facing error should subclass `AppCommandError` and carry a `.message`, which is how discord.py lets it past `CommandInvokeError` and into `app_command_message`.

**Never sync the command tree in `on_ready`.** It fires again on every reconnect. More importantly, Discord lists guild-scoped and global commands *side by side* rather than letting one shadow the other, so mixing `copy_global_to(guild=...)` with a global sync puts two of every command in the picker. Publishing is deliberate: `>sync_app_commands` (global), with `>clear_guild_commands` and `>app_commands_audit` for cleanup.

**Compile user-supplied regex with `re2`, not `re`.** `google-re2` cannot backtrack, so a pathological pattern from a command argument cannot hang the bot. Used by `/problem-title` and `/migrate`.

**`AsyncDatabaseManager.__aexit__` returns `Literal[False]` on purpose.** Annotating it `-> bool` tells a type checker the manager may suppress exceptions, which makes every method returning from inside `async with` look like it can fall through and return `None` — producing a wave of spurious `| None` returns.

## Data flow

Commands read the in-memory cache, then the database. **They never call the LeetCode API on a miss** — `get_problem_with_frontend_id` raises `ProblemNotFound`. Only `refresh_cache` talks to the API, on a daily `tasks.loop` and on `/refresh`. `/daily` is the exception, since the daily problem is not addressable by id.

`/problem`, `/daily` and `/random` are wrapped in `handle_leetcode_interaction` (`utils/handle_leetcode_interation.py`, note the filename typo), which defers, resolves errors and creates or reuses the thread. Their bodies only return a `ProblemWithTags`.

## Migrations

`main.py` applies them at startup, handing `alembic/env.py` its own connection through `config.attributes["connection"]`. `env.py` branches on that: it must not build a second engine, and must not call `fileConfig`, which would disable every logger the bot had configured.

`alembic/env.py` imports each model module explicitly. A model whose module nothing imports is absent from `Base.metadata`, and autogenerate then emits `op.drop_table` for its table with no warning. `db/problem_list.py` is deliberately excluded — its `Mapped[list[int]]` annotation raises on import, and issue #49 owns fixing it. Anything adding that module must add the import in the same change.

Generate revisions against a database built by migrations. The deployed database predates alembic, so its constraints are anonymous and `alembic check` reports five spurious `add_constraint` diffs there.

## Conventions

- Conventional Commits.
- Branch off `main`, open a PR, wait for checks, squash-merge. Never commit to `main`.
- Known typo in a public attribute: `bot.leetcode_problem_manger`.
