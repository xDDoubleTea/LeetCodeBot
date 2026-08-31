"""
Tests for the global error handlers.

The point of these handlers is that a user always gets a reply. The split that
matters is between errors the user can act on, which are shown verbatim, and
bugs, which are logged and answered with a generic message.
"""

from types import SimpleNamespace

import pytest
from discord import AppCommandOptionType, app_commands
from discord.ext.commands.errors import (
    CommandNotFound,
    CommandOnCooldown,
    MissingRequiredArgument,
)

from utils.checks import IsNotDev, UserNotAdministrator
from utils.custom_exceptions import ForumChannelNotFound
from utils.error_handlers import (
    UNEXPECTED_MESSAGE,
    ErrorHandlingTree,
    app_command_message,
    handle_command_error,
    respond,
)
from utils.tag_transformer import TagTransformer


class FakeContext:
    """Just enough Context for handle_command_error."""

    def __init__(self):
        self.sent: list[str] = []
        self.command = SimpleNamespace(qualified_name="tag")
        self.prefix = ">"

    async def send(self, message: str) -> None:
        self.sent.append(message)


def test_check_failures_are_shown_to_the_user():
    assert app_command_message(IsNotDev()) == IsNotDev().message
    assert app_command_message(UserNotAdministrator()) == UserNotAdministrator().message


def test_forum_channel_not_found_names_the_command_that_fixes_it():
    """
    It is an AppCommandError so discord.py re-raises it instead of wrapping it in
    CommandInvokeError, which is what lets it reach here rather than falling
    through to the generic message.
    """
    message = app_command_message(ForumChannelNotFound())
    assert message is not None
    assert "/set_forum_channel" in message


def test_missing_permissions_names_the_permission():
    message = app_command_message(app_commands.MissingPermissions(["manage_guild"]))
    assert message is not None
    assert "manage_guild" in message


def test_a_bug_has_no_user_facing_message():
    """None is the signal to log the error and reply generically."""
    assert app_command_message(app_commands.AppCommandError("boom")) is None


def test_transformer_error_surfaces_the_tag_that_was_rejected():
    """
    TagTransformer raises ValueError naming the tag the user typed. Without
    this branch /filter-by-tag answers a typo with "Something went wrong".
    """
    cause = ValueError("Tag 'arrayy' not found.")
    error = app_commands.TransformerError(
        "arrayy", AppCommandOptionType.string, TagTransformer()
    )
    error.__cause__ = cause

    assert app_command_message(error) == "Tag 'arrayy' not found."


def test_transformer_error_without_a_value_error_is_a_bug():
    error = app_commands.TransformerError(
        "x", AppCommandOptionType.string, TagTransformer()
    )
    assert app_command_message(error) is None


async def test_command_not_found_is_ignored():
    """A typo in chat must not produce a reply."""
    ctx = FakeContext()
    await handle_command_error(ctx, CommandNotFound())  # type: ignore[arg-type]
    assert ctx.sent == []


async def test_prefix_check_failure_is_shown_to_the_user():
    ctx = FakeContext()
    await handle_command_error(ctx, IsNotDev())  # type: ignore[arg-type]
    assert ctx.sent == [IsNotDev().message]


async def test_prefix_missing_argument_names_the_argument():
    ctx = FakeContext()
    param = SimpleNamespace(name="ext_name", displayed_name=None)
    await handle_command_error(ctx, MissingRequiredArgument(param))  # type: ignore[arg-type]
    assert "ext_name" in ctx.sent[0]


async def test_prefix_bug_gets_the_generic_message():
    ctx = FakeContext()
    await handle_command_error(ctx, Exception("boom"))  # type: ignore[arg-type]
    assert ctx.sent == [UNEXPECTED_MESSAGE]


@pytest.mark.parametrize("retry_after", [1.0, 42.0])
async def test_prefix_cooldown_reports_the_wait(retry_after):
    from discord.ext.commands import BucketType, Cooldown

    ctx = FakeContext()
    error = CommandOnCooldown(Cooldown(1, retry_after), retry_after, BucketType.user)
    await handle_command_error(ctx, error)  # type: ignore[arg-type]
    assert f"{retry_after:.0f}s" in ctx.sent[0]


class FakeResponse:
    def __init__(self, done: bool):
        self._done = done
        self.sent: list[tuple[str, bool]] = []

    def is_done(self) -> bool:
        return self._done

    async def send_message(self, message: str, ephemeral: bool = False) -> None:
        self.sent.append((message, ephemeral))


class FakeFollowup:
    def __init__(self):
        self.sent: list[tuple[str, bool]] = []

    async def send(self, message: str, ephemeral: bool = False) -> None:
        self.sent.append((message, ephemeral))


class FakeInteraction:
    def __init__(self, done: bool):
        self.response = FakeResponse(done)
        self.followup = FakeFollowup()
        self.command = SimpleNamespace(qualified_name="daily")
        self.user = SimpleNamespace(id=1)


async def test_respond_uses_the_initial_response_when_untouched():
    interaction = FakeInteraction(done=False)
    await respond(interaction, "nope")  # type: ignore[arg-type]
    assert interaction.response.sent == [("nope", True)]
    assert interaction.followup.sent == []


async def test_respond_falls_back_to_followup_after_a_defer():
    """
    The LeetCode commands defer before hitting the API, so by the time an error
    surfaces the interaction is already answered and send_message would raise.
    """
    interaction = FakeInteraction(done=True)
    await respond(interaction, "nope")  # type: ignore[arg-type]
    assert interaction.followup.sent == [("nope", True)]
    assert interaction.response.sent == []


async def test_respond_survives_a_dead_interaction(caplog):
    """A 15-minute-old interaction cannot be replied to; that must not raise."""

    class Dead(FakeInteraction):
        async def _boom(self, *args, **kwargs):
            raise RuntimeError("interaction expired")

    interaction = Dead(done=False)
    interaction.response.send_message = interaction._boom  # type: ignore[method-assign]

    await respond(interaction, "nope")  # type: ignore[arg-type]
    assert "Could not deliver" in caplog.text


async def test_tree_replies_with_the_generic_message_for_a_bug():
    tree = ErrorHandlingTree.__new__(ErrorHandlingTree)
    interaction = FakeInteraction(done=False)

    await tree.on_error(interaction, app_commands.AppCommandError("boom"))  # type: ignore[arg-type]

    assert interaction.response.sent == [(UNEXPECTED_MESSAGE, True)]


async def test_tree_replies_with_the_check_message():
    tree = ErrorHandlingTree.__new__(ErrorHandlingTree)
    interaction = FakeInteraction(done=False)

    await tree.on_error(interaction, IsNotDev())  # type: ignore[arg-type]

    assert interaction.response.sent == [(IsNotDev().message, True)]
