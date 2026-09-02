"""Cooldown keys shared by the app commands."""

from discord import Interaction


def thread_command_key(interaction: Interaction) -> tuple[int | None, int]:
    """
    Bucket the thread-creating commands per member per guild.

    Threads belong to a guild, so one member's budget in one server leaves
    every other server untouched.
    """
    return (interaction.guild_id, interaction.user.id)
