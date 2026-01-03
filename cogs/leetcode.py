from typing import Literal, Optional, Set

from discord import Interaction, Thread, app_commands
from discord.channel import ForumChannel, ThreadWithMessage
from discord.ext import commands

from config.constants import preview_len
from config.secrets import debug
from core.leetcode_api import FetchError
from db.problem import Problem, TopicTags
from models.leetcode import ThreadCreationEnum
from main import LeetCodeBot, logger
from utils.custom_exceptions import ForumChannelNotFound
from utils.embed_presenters import (
    get_difficulty_str_repr,
    get_problem_desc_embed,
    get_user_info_embed,
)


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

    async def _handle_thread_creation(
        self,
        channel: ForumChannel,
        problem: Problem,
        problem_tags: Set[TopicTags],
    ) -> ThreadWithMessage:
        logger.info(
            f"Creating thread in channel {channel.id} for problem {problem.problem_frontend_id}"
        )
        thread_name = f"{problem.problem_frontend_id}. {problem.title}"
        thread_content = f"{problem.url}\n"
        thread_embed = get_problem_desc_embed(
            problem=problem, problem_tags=problem_tags, bot=self.bot
        )
        available_tags = channel.available_tags
        available_tag_names = {tag.name for tag in channel.available_tags}

        logger.debug(f"Available tags in channel {channel.id}: {available_tag_names}")

        tags_to_create = {
            "LeetCode",
            "Easy",
            "Medium",
            "Hard",
        } - available_tag_names
        for tag_name in tags_to_create:
            await channel.create_tag(name=tag_name)

        tags_to_assign = {
            "LeetCode",
            get_difficulty_str_repr(problem.difficulty),
        }

        thread = await channel.create_thread(
            name=thread_name,
            content=thread_content,
            embed=thread_embed,
            applied_tags=[tag for tag in available_tags if tag.name in tags_to_assign],
        )
        await self.problem_threads_manager.create_thread_in_db(
            problem_frontend_id=problem.problem_frontend_id,
            guild_id=channel.guild.id,
            thread_id=thread.thread.id,
        )
        return thread

    @app_commands.command(name="daily", description="Get today's LeetCode problem")
    @app_commands.guild_only()
    async def daily_problem(self, interaction: Interaction) -> None:
        await interaction.response.defer(thinking=True)
        try:
            assert interaction.guild
            logger.info(f"Fetching today's problem for guild {interaction.guild.id}")
            problem = await self.leetcode_problem_manager.get_daily_problem()
            logger.debug(f"Problem fetched: {problem}")

            if not problem:
                await interaction.followup.send(
                    "Daily problem not found. Check the leetcode api by /check_leetcode_api."
                )
                return

            (
                thread,
                thread_creation_enum,
            ) = await self.problem_threads_manager.reopen_or_create_problem_thread(
                problem=problem, guild=interaction.guild, bot=self.bot, is_daily=True
            )
            problem_obj = problem["problem"]
            assert isinstance(problem_obj, Problem)
            if thread_creation_enum == ThreadCreationEnum.CREATE:
                assert isinstance(thread, ThreadWithMessage)
                await interaction.followup.send(
                    f"Created thread for today's problem in {thread.thread.mention}"
                )
            elif thread_creation_enum == ThreadCreationEnum.REOPEN:
                assert isinstance(thread, Thread)
                await interaction.followup.send(
                    f"Thread for today's problem already exists: {thread.mention}"
                )
        except ForumChannelNotFound as e:
            await interaction.followup.send(f"{e}")
            return
        except FetchError as e:
            logger.error("FetchError occurred", exc_info=e)
            await interaction.followup.send(f"{e}")
            return
        except Exception as e:
            logger.error("An error occurred", exc_info=e)
            await interaction.followup.send(
                f"An error occurred while processing the request: {e}"
            )
            return

    @app_commands.command(
        name="problem",
        description="Get Leetcode Problem with problem ID",
    )
    @app_commands.describe(id="The ID of the LeetCode problem")
    @app_commands.guild_only()
    async def leetcode_problem(self, interaction: Interaction, id: int) -> None:
        await interaction.response.defer(thinking=True)
        try:
            assert interaction.guild
            logger.info(
                f"Fetching problem with ID {id} for guild {interaction.guild.id}"
            )
            problem = await self.leetcode_problem_manager.get_problem_with_frontend_id(
                id
            )
            logger.debug(f"Problem fetched: {problem}")
            if not problem:
                await interaction.followup.send(f"Problem with ID {id} not found.")
                return
            (
                thread,
                thread_creation_enum,
            ) = await self.problem_threads_manager.reopen_or_create_problem_thread(
                problem=problem, guild=interaction.guild, bot=self.bot, is_daily=False
            )
            problem_obj = problem["problem"]
            assert isinstance(problem_obj, Problem)
            if thread_creation_enum == ThreadCreationEnum.CREATE:
                assert isinstance(thread, ThreadWithMessage)
                await interaction.followup.send(
                    f"Created thread for problem {problem_obj.problem_frontend_id} in {thread.thread.mention}"
                )
            elif thread_creation_enum == ThreadCreationEnum.REOPEN:
                assert isinstance(thread, Thread)
                await interaction.followup.send(
                    f"Thread for problem {problem_obj.problem_frontend_id} already exists: {thread.mention}"
                )
        except ForumChannelNotFound as e:
            await interaction.followup.send(f"{e}")
            return
        except FetchError as e:
            logger.error("FetchError occurred", exc_info=e)
            await interaction.followup.send(f"{e}")
            return
        except Exception as e:
            logger.error("An error occurred", exc_info=e)
            await interaction.followup.send(
                f"An error occurred while processing the request: {e}"
            )
            return

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
        name="random", description="Returns a random leetcode problem"
    )
    @app_commands.describe(
        difficulty="The problem difficulty",
        premium="Whether to include premium problems",
    )
    async def random_problem(
        self,
        interaction: Interaction,
        difficulty: Optional[Literal["Easy", "Medium", "Hard"]],
        premium: bool = False,
    ):
        await interaction.response.defer(thinking=True)
        try:
            assert interaction.guild
            logger.info(
                f"Fetching problem with ID {id} for guild {interaction.guild.id}"
            )
            problem = await self.leetcode_problem_manager.get_random_problem(
                difficulty=difficulty, premium=premium
            )
            logger.debug(f"Problem fetched: {problem}")
            if not problem:
                await interaction.followup.send(f"Problem with ID {id} not found.")
                return
            (
                thread,
                thread_creation_enum,
            ) = await self.problem_threads_manager.reopen_or_create_problem_thread(
                problem=problem, guild=interaction.guild, bot=self.bot, is_daily=False
            )
            problem_obj = problem["problem"]
            assert isinstance(problem_obj, Problem)
            if thread_creation_enum == ThreadCreationEnum.CREATE:
                assert isinstance(thread, ThreadWithMessage)
                await interaction.followup.send(
                    f"Created thread for problem {problem_obj.problem_frontend_id} in {thread.thread.mention}{'' if not difficulty else f' with difficulty {difficulty}'}"
                )
            elif thread_creation_enum == ThreadCreationEnum.REOPEN:
                assert isinstance(thread, Thread)
                await interaction.followup.send(
                    f"Thread for problem {problem_obj.problem_frontend_id} already exists: {thread.mention}"
                )
        except ForumChannelNotFound as e:
            await interaction.followup.send(f"{e}")
            return
        except FetchError as e:
            logger.error("FetchError occurred", exc_info=e)
            await interaction.followup.send(f"{e}")
            return
        except Exception as e:
            logger.error("An error occurred", exc_info=e)
            await interaction.followup.send(
                f"An error occurred while processing the request: {e}"
            )
            return

        pass

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
