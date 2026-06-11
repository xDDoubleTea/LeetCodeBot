from enum import IntEnum
from dataclasses import dataclass
from discord import Client, Color
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from db.problem import Problem


class PaginationViewButtonLayouts(IntEnum):
    FIRST_PAGE = 0
    PREV_PAGE = 1
    PAGE_DISPLAY = 2
    NEXT_PAGE = 3
    LAST_PAGE = 4


@dataclass
class BasePaginationMetaData:
    """The metadata used by the pagination view."""

    guild_name: str
    guild_id: int
    channel_name: str
    channel_id: int
    user_name: str
    user_id: int

    # Because we have to pass client to the embed_utils
    client: Client
    theme_color: Optional[Color]


@dataclass
class ProblemTitlePaginationMetaData(BasePaginationMetaData):
    search_regex: str
    data_len: int
