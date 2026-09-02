"""
Tests for the cooldown on the thread-creating commands.

The cooldown runs as a check, so it fires before the command body defers. A
refused attempt therefore leaves the interaction unanswered, and the reply goes
out through `respond`'s `send_message` branch, which is ephemeral.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from discord import app_commands

from config.constants import THREAD_COMMAND_PER, THREAD_COMMAND_RATE
from utils.cooldowns import thread_command_key

START = datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC)


def make_interaction(guild_id: int, user_id: int, offset: float = 0.0):
    return SimpleNamespace(
        guild_id=guild_id,
        user=SimpleNamespace(id=user_id),
        created_at=START + timedelta(seconds=offset),
    )


@pytest.fixture
def predicate():
    """A fresh decorator per test, so no bucket state crosses between them."""

    @app_commands.checks.cooldown(
        THREAD_COMMAND_RATE, THREAD_COMMAND_PER, key=thread_command_key
    )
    async def command(interaction):
        return True

    return command.__discord_app_commands_checks__[0]


def test_key_buckets_by_guild_and_member():
    assert thread_command_key(make_interaction(1, 2)) == (1, 2)  # type: ignore[arg-type]


def test_key_separates_the_same_member_in_two_guilds():
    assert thread_command_key(make_interaction(1, 2)) != thread_command_key(  # type: ignore[arg-type]
        make_interaction(9, 2)  # type: ignore[arg-type]
    )


async def test_invocations_up_to_the_rate_are_allowed(predicate):
    for attempt in range(THREAD_COMMAND_RATE):
        assert await predicate(make_interaction(1, 2, offset=attempt))


async def test_the_next_invocation_is_refused(predicate):
    for attempt in range(THREAD_COMMAND_RATE):
        await predicate(make_interaction(1, 2, offset=attempt))

    with pytest.raises(app_commands.CommandOnCooldown) as excinfo:
        await predicate(make_interaction(1, 2, offset=THREAD_COMMAND_RATE))

    assert excinfo.value.retry_after > 0


async def test_the_window_expiring_allows_another_invocation(predicate):
    for attempt in range(THREAD_COMMAND_RATE):
        await predicate(make_interaction(1, 2, offset=attempt))

    assert await predicate(make_interaction(1, 2, offset=THREAD_COMMAND_PER + 1))


async def test_members_do_not_share_a_bucket(predicate):
    for attempt in range(THREAD_COMMAND_RATE):
        await predicate(make_interaction(1, 2, offset=attempt))

    assert await predicate(make_interaction(1, 999, offset=THREAD_COMMAND_RATE))


async def test_guilds_do_not_share_a_bucket(predicate):
    for attempt in range(THREAD_COMMAND_RATE):
        await predicate(make_interaction(1, 2, offset=attempt))

    assert await predicate(make_interaction(999, 2, offset=THREAD_COMMAND_RATE))


@pytest.mark.parametrize(
    "command_name", ["daily_problem", "leetcode_problem", "random_problem"]
)
def test_every_thread_creating_command_carries_the_cooldown(command_name):
    """The three commands that can open a forum thread are all covered."""
    from cogs.leetcode import LeetCode

    command = getattr(LeetCode, command_name)

    assert len(command.checks) == 1
