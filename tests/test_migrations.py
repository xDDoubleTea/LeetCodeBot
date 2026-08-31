"""
Guards against the migrations drifting from the models.

`Base.metadata.create_all` used to build the schema, so the models were the only
source of truth and could not disagree with anything. Now the migrations own the
schema, and a model change without a matching revision means the bot runs against a
database missing whatever the change added -- surfacing as `OperationalError: no
such column` mid-command rather than at startup.
"""

from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from alembic import command
from db.base import Base

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


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
