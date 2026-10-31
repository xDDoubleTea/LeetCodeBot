"""
Latency instrumentation for application commands.

`LatencyTimingTree` stamps a `time.perf_counter()` reading and a fresh
`Breakdown` onto every interaction the command tree accepts, and makes that
breakdown current for the task handling the interaction. While the command
runs, time is added to it from three sources:

- HTTP requests through any aiohttp session built with `http_trace_config()`,
  filed under `discord` or `leetcode` by host. The bot's Discord client and
  its LeetCode session both use it.
- SQL statements on an engine passed to `instrument_engine`, filed under `db`.
- Blocks wrapped in `measure("lookup")`, which `handle_leetcode_interaction`
  puts around the problem lookup of `/problem`, `/daily` and `/random`.

`log_command_latency` logs one line per completed command with the handler
and end-to-end times, the breakdown, any fields a command added with
`annotate`, and the arguments the user passed as `arg_<name>` fields. Values
containing spaces or quotes are quoted for `shlex.split`. The lines go to
`logs/perf.log`, which never rotates, as well as to the console and
`logs/bot.log`.
"""

import logging
import shlex
import time
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from types import SimpleNamespace
from typing import Any

import aiohttp
from discord import Interaction, app_commands
from discord.utils import utcnow
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine

from config.constants import DISCORD_DOMAINS, LEETCODE_DOMAINS, PERF_LOGGER_NAME

logger = logging.getLogger(PERF_LOGGER_NAME)

START_KEY = "t0"
BREAKDOWN_KEY = "breakdown"
ANNOTATIONS_KEY = "perf_fields"
REPORTED_CATEGORIES = ("discord", "db", "leetcode")
_QUERY_STARTS_KEY = "perf_query_starts"


@dataclass
class Breakdown:
    """Milliseconds and call counts per category for one interaction."""

    ms: dict[str, float] = field(default_factory=dict)
    calls: dict[str, int] = field(default_factory=dict)

    def add(self, category: str, elapsed_ms: float) -> None:
        self.ms[category] = self.ms.get(category, 0.0) + elapsed_ms
        self.calls[category] = self.calls.get(category, 0) + 1


_current: ContextVar[Breakdown | None] = ContextVar("perf_breakdown", default=None)


def start_breakdown() -> Breakdown:
    """Make a new breakdown current for this task and the tasks it starts."""
    breakdown = Breakdown()
    _current.set(breakdown)
    return breakdown


def record(category: str, elapsed_ms: float) -> None:
    """Add time to the current breakdown; a no-op outside an interaction."""
    breakdown = _current.get()
    if breakdown is not None:
        breakdown.add(category, elapsed_ms)


@contextmanager
def measure(category: str) -> Iterator[None]:
    """Record the time spent in the block under `category`."""
    started = time.perf_counter()
    try:
        yield
    finally:
        record(category, (time.perf_counter() - started) * 1000)


class LatencyTimingTree(app_commands.CommandTree):
    """A command tree that records when it started handling an interaction."""

    async def interaction_check(self, interaction: Interaction, /) -> bool:
        interaction.extras[START_KEY] = time.perf_counter()
        interaction.extras[BREAKDOWN_KEY] = start_breakdown()
        return await super().interaction_check(interaction)


def _in_domains(host: str, domains: tuple[str, ...]) -> bool:
    return any(host == domain or host.endswith(f".{domain}") for domain in domains)


def http_category(host: str | None) -> str:
    """
    The breakdown category for a request to `host`.

    A host belongs to a domain when it is the domain or one of its subdomains.
    Discord serves its REST API, interaction responses and webhooks from
    discord.com, attachments from cdn.discordapp.com and media.discordapp.net,
    and the gateway from gateway.discord.gg. Every LeetCode request the bot
    makes goes to leetcode.com.
    """
    host = (host or "").lower().rstrip(".")
    if _in_domains(host, DISCORD_DOMAINS):
        return "discord"
    if _in_domains(host, LEETCODE_DOMAINS):
        return "leetcode"
    return "http"


async def _on_request_start(
    session: aiohttp.ClientSession,
    trace_ctx: SimpleNamespace,
    params: aiohttp.TraceRequestStartParams,
) -> None:
    trace_ctx.perf_started = time.perf_counter()


async def _on_request_done(
    session: aiohttp.ClientSession,
    trace_ctx: SimpleNamespace,
    params: aiohttp.TraceRequestEndParams | aiohttp.TraceRequestExceptionParams,
) -> None:
    started = getattr(trace_ctx, "perf_started", None)
    if started is None:
        return
    record(http_category(params.url.host), (time.perf_counter() - started) * 1000)


def http_trace_config() -> aiohttp.TraceConfig:
    """A trace config that files each request's duration in the breakdown."""
    trace_config = aiohttp.TraceConfig()
    trace_config.on_request_start.append(_on_request_start)
    trace_config.on_request_end.append(_on_request_done)
    trace_config.on_request_exception.append(_on_request_done)
    return trace_config


def instrument_engine(engine: AsyncEngine) -> None:
    """File the duration of every SQL statement on `engine` under `db`."""
    sync_engine = engine.sync_engine

    @event.listens_for(sync_engine, "before_cursor_execute")
    def _before(conn, cursor, statement, parameters, context, executemany):
        conn.info.setdefault(_QUERY_STARTS_KEY, []).append(time.perf_counter())

    @event.listens_for(sync_engine, "after_cursor_execute")
    def _after(conn, cursor, statement, parameters, context, executemany):
        started = conn.info[_QUERY_STARTS_KEY].pop()
        record("db", (time.perf_counter() - started) * 1000)

    @event.listens_for(sync_engine, "handle_error")
    def _error(exception_context):
        connection = exception_context.connection
        starts = connection.info.get(_QUERY_STARTS_KEY) if connection else None
        if starts:
            record("db", (time.perf_counter() - starts.pop()) * 1000)


def handler_ms(interaction: Interaction) -> float | None:
    """
    Milliseconds spent handling the interaction.

    Returns None when the interaction carries no start stamp, which is the case
    for anything that reached the command without passing through
    `LatencyTimingTree.interaction_check`.
    """
    started = interaction.extras.get(START_KEY)
    if started is None:
        return None
    return (time.perf_counter() - started) * 1000


def e2e_ms(created_at: datetime, now: datetime | None = None) -> float:
    """Milliseconds between Discord creating the interaction and `now`."""
    return ((now or utcnow()) - created_at).total_seconds() * 1000


def format_breakdown(breakdown: Breakdown) -> str:
    """
    The breakdown fields of a log line.

    `discord`, `db` and `leetcode` always appear, as milliseconds and a call
    count. `lookup_ms` is the wall time of the problem lookup, so it includes
    any `db` or `leetcode` time spent inside it; it appears as `-` for
    commands that do no problem lookup.
    """
    fields = [
        f"{category}_ms={breakdown.ms.get(category, 0.0):.1f} "
        f"{category}_calls={breakdown.calls.get(category, 0)}"
        for category in REPORTED_CATEGORIES
    ]
    lookup = breakdown.ms.get("lookup")
    fields.append(f"lookup_ms={'-' if lookup is None else f'{lookup:.3f}'}")
    return " ".join(fields)


def annotate(interaction: Interaction, key: str, value: Any) -> None:
    """Add a `key=value` field to the interaction's latency line."""
    interaction.extras.setdefault(ANNOTATIONS_KEY, {})[key] = value


def _field_value(value: Any) -> str:
    """A value as one shell-style word: an object's id, else its text, quoted."""
    if hasattr(value, "id"):
        value = value.id
    text = " ".join(str(value).splitlines())
    return shlex.quote(text) if text else "''"


def format_fields(fields: Iterable[tuple[str, Any]], prefix: str = "") -> str:
    """`key=value` fields, skipping values that are None."""
    return " ".join(
        f"{prefix}{key}={_field_value(value)}"
        for key, value in fields
        if value is not None
    )


def format_latency(
    command: str,
    handler: float | None,
    e2e: float,
    breakdown: Breakdown | None = None,
    annotations: dict[str, Any] | None = None,
    arguments: Iterable[tuple[str, Any]] = (),
) -> str:
    """The log line for one completed command."""
    handler_repr = "?" if handler is None else f"{handler:.1f}"
    parts = [f"latency command={command} handler_ms={handler_repr} e2e_ms={e2e:.1f}"]
    if breakdown is not None:
        parts.append(format_breakdown(breakdown))
    parts.append(format_fields((annotations or {}).items()))
    parts.append(format_fields(arguments, prefix="arg_"))
    return " ".join(part for part in parts if part)


def log_command_latency(
    interaction: Interaction,
    command: app_commands.Command | app_commands.ContextMenu,
) -> None:
    """Log the latency of a command that just completed."""
    logger.info(
        format_latency(
            command.qualified_name,
            handler_ms(interaction),
            e2e_ms(interaction.created_at),
            interaction.extras.get(BREAKDOWN_KEY),
            interaction.extras.get(ANNOTATIONS_KEY),
            interaction.namespace,
        )
    )
