from unittest.mock import MagicMock

import pytest

from db.base import Base


@pytest.fixture(scope="session", autouse=True)
def setup_sqlalchemy_mappers():
    # Configure SQLAlchemy mappers once for all tests
    # This is necessary when instantiating ORM models directly in tests that have relationships
    Base.registry.configure()


@pytest.fixture
def mock_logger():
    return MagicMock(spec=logging.Logger)
