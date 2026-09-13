import calendar
import datetime
import logging

from discord import Client, Embed

from config.constants import DEFAULT_FOOTER, DEV_ID, THEME_COLOR

logger = logging.getLogger(__name__)


def create_themed_embed(
    title: str, description: str = "", client: Client | None = None
) -> Embed:
    embed = Embed(title=title, description=description, color=THEME_COLOR)
    if client:
        add_std_footer(embed=embed, client=client)
    return embed


def add_std_footer(embed: Embed, client: Client):
    if not client.user:
        return
    dev = client.get_user(DEV_ID)
    assert dev is not None and dev.avatar is not None and client.user.avatar is not None

    dt = datetime.datetime.now(tz=datetime.UTC).timetuple()

    embed.description = (
        f"<t:{calendar.timegm(dt)}:F>\n{embed.description if embed.description else ''}"
    )
    embed.set_author(
        name=f"{client.user.display_name}", icon_url=client.user.avatar.url
    )
    embed.set_footer(
        text=f"{DEFAULT_FOOTER}\nDeveloped by {dev.name}.\n",
        icon_url=dev.avatar.url,
    )
