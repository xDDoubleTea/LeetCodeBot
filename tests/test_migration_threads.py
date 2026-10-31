"""
Which forum threads /migrate considers.

Threads opened by hand carry no LeetCode tag. When the scan kept only tagged
threads, those were never recorded, and /problem opened a duplicate thread for a
problem the forum already had.
"""

from types import SimpleNamespace

from cogs.migration import Migration


def make_cog() -> Migration:
    bot = SimpleNamespace(database_manager=SimpleNamespace())
    return Migration(bot)  # type: ignore[arg-type]


def make_thread(name: str, *tags):
    return SimpleNamespace(name=name, applied_tags=list(tags))


def make_channel(available_tags, active, archived):
    async def archived_threads(limit=None):
        for thread in archived:
            yield thread

    return SimpleNamespace(
        id=1,
        available_tags=available_tags,
        threads=active,
        archived_threads=archived_threads,
    )


LEETCODE = SimpleNamespace(name="LeetCode")
EASY = SimpleNamespace(name="Easy")


async def test_untagged_threads_are_considered_by_default():
    bot_thread = make_thread("1. Two Sum", LEETCODE, EASY)
    hand_made = make_thread("268. Missing Number")
    channel = make_channel([LEETCODE, EASY], [bot_thread], [hand_made])

    threads, tag = await make_cog()._collect_threads(channel, tagged_only=False)

    assert threads == [bot_thread, hand_made]
    assert tag is LEETCODE


async def test_tagged_only_drops_threads_without_the_tag():
    bot_thread = make_thread("1. Two Sum", LEETCODE)
    hand_made = make_thread("268. Missing Number", EASY)
    channel = make_channel([LEETCODE, EASY], [hand_made], [bot_thread])

    threads, _ = await make_cog()._collect_threads(channel, tagged_only=True)

    assert threads == [bot_thread]


async def test_the_tag_is_found_regardless_of_case():
    tag = SimpleNamespace(name="leetcode")
    thread = make_thread("1. Two Sum", tag)
    channel = make_channel([tag], [thread], [])

    threads, found = await make_cog()._collect_threads(channel, tagged_only=True)

    assert threads == [thread]
    assert found is tag


async def test_a_forum_without_the_tag_is_matched_on_titles():
    thread = make_thread("1. Two Sum")
    channel = make_channel([], [], [thread])

    threads, tag = await make_cog()._collect_threads(channel, tagged_only=False)

    assert threads == [thread]
    assert tag is None
