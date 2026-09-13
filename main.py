import asyncio
import logging
import os
import signal
from pathlib import Path

import aiohttp
import discord
import re2
from alembic.config import Config
from discord.ext import commands
from sqlalchemy import event
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from alembic import command
from config.constants import COMMAND_PREFIX
from config.logger import setup_logger
from config.secrets import DATABASE_URL, bot_token, debug
from core.leetcode_api import LeetCodeAPI
from core.leetcode_dc_link import LeetCodeDCLinkManager
from core.leetcode_problem import LeetCodeProblemManager
from core.problem_threads import ProblemThreadsManager
from db.async_db_manager import AsyncDatabaseManager
from utils.error_handlers import ErrorHandlingTree, handle_command_error

logger = logging.getLogger(__name__)
intents = discord.Intents.all()


def _upgrade_to_head(connection: Connection) -> None:
    cfg = Config(str(Path(__file__).parent / "alembic.ini"))
    cfg.attributes["connection"] = connection
    command.upgrade(cfg, "head")


async def run_migrations(engine: AsyncEngine) -> None:
    """Bring the database up to the latest revision.

    This replaces Base.metadata.create_all, which only ever created missing tables
    and so could not apply any change to a database that already existed.
    """
    logger.info("Applying database migrations...")
    async with engine.connect() as conn:
        await conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        await conn.commit()
        await conn.run_sync(_upgrade_to_head)
        await conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        await conn.commit()
    logger.info("Database is up to date.")


@event.listens_for(Engine, "connect")
def sqlite_engine_connect(dbapi_connection, connection_record):
    def regexp(expr, item):
        if item is None:
            return False
        reg = re2.compile(f"(?i){expr}")
        return reg.search(item) is not None

    dbapi_connection.create_function("REGEXP", 2, regexp)


class LeetCodeBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=COMMAND_PREFIX,
            intents=intents,
            tree_cls=ErrorHandlingTree,
        )
        self.engine = create_async_engine(
            DATABASE_URL, echo=debug, hide_parameters=True
        )
        self.database_manager: AsyncDatabaseManager
        self.leetcode_api: LeetCodeAPI
        self.leetcode_problem_manger: LeetCodeProblemManager
        self.problem_threads_manager: ProblemThreadsManager
        self.leetcode_discord_link_manager: LeetCodeDCLinkManager
        self.aiohttp_session: aiohttp.ClientSession

    async def setup_hook(self) -> None:
        self.database_manager: AsyncDatabaseManager = AsyncDatabaseManager(
            self, self.engine
        )

        self.aiohttp_session = aiohttp.ClientSession()
        self.leetcode_api: LeetCodeAPI = LeetCodeAPI(session=self.aiohttp_session)

        self.leetcode_discord_link_manager = LeetCodeDCLinkManager(
            async_db_manager=self.database_manager, leetcode_api=self.leetcode_api
        )
        self.leetcode_problem_manger: LeetCodeProblemManager = LeetCodeProblemManager(
            leetcode_api=self.leetcode_api,
            async_database_manager=self.database_manager,
        )
        self.problem_threads_manager: ProblemThreadsManager = ProblemThreadsManager(
            self.database_manager,
            leetcode_problem_manager=self.leetcode_problem_manger,
        )

        logger.info("Loading Graphql queries.")
        self.leetcode_api._load_graphql_queries()
        logger.info("Graphql queries loaded.")

        logger.info("Loading cogs...")
        for cog in os.listdir("cogs"):
            if cog.endswith(".py") and not cog.startswith("_"):
                await self.load_extension(f"cogs.{cog[:-3]}")
        logger.info("Cogs loaded.")

        logger.info("Initializing caches...")
        await self.leetcode_problem_manger.init_cache()
        await self.problem_threads_manager.init_cache()
        await self.leetcode_discord_link_manager.init_cache()
        logger.info("Caches initialized.")

    async def on_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        await handle_command_error(ctx, error)

    async def close(self) -> None:
        try:
            await super().close()
        finally:
            try:
                session = getattr(self, "session", None)
                if session is not None:
                    await session.close()
            finally:
                await self.engine.dispose()

    async def on_ready(self):
        synced = await self.tree.sync()
        logger.debug(f"Synced {len(synced)} app commands globally.")
        logger.info("Logged in as %s!", self.user)
        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                name="Solving LeetCode Problems",
                type=discord.ActivityType.watching,
            ),
        )


async def main():
    setup_logger(log_level=logging.DEBUG if debug else logging.INFO)
    bot = LeetCodeBot()

    main_task = asyncio.current_task()
    assert main_task is not None
    stopping = False

    def request_stop(sig: signal.Signals) -> None:
        nonlocal stopping
        if stopping:
            logger.warning(
                f"Received {sig.name} again, shutdown already in progress..."
            )
            return
        stopping = True
        logger.info(f"Received exit signal {sig.name}...")
        main_task.cancel()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, request_stop, sig)

    try:
        async with bot:
            await run_migrations(bot.engine)

            await bot.start(token=bot_token)
    except asyncio.CancelledError:
        logger.info("Bot shutdown initiated...")
    except Exception as e:
        logger.exception("An unhandled error occurred:", exc_info=e)
    finally:
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
