from typing import Union
from discord import Embed, Client

import time
from datetime import date

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

    t = time.localtime()
    today = date.today()
    today_date = today.strftime("%Y/%m/%d")
    current_time = time.strftime("%H:%M:%S", t)
    embed.set_author(
        name=f"{client.user.display_name}", icon_url=client.user.avatar.url
    )
    embed.set_footer(
        text=f"{default_footer}\tDeveloped by {dev.name}.\nSent at {today_date} , {current_time}",
        icon_url=dev.avatar.url,
    )
