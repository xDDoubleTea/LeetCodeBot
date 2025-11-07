from typing import Set
import discord
from discord import Interaction, app_commands
from discord.channel import ForumChannel, ThreadWithMessage
from discord.embeds import Embed
from discord.ext import commands
from core.leetcode_api import FetchError
from utils.discord_utils import try_get_channel

from config.constants import preview_len
from config.secrets import debug

from db.problem import Problem, TopicTags
from main import LeetCodeBot
from models.leetcode import ProblemDifficulity
from discord.ext import tasks


class LeetCode(commands.Cog):
    def __init__(self, bot: LeetCodeBot) -> None:
        self.bot = bot
        self.database_manager = bot.database_manager
        self.leetcode_problem_manager = bot.leetcode_problem_manger
        self.leetcode_api = bot.leetcode_api
        self.problem_threads_manager = bot.problem_threads_manager

    @tasks.loop(hours=24 * 7, name="weekly_cache_refresh")
    async def weekly_cache_refresh(self) -> None:
        print("Refreshing LeetCode problems cache...")
        await self.leetcode_problem_manager.refresh_cache()
        print("LeetCode problems cache refreshed.")

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if not debug and not self.weekly_cache_refresh.is_running():
            self.weekly_cache_refresh.start()

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

    async def parse_problem_desc(self, content: str) -> str:
        """
        Parses the problem description from the LeetCode API response.
        """
        if not content:
            return "No description available."
        return content[:preview_len] + ("..." if len(content) > preview_len else "")

    async def get_problem_desc_picture(self, problem: Problem) -> str:
        return ""

    async def get_problem_desc_embed(
        self, problem: Problem, problem_tags: Set[TopicTags]
    ) -> Embed:
        embed = Embed(
            title=f"{problem.problem_frontend_id}. {problem.title}",
            url=problem.url,
            description=problem.description,
        )
        difficulty_str = self.get_difficulty_str_repr(problem.difficulty)
        embed.add_field(name="Difficulty", value=difficulty_str, inline=True)
        embed.add_field(
            name="Tags",
            value=", ".join(map(lambda tag: tag.tag_name, problem_tags)),
            inline=True,
        )
        embed.color = await self.get_embed_color(problem.difficulty)
        assert self.bot.user is not None and self.bot.user.avatar is not None
        embed.set_footer(
            text=f"LeetCode Bot - {self.bot.user.display_name}",
            icon_url=self.bot.user.avatar.url,
        )
        return embed

    async def _create_thread(
        self,
        channel: ForumChannel,
        problem: Problem,
        problem_tags: Set[TopicTags],
        is_daily: bool = False,
    ) -> ThreadWithMessage:
        thread_name = f"{problem.problem_frontend_id}. {problem.title}"
        thread_content = f"{problem.url}\n"
        thread_embed = await self.get_problem_desc_embed(problem, problem_tags)
        available_tags = channel.available_tags
        available_tag_names = {tag.name for tag in channel.available_tags}
        tags_to_create = {
            "LeetCode",
            "Problem" if not is_daily else "Daily",
            "Easy",
            "Medium",
            "Hard",
        } - available_tag_names
        for tag_name in tags_to_create:
            await channel.create_tag(name=tag_name)

        tags_to_assign = {
            "LeetCode",
            "Problem" if not is_daily else "Daily",
            self.get_difficulty_str_repr(problem.difficulty),
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
        problem = await self.leetcode_problem_manager.get_daily_problem()
        if debug:
            print(problem)
        if not problem:
            await interaction.followup.send("Daily problem not found.")
            return

        problem_obj = problem["problem"]
        assert isinstance(problem_obj, Problem)
        assert isinstance(problem["tags"], Set)
        assert interaction.guild
        channel = await self.problem_threads_manager.get_forum_channel(
            interaction.guild.id
        )
        if not channel:
            await interaction.followup.send(
                "The bot doesn't know which Fourm Channel should the problem be created! Please use /set_thread_channel first to set the Fourm Channel!"
            )
            return
        forum_channel = await try_get_channel(
            guild=interaction.guild, channel_id=channel.channel_id
        )
        if not isinstance(forum_channel, ForumChannel):
            await interaction.followup.send(
                "Something went wrong! The forum channel is not found or not a valid forum channel. Contact the developer for help."
            )
            return
        forum_thread = await self.problem_threads_manager.get_thread_by_problem_id(
            problem_obj.problem_id, interaction.guild.id
        )
        if not forum_thread:
            thread = await self._create_thread(
                channel=forum_channel,
                problem=problem_obj,
                problem_tags=problem["tags"],
                is_daily=True,
            )
            await interaction.followup.send(
                f"Created thread for today's problem in {thread.thread.mention}."
            )
        else:
            thread_channel = await try_get_channel(
                guild=interaction.guild, channel_id=forum_thread.thread_id
            )
            if not thread_channel:
                await interaction.followup.send(
                    "The thread for today's problem was supposed to exist but cannot be found. It might have been deleted."
                )
                await self.problem_threads_manager.delete_thread_from_db(
                    thread_id=forum_thread.thread_id
                )
                return
            await interaction.followup.send(
                f"Thread for today's problem already exists: {thread_channel.mention}"
            )

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
            channel = await self.problem_threads_manager.get_forum_channel(
                interaction.guild.id
            )
            if not channel:
                await interaction.followup.send(
                    "The bot doesn't know which Fourm Channel should the problem be created! Please use /set_thread_channel first to set the Fourm Channel!"
                )
                return
            problem = await self.leetcode_problem_manager.get_problem(id)
            if not problem:
                await interaction.followup.send(f"Problem with ID {id} not found.")
                return
            problem_obj = problem["problem"]
            assert isinstance(problem_obj, Problem)

            forum_channel = await try_get_channel(
                guild=interaction.guild, channel_id=channel.channel_id
            )
            if not isinstance(forum_channel, ForumChannel):
                await interaction.followup.send(
                    "Something went wrong! The forum channel is not found or not a valid forum channel. Contact the developer for help."
                )
                return
            forum_thread = await self.problem_threads_manager.get_thread_by_problem_id(
                problem_obj.problem_id, interaction.guild.id
            )
            if not forum_thread:
                assert isinstance(problem["tags"], Set)
                thread = await self._create_thread(
                    channel=forum_channel,
                    problem=problem_obj,
                    problem_tags=problem["tags"],
                )
                await interaction.followup.send(
                    f"Created thread for problem {id} in {thread.thread.mention}."
                )
            else:
                thread_channel = await try_get_channel(
                    guild=interaction.guild, channel_id=forum_thread.thread_id
                )
                if not thread_channel:
                    msg = await interaction.followup.send(
                        "The thread for this problem was supposed to exist but cannot be found. It might have been deleted. I will create a new one now."
                    )
                    await self.problem_threads_manager.delete_thread_from_db(
                        thread_id=forum_thread.thread_id
                    )
                    assert isinstance(problem["tags"], Set)
                    thread = await self._create_thread(
                        channel=forum_channel,
                        problem=problem_obj,
                        problem_tags=problem["tags"],
                    )
                    if msg:
                        msg.edit(
                            "Created new thread for problem {id} in {thread.thread.mention}."
                        )
                    return
                await interaction.followup.send(
                    f"Thread for problem {id} already exists: {thread_channel.mention}"
                )

        except FetchError as e:
            await interaction.followup.send(f"{e}")
            return
        except Exception as e:
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
            problem = await self.leetcode_problem_manager.get_problem(id)
            if not problem:
                await interaction.followup.send(f"Problem with ID {id} not found.")
                return
            problem_obj = problem["problem"]
            assert isinstance(problem_obj, Problem)
            assert isinstance(problem["tags"], Set)
            await interaction.followup.send(
                embed=await self.get_problem_desc_embed(problem_obj, problem["tags"])
            )
        except Exception as e:
            await interaction.followup.send(
                f"An error occurred while fetching the problem: {e}"
            )
            return

    @app_commands.command(name="refresh", description="Refresh LeetCode problems cache")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guild_only()
    async def refresh_cache(self, interaction: Interaction) -> None:
        await interaction.response.defer(thinking=True)
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
        name="set_forum_channel", description="Set forum channel for problems"
    )
    @app_commands.describe(channel="The channel to set as thread channel")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guild_only()
    async def set_forum_channel(
        self, interaction: Interaction, channel: ForumChannel
    ) -> None:
        await interaction.response.defer(thinking=True)
        try:
            guild_id = interaction.guild_id
            channel_id = channel.id
            assert guild_id is not None
            await self.problem_threads_manager.add_forum_channel_to_db(
                guild_id, channel_id
            )
            await interaction.followup.send(
                f"Thread channel set to {channel.mention} for this server."
            )
        except Exception as e:
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


async def setup(bot) -> None:
    await bot.add_cog(LeetCode(bot))
