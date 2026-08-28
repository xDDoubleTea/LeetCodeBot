import logging
from contextvars import ContextVar

from discord import Client
from discord.ext.commands import Bot
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

# A single AsyncDatabaseManager instance is shared by every cog and both managers
# (see LeetCodeBot.setup_hook), so the active session cannot live on the
# instance: two commands running at the same time would overwrite each other's
# session. A ContextVar keeps one stack per asyncio task instead, and the stack
# (rather than a single value) keeps nested `async with` blocks inside the same
# task correct.
_session_stack: ContextVar[tuple[AsyncSession, ...]] = ContextVar(
    "_session_stack", default=()
)


class AsyncDatabaseManager:
    """
    An async context manager handing out SQLAlchemy sessions.

    Usage from a cog:

        async with self.bot.database_manager as session:
            await session.execute(statement)

    Leaving the block commits, or rolls back if the body raised.
    """

    def __init__(self, bot: Bot | Client, engine: AsyncEngine):
        self.bot = bot
        self.engine = engine
        self._sessionmaker = async_sessionmaker(
            bind=self.engine, autoflush=True, expire_on_commit=False
        )

    async def __aenter__(self) -> AsyncSession:
        try:
            logger.debug("Creating new async database session...")
            session = self._sessionmaker()
        except Exception as e:
            logger.error("Database connection error", exc_info=e)
            raise

        _session_stack.set((*_session_stack.get(), session))
        return session

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        stack = _session_stack.get()
        if not stack:
            logger.error("Database session was not initialized correctly.")
            return False

        session = stack[-1]
        _session_stack.set(stack[:-1])

        try:
            logger.debug("Closing async database session...")
            if exc_type:
                logger.error(
                    f"Exception occurred: {exc_val}. Rolling back session...",
                    exc_info=exc_val,
                )
                await session.rollback()
            else:
                await session.commit()
        finally:
            await session.close()

        # Never return True here: the exception raised inside the `async with`
        # body belongs to the caller, who decides how to report it to the user.
        return False
