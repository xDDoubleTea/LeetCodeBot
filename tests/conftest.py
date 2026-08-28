from types import SimpleNamespace
from unittest.mock import MagicMock
import logging

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from db.async_db_manager import AsyncDatabaseManager
from db.base import Base

# Importing the model modules registers their tables on Base.metadata, which
# create_all below needs. It also makes Base.registry.configure() independent of
# which test module happens to be collected first: Problem.tags and
# TopicTags.problems only resolve once both sides have been imported.
# db.problem_list is deliberately not imported: ProblemList declares
# Mapped[list[int]], which SQLAlchemy cannot map, so importing it raises. The
# model is unused (cogs/problem_list.py never references it) -- see issue #42.
import db.problem  # noqa: F401
import db.problem_threads  # noqa: F401
import db.thread_channel  # noqa: F401


@pytest.fixture(scope="session", autouse=True)
def setup_sqlalchemy_mappers():
    # Configure SQLAlchemy mappers once for all tests
    # This is necessary when instantiating ORM models directly in tests that have relationships
    Base.registry.configure()


@pytest.fixture
def mock_logger():
    return MagicMock(spec=logging.Logger)


@pytest.fixture
async def engine():
    """A fresh in-memory database, with the schema created."""
    # StaticPool keeps every connection pointed at the same in-memory database;
    # without it each connection would get its own empty one.
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture
def database_manager(engine):
    """The session manager the managers use, wired to the test database."""
    return AsyncDatabaseManager(SimpleNamespace(), engine)
