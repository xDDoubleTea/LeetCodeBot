from discord.ext import commands
import discord
from discord import ForumChannel, app_commands
import re
from db.problem_threads import ProblemThreads
from main import LeetCodeBot
from typing import Dict


class Migration(commands.Cog):
    def __init__(self, bot: LeetCodeBot):
        self.bot = bot
        self.database_manager = bot.database_manager

    @app_commands.command(name="migrate", description="Migrate from the old threads")
    @app_commands.guild_only()
    async def migrate(
        self, interaction: discord.Interaction, channel: ForumChannel
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            assert isinstance(channel, ForumChannel) and interaction.guild is not None
            if (
                await self.bot.problem_threads_manager.get_forum_channel(
                    interaction.guild.id
                )
                is None
            ):
                await interaction.followup.send(
                    "Forum channel not set up in the database. Please set it up first."
                )
                return
            leetcode_tag = None
            for tag in channel.available_tags:
                if tag.name.lower() == "leetcode":
                    leetcode_tag = tag
                    break
            if not leetcode_tag:
                await interaction.followup.send("No tag named LeetCode found!")
                return

            problem_threads: Dict[int, ProblemThreads] = dict()
            all_leetcode_threads = []
            # Example thread name: "1. Two Sum"
            all_leetcode_threads += list(
                filter(lambda thd: leetcode_tag in thd.applied_tags, channel.threads)
            )
            async for thd in channel.archived_threads(limit=None):
                if leetcode_tag in thd.applied_tags:
                    all_leetcode_threads.append(thd)

            problem_name_regex = re.compile(r"^(\d+)\.\s")
            for thread in all_leetcode_threads:
                match = problem_name_regex.match(thread.name)
                if not match:
                    continue
                problem_frontend_id = int(match.group(1))
                problem_thread_instance = (
                    await self.bot.problem_threads_manager.create_thread_instance(
                        problem_frontend_id, interaction.guild.id, thread.id
                    )
                )
                if problem_thread_instance:
                    problem_threads[thread.id] = problem_thread_instance
            await self.bot.problem_threads_manager.bulk_upsert_thread_to_db(
                problem_threads
            )
            await interaction.followup.send(
                f"Migration complete! Migrated {len(problem_threads)} threads."
            )

        except Exception as e:
            await interaction.followup.send(
                f"Something went wrong when migrating! Error : {e}"
            )


async def setup(bot: LeetCodeBot) -> None:
    await bot.add_cog(Migration(bot))
