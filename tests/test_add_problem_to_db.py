"""
Regression tests for add_problem_to_db and the tags relationship.

The tag loop reads db_problem.tags. On the async engine a lazy load cannot do IO
from plain attribute access, so the collection has to be eager loaded first or
the whole call raises MissingGreenlet -- which is what stopped the bot booting
against an empty database.
"""

from types import SimpleNamespace

from core.leetcode_problem import LeetCodeProblemManager
from db.problem import Problem, TopicTags


def make_problem(problem_id: int = 1) -> Problem:
    return Problem(
        title="Two Sum",
        problem_id=problem_id,
        problem_frontend_id=problem_id,
        url="https://leetcode.com/problems/two-sum/",
        difficulty=0,
        premium=False,
    )


def make_manager(database_manager) -> LeetCodeProblemManager:
    return LeetCodeProblemManager(SimpleNamespace(), database_manager)


async def test_adds_problem_to_an_empty_database(database_manager):
    """The path a fresh clone takes at startup: nothing in the database yet."""
    manager = make_manager(database_manager)

    problem = await manager.add_problem_to_db(
        make_problem(), {TopicTags(tag_name="Array"), TopicTags(tag_name="Hash Table")}
    )

    assert sorted(tag.tag_name for tag in problem.tags) == ["Array", "Hash Table"]


async def test_adds_tags_to_an_already_stored_problem(database_manager):
    """The second call must find the existing row and merge the new tag in."""
    manager = make_manager(database_manager)

    await manager.add_problem_to_db(make_problem(), {TopicTags(tag_name="Array")})
    problem = await manager.add_problem_to_db(
        make_problem(), {TopicTags(tag_name="Array"), TopicTags(tag_name="Two Pointers")}
    )

    assert sorted(tag.tag_name for tag in problem.tags) == ["Array", "Two Pointers"]


async def test_tags_are_readable_after_the_session_closes(database_manager):
    """
    The managers cache the returned problem and read its tags long after the
    session is gone, so the collection must already be loaded on the way out.
    """
    manager = make_manager(database_manager)

    problem = await manager.add_problem_to_db(
        make_problem(), {TopicTags(tag_name="Array")}
    )

    # No await, no session: this is a plain attribute read outside the block.
    assert [tag.tag_name for tag in problem.tags] == ["Array"]
