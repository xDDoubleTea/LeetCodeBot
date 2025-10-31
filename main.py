import discord
from discord.ext import commands
from config.constants import command_prefix, MY_GUILD
from config.secrets import bot_token, DATABASE_URL
import asyncio
from db.database_manager import DatabaseManager
from sqlalchemy import create_engine


class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix=command_prefix, intents=intents)
        self.engine = create_engine(DATABASE_URL, echo=True)
        self.database_manager = DatabaseManager(self, self.engine)

    async def setup_hook(self) -> None:
        await self.load_extension("cogs.general")

    async def close(self) -> None:
        await super().close()
        self.engine.dispose()

    async def on_ready(self):
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)
        print(f"Logged in as {self.user}!")


async def main():
    bot = MyBot()
    try:
        await bot.start(token=bot_token)
    except KeyboardInterrupt:
        await bot.close()
    except Exception as e:
        print(f"An error occurred: {e}")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
