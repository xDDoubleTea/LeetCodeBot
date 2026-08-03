import logging

from discord import Client
from discord.ext.commands import Bot
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)


class AsyncDatabaseManager:
    def __init__(self, bot: Bot | Client, engine: AsyncEngine):
        self.bot = bot
        self.engine = engine
        self.session: AsyncSession | None = None
        self._sessionmaker = async_sessionmaker(
            bind=self.engine, autoflush=True, expire_on_commit=False
        )

    async def __aenter__(self) -> AsyncSession:
        try:
            logger.debug("Creating new async database session...")
            self.session = self._sessionmaker()
            return self.session
        except Exception as e:
            logger.error("Database connection error", exc_info=e)
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            assert self.session
            logger.debug("Closing async database session...")
            if exc_type:
                logger.error(
                    f"Exception occurred: {exc_val}. Rolling back session...",
                    exc_info=exc_val,
                )
                await self.session.rollback()
            else:
                await self.session.commit()
            await self.session.close()
        except AssertionError:
            logger.error("Database session was not initialized correctly.")
            return True
        finally:
            return False
