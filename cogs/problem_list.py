import logging

from discord import Interaction, app_commands
from discord.ext.commands import Cog

from main import LeetCodeBot

logger = logging.getLogger(__name__)


class ProblemListCog(Cog):
    def __init__(self, bot: LeetCodeBot) -> None:
        self.bot = bot
        self.database_manager = bot.database_manager
        self.leetcode_problem_manager = bot.leetcode_problem_manger
        self.leetcode_api = bot.leetcode_api
        self.problem_threads_manager = bot.problem_threads_manager

    @app_commands.command(name="problem-list", description="Problem list")
    async def problem_list(self, interaction: Interaction, name: str):
        pass


async def setup(bot) -> None:
    await bot.add_cog(ProblemListCog(bot))
