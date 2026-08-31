"""
Guards against the migrations drifting from the models.

`Base.metadata.create_all` used to build the schema, so the models were the only
source of truth and could not disagree with anything. Now the migrations own the
schema, and a model change without a matching revision means the bot runs against a
database missing whatever the change added -- surfacing as `OperationalError: no
such column` mid-command rather than at startup.
"""

import logging
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from alembic import command
from db.base import Base

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


@pytest.fixture(autouse=True)
def restore_logging():
    """
    Put logging back the way it was found.

    The CLI path through env.py applies alembic.ini's [loggers] section, which
    disables every logger that already existed and resets root. Without this the
    first test here would silence the rest of the run.
    """
    root = logging.getLogger()
    saved_level = root.level
    saved_handlers = root.handlers[:]
    saved_disabled = {
        name: logger.disabled
        for name, logger in logging.root.manager.loggerDict.items()
        if isinstance(logger, logging.Logger)
    }

    yield

    root.setLevel(saved_level)
    root.handlers[:] = saved_handlers
    for name, disabled in saved_disabled.items():
        logger = logging.root.manager.loggerDict.get(name)
        if isinstance(logger, logging.Logger):
            logger.disabled = disabled


def test_migrations_reproduce_the_models(tmp_path):
    """
    Upgrading an empty database to head must produce exactly Base.metadata.

    A file-based database is needed rather than the in-memory engine from
    conftest: alembic opens its own connection, and `sqlite://` would give it a
    different, empty database.
    """
    db_path = tmp_path / "drift.db"

    config = Config(str(ALEMBIC_INI))
    # env.py drives an async engine, as production does. The comparison below wants
    # a plain connection, so it opens the same file through the sync driver.
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")
    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{db_path}")

    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        diff = compare_metadata(context, Base.metadata)

    engine.dispose()

    assert diff == [], (
        "The migrations no longer match the models. Run "
        "`uv run alembic revision --autogenerate -m '...'`, read the generated "
        f"revision, and commit it. Difference: {diff}"
    )


def test_embedded_migrations_leave_logging_alone(tmp_path):
    """
    Upgrading through a caller-supplied connection must not reconfigure logging.

    main.py sets up the bot's handlers and then applies migrations. env.py used to
    call fileConfig unconditionally, which defaults to disable_existing_loggers=True
    -- so the bot logged its "Applying database migrations..." line and then went
    silent for the rest of its life, gateway and command logs included.
    """
    db_path = tmp_path / "logging.db"

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("tests.embedded_migration_caller")
    root_level_before = logging.getLogger().level

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.begin() as connection:
            config = Config(str(ALEMBIC_INI))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
    finally:
        engine.dispose()

    assert not logger.disabled, (
        "Running migrations in-process disabled the caller's loggers. env.py must "
        "not call fileConfig when it was handed a connection."
    )
    assert logging.getLogger().level == root_level_before, (
        "Running migrations in-process reset the root logger's level to "
        "alembic.ini's WARNING."
    )
