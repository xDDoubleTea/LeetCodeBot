import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

# Importing the model modules registers their tables on Base.metadata, which
# create_all below needs.
import db.problem
import db.problem_threads
import db.thread_channel  # noqa: F401
from db.async_db_manager import AsyncDatabaseManager
from db.base import Base


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
