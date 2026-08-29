# Database

The schema is managed by [alembic](https://alembic.sqlalchemy.org/). The bot applies
any outstanding migrations at startup, before it connects to Discord, so a running bot
is always at the latest revision.

## How it works

Each schema change is a Python file under `alembic/versions/`. Every file names the
revision it follows, so together they form a chain. Alembic creates an
`alembic_version` table in the database holding a single row: the revision that
database is currently at. To bring a database up to date it reads that row, works out
which revisions come after it, and runs them in order.

The models under `db/` remain the source of truth for what the schema *should* be.
`alembic/env.py` points at `Base.metadata` so alembic can compare the two.

## Commands

Run these from the repository root.

| Command | Purpose |
| --- | --- |
| `uv run alembic upgrade head` | Apply outstanding migrations |
| `uv run alembic current` | Show the revision this database is at |
| `uv run alembic history` | List the revision chain |
| `uv run alembic revision --autogenerate -m "message"` | Write a new migration from model changes |
| `uv run alembic downgrade -1` | Undo the most recent migration |

The database URL comes from `DATABASE_URL` in your `.env`, the same value the bot uses.

## Changing the schema

1. Edit the model under `db/`.
2. Run `uv run alembic revision --autogenerate -m "what changed"`.
3. **Read the generated file.** Autogenerate produces a draft. It cannot detect a
   rename — it emits a drop plus an add, which loses the column's data — and it is
   inconsistent about server defaults.
4. Run `uv run pytest tests/test_migrations.py` to confirm the migration reproduces the
   models.
5. Commit the model change and the revision together.

Generate revisions against a database that was itself built by migrations. A database
created before alembic was adopted has unnamed constraints, and autogenerate will
propose renaming all of them alongside your actual change.

`tests/test_migrations.py` runs in CI and fails if the models and the migrations
disagree, so a model change committed without its revision does not reach `main`.

## Existing databases

A database created before alembic was adopted has all the tables but no
`alembic_version` table. Running `upgrade head` against it tries to create tables that
already exist:

```
sqlite3.OperationalError: table guild_forum_channel already exists
```

Mark it as already at the current revision instead, which records the version without
running any migrations:

```bash
uv run alembic stamp head
```

This is a one-time step, needed for the deployed database and for any local
`db/testbot.db` that predates alembic. In Docker, `restart: unless-stopped` means a bot
that fails this way restarts forever, so do the stamp before pulling the change.

## SQLite

SQLite cannot alter or drop a column in place, so alembic rebuilds the whole table.
This is enabled by `render_as_batch=True` in `alembic/env.py`, and generated revisions
use `with op.batch_alter_table(...)`.

The rebuild has to name every constraint it recreates, which is why `db/base.py` sets a
`naming_convention` on `Base.metadata`.
