import datetime
import logging
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import TYPE_CHECKING

import discord

logger = logging.getLogger(__name__)
if TYPE_CHECKING:
    from db.problem import Problem, TopicTags


class ProblemDifficulity(Enum):
    EASY = (0, "Easy", discord.Color.green())
    MEDIUM = (1, "Medium", discord.Color.orange())
    HARD = (2, "Hard", discord.Color.red())

    def __init__(self, db_repr: int, str_repr: str, embed_color: discord.Color) -> None:
        self.db_repr = db_repr
        self.str_repr = str_repr
        self.embed_color = embed_color

    @classmethod
    def from_db_repr(cls, db_repr: int) -> "ProblemDifficulity":
        for difficulty in ProblemDifficulity:
            if difficulty.db_repr == db_repr:
                return difficulty
        raise ValueError(f"No matching difficulty for db_repr: {db_repr}")

    @classmethod
    def from_str_repr(cls, str_repr: str) -> "ProblemDifficulity":
        for difficulty in ProblemDifficulity:
            if difficulty.str_repr.lower() == str_repr.lower():
                return difficulty
        raise ValueError(f"No matching difficulty for str_repr: {str_repr}")


class ThreadCreationEnum(IntEnum):
    REOPEN = 0
    CREATE = 1


class VerificationStatus(IntEnum):
    FAILED = 0
    PENDING = 1
    EXPIRED = 2
    COMPLETE = 3


@dataclass
class ProblemWithTags:
    problem: "Problem"
    tags: set["TopicTags"]


@dataclass
class UserSubmissionStat:
    difficulity: str
    ac_submission_count: int
    total_submissions_and_ac_count: int


@dataclass
class UserProfile:
    user_avatar: str
    country_name: str
    about_me: str
    company: str
    job_title: str
    school: str
    websites: list[str]


@dataclass
class UserSubmission:
    title: str
    title_slug: str
    timestamp: str
    status_display: str
    url: str
    lang_name: str
    runtime: str
    is_pending: bool
    memory: str
    frontend_id: int


@dataclass
class UserInfo:
    user_name: str
    github_url: str
    twitter_url: str
    linkedin_url: str
    ac_submission: UserSubmissionStat
    user_profile: UserProfile


@dataclass
class VerificationEntry:
    discord_user_id: int
    leetcode_user_name: str
    verification_token: str
    timestamp: datetime.datetime
    status: VerificationStatus
