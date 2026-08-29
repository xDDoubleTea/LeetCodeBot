import logging

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    # SQLite cannot alter or drop a column in place, so alembic rebuilds the whole
    # table instead, and the rebuild has to name every constraint it recreates.
    # Leaving the names to the backend makes those migrations impossible to write.
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )
