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
from discord.ext import tasks


class LeetCodeBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix=command_prefix, intents=intents)
        self.engine = create_engine(DATABASE_URL, echo=debug)
        self.database_manager = DatabaseManager(self, self.engine)
        self.leetcode_api = LeetCodeAPI()
        self.leetcode_problem_manger: LeetCodeProblemManager = LeetCodeProblemManager(
            leetcode_api=self.leetcode_api,
            database_manager=self.database_manager,
        )
        self.problem_threads_manager = ProblemThreadsManager(
            self.database_manager, leetcode_problem_manager=self.leetcode_problem_manger
        )

    async def setup_hook(self) -> None:
        for cog in os.listdir("cogs"):
            if cog.endswith(".py"):
                await self.load_extension(f"cogs.{cog[:-3]}")
        await self.leetcode_problem_manger.init_cache()
        await self.problem_threads_manager.init_cache()

    async def close(self) -> None:
        await super().close()
        self.engine.dispose()

    async def on_ready(self):
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)
        print(f"Logged in as {self.user}!")
        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                name="Solving LeetCode Problems!",
                type=discord.ActivityType.watching,
                url="https://leetcode.com",
            ),
        )


async def main():
    bot = LeetCodeBot()

    async def shutdown(sig: signal.Signals, loop: asyncio.AbstractEventLoop):
        for task in asyncio.all_tasks(loop):
            task.cancel()

        await bot.close()

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
        print("Shutting down gracefully...")
    except Exception as e:
        print(f"An unhandled error occurred: {e}")
    finally:
        if not bot.is_closed():
            await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
