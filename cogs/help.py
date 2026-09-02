import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from main import LeetCodeBot

logger = logging.getLogger(__name__)


class HelpCog(commands.Cog):
    def __init__(self, bot: "LeetCodeBot") -> None:
        self.bot = bot
        self.database_manager = bot.database_manager

    def help_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="Help - Available Commands",
            description="Here are the available commands for the LeetCode Bot:",
            color=discord.Color.blue(),
        )
        all_slash_cmds = self.bot.tree.get_commands(
            type=discord.AppCommandType.chat_input
        )
        for cmd in all_slash_cmds:
            if isinstance(cmd, app_commands.Group):
                # Subcommands are listed under their parent, not on their own.
                continue
            elif cmd.extras.get("hidden", False):
                # extras["hidden"] is how a command opts out of the listing.
                continue

            value = cmd.description or "No description available."
            parameters_str = ""
            if cmd.parameters:
                params = []
                for param in cmd.parameters:
                    if param.required:
                        params.append(f"`<{param.name}>`")
                    else:
                        params.append(f"`[{param.name}]`")
                parameters_str += " ".join(params)

            embed.add_field(
                name=f"/{cmd.name}" + (f" {parameters_str}" if parameters_str else ""),
                value=value,
                inline=False,
            )
        return embed

    @app_commands.command(name="help", description="Get help about the bot's commands")
    async def help_command(self, interaction: discord.Interaction) -> None:
        """Sends a help message listing available commands."""
        help_embed = self.help_embed()
        await interaction.response.send_message(embed=help_embed)


async def setup(bot: "LeetCodeBot") -> None:
    await bot.add_cog(HelpCog(bot))
