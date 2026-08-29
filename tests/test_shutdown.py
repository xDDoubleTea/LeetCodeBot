"""
Tests for LeetCodeBot.close().

engine.dispose() has to run on every path out of close(). aiosqlite's
connection worker is a non-daemon thread, so an engine that is never disposed
outlives asyncio.run() and blocks the interpreter in threading._shutdown().
"""

import asyncio
import importlib
import os

import pytest
from discord import Client


@pytest.fixture
def leetcode_bot():
    # main imports config.secrets at module scope, which raises if the
    # environment is missing. setdefault leaves a real .env alone.
    os.environ.setdefault("BOT_TOKEN", "test-token")
    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
    main = importlib.import_module("main")
    return main.LeetCodeBot()


async def test_close_disposes_the_engine(leetcode_bot):
    pool = leetcode_bot.engine.pool
    await leetcode_bot.close()
    # dispose() swaps in a fresh pool, so a new one proves it ran.
    assert leetcode_bot.engine.pool is not pool


async def test_close_disposes_the_engine_when_the_gateway_teardown_raises(
    leetcode_bot, monkeypatch
):
    async def boom(self) -> None:
        raise RuntimeError("gateway teardown failed")

    monkeypatch.setattr(Client, "close", boom)
    pool = leetcode_bot.engine.pool

    with pytest.raises(RuntimeError):
        await leetcode_bot.close()

    assert leetcode_bot.engine.pool is not pool


async def test_close_disposes_the_engine_when_cancelled(leetcode_bot, monkeypatch):
    """
    A SIGINT during shutdown cancels the task running close(). The engine still
    has to be disposed, or the interpreter hangs on exit instead of quitting.
    """

    async def cancelled(self) -> None:
        raise asyncio.CancelledError

    monkeypatch.setattr(Client, "close", cancelled)
    pool = leetcode_bot.engine.pool

    with pytest.raises(asyncio.CancelledError):
        await leetcode_bot.close()

    assert leetcode_bot.engine.pool is not pool
