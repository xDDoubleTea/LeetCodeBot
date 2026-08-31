import logging

import discord
import re2
from discord import ForumChannel, app_commands
from discord.ext import commands

from db.problem_threads import ProblemThreads
from main import LeetCodeBot

logger = logging.getLogger(__name__)

# "1. Two Sum", which is what this bot names its own threads.
DEFAULT_TITLE_PATTERN = r"^(\d+)\.\s"


def problem_id_from_title(title: str, title_regex) -> int | None:
    """
    The problem number in a thread title, or None when the title does not match.

    The first capturing group has to be the number. A pattern that captures
    something else matches but yields no id, which is a mistake worth reporting
    to whoever ran the command rather than crashing on.
    """
    match = title_regex.match(title)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


class Migration(commands.Cog):
    def __init__(self, bot: LeetCodeBot):
        self.bot = bot
        self.database_manager = bot.database_manager

    @app_commands.command(
        name="migrate",
        description="<Admin> Record existing forum threads as problem threads",
    )
    @app_commands.describe(
        channel="The forum channel holding the existing threads",
        title_pattern=(
            "Regex for the thread titles, anchored at the start, with the "
            f"problem number as the first group. Default: {DEFAULT_TITLE_PATTERN}"
        ),
    )
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guild_only()
    async def migrate(
        self,
        interaction: discord.Interaction,
        channel: ForumChannel,
        title_pattern: str | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        assert interaction.guild is not None

        pattern = title_pattern or DEFAULT_TITLE_PATTERN
        logger.info(
            f"User {interaction.user} initiated migration in guild "
            f"{interaction.guild.id} for channel {channel.id} with pattern {pattern!r}"
        )

        # re2 rather than re: the pattern comes from whoever ran the command, and
        # re2 cannot backtrack, so a pathological one cannot hang the bot.
        try:
            title_regex = re2.compile(pattern)
        except re2.error as e:
            await interaction.followup.send(f"That is not a valid regex: {e}")
            return

        if title_regex.groups < 1:
            await interaction.followup.send(
                "The pattern needs a capturing group around the problem number, "
                r"for example `^(\d+)\.\s`. It is matched from the start of the "
                "title, so use `.*` to reach a number in the middle."
            )
            return

        if (
            await self.bot.problem_threads_manager.get_forum_channel(
                interaction.guild.id
            )
            is None
        ):
            await interaction.followup.send(
                "No forum channel is set for this server. Run /set_forum_channel first."
            )
            return

        threads = await self._collect_threads(channel)
        logger.info(
            f"Found {len(threads)} threads in channel {channel.id} to consider."
        )

        problem_threads: dict[int, ProblemThreads] = dict()
        skipped_titles: list[str] = []
        for thread in threads:
            problem_frontend_id = problem_id_from_title(thread.name, title_regex)
            if problem_frontend_id is None:
                skipped_titles.append(thread.name)
                continue

            instance = await self.bot.problem_threads_manager.create_thread_instance(
                problem_frontend_id, interaction.guild.id, thread.id
            )
            if instance:
                problem_threads[thread.id] = instance

        await self.bot.problem_threads_manager.bulk_upsert_thread_to_db(problem_threads)

        # Thread names are never touched; this only records what is already there.
        summary = f"Recorded {len(problem_threads)} of {len(threads)} threads."
        if skipped_titles:
            preview = ", ".join(f"`{title}`" for title in skipped_titles[:5])
            summary += (
                f"\n{len(skipped_titles)} did not match `{pattern}`, for example: "
                f"{preview}"
            )
        await interaction.followup.send(summary)

    async def _collect_threads(self, channel: ForumChannel) -> list[discord.Thread]:
        """
        Every thread in the forum, active and archived.

        Threads carrying a "LeetCode" tag are preferred when that tag exists,
        since a shared forum may hold unrelated posts. Where it does not exist --
        a forum this bot has never posted in, which is the case migration is for
        -- the title pattern is the only filter.
        """
        leetcode_tag = next(
            (tag for tag in channel.available_tags if tag.name.lower() == "leetcode"),
            None,
        )

        threads = list(channel.threads)
        async for thread in channel.archived_threads(limit=None):
            threads.append(thread)

        if leetcode_tag is None:
            logger.info(
                f"Channel {channel.id} has no LeetCode tag; matching on the title only."
            )
            return threads

        tagged = [thread for thread in threads if leetcode_tag in thread.applied_tags]
        logger.info(
            f"Channel {channel.id} has a LeetCode tag; {len(tagged)} of "
            f"{len(threads)} threads carry it."
        )
        return tagged


async def setup(bot: LeetCodeBot) -> None:
    await bot.add_cog(Migration(bot))
