"""
Wrap long method signatures in a pyreverse class chart, one parameter per line.

Reads pyreverse `--output dot` from stdin and prints it to stdout. Run by
`scripts/generate_uml.sh` before `dot` renders each class chart.
"""

import re
import sys

MAX_WIDTH = 60
BREAK = '<br ALIGN="LEFT"/>'
INDENT = "&nbsp;" * 4
SEPARATOR = re.compile(rf"({re.escape(BREAK)}|(?<!\\)\||\{{|\}})")
METHOD = re.compile(r"^(\w+)\((.*)\)(:.*)?$")


def split_parameters(parameters: str) -> list[str]:
    """Split a parameter list at the commas outside brackets."""
    parts, depth, start = [], 0, 0
    for index, char in enumerate(parameters):
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(parameters[start:index].strip())
            start = index + 1
    parts.append(parameters[start:].strip())
    return parts


def wrap(segment: str) -> str:
    match = METHOD.match(segment)
    if len(segment) <= MAX_WIDTH or not match:
        return segment
    name, parameters, returns = match.groups()
    lines = f",{BREAK}".join(f"{INDENT}{part}" for part in split_parameters(parameters))
    return BREAK.join([f"{name}(", lines, f"){returns or ''}"])


def wrap_label(label: str) -> str:
    return "".join(wrap(part) for part in SEPARATOR.split(label))


def main() -> None:
    dot = sys.stdin.read()
    print(re.sub(r"label=<(.*)>", lambda m: f"label=<{wrap_label(m[1])}>", dot))


if __name__ == "__main__":
    main()
