import re

_FENCE = re.compile(r"```([^\s`]*)[^\n`]*\n.*?```", re.DOTALL)


def code_block_languages(content: str) -> list[str | None]:
    """
    The language of each fenced code block in a Discord message, in order.

    A block without a language, such as a bare ```` ``` ````, gives `None`.
    An empty list means the message has no fenced code block. Discord renders
    a fence only when a newline follows the opening backticks, so a one-line
    ```` ```x``` ```` is not a block.
    """
    return [match.group(1).lower() or None for match in _FENCE.finditer(content)]
