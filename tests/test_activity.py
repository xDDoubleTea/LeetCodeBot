from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from core.activity import ActivityManager
from db.activity import ProblemOpen, ThreadSolution
from db.problem import Problem

WHEN = datetime(2026, 10, 18, 12, 30, tzinfo=UTC)


@pytest.fixture
async def problem_db_id(database_manager) -> int:
    async with database_manager as db:
        problem = Problem(
            title="Two Sum",
            problem_id=1,
            problem_frontend_id=1,
            url="https://leetcode.com/problems/two-sum/",
            difficulty=1,
        )
        db.add(problem)
        await db.flush()
        return problem.id


@pytest.fixture
def manager(database_manager) -> ActivityManager:
    return ActivityManager(database_manager)


async def rows(database_manager, model):
    async with database_manager as db:
        return list((await db.scalars(select(model))).all())


async def record_solution(manager, problem_db_id, message_id=10, language="py"):
    await manager.record_thread_solution(
        message_id=message_id,
        thread_id=20,
        discord_user_id=30,
        problem_db_id=problem_db_id,
        language=language,
        posted_at=WHEN,
    )


async def test_a_problem_open_is_stored(manager, database_manager, problem_db_id):
    await manager.record_problem_open(
        discord_user_id=30,
        guild_id=40,
        problem_db_id=problem_db_id,
        command="filter-by-tag",
        opened_at=WHEN,
    )

    [opened] = await rows(database_manager, ProblemOpen)
    assert (opened.discord_user_id, opened.guild_id, opened.command) == (
        30,
        40,
        "filter-by-tag",
    )
    assert opened.problem_db_id == problem_db_id
    assert opened.opened_at == WHEN.replace(tzinfo=None)


async def test_every_open_is_a_new_row(manager, database_manager, problem_db_id):
    for _ in range(2):
        await manager.record_problem_open(30, 40, problem_db_id, "problem", WHEN)

    assert len(await rows(database_manager, ProblemOpen)) == 2


async def test_a_thread_solution_is_stored(manager, database_manager, problem_db_id):
    await record_solution(manager, problem_db_id)

    [solution] = await rows(database_manager, ThreadSolution)
    assert (solution.message_id, solution.thread_id, solution.discord_user_id) == (
        10,
        20,
        30,
    )
    assert (solution.problem_db_id, solution.language) == (problem_db_id, "py")


async def test_a_message_is_recorded_once(manager, database_manager, problem_db_id):
    await record_solution(manager, problem_db_id, language="py")
    await record_solution(manager, problem_db_id, language="cpp")

    [solution] = await rows(database_manager, ThreadSolution)
    assert solution.language == "py"


async def test_a_database_error_is_logged_not_raised(
    manager, database_manager, monkeypatch
):
    logger = MagicMock()
    monkeypatch.setattr("core.activity.logger", logger)

    monkeypatch.setattr(
        database_manager, "_sessionmaker", MagicMock(side_effect=RuntimeError("down"))
    )

    await manager.record_problem_open(30, 40, 1, "problem", WHEN)
    await record_solution(manager, 1)

    assert logger.error.call_count == 2
