import datetime
import logging
from re import sub
from typing import List, Literal, Optional

from discord.ext import tasks
from discord import (
    DMChannel,
    Embed,
    Guild,
    Interaction,
    SelectOption,
    Thread,
    app_commands,
)
from discord.channel import ForumChannel, ThreadWithMessage
from discord.ext import commands

from config.constants import THEME_COLOR, PREVIEW_LEN, LEETCODE_API_REFRESH_TIME
from config.secrets import debug
from db.problem import Problem
from main import LeetCodeBot
from models.leetcode import (
    ProblemDifficulity,
    ProblemWithTags,
    ThreadCreationEnum,
    UserSubmission,
)

from models.pagination import (
    AllTagsPaginationMetaData,
    FilterbyTagPaginationMetaData,
    ProblemTitlePaginationMetaData,
    UserSubmissionPaginationMetaData,
)
from utils import embed_utils
from utils.embed_presenters import (
    get_user_info_embed,
)
from utils.handle_leetcode_interation import handle_leetcode_interaction
from utils.tag_transformer import TagTransformer
from view.pagination_view import (
    AllTagsPaginationView,
    BasePaginationView,
    FilterbyTagPaginationView,
    ProblemTitlePaginationView,
    UserSubmissionPaginationView,
)

logger = logging.getLogger(__name__)


class LeetCode(commands.Cog):
    def __init__(self, bot: LeetCodeBot) -> None:
        self.bot = bot
        self.database_manager = bot.database_manager
        self.leetcode_problem_manager = bot.leetcode_problem_manger
        self.leetcode_api = bot.leetcode_api
        self.problem_threads_manager = bot.problem_threads_manager

    @tasks.loop(time=LEETCODE_API_REFRESH_TIME, name="daily_cache_refresh")
    async def daily_cache_refresh(self) -> None:
        logger.info("Refreshing LeetCode problems cache...")
        await self.leetcode_problem_manager.refresh_cache()
        logger.info("LeetCode problems cache refreshed.")

    async def cog_load(self) -> None:
        if debug:
            return
        logger.info("Starting daily LeetCode cache refresh task...")
        self.daily_cache_refresh.start()

    async def cog_unload(self) -> None:
        self.daily_cache_refresh.cancel()

    async def cog_app_command_error(
        self, interaction: Interaction, error: app_commands.AppCommandError
    ):
        logger.error(error.__cause__)
        if isinstance(error, app_commands.TransformerError):
            await interaction.response.send_message(
                str(error.__cause__), ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "An error occurred.", ephemeral=True
            )

    async def parse_problem_desc(self, content: str) -> str:
        """
        Parses the problem description from the LeetCode API response.
        """
        if not content:
            return "No description available."
        return content[:PREVIEW_LEN] + ("..." if len(content) > PREVIEW_LEN else "")

    def format_submissions(
        self,
        metadata: UserSubmissionPaginationMetaData,
        submission_list: List[UserSubmission],
    ) -> Embed:
        embed = embed_utils.create_themed_embed(
            title=f"Recent Submissions for {metadata.leetcode_username}",
            description=f"Total submissions fetched {metadata.data_len}",
            client=metadata.client,
        )
        for submission in submission_list:
            embed.add_field(
                name=f"{submission.frontend_id}. {submission.title} submission status",
                value=f"""
- [View submission on LeetCode]({submission.url})
- [View Problem](https://leetcode.com/problems/{submission.title_slug})
- Language: {submission.lang_name}
- Time: <t:{submission.timestamp}:f>
- Runtime: {submission.runtime}
- Memory: {submission.memory}
- Status: {submission.status_display}
                """,
                inline=False,
            )

        return embed

    def format_problem(
        self,
        metadata: ProblemTitlePaginationMetaData | FilterbyTagPaginationMetaData,
        problems_list: List[Problem],
    ) -> Embed:
        embed_title = ""
        if isinstance(metadata, ProblemTitlePaginationMetaData):
            embed_title = f"Problem title matching '{metadata.search_regex}'"
        elif isinstance(metadata, FilterbyTagPaginationMetaData):
            embed_title = f"Filtered by tag '{metadata.tag_name_query}'"

        embed = embed_utils.create_themed_embed(
            title=embed_title,
            description=f"Total problems found: {metadata.data_len}",
            client=metadata.client,
        )
        for problem in problems_list:
            embed.add_field(
                name=f"{problem.problem_frontend_id}. {problem.title} [{ProblemDifficulity.from_db_repr(problem.difficulty).value[1]}]",
                value=problem.url,
                inline=False,
            )
        return embed

    def format_tags(
        self, metadata: AllTagsPaginationMetaData, tags_list: List[str]
    ) -> Embed:
        embed = embed_utils.create_themed_embed(
            title="All available tags",
            description=f"Total tags found: {metadata.data_len}",
            client=metadata.client,
        )
        for tag in tags_list:
            embed.add_field(
                name="Tag name",
                value=tag,
                inline=False,
            )
        return embed

    def build_problem_options(
        self, cur_page_problem: List[Problem]
    ) -> List[SelectOption]:
        return [
            SelectOption(
                label=f"{p.problem_frontend_id}. {p.title} [{ProblemDifficulity.from_db_repr(p.difficulty).value[1]}]"[
                    :100
                ],
                value=str(p.problem_frontend_id),
            )
            for p in cur_page_problem
        ]

    async def handle_problem_select(
        self, interaction: Interaction, view: BasePaginationView, values: List[str]
    ):
        problem_frontend_id = int(values[0])
        problem_with_tags = (
            await self.leetcode_problem_manager.get_problem_with_frontend_id(
                problem_frontend_id=problem_frontend_id
            )
        )
        assert interaction.guild
        (
            thread,
            thread_creation_enum,
        ) = await self.problem_threads_manager.reopen_or_create_problem_thread(
            problem_with_tags=problem_with_tags,
            guild=interaction.guild,
            bot=self.bot,
            is_daily=False,
        )

        msg = ""
        if thread_creation_enum == ThreadCreationEnum.CREATE:
            assert isinstance(thread, ThreadWithMessage)
            msg = f"Created thread for problem {problem_with_tags.problem.problem_frontend_id} in {thread.thread.mention}"
        else:
            assert isinstance(thread, Thread)
            msg = f"Thread for problem {problem_with_tags.problem.problem_frontend_id} already exists: {thread.mention}"
            await thread.send(
                f"Thread already exists {interaction.user.mention}",
                delete_after=5,
            )

        await interaction.response.send_message(msg)

    @app_commands.command(
        name="problem-title", description="Get LeetCode Problem with problem title"
    )
    @app_commands.guild_only()
    @app_commands.describe(
        title="The title. Supports regex (google-re2), case insensitve."
    )
    async def problem_title(self, interaction: Interaction, title: str):
        await interaction.response.defer(thinking=True)
        try:
            problems = await self.leetcode_problem_manager.get_problem_with_title_regex(
                title
            )
            logger.debug(problems is None)
            if problems is None:
                await interaction.followup.send("No problem found!", ephemeral=True)
                return
            problems_list = list(problems)

            guild = interaction.guild
            assert isinstance(guild, Guild)
            channel = interaction.channel
            if not channel or isinstance(channel, DMChannel):
                return await interaction.response.send_message(
                    "This command can only be used in a server!", ephemeral=True
                )

            metadata = ProblemTitlePaginationMetaData(
                guild_name=guild.name,
                guild_id=guild.id,
                channel_name=channel.name or "No name",
                channel_id=channel.id,
                user_name=interaction.user.name,
                user_id=interaction.user.id,
                client=interaction.client,
                theme_color=THEME_COLOR,
                search_regex=title,
                data_len=len(problems_list),
            )
            view = ProblemTitlePaginationView(
                metadata=metadata,
                data=problems_list,
                format_page=self.format_problem,
                ephemeral=False,
                select_options_builder=self.build_problem_options,
                select_callback=self.handle_problem_select,
                select_placeholder="Select a problem to open/create thread...",
            )

            await view.send_initial_message(interaction=interaction, followup=True)
        except ValueError as e:
            await interaction.followup.send(
                "Something went wrong when compiling regex. Check syntax!",
                ephemeral=True,
            )
            logger.debug(e)

    @app_commands.command(
        name="check-available-tags",
        description="Get all possible tags for a LeetCode Problem",
    )
    async def check_available_tags(self, interaction: Interaction):
        await interaction.response.defer(thinking=True)

        guild = interaction.guild
        assert isinstance(guild, Guild)
        channel = interaction.channel
        if not channel or isinstance(channel, DMChannel):
            return await interaction.response.send_message(
                "This command can only be used in a server!", ephemeral=True
            )

        metadata = AllTagsPaginationMetaData(
            guild_name=guild.name,
            guild_id=guild.id,
            channel_name=channel.name or "No name",
            channel_id=channel.id,
            user_name=interaction.user.name,
            user_id=interaction.user.id,
            client=interaction.client,
            theme_color=THEME_COLOR,
            data_len=len(self.bot.tag_cache),
        )
        view = AllTagsPaginationView(
            metadata=metadata,
            data=self.bot.tag_cache,
            format_page=self.format_tags,
            ephemeral=False,
            items_per_page=15,
        )
        await view.send_initial_message(interaction=interaction, followup=True)

    @app_commands.command(
        name="filter-by-tag", description="Get LeetCode Problem with tags"
    )
    @app_commands.describe(tag_name="The tag name")
    @app_commands.guild_only()
    async def filter_by_tag(
        self,
        interaction: Interaction,
        tag_name: app_commands.Transform[str, TagTransformer],
    ):
        await interaction.response.defer(thinking=True)
        filtered_list = list(
            await self.leetcode_problem_manager.get_problems_with_tag_name(tag_name)
        )

        guild = interaction.guild
        assert isinstance(guild, Guild)
        channel = interaction.channel
        if not channel or isinstance(channel, DMChannel):
            return await interaction.response.send_message(
                "This command can only be used in a server!", ephemeral=True
            )

        metadata = FilterbyTagPaginationMetaData(
            guild_name=guild.name,
            guild_id=guild.id,
            channel_name=channel.name or "No name",
            channel_id=channel.id,
            user_name=interaction.user.name,
            user_id=interaction.user.id,
            client=interaction.client,
            theme_color=THEME_COLOR,
            tag_name_query=tag_name,
            data_len=len(filtered_list),
        )
        view = FilterbyTagPaginationView(
            metadata=metadata,
            data=filtered_list,
            format_page=self.format_problem,
            ephemeral=False,
            select_options_builder=self.build_problem_options,
            select_callback=self.handle_problem_select,
            select_placeholder="Select a problem to open/create thread...",
        )
        await view.send_initial_message(interaction=interaction, followup=True)

    @app_commands.command(
        name="desc", description="Get LeetCode Problem description with problem ID"
    )
    @app_commands.describe(
        id="The problem id. If not provided, attempts to resovle problem id from thread."
    )
    @app_commands.guild_only()
    async def leetcode_desc(self, interaction: Interaction, id: Optional[int]) -> None:
        await interaction.response.defer(thinking=True)
        try:
            assert interaction.guild
            problem_frontend_id = None
            if id:
                problem_frontend_id = id

            if not id and not isinstance(interaction.channel, Thread):
                await interaction.followup.send(
                    "This command should be used in a problem thread if problem ID is not provided"
                )
                return
            if not id and isinstance(interaction.channel, Thread):
                problem_frontend_id = await self.problem_threads_manager.get_problem_frontend_id_by_thread_id(
                    thread_id=interaction.channel.id
                )
            if not problem_frontend_id:
                await interaction.followup.send(
                    "This channel does not seem to be a problem thread..."
                )
                return

            logger.info(
                f"Fetching problem description with ID {id} for guild {interaction.guild_id}"
            )
            embeds = await self.leetcode_problem_manager.get_problem_desc(
                problem_frontend_id=problem_frontend_id,
                bot=self.bot,
            )
            if not embeds:
                await interaction.followup.send(f"Problem id with {id} not found.")
                return

            await interaction.followup.send(embeds=embeds)
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
        name="is-leetcode-down", description="Check LeetCode API status"
    )
    async def is_leetcode_down(self, interaction: Interaction) -> None:
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

    @app_commands.command(name="daily", description="Get today's LeetCode problem")
    @app_commands.guild_only()
    @handle_leetcode_interaction(is_daily=True)
    async def daily_problem(self, interaction: Interaction) -> ProblemWithTags:
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
    async def leetcode_problem(
        self, interaction: Interaction, id: int
    ) -> ProblemWithTags:
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

    @app_commands.command(name="statistics", description="Get user statistics")
    @app_commands.describe(leetcode_username="The LeetCode username")
    async def user_statistics(
        self, interaction: Interaction, leetcode_username: str
    ) -> None:
        await interaction.response.defer(thinking=True, ephemeral=False)
        try:
            info = await self.leetcode_api.user_info(username=leetcode_username)
            logger.debug(info)
            embed = get_user_info_embed(
                username=leetcode_username, info=info, bot=self.bot
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(
                "Something went wrong when fetching user statistics.", exc_info=e
            )
            await interaction.followup.send(
                "Something went wrong when fetching user statistics."
            )

    @app_commands.command(
        name="recent-submissions", description="Get user's recent submissions."
    )
    @app_commands.describe(
        leetcode_username="The LeetCode user name.",
        limit="How many submissions you want. 1 <= limit <= 100",
    )
    @app_commands.guild_only()
    async def recent_submissions(
        self, interaction: Interaction, leetcode_username: str, limit: int = 20
    ) -> None:
        await interaction.response.defer(thinking=True)

        try:
            submissions_list = await self.leetcode_api.user_submission(
                username=leetcode_username, limit=limit
            )
            logger.debug(submissions_list)

            guild = interaction.guild
            assert isinstance(guild, Guild)
            channel = interaction.channel
            if not channel or isinstance(channel, DMChannel):
                await interaction.response.send_message(
                    "This command can only be used in a server!", ephemeral=True
                )
                return

            metadata = UserSubmissionPaginationMetaData(
                guild_name=guild.name,
                guild_id=guild.id,
                channel_name=channel.name or "No name",
                channel_id=channel.id,
                user_name=interaction.user.name,
                user_id=interaction.user.id,
                client=interaction.client,
                theme_color=THEME_COLOR,
                data_len=len(submissions_list),
                leetcode_username=leetcode_username,
            )
            view = UserSubmissionPaginationView(
                metadata=metadata,
                data=submissions_list,
                items_per_page=5,
                format_page=self.format_submissions,
                ephemeral=False,
            )

            await view.send_initial_message(interaction=interaction, followup=True)
        except Exception as e:
            logger.error(
                "Something went wrong when fetching user's recent submissions.",
                exc_info=e,
            )
            await interaction.followup.send(
                "Something went wrong when fetching user's recent submissions."
            )

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
