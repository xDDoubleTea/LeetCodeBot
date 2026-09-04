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


class VerificationTokenNotGenerated(Exception):
    """
    Raised when a user tries to verify when they haven't generated a verification token yet
    """

    def __init__(
        self,
        message: str = (
            "You haven't generated a verification token yet! Generate one with `/link`!"
        ),
    ):
        self.message = message
        super().__init__(message)


class VerificationTokenExpired(Exception):
    """
    Raised when a verification token has expired when getting checked.
    """

    def __init__(
        self,
        message: str = (
            "Your verification token has expired! Generate a new one with `/link`!"
        ),
    ):
        self.message = message
        super().__init__(message)


class VerificationAlreadyFailed(Exception):
    """
    Raised when a verification has already failed.
    """

    def __init__(
        self,
        message: str = (
            "Your verification token has expired! Generate a new one with `/link`!"
        ),
    ):
        self.message = message
        super().__init__(message)


class VerificationFailed(Exception):
    """
    Raised when a verification failed.
    """

    def __init__(
        self,
        message: str = (
            "Verification failed!\n"
            "If you think this is not your fault, please contact admin or open an issue on github!"
        ),
    ):
        self.message = message
        super().__init__(message)


class VerificationTokenAlreadyCompleted(Exception):
    """
    Raised when a verification token has been completed already.
    """

    def __init__(
        self,
        message: str = (
            "You have already completed the verification!\n"
            "If you want to link to another user run `/link` with that user name again!"
        ),
    ):
        self.message = message
        super().__init__(message)


class VerificationTokenNotFound(Exception):
    """
    Raised when a user tries to verify but the bot cannot find the token in their about_me.
    """

    def __init__(
        self,
        message: str = (
            "I can't find the token in your ReadMe. Possible problems:\n"
            "1. The change hasn't propagated yet.\n"
            "2. The `leetcodebot-verify-` prefix was dropped.\n"
            "3. You didn't copy the whole code."
        ),
    ):
        self.message = message
        super().__init__(message)
