import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from core.leetcode_api import LeetCodeAPI, FetchError
from models.leetcode import ProblemDifficulity
import logging

# We will patch db.problem.Problem and db.problem.TopicTags
# when these are imported into core/leetcode_api.py and core/leetcode_problem.py.

# The logger fixture is now in conftest.py
# @pytest.fixture
# def mock_logger():
#     return MagicMock(spec=logging.Logger)

@pytest.fixture
def leetcode_api(mock_logger):
    return LeetCodeAPI(logger=mock_logger)

def test_parse_problem_desc(leetcode_api):
    html_content = "<p>Test <strong>Bold</strong> <em>Italic</em> <code>Code</code> <sup>Sup</sup></p>"
    
    parsed = leetcode_api._parse_problem_desc(html_content)
    assert "**Bold**" in parsed
    assert "*Italic*" in parsed
    assert "`Code`" in parsed
    assert "^Sup" in parsed

@pytest.mark.asyncio
@patch('core.leetcode_api.Problem')
@patch('core.leetcode_api.TopicTags')
async def test_fetch_daily_success(mock_topic_tags_cls, mock_problem_cls, leetcode_api):
    mock_data = {
        "link": "https://leetcode.com/problems/test-problem",
        "question": {
            "title": "Test Problem",
            "questionId": "1",
            "questionFrontendId": "1",
            "difficulty": "Easy",
            "content": "<p>Description</p>",
            "topicTags": [{"name": "Array"}, {"name": "Hash Table"}]
        }
    }
    
    mock_problem_instance = MagicMock()
    mock_problem_instance.title = "Test Problem"
    mock_problem_instance.problem_id = 1
    mock_problem_instance.problem_frontend_id = 1
    mock_problem_instance.difficulty = ProblemDifficulity.EASY.db_repr
    mock_problem_cls.return_value = mock_problem_instance

    mock_topic_tag_array = MagicMock(tag_name="Array")
    mock_topic_tag_hash_table = MagicMock(tag_name="Hash Table")
    mock_topic_tags_cls.side_effect = [mock_topic_tag_array, mock_topic_tag_hash_table]
    
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = mock_data
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await leetcode_api.fetch_daily()
        
        problem = result["problem"]
        tags = result["tags"]
        
        assert problem == mock_problem_instance
        assert problem.title == "Test Problem"
        assert problem.problem_id == 1
        assert problem.difficulty == ProblemDifficulity.EASY.db_repr
        assert len(tags) == 2
        tag_names = {tag.tag_name for tag in tags}
        assert "Array" in tag_names
        assert "Hash Table" in tag_names

@pytest.mark.asyncio
async def test_fetch_daily_fetch_error(leetcode_api):
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_get.return_value.__aenter__.return_value = mock_response

        with pytest.raises(FetchError):
            await leetcode_api.fetch_daily()

@pytest.mark.asyncio
@patch('core.leetcode_api.Problem')
@patch('core.leetcode_api.TopicTags')
async def test_fetch_problem_by_id_success(mock_topic_tags_cls, mock_problem_cls, leetcode_api):
    mock_data = {
        "title": "Two Sum",
        "questionId": "1",
        "questionFrontendId": "1",
        "url": "https://leetcode.com/problems/two-sum",
        "difficulty": "Easy",
        "content": "<p>Sum two numbers</p>",
        "topicTags": [{"name": "Array"}]
    }

    mock_problem_instance = MagicMock()
    mock_problem_instance.title = "Two Sum"
    mock_problem_instance.problem_frontend_id = 1
    mock_problem_instance.difficulty = ProblemDifficulity.EASY.db_repr
    mock_problem_cls.return_value = mock_problem_instance

    mock_topic_tag_array = MagicMock(tag_name="Array")
    mock_topic_tags_cls.return_value = mock_topic_tag_array

    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = mock_data
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await leetcode_api.fetch_problem_by_id(1)
        
        problem = result["problem"]
        assert problem == mock_problem_instance
        assert problem.title == "Two Sum"
        assert problem.problem_frontend_id == 1
        assert problem.difficulty == ProblemDifficulity.EASY.db_repr

@pytest.mark.asyncio
@patch('core.leetcode_api.Problem')
@patch('core.leetcode_api.TopicTags')
async def test_fetch_all_problems_success(mock_topic_tags_cls, mock_problem_cls, leetcode_api):
    mock_data = [
        {
            "data": {
                "question": {
                    "title": "Problem 1",
                    "questionId": "1",
                    "questionFrontendId": "1",
                    "url": "url1",
                    "difficulty": "Easy",
                    "content": "desc1",
                    "topicTags": [{"name": "Tag1"}]
                }
            }
        },
        {
            "data": {
                "question": {
                    "title": "Problem 2",
                    "questionId": "2",
                    "questionFrontendId": "2",
                    "url": "url2",
                    "difficulty": "Medium",
                    "content": "desc2",
                    "topicTags": [{"name": "Tag2"}]
                }
            }
        }
    ]

    mock_problem_instance_1 = MagicMock(problem_frontend_id=1, title="Problem 1", difficulty=ProblemDifficulity.EASY.db_repr)
    mock_problem_instance_2 = MagicMock(problem_frontend_id=2, title="Problem 2", difficulty=ProblemDifficulity.MEDIUM.db_repr)
    mock_problem_cls.side_effect = [mock_problem_instance_1, mock_problem_instance_2]

    mock_topic_tag_1 = MagicMock(tag_name="Tag1")
    mock_topic_tag_2 = MagicMock(tag_name="Tag2")
    mock_topic_tags_cls.side_effect = [mock_topic_tag_1, mock_topic_tag_2]


    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = mock_data
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await leetcode_api.fetch_all_problems()
        
        assert len(result) == 2
        assert 1 in result
        assert 2 in result
        assert result[1]["problem"].title == "Problem 1"
        assert result[2]["problem"].difficulty == ProblemDifficulity.MEDIUM.db_repr

@pytest.mark.asyncio
async def test_user_info_success(leetcode_api):
    mock_data = {"username": "testuser", "ranking": 100}
    
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = mock_data
        mock_get.return_value.__aenter__.return_value = mock_response
        
        info = await leetcode_api.user_info("testuser")
        assert info == mock_data

@pytest.mark.asyncio
async def test_user_submission_success(leetcode_api):
    mock_data = {"submissions": []}
    
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = mock_data
        mock_get.return_value.__aenter__.return_value = mock_response
        
        submissions = await leetcode_api.user_submission("testuser")
        assert submissions == mock_data

