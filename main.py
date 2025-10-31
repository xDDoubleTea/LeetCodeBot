import discord
from discord.ext import commands
from config.constants import command_prefix, MY_GUILD
from config.secrets import bot_token, DATABASE_URL
import asyncio
from db.base import Base
from core.leetcode_problem import LeetCodeProblemManager
from core.leetcode_api import LeetCodeAPI
from db.database_manager import DatabaseManager
from sqlalchemy import create_engine
import os


class LeetCodeBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix=command_prefix, intents=intents)
        self.engine = create_engine(DATABASE_URL, echo=True)
        self.database_manager = DatabaseManager(self, self.engine)
        self.leetcode_api = LeetCodeAPI()
        self.leetcode_problem_manger: LeetCodeProblemManager = LeetCodeProblemManager(
            leetcode_api=self.leetcode_api,
            database_manager=self.database_manager,
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
        print(f"Logged in as {self.user}!")


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


if __name__ == "__main__":
    asyncio.run(main())
