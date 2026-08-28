import logging
from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING

from discord import Client, Color

logger = logging.getLogger(__name__)
if TYPE_CHECKING:
    pass


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
    theme_color: Color | None


@dataclass
class ProblemTitlePaginationMetaData(BasePaginationMetaData):
    search_regex: str
    data_len: int


@dataclass
class FilterbyTagPaginationMetaData(BasePaginationMetaData):
    tag_name_query: str
    data_len: int


@dataclass
class AllTagsPaginationMetaData(BasePaginationMetaData):
    data_len: int


@dataclass
class UserSubmissionPaginationMetaData(BasePaginationMetaData):
    leetcode_username: str
    data_len: int
