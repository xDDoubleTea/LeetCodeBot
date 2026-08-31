"""
The thread-title matching behind /migrate.

The command itself is Discord-bound, but the part that decides which threads get
recorded is not, and it is the part an admin's own regex reaches.
"""

import re2

from utils.thread_titles import DEFAULT_TITLE_PATTERN, problem_id_from_title


def match(title: str, pattern: str = DEFAULT_TITLE_PATTERN) -> int | None:
    return problem_id_from_title(title, re2.compile(pattern))


def test_the_default_pattern_reads_this_bots_own_titles():
    assert match("1. Two Sum") == 1
    assert match("1470. Shuffle the Array") == 1470


def test_a_title_that_does_not_match_is_skipped():
    assert match("Weekly contest discussion") is None
    assert match("Two Sum") is None


def test_a_custom_pattern_can_describe_another_bots_titles():
    assert match("[LC 42] Trapping Rain Water", r"^\[LC (\d+)\]") == 42
    assert match("Problem #42 - Trapping Rain Water", r"^Problem #(\d+)") == 42


def test_the_pattern_is_anchored_at_the_start_of_the_title():
    r"""
    match(), not search(). A pattern that describes the middle of a title has to
    say so, which keeps a bare `(\d+)` from picking up the first number it finds
    anywhere in an unrelated thread name.
    """
    assert match("Problem #42 - Trapping Rain Water", r"#(\d+)") is None
    assert match("Problem #42 - Trapping Rain Water", r".*#(\d+)") == 42


def test_a_pattern_capturing_something_other_than_the_number_is_skipped():
    """
    Rather than raising: the whole point of the parameter is that whoever runs
    /migrate writes the pattern, so a wrong one has to be reportable.
    """
    assert match("1. Two Sum", r"^\d+\.\s(\w+)") is None


def test_the_number_is_taken_from_the_first_group():
    assert match("2024: 1. Two Sum", r"^(\d+): (\d+)\.") == 2024
