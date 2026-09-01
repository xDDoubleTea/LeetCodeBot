"""
Guards the select-option builder against being importable but not callable.

`build_problem_options` calls `ProblemDifficulity` in its body, not just in an
annotation. When that import sat under `if TYPE_CHECKING:` the module imported
cleanly and ruff stayed quiet, but the first page holding a result raised
`NameError` -- and since `BasePaginationView.__init__` builds the options, the
failure was in the constructor, so `/problem-title` and `/filter-by-tag` broke
for every search that actually matched something.
"""

from unittest.mock import MagicMock

import pytest
from discord import Color

from db.problem import Problem
from models.pagination import ProblemTitlePageMeta
from utils.build_page_option import build_problem_options
from view.pagination_view import ProblemTitlePaginationView


def make_problem(frontend_id: int, title: str, difficulty: int) -> Problem:
    return Problem(
        problem_id=frontend_id,
        problem_frontend_id=frontend_id,
        title=title,
        url=f"https://leetcode.com/problems/{title.lower().replace(' ', '-')}/",
        difficulty=difficulty,
        description="",
    )


def make_metadata(data_len: int) -> ProblemTitlePageMeta:
    return ProblemTitlePageMeta(
        guild_name="guild",
        guild_id=1,
        channel_name="channel",
        channel_id=2,
        user_name="user",
        user_id=3,
        client=MagicMock(),
        theme_color=Color.blurple(),
        search_regex="two",
        data_len=data_len,
    )


@pytest.mark.parametrize(
    ("difficulty", "expected"),
    [(0, "Easy"), (1, "Medium"), (2, "Hard")],
)
def test_option_label_names_the_difficulty(difficulty, expected):
    options = build_problem_options([make_problem(1, "Two Sum", difficulty)])

    assert len(options) == 1
    assert options[0].label == f"1. Two Sum [{expected}]"
    assert options[0].value == "1"


def test_no_problems_gives_no_options():
    # The empty case never reached ProblemDifficulity, which is why the missing
    # import survived a smoke test: a search returning nothing looked fine.
    assert build_problem_options([]) == []


def test_a_long_title_is_truncated_to_discord_s_limit():
    options = build_problem_options([make_problem(1, "x" * 200, 0)])

    assert len(options[0].label) == 100


async def test_building_the_view_with_a_result_populates_the_select():
    """
    The regression guard. The builder runs inside `__init__`, so a broken one
    raises before the command ever replies.
    """
    problems = [make_problem(1, "Two Sum", 0), make_problem(2, "Add Two Numbers", 1)]

    view = ProblemTitlePaginationView(
        metadata=make_metadata(len(problems)),
        data=problems,
        format_page=lambda metadata, page: MagicMock(),
        select_options_builder=build_problem_options,
        select_callback=MagicMock(),
    )

    assert view.select_menu is not None
    assert not view.select_menu.disabled
    assert [option.value for option in view.select_menu.options] == ["1", "2"]


async def test_building_the_view_with_no_results_disables_the_select():
    view = ProblemTitlePaginationView(
        metadata=make_metadata(0),
        data=[],
        format_page=lambda metadata, page: MagicMock(),
        select_options_builder=build_problem_options,
        select_callback=MagicMock(),
    )

    assert view.select_menu is not None
    assert view.select_menu.disabled
