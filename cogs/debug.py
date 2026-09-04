import logging
from typing import TYPE_CHECKING

from discord import Interaction, app_commands
from discord.ext import commands

from utils.custom_exceptions import (
    LeetCodeUserNameNotFound,
)

if TYPE_CHECKING:
    from main import LeetCodeBot
from utils.checks import is_me_app_command

logger = logging.getLogger(__name__)


class Debug(commands.Cog):
    def __init__(self, bot: "LeetCodeBot") -> None:
        self.bot = bot
        self.database_manager = bot.database_manager

    debug = app_commands.Group(
        name="debug",
        description="Debug commands for the LeetCode Bot",
        extras={"hidden": True},
    )

    @debug.command(
        name="reload-graphql-queries", description="Reloads the graphql queries"
    )
    @is_me_app_command()
    async def reload_graphql_queries(self, interaction: Interaction) -> None:
        await interaction.response.send_message(
            "Reloading graphql queries.", ephemeral=True
        )
        await self.bot.leetcode_api.reload_graphql_queries()
        await interaction.followup.send("Graphql queries reloaded.", ephemeral=True)

    @debug.command(name="print_problems_cache", description="Print the problems cache")
    @is_me_app_command()
    async def print_problems_cache(self, interaction: Interaction) -> None:
        """Prints the current problems cache to the console."""
        await interaction.response.send_message(
            "Printing problems cache to console...", ephemeral=True
        )
        logger.debug("Problems Cache:")

    @debug.command(name="test-link", description="Test link")
    @is_me_app_command()
    async def test_link(
        self, interaction: Interaction, leetcode_user_name: str
    ) -> None:
        try:
            await self.bot.leetcode_api.user_info(username=leetcode_user_name)
        except LeetCodeUserNameNotFound as e:
            await interaction.response.send_message(e.message, ephemeral=True)
            return

        await self.bot.leetcode_discord_link_manager.upsert_link(
            discord_user_id=interaction.user.id,
            leetcode_user_name=leetcode_user_name,
        )

        await interaction.response.send_message("Done!", ephemeral=True)


async def setup(bot: "LeetCodeBot") -> None:
    await bot.add_cog(Debug(bot))
