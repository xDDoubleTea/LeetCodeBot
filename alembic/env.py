import asyncio
import os
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Importing these registers their tables on Base.metadata, which autogenerate
# compares against the database. main.py gets away without them because it imports
# core.leetcode_problem, which pulls them in transitively; relying on that here
# would mean a revision silently missing whatever nothing happens to import.
#
# db.problem_list is deliberately absent: its problem_frontend_id is annotated
# Mapped[list[int]], which SQLAlchemy cannot map, so importing it raises. It has no
# table in any existing database. #49 owns designing it properly.
import db.problem
import db.problem_threads
import db.thread_channel  # noqa: F401
from alembic import context
from db.base import Base

config = context.config

# The URL comes from the same .env the bot reads, rather than a second copy in
# alembic.ini. Read straight from the environment instead of through
# config.secrets: that module also requires BOT_TOKEN at import, and applying a
# migration should not need a Discord token.
#
# Only a default, though. A caller that sets the URL explicitly -- the drift test
# pointing at a scratch database, say -- must not be redirected at the real one.
load_dotenv()
_database_url = os.getenv("DATABASE_URL")
if _database_url and not config.get_main_option("sqlalchemy.url", None):
    config.set_main_option("sqlalchemy.url", _database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    # SQLite cannot alter or drop a column in place, so alembic has to rebuild the
    # table. That only works if the revisions are rendered in batch mode.
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    # main.py upgrades the schema at startup and hands its own connection over, so
    # that path must not build a second engine against the same SQLite file.
    connection = config.attributes.get("connection", None)
    if connection is not None:
        do_run_migrations(connection)
        return

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
