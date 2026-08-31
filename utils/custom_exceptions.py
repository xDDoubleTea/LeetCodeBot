import logging

from discord.app_commands import AppCommandError

logger = logging.getLogger(__name__)


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
