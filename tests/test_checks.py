"""
Tests for the command check exceptions.

The base classes are load-bearing rather than decorative: discord.py routes an
error by its type, and each front end catches a different base.
"""

from discord.app_commands.errors import AppCommandError
from discord.ext.commands import CommandError

from utils.checks import IsNotDev, UserNotAdministrator


def test_is_not_dev_reaches_the_command_tree():
    """
    CommandTree._from_interaction wraps the call in `except AppCommandError`
    only, and it runs inside a task. An IsNotDev that is not an
    AppCommandError escapes unretrieved and the interaction times out with no
    reply, which is what is_me_app_command would otherwise produce.
    """
    assert issubclass(IsNotDev, AppCommandError)


def test_is_not_dev_reaches_the_prefix_command_handler():
    """is_me_command raises the same class from prefix commands."""
    assert issubclass(IsNotDev, CommandError)


def test_user_not_administrator_reaches_the_command_tree():
    assert issubclass(UserNotAdministrator, AppCommandError)


def test_exceptions_carry_their_message():
    """The cog error handlers read error.message to reply to the user."""
    assert IsNotDev().message
    assert UserNotAdministrator().message
    assert IsNotDev("custom").message == "custom"
