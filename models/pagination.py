import logging
from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING

from discord import Client, Color

logger = logging.getLogger(__name__)
if TYPE_CHECKING:
    pass


class PageButtons(IntEnum):
    FIRST_PAGE = 0
    PREV_PAGE = 1
    PAGE_DISPLAY = 2
    NEXT_PAGE = 3
    LAST_PAGE = 4


@dataclass
class BasePageMetaData:
    """The metadata used by the pagination view."""

    guild_name: str
    guild_id: int
    channel_name: str
    channel_id: int
    user_name: str
    user_id: int

    # Because we have to pass client to the embed_utils
    client: Client
    theme_color: Color | None


@dataclass
class ProblemTitlePageMeta(BasePageMetaData):
    search_regex: str
    data_len: int


@dataclass
class FilterbyTagPageMeta(BasePageMetaData):
    tag_name_query: str
    data_len: int


@dataclass
class AllTagsPageMeta(BasePageMetaData):
    data_len: int


@dataclass
class UserSubmissionPageMeta(BasePageMetaData):
    leetcode_username: str
    data_len: int
