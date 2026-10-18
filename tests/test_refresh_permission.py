from types import SimpleNamespace

import pytest

from cogs.leetcode import LeetCode
from config.constants import DEV_ID
from utils.checks import IsNotDev


def interaction_from(user_id: int) -> SimpleNamespace:
    return SimpleNamespace(user=SimpleNamespace(id=user_id))


async def passes_checks(interaction) -> bool:
    return all([await check(interaction) for check in LeetCode.refresh_cache.checks])


async def test_refresh_is_allowed_for_the_dev():
    assert await passes_checks(interaction_from(DEV_ID))


async def test_refresh_is_refused_for_anyone_else():
    with pytest.raises(IsNotDev):
        await passes_checks(interaction_from(DEV_ID + 1))
