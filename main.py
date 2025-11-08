import logging
import discord
import signal
from discord.ext import commands
from config.constants import command_prefix, MY_GUILD
from config.secrets import bot_token, DATABASE_URL
import asyncio
from core.problem_threads import ProblemThreadsManager
from db.base import Base
from core.leetcode_problem import LeetCodeProblemManager
from core.leetcode_api import LeetCodeAPI
from db.database_manager import DatabaseManager
from sqlalchemy import create_engine
import os
from config.secrets import debug
from config.logger import setup_logger


logger = logging.getLogger("LeetCodeBot")


class LeetCodeBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix=command_prefix, intents=intents)
        print("Initializing LeetCodeBot...")
        self.logger = logging.getLogger("LeetCodeBot")
        self.engine = create_engine(DATABASE_URL, echo=debug, hide_parameters=True)
        self.database_manager = DatabaseManager(self, self.engine, logger=self.logger)
        self.leetcode_api = LeetCodeAPI(logger=self.logger)
        self.leetcode_problem_manger = LeetCodeProblemManager(
            leetcode_api=self.leetcode_api,
            database_manager=self.database_manager,
            logger=self.logger,
        )
        self.problem_threads_manager = ProblemThreadsManager(
            self.database_manager,
            leetcode_problem_manager=self.leetcode_problem_manger,
            logger=self.logger,
        )

    async def setup_hook(self) -> None:
        self.logger.info("Loading cogs...")
        for cog in os.listdir("cogs"):
            if cog.endswith(".py"):
                await self.load_extension(f"cogs.{cog[:-3]}")
        self.logger.info("Cogs loaded.")
        self.logger.info("Initializing caches...")
        await self.leetcode_problem_manger.init_cache()
        await self.problem_threads_manager.init_cache()
        self.logger.info("Caches initialized.")

    async def close(self) -> None:
        await super().close()
        self.engine.dispose()

    async def on_ready(self):
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)
        self.logger.info("Logged in as %s!", self.user)
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
            bot.logger.info(f"Received exit signal {sig.name}...")

        for task in asyncio.all_tasks(loop):
            task.cancel()
            bot.logger.info(f"Cancelling task {task.get_name()}...")

        await bot.close()
        bot.logger.info("Shutdown complete.")
        loop.stop()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(
            sig, lambda s=sig: asyncio.create_task(shutdown(s, loop))
        )

    if debug:
        setup_logger(log_level=logging.DEBUG)
    else:
        setup_logger(log_level=logging.INFO)
    Base.metadata.create_all(bind=bot.engine)
    try:
        await bot.start(token=bot_token)
    except asyncio.CancelledError:
        bot.logger.info("Bot shutdown initiated...")
    except Exception as e:
        bot.logger.exception("An unhandled error occurred:", exc_info=e)
    finally:
        if not bot.is_closed():
            await bot.close()
            bot.logger.info("Bot closed.")


if __name__ == "__main__":
    asyncio.run(main())
