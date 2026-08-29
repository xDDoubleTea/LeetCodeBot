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
from config.constants import MY_GUILD, command_prefix
from config.logger import setup_logger
from config.secrets import DATABASE_URL, bot_token, debug
from core.leetcode_api import LeetCodeAPI
from core.leetcode_problem import LeetCodeProblemManager
from core.problem_threads import ProblemThreadsManager
from db.async_db_manager import AsyncDatabaseManager
from utils.error_handlers import ErrorHandlingTree, handle_command_error

logger = logging.getLogger(__name__)
intents = discord.Intents.all()


def _upgrade_to_head(connection: Connection) -> None:
    # alembic.ini is resolved from this file rather than the working directory: the
    # container runs from /app, but a local `uv run main.py` should not depend on
    # where it was launched from.
    cfg = Config(str(Path(__file__).parent / "alembic.ini"))
    # Hand env.py the connection we already hold, so it does not open a second one
    # against the same SQLite file.
    cfg.attributes["connection"] = connection
    command.upgrade(cfg, "head")


async def run_migrations(engine: AsyncEngine) -> None:
    """Bring the database up to the latest revision.

    This replaces Base.metadata.create_all, which only ever created missing tables
    and so could not apply any change to a database that already existed.
    """
    logger.info("Applying database migrations...")
    async with engine.begin() as conn:
        await conn.run_sync(_upgrade_to_head)
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
            command_prefix=command_prefix,
            intents=intents,
            tree_cls=ErrorHandlingTree,
        )
        self.engine = create_async_engine(
            DATABASE_URL, echo=debug, hide_parameters=True
        )
        self.tag_cache: list[str] = []
        self.database_manager: AsyncDatabaseManager
        self.leetcode_api: LeetCodeAPI
        self.leetcode_problem_manger: LeetCodeProblemManager
        self.problem_threads_manager: ProblemThreadsManager
        self.session: aiohttp.ClientSession

    async def setup_hook(self) -> None:
        self.database_manager: AsyncDatabaseManager = AsyncDatabaseManager(
            self, self.engine
        )

        self.session = aiohttp.ClientSession()
        self.leetcode_api: LeetCodeAPI = LeetCodeAPI(session=self.session)
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

        all_topics_dict = await self.leetcode_problem_manger.get_all_topics_from_db()
        self.tag_cache = [topic.tag_name for topic in all_topics_dict.values()]
        logger.info("Caches initialized.")

    async def on_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        await handle_command_error(ctx, error)

    async def close(self) -> None:
        # engine.dispose() has to run on every path out of here. aiosqlite's
        # connection worker is a non-daemon thread, so an undisposed engine
        # outlives asyncio.run() and blocks the interpreter in
        # threading._shutdown() forever.
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
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)
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
        # Only this task is cancelled: bot.close() tears the gateway, the HTTP
        # session and the engine down in order, and cancelling every task would
        # interrupt that teardown half-way. The guard above keeps a second
        # Ctrl+C from cancelling us again mid-shutdown.
        main_task.cancel()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, request_stop, sig)

    try:
        # Entering the bot's context means close() runs on every exit path,
        # including a failed migration.
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
