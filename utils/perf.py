"""
Latency instrumentation for application commands.

`LatencyTimingTree` stamps a `time.perf_counter()` reading onto every
interaction the command tree accepts. `log_command_latency` reads that stamp
back when the command finishes and logs one line per invocation, reporting both
the time spent inside the bot and the time since Discord created the
interaction.
"""

import logging
import time
from datetime import datetime

from discord import Interaction, app_commands
from discord.utils import utcnow

logger = logging.getLogger(__name__)

START_KEY = "t0"


class LatencyTimingTree(app_commands.CommandTree):
    """A command tree that records when it started handling an interaction."""

    async def interaction_check(self, interaction: Interaction, /) -> bool:
        interaction.extras[START_KEY] = time.perf_counter()
        return await super().interaction_check(interaction)


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


def format_latency(command: str, handler: float | None, e2e: float) -> str:
    """The log line for one completed command."""
    handler_repr = "?" if handler is None else f"{handler:.1f}"
    return f"latency command={command} handler_ms={handler_repr} e2e_ms={e2e:.1f}"


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
        )
    )
