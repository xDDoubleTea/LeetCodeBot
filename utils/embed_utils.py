from typing import Union
from discord import Embed, Client
import datetime
import calendar
from config.constants import THEME_COLOR, DEV_ID, default_footer


def create_themed_embed(
    title: str, description: str = "", client: Union[Client, None] = None
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

    dt = datetime.datetime.now(tz=datetime.timezone.utc).timetuple()

    embed.description = (
        f"<t:{calendar.timegm(dt)}:F>\n{embed.description if embed.description else ''}"
    )
    embed.set_author(
        name=f"{client.user.display_name}", icon_url=client.user.avatar.url
    )
    embed.set_footer(
        text=f"{default_footer}\nDeveloped by {dev.name}.\n",
        icon_url=dev.avatar.url,
    )
