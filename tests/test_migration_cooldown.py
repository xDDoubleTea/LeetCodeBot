"""
The per-guild scan cooldown on /migrate.

archived_threads(limit=None) walks every archived post in a forum, so the cost
grows with the channel. The cooldown is checked by hand rather than through
app_commands.checks.cooldown, because that decorator consumes a use before the
command body runs -- a mistyped pattern would cost as much as a real scan.
"""

from types import SimpleNamespace

from cogs.migration import SCAN_PER, Migration


def make_cog() -> Migration:
    bot = SimpleNamespace(database_manager=SimpleNamespace())
    return Migration(bot)  # type: ignore[arg-type]


def test_the_first_scan_in_a_guild_is_allowed():
    cog = make_cog()
    bucket = cog._scan_bucket(guild_id=1, now=1000.0)
    assert bucket.get_retry_after(1000.0) == 0


def test_a_second_scan_inside_the_window_has_to_wait():
    cog = make_cog()
    bucket = cog._scan_bucket(guild_id=1, now=1000.0)
    bucket.update_rate_limit(1000.0)

    again = cog._scan_bucket(guild_id=1, now=1010.0)
    assert again is bucket
    assert again.get_retry_after(1010.0) > 0


def test_the_window_expires():
    cog = make_cog()
    cog._scan_bucket(guild_id=1, now=1000.0).update_rate_limit(1000.0)

    later = 1000.0 + SCAN_PER + 1
    assert cog._scan_bucket(guild_id=1, now=later).get_retry_after(later) == 0


def test_guilds_do_not_share_a_bucket():
    """One server exhausting its scan must not block another's."""
    cog = make_cog()
    cog._scan_bucket(guild_id=1, now=1000.0).update_rate_limit(1000.0)

    other = cog._scan_bucket(guild_id=2, now=1000.0)
    assert other.get_retry_after(1000.0) == 0


def test_expired_buckets_are_dropped():
    """
    Otherwise a bot in many servers accumulates one entry per server forever.
    """
    cog = make_cog()
    cog._scan_bucket(guild_id=1, now=1000.0).update_rate_limit(1000.0)
    assert 1 in cog._scan_cooldowns

    cog._scan_bucket(guild_id=2, now=1000.0 + SCAN_PER + 1)
    assert 1 not in cog._scan_cooldowns
