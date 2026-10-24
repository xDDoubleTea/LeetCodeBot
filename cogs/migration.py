import logging
from typing import TYPE_CHECKING

import discord
import re2
from discord import ForumChannel, app_commands
from discord.ext import commands

from config.constants import MIGRATE_SCAN_PER, MIGRATE_SCAN_RATE
from db.problem_threads import ProblemThreads
from utils.thread_titles import DEFAULT_TITLE_PATTERN, problem_id_from_title

if TYPE_CHECKING:
    from main import LeetCodeBot

logger = logging.getLogger(__name__)


class Migration(commands.Cog):
    def __init__(self, bot: "LeetCodeBot") -> None:
        self.bot = bot
        self.database_manager = bot.database_manager
        # Keyed by guild, not by user: the forum is the thing being spared, and
        # the command is administrator-only, so several admins in one server
        # should not multiply what that server can spend.
        self._scan_cooldowns: dict[int, app_commands.Cooldown] = {}

    def _scan_bucket(self, guild_id: int, now: float) -> app_commands.Cooldown:
        # Drop buckets whose window has passed, so a bot in many servers does not
        # accumulate one entry per server forever. Same approach discord.py takes
        # in its own cooldown decorator.
        expired = [
            key
            for key, bucket in self._scan_cooldowns.items()
            if now > bucket._last + bucket.per
        ]
        for key in expired:
            del self._scan_cooldowns[key]

        if guild_id not in self._scan_cooldowns:
            self._scan_cooldowns[guild_id] = app_commands.Cooldown(
                MIGRATE_SCAN_RATE, MIGRATE_SCAN_PER
            )
        return self._scan_cooldowns[guild_id]

    @app_commands.command(
        name="migrate",
        description="<Admin> Record existing forum threads as problem threads",
    )
    @app_commands.describe(
        channel="The forum channel holding the existing threads",
        # Discord caps a parameter description at 100 characters and discord.py
        # silently truncates past that, so the default pattern has to fit inside
        # the budget rather than trail off the end. The anchoring rule is in the
        # error message the command replies with instead.
        title_pattern=(
            "Regex matching thread titles; group 1 is the problem number. "
            f"Default: {DEFAULT_TITLE_PATTERN}"
        ),
        tagged_only="Only consider threads carrying the forum's LeetCode tag. Default: False",
    )
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guild_only()
    async def migrate(
        self,
        interaction: discord.Interaction,
        channel: ForumChannel,
        title_pattern: str | None = None,
        tagged_only: bool = False,
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

        if tagged_only and not any(
            tag.name.lower() == "leetcode" for tag in channel.available_tags
        ):
            await interaction.followup.send(
                f"{channel.mention} has no LeetCode tag, so tagged_only would "
                "record nothing. Run /migrate without it to match on titles."
            )
            return

        # Checked here rather than through app_commands.checks.cooldown, which
        # consumes a use before the command body runs: a mistyped pattern or an
        # unconfigured forum channel would then cost the same as a real scan.
        # Everything above this point is validation and costs nothing.
        now = interaction.created_at.timestamp()
        bucket = self._scan_bucket(interaction.guild.id, now)
        retry_after = bucket.get_retry_after(now)
        if retry_after:
            # CommandOnCooldown is what error_handlers already words for the user.
            raise app_commands.CommandOnCooldown(bucket, retry_after)

        threads, leetcode_tag = await self._collect_threads(channel, tagged_only)
        bucket.update_rate_limit(now)
        logger.info(
            f"Found {len(threads)} threads in channel {channel.id} to consider."
        )

        problem_threads: dict[int, ProblemThreads] = dict()
        skipped_titles: list[str] = []
        untagged_recorded = 0
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
                if leetcode_tag is not None and leetcode_tag not in thread.applied_tags:
                    untagged_recorded += 1

        if problem_threads:
            await self.bot.problem_threads_manager.bulk_upsert_thread_to_db(
                problem_threads
            )

        # Thread names are never touched; this only records what is already there.
        summary = f"Recorded {len(problem_threads)} of {len(threads)} threads."
        if untagged_recorded:
            summary += (
                f"\n{untagged_recorded} of them have no LeetCode tag; "
                "use tagged_only to skip threads like these."
            )
        if skipped_titles:
            preview = ", ".join(f"`{title}`" for title in skipped_titles[:5])
            summary += (
                f"\n{len(skipped_titles)} did not match `{pattern}`, for example: "
                f"{preview}"
            )
        await interaction.followup.send(summary)

    async def _collect_threads(
        self, channel: ForumChannel, tagged_only: bool
    ) -> tuple[list[discord.Thread], discord.ForumTag | None]:
        """
        Every thread in the forum, active and archived, and the forum's LeetCode
        tag if it has one.

        The title pattern is the filter. Threads opened by hand usually carry no
        tag, so requiring it would leave them unrecorded and the bot would open
        duplicates. With tagged_only, threads without the LeetCode tag are
        dropped, for a forum shared with unrelated posts whose titles still match.
        """
        leetcode_tag = next(
            (tag for tag in channel.available_tags if tag.name.lower() == "leetcode"),
            None,
        )

        threads = list(channel.threads)
        async for thread in channel.archived_threads(limit=None):
            threads.append(thread)

        if not tagged_only:
            return threads, leetcode_tag

        if leetcode_tag is None:
            logger.info(f"Channel {channel.id} has no LeetCode tag; nothing to keep.")
            return [], None

        tagged = [thread for thread in threads if leetcode_tag in thread.applied_tags]
        logger.info(
            f"Channel {channel.id}: {len(tagged)} of {len(threads)} threads carry "
            "the LeetCode tag."
        )
        return tagged, leetcode_tag


async def setup(bot: "LeetCodeBot") -> None:
    await bot.add_cog(Migration(bot))
