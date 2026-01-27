import pytest
from unittest.mock import MagicMock, AsyncMock, call, ANY
from core.leetcode_problem import LeetCodeProblemManager, ProblemNotFound
from core.leetcode_api import LeetCodeAPI
from db.database_manager import DatabaseManager
from db.problem import Problem, TopicTags # Use actual Problem/TopicTags for instantiation
import logging

@pytest.fixture
def mock_api():
    return AsyncMock(spec=LeetCodeAPI)

@pytest.fixture
def mock_db_session():
    session = MagicMock()
    session.execute.return_value.scalars.return_value.all.return_value = [] # Default empty list for all()
    session.execute.return_value.scalars.return_value.first.return_value = None # Default None for first()
    session.query.return_value.filter_by.return_value.first.return_value = None # Default None for query().filter_by().first()
    session.query.return_value.all.return_value = [] # Default empty list for query().all()

    return session

@pytest.fixture
def mock_db_manager(mock_db_session):
    manager = MagicMock(spec=DatabaseManager)
    manager.__enter__.return_value = mock_db_session
    manager.__exit__.return_value = False # Don't suppress exceptions
    return manager

@pytest.fixture
def manager(mock_api, mock_db_manager, mock_logger):
    return LeetCodeProblemManager(mock_api, mock_db_manager, mock_logger)

@pytest.mark.asyncio
async def test_get_daily_problem_in_cache(manager):
    mock_problem = Problem(problem_frontend_id=100, title="Daily Cached", problem_id=1, difficulty=0, url="http://example.com/daily", description="desc", premium=False)
    manager.all_problem_cache[100] = mock_problem
    
    api_problem_obj = Problem(problem_frontend_id=100, title="API Problem", problem_id=1, difficulty=0, url="http://example.com/api", description="desc", premium=False)
    manager.leetcode_api.fetch_daily.return_value = {
        "problem": api_problem_obj,
        "tags": set()
    }
    
    result = await manager.get_daily_problem()
    assert result["problem"] == mock_problem
    assert result["problem"].title == "Daily Cached"

@pytest.mark.asyncio
async def test_get_daily_problem_in_db_not_cache(manager, mock_db_session):
    api_problem_obj = Problem(problem_frontend_id=200, title="Daily API", problem_id=2, difficulty=0, url="http://example.com/api", description="desc", premium=False)
    manager.leetcode_api.fetch_daily.return_value = {
        "problem": api_problem_obj,
        "tags": set()
    }
    
    assert 200 not in manager.all_problem_cache
    
    db_problem = Problem(problem_frontend_id=200, title="Daily DB", problem_id=2, difficulty=0, url="http://example.com/db", description="desc", premium=False)
    
    mock_db_session.execute.return_value.scalars.return_value.first.return_value = db_problem
    
    result = await manager.get_daily_problem()
    
    assert result["problem"] == db_problem
    assert result["problem"].title == "Daily DB"
    assert manager.all_problem_cache[200] == db_problem

@pytest.mark.asyncio
async def test_get_daily_problem_fetch_new(manager, mock_db_session):
    api_problem_obj = Problem(problem_frontend_id=300, problem_id=3000, title="New Daily", difficulty=0, url="http://example.com/new", description="desc", premium=False)
    tags = {TopicTags(tag_name="Tag1")}
    manager.leetcode_api.fetch_daily.return_value = {
        "problem": api_problem_obj,
        "tags": tags
    }
    
    assert 300 not in manager.all_problem_cache
    
    mock_db_session.execute.return_value.scalars.return_value.first.return_value = None

    mock_db_session.query.return_value.filter_by.return_value.first.return_value = None
    
    # Mocking the problem added to db.add
    mock_db_session.add.side_effect = lambda x: setattr(x, 'tags', list(tags)) # Simulate adding tags to problem

    result = await manager.get_daily_problem()
    
    assert result["problem"] == api_problem_obj
    assert 300 in manager.all_problem_cache
    
    mock_db_session.add.assert_any_call(api_problem_obj)
    mock_db_session.commit.assert_called()

@pytest.mark.asyncio
async def test_get_problem_found_in_cache(manager):
    mock_problem = Problem(problem_frontend_id=1, title="Cached", problem_id=1, difficulty=0, url="http://example.com/cached", description="desc", premium=False)
    manager.all_problem_cache[1] = mock_problem
    
    result = await manager.get_problem_with_frontend_id(1)
    assert result["problem"] == mock_problem
    manager.leetcode_api.fetch_problem_by_id.assert_not_called()

@pytest.mark.asyncio
async def test_get_problem_fetch_api(manager, mock_db_session):
    mock_db_session.execute.return_value.scalars.return_value.first.return_value = None
    
    api_problem = Problem(problem_frontend_id=5, problem_id=50, title="API Fetch", difficulty=0, url="http://example.com/api-fetch", description="desc", premium=False)
    tags = {TopicTags(tag_name="TagA")}
    manager.leetcode_api.fetch_problem_by_id.return_value = {
        "problem": api_problem,
        "tags": tags
    }
    
    mock_db_session.query.return_value.filter_by.return_value.first.return_value = None
    
    mock_db_session.add.side_effect = lambda x: setattr(x, 'tags', list(tags))

    result = await manager.get_problem_with_frontend_id(5)
    assert result["problem"] == api_problem
    assert 5 in manager.all_problem_cache
    manager.leetcode_api.fetch_problem_by_id.assert_awaited_with(5)
    mock_db_session.add.assert_any_call(api_problem)
    mock_db_session.commit.assert_called()

@pytest.mark.asyncio
async def test_refresh_cache_success(manager, mock_db_session):
    p1 = Problem(problem_frontend_id=1, problem_id=10, title="P1", difficulty=0, url="url1", description="desc1", premium=False, id=100)
    p2 = Problem(problem_frontend_id=2, problem_id=20, title="P2", difficulty=1, url="url2", description="desc2", premium=False, id=101)
    t1 = TopicTags(tag_name="T1", id=500)
    t2 = TopicTags(tag_name="T2", id=501)
    
    api_data = {
        1: {"problem": p1, "tags": {t1}},
        2: {"problem": p2, "tags": {t2}}
    }
    manager.leetcode_api.fetch_all_problems.return_value = api_data
    
    mock_db_session.query.return_value.all.side_effect = [
        [p1, p2], # For db_problems
        [t1, t2]  # For db_tags
    ]
    mock_db_session.execute.return_value.scalars.return_value.all.return_value = [p1, p2]

    await manager.refresh_cache()
    
    assert 1 in manager.all_problem_cache
    assert 2 in manager.all_problem_cache
    assert manager.all_problem_cache[1] == p1
    mock_db_session.execute.assert_has_calls([
        call(ANY, [{'problem_frontend_id': 1, 'problem_id': 10, 'title': 'P1', 'url': 'url1', 'difficulty': 0, 'description': 'desc1', 'premium': False, 'id': 100, 'tags': []}, {'problem_frontend_id': 2, 'problem_id': 20, 'title': 'P2', 'url': 'url2', 'difficulty': 1, 'description': 'desc2', 'premium': False, 'id': 101, 'tags': []}]),
        call(ANY, [{'tag_name': 'T1', 'id': 500}, {'tag_name': 'T2', 'id': 501}]),
        call(ANY), # delete associations
        call(ANY, [{'problem_id': 100, 'tag_id': 500}, {'problem_id': 101, 'tag_id': 501}]) # insert associations
    ], any_order=True)
