import logging

from discord.app_commands import AppCommandError

logger = logging.getLogger(__name__)


class FetchError(Exception):
    """
    Raised when LeetCode API caller cannot fetch data.
    """

    def __init__(
        self,
        error_response: dict | None,
        message: str = ("Something is wrong when fetching"),
    ):
        self.message = message
        self.error_response = error_response
        super().__init__(message)


class QueryNotFound(Exception):
    """
    Raised when a GraphQL query is not found
    """


class ForumChannelNotFound(AppCommandError):
    """
    Raised when a guild has no usable forum channel for problem threads.

    An AppCommandError rather than a plain Exception: discord.py re-raises those
    untouched instead of wrapping them in CommandInvokeError, so this reaches
    app_command_message and gets its own reply rather than the generic
    "something went wrong" every unrecognised exception receives.
    """

    def __init__(
        self,
        message: str = (
            "I do not know which forum channel to create the thread in. "
            "Ask a server administrator to run /set_forum_channel first."
        ),
    ):
        self.message = message
        super().__init__(message)


class CacheInitError(Exception):
    """
    Raised when the problem, tag and thread caches could not be built.

    Deliberately not an AppCommandError. This is raised from init_cache and
    refresh_cache, which run at startup and on a daily loop where no interaction
    exists; /refresh is the only command that can trigger it and it reports the
    failure itself.
    """


class DuplicateLinkName(ValueError):
    """
    Raised when a user is trying to create a list with name that they already have created with.
    """

    def __init__(
        self,
        message: str = ("You already created a list with that name!"),
    ):
        self.message = message
        super().__init__(message)


class NotLinkedError(Exception):
    """
    Raised when a user has not linked their leetcode user name to their discord account.
    """


class LeetCodeUserNameNotFound(Exception):
    """
    Raised when a LeetCode user name is not found.
    """

    def __init__(
        self,
        message: str = ("That user name is invalid. Check for typo."),
    ):
        self.message = message
        super().__init__(message)
