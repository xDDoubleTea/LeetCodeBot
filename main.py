import discord
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
        self.engine = create_engine(DATABASE_URL, echo=False)
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

    async def close(self) -> None:
        await super().close()
        self.engine.dispose()

    async def on_ready(self):
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)
        if not debug:
            await weekly_cache_refresh.start(self)
        print(f"Logged in as {self.user}!")
        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Game("Leetcode Bot"),
        )


async def main():
    bot = LeetCodeBot()
    Base.metadata.create_all(bind=bot.engine)
    try:
        await bot.start(token=bot_token)
    except KeyboardInterrupt:
        await bot.close()
    except Exception as e:
        print(f"An error occurred: {e}")
        exit(1)


@tasks.loop(hours=24 * 7, name="weekly_cache_refresh")
async def weekly_cache_refresh(bot: LeetCodeBot) -> None:
    print("Refreshing LeetCode problems cache...")
    await bot.leetcode_problem_manger.refresh_cache()
    print("LeetCode problems cache refreshed.")


if __name__ == "__main__":
    asyncio.run(main())
