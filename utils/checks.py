from discord.app_commands.errors import AppCommandError
from discord import Member, app_commands
from discord import Interaction
from discord.ext.commands import CommandError, Context
from discord.ext import commands
from config.constants import DEV_ID as My_user_id


class UserNotAdministrator(AppCommandError):
    """Custom exception raised when a user is not a server administrator or the bot owner."""

    def __init__(self, message: str = "您沒有權限使用此指令，需要伺服器管理員權限。"):
        self.message = message
        super().__init__(self.message)


class IsNotDev(CommandError):
    """
    Custom exception raised when a user is not a dev (i.e., not me)
    """

    def __init__(self, message: str = "還想偷用奇怪的指令阿"):
        self.message = message
        super().__init__(self.message)


# --- The Check Function ---


def is_me_command():
    async def predicate(ctx: Context) -> bool:
        if not ctx.author.id == My_user_id:
            raise IsNotDev
        return True

    return commands.check(predicate)


def is_me_app_command():
    async def predicate(interaction: Interaction) -> bool:
        if not interaction.user.id == My_user_id:
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
        if interaction.user.id == My_user_id:
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
