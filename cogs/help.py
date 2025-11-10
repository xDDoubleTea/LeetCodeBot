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
        all_slash_cmds = self.bot.tree.get_commands(
            type=discord.AppCommandType.chat_input
        )
        for cmd in all_slash_cmds:
            if isinstance(cmd, app_commands.Group):
                continue  # Skip groups for simplicity
            elif cmd.extras.get("hidden", False):
                continue  # Skip hidden commands

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
        # Add more commands as needed
        return embed

    @app_commands.command(name="help", description="Get help about the bot's commands")
    async def help_command(self, interaction: discord.Interaction) -> None:
        """Sends a help message listing available commands."""
        help_embed = self.help_embed()
        await interaction.response.send_message(embed=help_embed)


async def setup(bot: LeetCodeBot) -> None:
    await bot.add_cog(HelpCog(bot))
