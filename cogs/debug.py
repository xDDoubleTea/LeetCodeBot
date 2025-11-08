from discord.ext import commands
import discord
from discord import app_commands
from utils.checks import is_me_app_command
from main import LeetCodeBot
from db.problem import Problem

from main import logger


class Debug(commands.Cog):
    def __init__(self, bot: LeetCodeBot) -> None:
        self.bot = bot
        self.database_manager = bot.database_manager

    @app_commands.command(
        name="print_problems_cache", description="Print the problems cache"
    )
    @is_me_app_command()
    async def print_problems_cache(self, interaction: discord.Interaction) -> None:
        """Prints the current problems cache to the console."""
        await interaction.response.send_message(
            "Printing problems cache to console...", ephemeral=True
        )
        logger.debug("Problems Cache:")
        print(self.bot.leetcode_problem_manger.problem_cache)

    @app_commands.command(
        name="fetch_problem", description="Fetch a problem by its ID from LeetCode"
    )
    @is_me_app_command()
    async def fetch_problem(
        self, interaction: discord.Interaction, problem_id: int
    ) -> None:
        """Fetches a problem by its ID from LeetCode and adds it to the cache and database."""
        await interaction.response.send_message(
            f"Fetching problem with ID {problem_id}...", ephemeral=True
        )
        try:
            problem_data = (
                await self.bot.leetcode_problem_manger.leetcode_api.fetch_problem_by_id(
                    problem_id
                )
            )
            if not problem_data:
                await interaction.followup.send(
                    f"Problem with ID {problem_id} not found.", ephemeral=True
                )
                return
            problem = problem_data["problem"]
            tags = problem_data["tags"]
            assert isinstance(tags, set) and isinstance(problem, Problem)
            await interaction.followup.send(
                f"Fetched Problem ID: {problem.problem_id}, Title: {problem.title}, Tags: {[tag.tag_name for tag in tags]}",
                ephemeral=True,
            )
        except Exception as e:
            await interaction.followup.send(
                f"An error occurred while fetching the problem: {e}", ephemeral=True
            )


async def setup(bot: LeetCodeBot) -> None:
    await bot.add_cog(Debug(bot))
