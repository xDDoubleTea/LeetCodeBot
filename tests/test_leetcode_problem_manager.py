from unittest.mock import AsyncMock, MagicMock

import pytest

from core.leetcode_api import LeetCodeAPI
from core.leetcode_problem import LeetCodeProblemManager
from db.async_db_manager import AsyncDatabaseManager
from db.problem import (
    Problem,
    TopicTags,
)  # Use actual Problem/TopicTags for instantiation
from models.leetcode import ProblemWithTags


@pytest.fixture
def mock_api():
    return AsyncMock(spec=LeetCodeAPI)


@pytest.fixture
def mock_db_session():
    session = MagicMock()
    mock_execute_result = MagicMock()
    mock_scalars_result = MagicMock()

    session.execute = AsyncMock(return_value=mock_execute_result)
    session.scalars = AsyncMock(return_value=mock_scalars_result)

    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.flush = AsyncMock()
    session.delete = AsyncMock()
    # session.add stays a plain MagicMock — it's sync on AsyncSession too
    return session


@pytest.fixture
def mock_db_manager(mock_db_session):
    manager = MagicMock(spec=AsyncDatabaseManager)
    manager.__aenter__.return_value = mock_db_session
    manager.__aexit__.return_value = False  # Don't suppress exceptions
    return manager


@pytest.fixture
def manager(mock_api, mock_db_manager, mock_logger):
    return LeetCodeProblemManager(mock_api, mock_db_manager)


@pytest.mark.asyncio
async def test_get_daily_problem_in_cache(manager):
    mock_problem = Problem(
        problem_frontend_id=100,
        title="Daily Cached",
        problem_id=1,
        difficulty=0,
        url="http://example.com/daily",
        description="desc",
        premium=False,
    )
    manager.all_problem_cache[100] = mock_problem

    api_problem_obj = Problem(
        problem_frontend_id=100,
        title="API Problem",
        problem_id=1,
        difficulty=0,
        url="http://example.com/api",
        description="desc",
        premium=False,
    )
    manager.leetcode_api.fetch_daily.return_value = ProblemWithTags(
        api_problem_obj, set()
    )

    result = await manager.get_daily_problem()
    assert result.problem == mock_problem
    assert result.problem.title == "Daily Cached"


@pytest.mark.asyncio
async def test_get_daily_problem_in_db_not_in_cache(manager, mock_db_session):
    api_problem_obj = Problem(
        problem_frontend_id=200,
        title="Daily API",
        problem_id=2,
        difficulty=0,
        url="http://example.com/api",
        description="desc",
        premium=False,
    )
    manager.leetcode_api.fetch_daily.return_value = ProblemWithTags(
        api_problem_obj, set()
    )

    assert 200 not in manager.all_problem_cache

    db_problem = Problem(
        problem_frontend_id=200,
        title="Daily DB",
        problem_id=2,
        difficulty=0,
        url="http://example.com/db",
        description="desc",
        premium=False,
    )

    mock_db_session.scalars.return_value.first.return_value = db_problem

    result = await manager.get_daily_problem()

    assert result.problem == db_problem
    assert result.problem.title == "Daily DB"
    assert manager.all_problem_cache[200] == db_problem


@pytest.mark.asyncio
async def test_get_daily_problem_fetch_new(manager, mock_db_session):
    api_problem_obj = Problem(
        problem_frontend_id=300,
        problem_id=3000,
        title="New Daily",
        difficulty=0,
        url="http://example.com/new",
        description="desc",
        premium=False,
    )
    tags = {TopicTags(tag_name="Tag1")}
    manager.leetcode_api.fetch_daily.return_value = ProblemWithTags(
        api_problem_obj, tags
    )

    assert 300 not in manager.all_problem_cache

    mock_db_session.scalars.return_value.first.return_value = None

    # Mocking the problem added to db.add
    mock_db_session.add.side_effect = lambda x: setattr(
        x, "tags", list(tags)
    )  # Simulate adding tags to problem

    result = await manager.get_daily_problem()

    assert result.problem == api_problem_obj
    assert 300 in manager.all_problem_cache

    mock_db_session.add.assert_any_call(api_problem_obj)
    mock_db_session.commit.assert_called()


@pytest.mark.asyncio
async def test_get_problem_found_in_cache(manager):
    mock_problem = Problem(
        problem_frontend_id=1,
        title="Cached",
        problem_id=1,
        difficulty=0,
        url="http://example.com/cached",
        description="desc",
        premium=False,
    )
    manager.all_problem_cache[1] = mock_problem

    result = await manager.get_problem_with_frontend_id(1)
    assert result.problem == mock_problem


@pytest.mark.asyncio
async def test_refresh_cache_success(manager, mock_db_session):
    p1 = Problem(
        problem_frontend_id=1,
        problem_id=10,
        title="P1",
        difficulty=0,
        url="url1",
        description="desc1",
        premium=False,
        id=100,
    )
    p2 = Problem(
        problem_frontend_id=2,
        problem_id=20,
        title="P2",
        difficulty=1,
        url="url2",
        description="desc2",
        premium=False,
        id=101,
    )
    t1 = TopicTags(tag_name="T1", id=500)
    t2 = TopicTags(tag_name="T2", id=501)

    api_data = {
        1: ProblemWithTags(problem=p1, tags={t1}),
        2: ProblemWithTags(problem=p2, tags={t2}),
    }

    # api_data = {1: {"problem": p1, "tags": {t1}}, 2: {"prblem": p2, "tags": {t2}}}

    manager.leetcode_api.fetch_all_problems.return_value = api_data

    # _create_problem_tag_associations reads problems then tags, then init_cache
    # reads the problems and finally the topic tags it builds the tag cache from.
    mock_db_session.scalars.return_value.all.side_effect = [
        [p1, p2],
        [t1, t2],
        [p1, p2],
        [t1, t2],
    ]

    api_problem_obj = Problem(
        problem_frontend_id=300,
        problem_id=3000,
        title="New Daily",
        difficulty=0,
        url="http://example.com/new",
        description="desc",
        premium=False,
    )
    tags = {TopicTags(tag_name="Tag1")}
    manager.leetcode_api.fetch_daily.return_value = ProblemWithTags(
        api_problem_obj, tags
    )

    await manager.refresh_cache()

    assert 1 in manager.all_problem_cache
    assert 2 in manager.all_problem_cache
    assert manager.all_problem_cache[1] == p1

    # The tag cache is rebuilt by the refresh. It used to be filled once in
    # setup_hook and never again, so a tag added to LeetCode stayed invisible to
    # /check-available-tags, the autocomplete and TagTransformer until a restart.
    assert manager.tag_cache_literal == ["T1", "T2"]

    execute_calls = mock_db_session.execute.call_args_list
    assert len(execute_calls) == 4

    scalars_calls = mock_db_session.scalars.call_args_list
    # Five, not four: init_cache now reads the topic tags as well, to rebuild the
    # tag cache.
    assert len(scalars_calls) == 5

    # 1. Problem bulk upsert
    problem_upsert_data = execute_calls[0].args[1]
    assert len(problem_upsert_data) == 2
    assert problem_upsert_data[0]["problem_frontend_id"] in (1, 2)
    assert problem_upsert_data[1]["problem_frontend_id"] in (1, 2)

    # 2. Topic Tags bulk upsert (Order independent)
    tag_upsert_data = execute_calls[1].args[1]
    assert len(tag_upsert_data) == 2
    assert {"tag_name": "T1", "id": 500} in tag_upsert_data
    assert {"tag_name": "T2", "id": 501} in tag_upsert_data

    # 3. Delete old associations (Statement only, no arguments)
    assert len(execute_calls[2].args) == 1

    # 4. Insert new associations (Order independent)
    assoc_upsert_data = execute_calls[3].args[1]
    assert len(assoc_upsert_data) == 2
    assert {"problem_id": 100, "tag_id": 500} in assoc_upsert_data
    assert {"problem_id": 101, "tag_id": 501} in assoc_upsert_data
