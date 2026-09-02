"""
Global error handling for both command families.

`ErrorHandlingTree` catches everything raised by a slash command, and
`on_command_error` in main.py does the same for the prefix commands. Cogs only
need their own handler for errors that deserve a command-specific reply.
"""

import logging

from discord import Interaction, app_commands
from discord.app_commands.errors import AppCommandError, CommandInvokeError
from discord.ext.commands import Context
from discord.ext.commands.errors import (
    CheckFailure,
    CommandError,
    CommandNotFound,
    CommandOnCooldown,
    MissingPermissions,
    MissingRequiredArgument,
)
from discord.ui import Item

from utils.checks import IsNotDev, UserNotAdministrator
from utils.custom_exceptions import ForumChannelNotFound

logger = logging.getLogger(__name__)

UNEXPECTED_MESSAGE = "Something went wrong running that command."


def app_command_message(error: Exception) -> str | None:
    """
    The reply for an error a user can do something about, or None when the error
    is a bug and should be logged instead.
    """
    if isinstance(error, (UserNotAdministrator, IsNotDev, ForumChannelNotFound)):
        return error.message

    if isinstance(error, app_commands.CommandOnCooldown):
        return f"That command is on cooldown; try again in {error.retry_after:.0f}s."

    if isinstance(error, app_commands.MissingPermissions):
        missing = ", ".join(error.missing_permissions)
        return f"You need the following permissions to do that: {missing}."

    if isinstance(error, app_commands.BotMissingPermissions):
        missing = ", ".join(error.missing_permissions)
        return f"I need the following permissions to do that: {missing}."

    if isinstance(error, app_commands.CheckFailure):
        return "You cannot use that command here."

    if isinstance(error, app_commands.TransformerError):
        # TagTransformer raises ValueError with the name the user typed, which
        # is worth showing. Anything else is an internal conversion failure.
        cause = error.__cause__
        if isinstance(cause, ValueError):
            return str(cause)

    return None


class ErrorHandlingTree(app_commands.CommandTree):
    """A command tree that replies to the user instead of failing silently."""

    async def on_error(self, interaction: Interaction, error: AppCommandError) -> None:
        command = interaction.command.qualified_name if interaction.command else "?"

        message = app_command_message(error)
        if message is None:
            # CommandInvokeError wraps whatever the command body raised; the cause
            # is what is worth reading in the log.
            cause = error.__cause__ if isinstance(error, CommandInvokeError) else error
            logger.exception(f"Unhandled error in /{command}", exc_info=cause or error)
            message = UNEXPECTED_MESSAGE
        else:
            logger.info(f"/{command} refused for {interaction.user.id}: {message}")

        await respond(interaction, message)


async def respond(interaction: Interaction, message: str) -> None:
    """Reply ephemerally, whether or not the command already responded."""
    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except Exception as e:
        # The interaction may have expired, or the command may have used up its
        # response already; nothing more can be done for the user here.
        logger.warning("Could not deliver the error message", exc_info=e)


async def handle_component_error(
    interaction: Interaction, error: Exception, item: Item
) -> None:
    """
    Handler for `discord.ui` component callbacks, wired up as `View.on_error`.

    Applies the same user-facing/bug split the command families get, so an
    error raised from a button or select menu reaches the user as a reply.
    """
    label = getattr(item, "placeholder", None) or type(item).__name__

    message = app_command_message(error)
    if message is None:
        logger.exception(f"Unhandled error in component {label}", exc_info=error)
        message = UNEXPECTED_MESSAGE
    else:
        logger.info(f"Component {label} refused for {interaction.user.id}: {message}")

    await respond(interaction, message)


async def handle_command_error(ctx: Context, error: CommandError) -> None:
    """Handler for prefix commands, wired up as MyBot.on_command_error."""
    # A typo in chat is not an error worth reporting.
    if isinstance(error, CommandNotFound):
        return

    command = ctx.command.qualified_name if ctx.command else "?"

    if isinstance(error, IsNotDev):
        message = error.message
    elif isinstance(error, CommandOnCooldown):
        message = f"That command is on cooldown; try again in {error.retry_after:.0f}s."
    elif isinstance(error, MissingPermissions):
        missing = ", ".join(error.missing_permissions)
        message = f"You need the following permissions to do that: {missing}."
    elif isinstance(error, MissingRequiredArgument):
        message = f"Missing argument `{error.param.name}`."
    elif isinstance(error, CheckFailure):
        message = "You cannot use that command here."
    else:
        logger.exception(
            f"Unhandled error in {ctx.prefix}{command}",
            exc_info=error.__cause__ or error,
        )
        message = UNEXPECTED_MESSAGE

    await ctx.send(message)
