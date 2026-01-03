from typing import Literal, Optional, Set

from discord import Interaction, app_commands
from discord.channel import ForumChannel
from discord.ext import commands

from config.constants import preview_len
from config.secrets import debug
from db.problem import Problem
from main import LeetCodeBot, logger
from utils.embed_presenters import (
    get_problem_desc_embed,
    get_user_info_embed,
)
from utils.handle_leetcode_interation import handle_leetcode_interaction


class LeetCode(commands.Cog):
    def __init__(self, bot: LeetCodeBot) -> None:
        self.bot = bot
        self.database_manager = bot.database_manager
        self.leetcode_problem_manager = bot.leetcode_problem_manger
        self.leetcode_api = bot.leetcode_api
        self.problem_threads_manager = bot.problem_threads_manager

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if (
            not debug
            and not self.leetcode_problem_manager.weekly_cache_refresh.is_running()
        ):
            logger.info("Starting weekly LeetCode cache refresh task...")
            self.leetcode_problem_manager.weekly_cache_refresh.start()

    async def parse_problem_desc(self, content: str) -> str:
        """
        Parses the problem description from the LeetCode API response.
        """
        if not content:
            return "No description available."
        return content[:preview_len] + ("..." if len(content) > preview_len else "")

    @app_commands.command(name="daily", description="Get today's LeetCode problem")
    @app_commands.guild_only()
    @handle_leetcode_interaction(is_daily=True)
    async def daily_problem(self, interaction: Interaction) -> dict | None:
        assert interaction.guild
        logger.info(f"Fetching today's problem for guild {interaction.guild.id}")
        problem = await self.leetcode_problem_manager.get_daily_problem()
        logger.debug(f"Problem fetched: {problem}")
        return problem

    @app_commands.command(
        name="problem",
        description="Get Leetcode Problem with problem ID",
    )
    @app_commands.describe(id="The ID of the LeetCode problem")
    @app_commands.guild_only()
    @handle_leetcode_interaction(is_daily=False)
    async def leetcode_problem(self, interaction: Interaction, id: int) -> dict | None:
        assert interaction.guild
        logger.info(f"Fetching problem with ID {id} for guild {interaction.guild.id}")
        problem = await self.leetcode_problem_manager.get_problem_with_frontend_id(id)
        logger.debug(f"Problem fetched: {problem}")
        return problem

    @app_commands.command(
        name="random", description="Returns a random leetcode problem"
    )
    @app_commands.describe(
        difficulty="The problem difficulty",
        premium="Whether to include premium problems, default is False",
    )
    @app_commands.guild_only()
    @handle_leetcode_interaction(is_daily=False)
    async def random_problem(
        self,
        interaction: Interaction,
        difficulty: Optional[Literal["Easy", "Medium", "Hard"]],
        premium: bool = False,
    ):
        assert interaction.guild
        logger.info(
            f"Fetching random problem (Difficulty: {difficulty}) for guild {interaction.guild.id}"
        )
        problem = await self.leetcode_problem_manager.get_random_problem(
            difficulty=difficulty, premium=premium
        )
        logger.debug(f"Problem fetched: {problem}")
        return problem

    @app_commands.command(
        name="desc", description="Get LeetCode Problem description with problem ID"
    )
    @app_commands.guild_only()
    async def leetcode_desc(self, interaction: Interaction, id: int) -> None:
        await interaction.response.defer(thinking=True)
        try:
            logger.info(
                f"Fetching problem description with ID {id} for guild {interaction.guild_id}"
            )
            problem = await self.leetcode_problem_manager.get_problem_with_frontend_id(
                id
            )
            if not problem:
                await interaction.followup.send(f"Problem with ID {id} not found.")
                return
            problem_obj = problem["problem"]
            assert isinstance(problem_obj, Problem)
            assert isinstance(problem["tags"], Set)
            logger.debug(f"Problem object: {problem_obj}")
            logger.info(f"Sending problem description for problem ID {id}")
            await interaction.followup.send(
                embed=get_problem_desc_embed(problem_obj, problem["tags"], bot=self.bot)
            )
        except Exception as e:
            logger.error("An error occurred", exc_info=e)
            await interaction.followup.send(
                f"An error occurred while fetching the problem: {e}"
            )
            return

    @app_commands.command(
        name="refresh", description="<Admin> Refresh LeetCode problems cache"
    )
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guild_only()
    async def refresh_cache(self, interaction: Interaction) -> None:
        await interaction.response.defer(thinking=True)
        logger.info(
            f"Refreshing LeetCode problems cache for guild {interaction.guild_id}"
        )
        try:
            await self.leetcode_problem_manager.refresh_cache()
        except Exception as e:
            await interaction.followup.send(
                f"An error occurred while refreshing the cache: {e}"
            )
            return
        await interaction.followup.send("LeetCode problems cache refreshed.")

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

    @app_commands.command(
        name="set_forum_channel", description="<Admin> Set forum channel for problems"
    )
    @app_commands.describe(channel="The channel to set as thread channel")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guild_only()
    async def set_forum_channel(
        self, interaction: Interaction, channel: ForumChannel
    ) -> None:
        await interaction.response.defer(thinking=True)
        try:
            logger.info(
                f"Setting forum channel {channel.id} for guild {interaction.guild_id}"
            )
            guild_id = interaction.guild_id
            channel_id = channel.id
            assert guild_id is not None
            await self.problem_threads_manager.add_forum_channel_to_db(
                guild_id, channel_id
            )
            logger.info(
                f"Forum channel {channel.id} set for guild {interaction.guild_id}"
            )
            await interaction.followup.send(
                f"Thread channel set to {channel.mention} for this server."
            )
        except Exception as e:
            logger.error("An error occurred", exc_info=e)
            await interaction.followup.send(
                f"An error occurred while setting the thread channel: {e}"
            )
            return

    @set_forum_channel.error
    async def on_set_forum_error(
        self, interaction: Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message(
                "You do not have the required permissions to use this command.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"An error occurred: {error}", ephemeral=True
            )

    @app_commands.command(name="statistics", description="Get user statistics")
    @app_commands.describe(username="The LeetCode username")
    async def user_statistics(self, interaction: Interaction, username: str) -> None:
        await interaction.response.defer(thinking=True, ephemeral=False)
        try:
            info = await self.leetcode_api.user_info(username=username)
            embed = get_user_info_embed(username=username, info=info, bot=self.bot)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(
                "Something went wrong when fetching user statistics.", exc_info=e
            )
            await interaction.followup.send(
                "Something went wrong when fetching user statistics."
            )


async def setup(bot) -> None:
    await bot.add_cog(LeetCode(bot))
