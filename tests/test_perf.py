from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from utils.perf import (
    START_KEY,
    LatencyTimingTree,
    e2e_ms,
    format_latency,
    handler_ms,
)


def test_handler_ms_returns_none_without_a_start_stamp():
    interaction = SimpleNamespace(extras={})

    assert handler_ms(interaction) is None


def test_handler_ms_measures_from_the_recorded_start():
    interaction = SimpleNamespace(extras={START_KEY: 0.0})

    elapsed = handler_ms(interaction)

    assert elapsed is not None
    assert elapsed > 0


def test_e2e_ms_is_the_gap_between_creation_and_now():
    created_at = datetime(2026, 10, 2, 12, 0, 0, tzinfo=UTC)

    assert e2e_ms(created_at, created_at + timedelta(milliseconds=250)) == 250.0


def test_format_latency_reports_both_timings():
    line = format_latency("problem", 12.345, 678.9)

    assert line == "latency command=problem handler_ms=12.3 e2e_ms=678.9"


def test_format_latency_marks_a_missing_handler_timing():
    assert "handler_ms=?" in format_latency("problem", None, 1.0)


async def test_interaction_check_stamps_the_start_and_admits_the_interaction():
    tree = LatencyTimingTree.__new__(LatencyTimingTree)
    interaction = SimpleNamespace(extras={})

    assert await tree.interaction_check(interaction) is True
    assert isinstance(interaction.extras[START_KEY], float)
