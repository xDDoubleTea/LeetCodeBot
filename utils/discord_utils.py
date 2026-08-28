import logging
from typing import Any

import discord
from discord import Guild, Member, Message, PartialMessage, Role, TextChannel
from discord.abc import GuildChannel
from discord.channel import DMChannel
from discord.ext.commands import Bot
from discord.user import User

logger = logging.getLogger(__name__)


async def get_or_fetch(
    container: Any,
    obj_id: int,
    get_method_name: str,
    fetch_method_name: str,
) -> Any:
    """
    A generic utility to get a Discord object from cache or fetch it from the API.
    Returns the resolved object, or None if it's not found.
    """
    try:
        if (obj := getattr(container, get_method_name)(obj_id)) is not None:
            return obj
    except AttributeError:
        pass

    try:
        return await getattr(container, fetch_method_name)(obj_id)
    except (discord.errors.NotFound, discord.errors.HTTPException):
        return None
    except AttributeError:
        return None


async def try_get_channel_by_bot(
    bot: discord.Client | Bot, channel_id: int
) -> GuildChannel | discord.TextChannel | None:
    return await get_or_fetch(
        container=bot,
        obj_id=channel_id,
        get_method_name="get_channel",
        fetch_method_name="fetch_channel",
    )


async def try_get_user(bot: discord.Client | Bot, user_id: int) -> User | None:
    return await get_or_fetch(
        container=bot,
        obj_id=user_id,
        get_method_name="get_user",
        fetch_method_name="fetch_user",
    )


async def try_get_channel(
    guild: discord.Guild, channel_id: int
) -> GuildChannel | discord.TextChannel | None:
    return await get_or_fetch(
        container=guild,
        obj_id=channel_id,
        get_method_name="get_channel",
        fetch_method_name="fetch_channel",
    )


async def try_get_guild(bot: discord.Client | Bot, guild_id: int) -> Guild | None:
    return await get_or_fetch(
        container=bot,
        obj_id=guild_id,
        get_method_name="get_guild",
        fetch_method_name="fetch_guild",
    )


async def try_get_member(guild: Guild, member_id: int) -> Member | None:
    return await get_or_fetch(
        container=guild,
        obj_id=member_id,
        get_method_name="get_member",
        fetch_method_name="fetch_member",
    )


async def try_get_role(guild: Guild, role_id: int) -> Role | None:
    return await get_or_fetch(
        container=guild,
        obj_id=role_id,
        get_method_name="get_role",
        fetch_method_name="fetch_role",
    )


async def try_get_message(
    channel: TextChannel | DMChannel, message_id: int
) -> PartialMessage | Message | None:
    return await get_or_fetch(
        container=channel,
        obj_id=message_id,
        get_method_name="get_partial_message",
        fetch_method_name="fetch_message",
    )
