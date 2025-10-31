import discord
from discord import Interaction, app_commands
from discord.embeds import Embed
from discord.ext import commands

from db.problem import Problem
from main import LeetCodeBot
from models.leetcode import ProblemDifficulity


class LeetCode(commands.Cog):
    def __init__(self, bot: LeetCodeBot) -> None:
        self.bot = bot
        self.database_manager = bot.database_manager
        self.leetcode_problem_manager = bot.leetcode_problem_manger
        self.leetcode_api = bot.leetcode_api

    @staticmethod
    def get_difficulty_str_repr(difficulty_db_repr: int) -> str:
        try:
            difficulty = ProblemDifficulity.from_db_repr(difficulty_db_repr)
            return difficulty.str_repr
        except Exception:
            return "Unknown"

    async def get_embed_color(self, difficulty_db_repr: int) -> discord.Color:
        try:
            difficulty = ProblemDifficulity.from_db_repr(difficulty_db_repr)
            return difficulty.embed_color
        except Exception:
            return discord.Color.blue()  # Default to blue if unknown

    async def get_problem_desc_embed(self, problem: Problem) -> Embed:
        embed = Embed(
            title=f"{problem.problem_id}. {problem.title}",
            url=problem.url,
            description=problem.description,
        )
        difficulty_str = self.get_difficulty_str_repr(problem.difficulty)
        embed.add_field(name="Difficulty", value=difficulty_str, inline=True)
        embed.color = await self.get_embed_color(problem.difficulty)
        assert self.bot.user is not None and self.bot.user.avatar is not None
        embed.set_footer(
            text=f"LeetCode Bot - {self.bot.user.display_name}",
            icon_url=self.bot.user.avatar.url,
        )
        return embed

    @app_commands.command(name="daily", description="Get today's LeetCode problem")
    async def daily_problem(self, interaction: Interaction) -> None:
        pass

    @app_commands.command(
        name="problem",
        description="Get Leetcode Problem with problem ID",
    )
    async def leetcode_problem(self, interaction: Interaction, id: int) -> None:
        await interaction.response.defer(thinking=True)
        try:
            problem = await self.leetcode_problem_manager.get_problem(id)
            if not problem:
                await interaction.followup.send(f"Problem with ID {id} not found.")
                return
            problem_obj = problem["problem"]
            assert isinstance(problem_obj, Problem)
            await interaction.followup.send(
                f"Problem ID: {problem_obj.problem_id}, Title: {problem_obj.title}, URL: {problem_obj.url}, Difficulty: {self.get_difficulty_str_repr(problem_obj.difficulty)}"
            )
        except Exception as e:
            await interaction.followup.send(
                f"An error occurred while fetching the problem: {e}"
            )
            return

    @app_commands.command(
        name="desc", description="Get LeetCode Problem description with problem ID"
    )
    async def leetcode_desc(self, interaction: Interaction, id: int) -> None:
        await interaction.response.defer(thinking=True)
        try:
            problem = await self.leetcode_problem_manager.get_problem(id)
            if not problem:
                await interaction.followup.send(f"Problem with ID {id} not found.")
                return
            problem_obj = problem["problem"]
            assert isinstance(problem_obj, Problem)
            await interaction.followup.send(
                embed=await self.get_problem_desc_embed(problem_obj)
            )
        except Exception as e:
            await interaction.followup.send(
                f"An error occurred while fetching the problem: {e}"
            )
            return

    @app_commands.command(name="refresh", description="Refresh LeetCode problems cache")
    async def refresh_cache(self, interaction: Interaction) -> None:
        pass

    @app_commands.command(
        name="check_leetcode_api", description="Check LeetCode API status"
    )
    async def check_leetcode_api(self, interaction: Interaction) -> None:
        await interaction.response.defer(thinking=True)
        try:
            status = await self.leetcode_api.health_check()
            await interaction.followup.send(status)
        except Exception as e:
            await interaction.followup.send(
                f"An error occurred while checking the LeetCode API: {e}"
            )
            return


async def setup(bot) -> None:
    await bot.add_cog(LeetCode(bot))
