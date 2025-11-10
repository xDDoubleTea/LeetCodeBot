from discord.ext import commands
import discord
from discord import app_commands
from main import LeetCodeBot


class HelpCog(commands.Cog):
    def __init__(self, bot: LeetCodeBot):
        self.bot = bot
        self.database_manager = bot.database_manager
        self.logger = bot.logger

    def help_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="Help - Available Commands",
            description="Here are the available commands for the LeetCode Bot:",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="/help", value="Get help about the bot's commands", inline=False
        )
        # Add more commands as needed
        return embed

    @app_commands.command(name="help", description="Get help about the bot's commands")
    async def help_command(self, interaction: discord.Interaction) -> None:
        """Sends a help message listing available commands."""
        help_message = (
            "Here are the available commands:\n"
            "/help - Get help about the bot's commands\n"
            # Add more commands as needed
        )
        await interaction.response.send_message(help_message, ephemeral=True)


async def setup(bot: LeetCodeBot) -> None:
    await bot.add_cog(HelpCog(bot))
