from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from yarl import URL

from utils import perf
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


@pytest.fixture(autouse=True)
def no_current_breakdown():
    """Start every test with no breakdown current, and restore afterwards."""
    token = perf._current.set(None)
    yield
    perf._current.reset(token)


class TestRecord:
    """Time is added to the current breakdown, and only to it."""

    def test_outside_an_interaction_records_nothing(self):
        perf.record("db", 5.0)

        assert perf._current.get() is None

    def test_accumulates_time_and_calls_per_category(self):
        breakdown = perf.start_breakdown()

        perf.record("db", 1.5)
        perf.record("db", 2.5)
        perf.record("discord", 100.0)

        assert breakdown.ms == {"db": 4.0, "discord": 100.0}
        assert breakdown.calls == {"db": 2, "discord": 1}

    def test_measure_records_even_when_the_block_raises(self):
        breakdown = perf.start_breakdown()

        with pytest.raises(RuntimeError), perf.measure("lookup"):
            raise RuntimeError

        assert breakdown.calls == {"lookup": 1}


class TestHttpCategory:
    @pytest.mark.parametrize(
        ("host", "category"),
        [
            ("discord.com", "discord"),
            ("gateway.discord.com", "discord"),
            ("cdn.discordapp.com", "discord"),
            ("media.discordapp.net", "discord"),
            ("gateway-us-east1-b.discord.gg", "discord"),
            ("discord.com.", "discord"),
            ("leetcode.com", "leetcode"),
            ("LeetCode.com", "leetcode"),
            ("notdiscord.com", "http"),
            ("fakeleetcode.com", "http"),
            ("leetcode-api-pied.vercel.app", "http"),
            ("example.com", "http"),
            (None, "http"),
        ],
    )
    def test_files_requests_by_host(self, host, category):
        assert perf.http_category(host) == category


class TestHttpTrace:
    """The trace callbacks file a request's duration by its host."""

    async def test_completed_request_is_recorded(self):
        breakdown = perf.start_breakdown()
        trace_ctx = SimpleNamespace()
        params = SimpleNamespace(url=URL("https://discord.com/api/v10/interactions"))

        await perf._on_request_start(None, trace_ctx, params)
        await perf._on_request_done(None, trace_ctx, params)

        assert breakdown.calls == {"discord": 1}

    async def test_end_without_a_start_records_nothing(self):
        breakdown = perf.start_breakdown()
        params = SimpleNamespace(url=URL("https://leetcode.com/graphql"))

        await perf._on_request_done(None, SimpleNamespace(), params)

        assert breakdown.calls == {}

    def test_trace_config_hooks_start_end_and_exception(self):
        trace_config = perf.http_trace_config()

        assert perf._on_request_start in trace_config.on_request_start
        assert perf._on_request_done in trace_config.on_request_end
        assert perf._on_request_done in trace_config.on_request_exception


class TestInstrumentEngine:
    """SQL on an instrumented engine is filed under db."""

    async def test_each_statement_is_recorded(self, engine):
        perf.instrument_engine(engine)
        breakdown = perf.start_breakdown()

        async with engine.connect() as conn:
            await conn.execute(text("select 1"))
            await conn.execute(text("select 2"))

        assert breakdown.calls["db"] == 2

    async def test_a_failing_statement_is_still_recorded(self, engine):
        perf.instrument_engine(engine)
        breakdown = perf.start_breakdown()

        async with engine.connect() as conn:
            with pytest.raises(OperationalError):
                await conn.execute(text("select * from no_such_table"))

        assert breakdown.calls["db"] == 1

    async def test_statements_outside_an_interaction_are_ignored(self, engine):
        perf.instrument_engine(engine)

        async with engine.connect() as conn:
            await conn.execute(text("select 1"))

        assert perf._current.get() is None


class TestFormatBreakdown:
    def test_reports_every_category_and_the_lookup(self):
        breakdown = perf.Breakdown()
        breakdown.add("discord", 1800.04)
        breakdown.add("db", 2.0)
        breakdown.add("lookup", 0.0042)

        line = perf.format_latency("problem", 2000.0, 2130.0, breakdown)

        assert line == (
            "latency command=problem handler_ms=2000.0 e2e_ms=2130.0 "
            "discord_ms=1800.0 discord_calls=1 db_ms=2.0 db_calls=1 "
            "leetcode_ms=0.0 leetcode_calls=0 lookup_ms=0.004"
        )

    def test_marks_a_command_without_a_lookup(self):
        assert perf.format_breakdown(perf.Breakdown()).endswith("lookup_ms=-")


class TestInteractionCheckBreakdown:
    async def test_makes_a_fresh_breakdown_current(self):
        tree = LatencyTimingTree.__new__(LatencyTimingTree)
        interaction = SimpleNamespace(extras={})

        await tree.interaction_check(interaction)

        assert interaction.extras[perf.BREAKDOWN_KEY] is perf._current.get()
