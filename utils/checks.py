import logging

from discord import Interaction, Member, app_commands
from discord.app_commands.errors import AppCommandError
from discord.ext import commands
from discord.ext.commands import CommandError, Context

from config.constants import DEV_ID

logger = logging.getLogger(__name__)


class UserNotAdministrator(AppCommandError):
    """Custom exception raised when a user is not a server administrator or the bot owner."""

    def __init__(
        self,
        message: str = "You do not have permission to use this command; it requires server administrator permissions.",
    ):
        self.message = message
        super().__init__(self.message)


class IsNotDev(CommandError, AppCommandError):
    """
    Custom exception raised when a user is not a dev (i.e., not me)

    Both bases are needed because the same class is raised from a prefix
    command check (is_me_command) and a slash command check
    (is_me_app_command).
    """

    def __init__(
        self, message: str = "Trying to sneak into the dev commands, are you?"
    ):
        self.message = message
        super().__init__(self.message)


# --- The Check Function ---


def is_me_command():
    async def predicate(ctx: Context) -> bool:
        if not ctx.author.id == DEV_ID:
            raise IsNotDev
        return True

    return commands.check(predicate)


def is_me_app_command():
    async def predicate(interaction: Interaction) -> bool:
        if not interaction.user.id == DEV_ID:
            raise IsNotDev
        return True

    return app_commands.check(predicate)


def is_administrator():
    """
    A custom check to verify that the user is either an administrator of the guild
    or the owner of the bot.

    This decorator can be applied to any app command.
    """

    async def predicate(interaction: Interaction) -> bool:
        # The bot owner should always be allowed to run admin commands.
        if interaction.user.id == DEV_ID:
            return True

        # Check for guild context and administrator permissions.
        if not interaction.guild:
            # This check is not applicable in DMs, so we deny.
            return False

        assert isinstance(interaction.user, Member)
        if interaction.user.guild_permissions.administrator:
            return True

        raise UserNotAdministrator()

    return app_commands.check(predicate)
