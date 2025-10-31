from typing import Optional, Set
import discord
from discord import Interaction, app_commands
from discord.channel import ForumChannel, ThreadWithMessage
from discord.embeds import Embed
from discord.ext import commands
from core.leetcode_api import FetchError
from utils.discord_utils import try_get_channel
from discord.ext import tasks

from db.problem import Problem, TopicTags
from main import LeetCodeBot
from models.leetcode import ProblemDifficulity


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

    async def get_problem_desc_embed(
        self, problem: Problem, problem_tags: Set[TopicTags]
    ) -> Embed:
        embed = Embed(
            title=f"{problem.problem_id}. {problem.title}",
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
        thread_name = f"{problem.problem_id}. {problem.title}"
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
            problem_id=problem.problem_id,
            guild_id=channel.guild.id,
            thread_id=thread.thread.id,
        )
        return thread

    @app_commands.command(name="daily", description="Get today's LeetCode problem")
    async def daily_problem(self, interaction: Interaction) -> None:
        await interaction.response.send_message("This command is not implemented yet.")

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
                await self._create_thread(
                    channel=forum_channel,
                    problem=problem_obj,
                    problem_tags=problem["tags"],
                )
                await interaction.followup.send(
                    f"Created thread for problem {id} in {forum_channel.mention}."
                )
            else:
                thread_channel = await try_get_channel(
                    guild=interaction.guild, channel_id=forum_thread.thread_id
                )
                if not thread_channel:
                    await interaction.followup.send(
                        "The thread for this problem was supposed to exist but cannot be found. It might have been deleted."
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
        self, interaction: Interaction, channel: Optional[ForumChannel]
    ) -> None:
        await interaction.response.defer(thinking=True)
        if not channel:
            if not isinstance(interaction.channel, ForumChannel):
                await interaction.followup.send(
                    "Please specify a valid forum channel or run this command in a forum channel."
                )
                return
            channel = interaction.channel
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


async def setup(bot) -> None:
    await bot.add_cog(LeetCode(bot))
