from discord.ext import commands
import discord
from discord import app_commands


class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.database_manager = bot.database_manager

    @app_commands.command(name="ping", description="Check the bot's latency")
    async def ping(self, interaction: discord.Interaction):
        latency = self.bot.latency * 1000
        await interaction.response.send_message(f"Pong! Latency: {round(latency)} ms")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(General(bot))
