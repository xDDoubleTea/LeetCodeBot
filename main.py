import asyncio
import logging
import os
import signal

import aiohttp
import discord
import re2
from discord.ext import commands
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

from config.constants import MY_GUILD, command_prefix
from config.logger import setup_logger
from config.secrets import DATABASE_URL, bot_token, debug
from core.leetcode_api import LeetCodeAPI
from core.leetcode_problem import LeetCodeProblemManager
from core.problem_threads import ProblemThreadsManager
from db.base import Base
from db.database_manager import DatabaseManager

logger = logging.getLogger("main")
setup_logger(log_level=logging.DEBUG if debug else logging.INFO)


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
        intents = discord.Intents.all()
        super().__init__(command_prefix=command_prefix, intents=intents)
        self.engine = create_engine(DATABASE_URL, echo=debug, hide_parameters=True)
        self.tag_cache: list[str] = []
        self.database_manager: DatabaseManager
        self.leetcode_api: LeetCodeAPI
        self.leetcode_problem_manger: LeetCodeProblemManager
        self.problem_threads_manager: ProblemThreadsManager
        self.session: aiohttp.ClientSession

    async def setup_hook(self) -> None:
        self.database_manager: DatabaseManager = DatabaseManager(self, self.engine)

        self.session = aiohttp.ClientSession()
        self.leetcode_api: LeetCodeAPI = LeetCodeAPI(session=self.session)
        self.leetcode_problem_manger: LeetCodeProblemManager = LeetCodeProblemManager(
            leetcode_api=self.leetcode_api,
            database_manager=self.database_manager,
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

    async def close(self) -> None:
        await super().close()
        self.engine.dispose()

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
    bot = LeetCodeBot()

    async def shutdown(sig: signal.Signals, loop: asyncio.AbstractEventLoop):
        if sig:
            logger.info(f"Received exit signal {sig.name}...")

        for task in asyncio.all_tasks(loop):
            task.cancel()
            logger.info(f"Cancelling task {task.get_name()}...")

        await bot.session.close()
        await bot.close()
        logger.info("Shutdown complete.")
        loop.stop()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(
            sig, lambda s=sig: asyncio.create_task(shutdown(s, loop))
        )

    Base.metadata.create_all(bind=bot.engine)
    try:
        await bot.start(token=bot_token)
    except asyncio.CancelledError:
        logger.info("Bot shutdown initiated...")
    except Exception as e:
        logger.exception("An unhandled error occurred:", exc_info=e)
    finally:
        if not bot.is_closed():
            await bot.close()
            logger.info("Bot closed.")


if __name__ == "__main__":
    asyncio.run(main())
