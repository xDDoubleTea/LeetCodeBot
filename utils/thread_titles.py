"""
Reading a problem number out of a forum thread title.

Lives here rather than in cogs/migration.py because it is pure re2 and nothing
else: importing that cog pulls in discord, main and config.secrets, which makes a
unit test of a regex depend on a configured environment.
"""

# "1. Two Sum", which is what this bot names its own threads.
DEFAULT_TITLE_PATTERN = r"^(\d+)\.\s"


def problem_id_from_title(title: str, title_regex) -> int | None:
    """
    The problem number in a thread title, or None when the title does not match.

    The first capturing group has to be the number. A pattern that captures
    something else matches but yields no id, which is a mistake worth reporting
    to whoever ran the command rather than crashing on.
    """
    match = title_regex.match(title)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None
