"""Tests for the session manager every cog and manager uses."""

import asyncio

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from db.thread_channel import GuildForumChannel

GUILD_ID = 1039906085626196079
CHANNEL_ID = 1245973831190056991


async def test_commits_on_success(database_manager):
    async with database_manager as session:
        session.add(GuildForumChannel(channel_id=CHANNEL_ID, guild_id=GUILD_ID))

    # A second block only sees the row if the first one committed on the way out.
    async with database_manager as session:
        stored = await session.scalar(select(GuildForumChannel))

    assert stored is not None
    assert stored.channel_id == CHANNEL_ID


async def test_rolls_back_when_the_body_raises(database_manager):
    with pytest.raises(ValueError):
        async with database_manager as session:
            session.add(GuildForumChannel(channel_id=CHANNEL_ID, guild_id=GUILD_ID))
            raise ValueError("something went wrong")

    async with database_manager as session:
        rows = (await session.scalars(select(GuildForumChannel))).all()

    assert len(rows) == 0


async def test_exception_reaches_the_caller(database_manager):
    """The manager must not swallow what the command raised."""
    with pytest.raises(ValueError, match="boom"):
        async with database_manager:
            raise ValueError("boom")


async def test_a_failing_commit_reaches_the_caller(database_manager):
    """
    channel_id is unique, so the second row makes the commit inside __aexit__
    fail. That failure has to surface: reporting success for a write that never
    landed is worse than the error.
    """
    async with database_manager as session:
        session.add(GuildForumChannel(channel_id=CHANNEL_ID, guild_id=GUILD_ID))

    with pytest.raises(IntegrityError):
        async with database_manager as session:
            session.add(GuildForumChannel(channel_id=CHANNEL_ID, guild_id=GUILD_ID))


async def test_concurrent_blocks_get_separate_sessions(database_manager):
    """
    The manager is shared by every cog, so overlapping commands must not end up
    sharing one session.
    """
    sessions = []

    async def write(index: int):
        async with database_manager as session:
            sessions.append(session)
            # Yield control so the tasks genuinely interleave inside their blocks.
            await asyncio.sleep(0)
            session.add(
                GuildForumChannel(channel_id=CHANNEL_ID + index, guild_id=GUILD_ID)
            )

    await asyncio.gather(*(write(i) for i in range(10)))

    assert len({id(s) for s in sessions}) == 10

    # The row count is what actually catches a shared session: every block hands
    # back a distinct object even when __aexit__ commits the wrong one.
    async with database_manager as session:
        rows = (await session.scalars(select(GuildForumChannel))).all()

    assert len(rows) == 10


async def test_nested_blocks_unwind_in_order(database_manager):
    """
    ProblemThreadsManager.create_thread_in_db opens a session, calls helpers that
    open their own, and only then adds its row -- so the outer session has to
    survive the inner block and still be the one that gets committed.
    """
    async with database_manager as outer:
        async with database_manager as inner:
            assert inner is not outer
        # Leaving the inner block must not have closed the outer one.
        assert await outer.scalar(select(GuildForumChannel)) is None
        outer.add(GuildForumChannel(channel_id=CHANNEL_ID, guild_id=GUILD_ID))

    # The write went to the outer session after the inner block exited. If
    # __aexit__ commits anything other than the session it was handed, this row
    # is silently lost.
    async with database_manager as session:
        stored = await session.scalar(select(GuildForumChannel))

    assert stored is not None
    assert stored.channel_id == CHANNEL_ID
