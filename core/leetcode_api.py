import re
from typing import Dict, List, Set, Literal, Any

import aiohttp
from bs4 import BeautifulSoup

from config.constants import preview_len
from db.problem import Problem, TopicTags
from models.leetcode import ProblemDifficulity
import logging


class FetchError(Exception):
    pass


class LeetCodeAPI:
    def __init__(self, logger: logging.Logger) -> None:
        self._base_url = "https://leetcode-api-pied.vercel.app"
        self._github_url = "https://raw.githubusercontent.com/noworneverev/leetcode-api/refs/heads/main/data/leetcode_questions.json"
        self._github_headers = {
            "content-type": "application/json",
        }
        self.logger = logger

    async def health_check(self) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(url=self._base_url) as response:
                self.logger.info(f"LeetCode API Health Check Status: {response.status}")
                if response.status == 200:
                    return "LeetCode API is healthy."
                else:
                    return "LeetCode API is down."

    def _parse_problem_desc(self, content: str) -> str:
        """
        Parses the problem description from the LeetCode API response.
        """
        self.logger.debug("Parsing problem description")
        if not content:
            return "No description available."
        soup = BeautifulSoup(content, "html.parser")

        for tag in soup.find_all("sup"):
            tag.string = f"^{tag.get_text()}"
        for tag in soup.find_all("code"):
            tag.string = f"`{tag.get_text()}`"
        for tag in soup.find_all("em"):
            tag.string = f"*{tag.get_text()}*"
        for tag in soup.find_all("strong"):
            tag.string = f"**{tag.get_text()}**"

        text_only = soup.get_text()
        problem_md = re.sub(r"\n\s*\n", "\n\n", text_only.strip())[:preview_len]
        if len(text_only.strip()) > preview_len:
            problem_md += "..."
        return problem_md

    async def parse_daily_problem_response(
        self, response_json: dict
    ) -> Dict[Literal["problem", "tags"], Problem | Set[TopicTags]]:
        self.logger.info("Parsing daily problem response")
        self.logger.debug("Daily Problem Response: %s", response_json)
        response_url = response_json.get("link", "")
        response_problem = response_json.get("question", {})
        self.logger.debug("Parsed Problem Data: %s", response_problem)
        try:
            problem = Problem(
                title=response_problem.get("title", ""),
                problem_id=response_problem.get("questionId", 0),
                problem_frontend_id=response_problem.get("questionFrontendId", 0),
                url=response_url,
                difficulty=ProblemDifficulity.from_str_repr(
                    response_problem.get("difficulty", "")
                ).db_repr,
                description=self._parse_problem_desc(
                    response_problem.get("content", "")
                ),
            )
            self.logger.debug("Parsed Daily Problem: %s", problem)
            problem_tags: List[dict] = response_problem.get("topicTags", [])
            tags: Set[TopicTags] = set()
            for tag in problem_tags:
                tag_obj = TopicTags(tag_name=tag.get("name", ""))
                tags.add(tag_obj)
            self.logger.debug("Parsed Daily Problem Tags: %s", tags)
            return {"problem": problem, "tags": tags}
        except ValueError:
            raise Exception("Invalid difficulty value")

    async def parse_single_problem_response(
        self, response_json: dict
    ) -> Dict[Literal["problem", "tags"], Problem | Set[TopicTags]]:
        """
        Parses the problem response from the LeetCode API and returns a Problem object.
        Not that Expensive, but don't use it too often, especially in loops.
        """
        self.logger.info("Parsing single problem response")
        try:
            self.logger.debug("Single Problem Response: %s", response_json)
            problem = Problem(
                title=response_json.get("title", ""),
                problem_id=int(response_json.get("questionId", 0)),
                problem_frontend_id=int(response_json.get("questionFrontendId", 0)),
                url=response_json.get("url", ""),
                difficulty=ProblemDifficulity.from_str_repr(
                    response_json.get("difficulty", "")
                ).db_repr,
                description=self._parse_problem_desc(response_json.get("content", "")),
            )
            self.logger.debug("Parsed Single Problem: %s", problem)
            problem_tags: List[dict] = response_json.get("topicTags", [])
            tags: Set[TopicTags] = set()
            for tag in problem_tags:
                tag_obj = TopicTags(tag_name=tag.get("name", ""))
                tags.add(tag_obj)
            self.logger.debug("Parsed Single Problem Tags: %s", tags)
            return {"problem": problem, "tags": tags}
        except ValueError:
            raise Exception("Invalid difficulty value")
        except Exception as e:
            self.logger.error("Error parsing single problem response: %s", e)
            raise Exception("Error parsing single problem response") from e

    async def parse_all_problem_response(
        self, response_json: dict
    ) -> Dict[int, Dict[Literal["problem", "tags"], Problem | Set[TopicTags]]]:
        """
        Parses the problem response from the LeetCode API and returns a mapping of problem IDs to a dictionary.
        The dictionary contains the Problem object and its set of TopicTags, with key being the problem_id.
        Very Expensive!
        """
        result: Dict[
            int, Dict[Literal["problem", "tags"], Problem | Set[TopicTags]]
        ] = {}
        tags: Set[TopicTags] = set()
        self.logger.debug("All Problems Response: %s", response_json)
        self.logger.info("Parsing all problem responses")
        for item in response_json:
            problem_data = item.get("data", {})
            problem_data_question = problem_data.get("question", {})
            if not problem_data or not problem_data_question:
                continue
            try:
                problem = Problem(
                    title=problem_data_question.get("title", ""),
                    problem_id=int(problem_data_question.get("questionId", 0)),
                    problem_frontend_id=int(
                        problem_data_question.get("questionFrontendId", 0)
                    ),
                    url=problem_data_question.get("url", ""),
                    difficulty=ProblemDifficulity.from_str_repr(
                        problem_data_question.get("difficulty", "")
                    ).db_repr,
                    description=self._parse_problem_desc(
                        problem_data_question.get("content", "")
                    ),
                )
                problem_tags: List[dict] = problem_data_question.get("topicTags", [])
                cur_tags: Set[TopicTags] = set()
                for tag in problem_tags:
                    tag_obj = TopicTags(tag_name=tag.get("name", ""))
                    tags.add(tag_obj)
                    cur_tags.add(tag_obj)
                result[problem.problem_frontend_id] = {
                    "problem": problem,
                    "tags": cur_tags,
                }

            except ValueError:
                self.logger.error(
                    "Invalid difficulty value for problem ID %s",
                    problem_data_question.get("questionId", 0),
                )
                raise Exception("Invalid difficulty value")
            except Exception as e:
                self.logger.error(
                    "Error parsing problem ID %s: %s",
                    problem_data_question.get("questionId", 0),
                    e,
                )
                raise Exception("Error parsing all problem response") from e
        self.logger.debug("Parsed All Problems: %s", result)
        return result

    async def _validate_response(
        self, response: aiohttp.ClientResponse, error_message: str
    ) -> dict:
        if response.status == 200:
            self.logger.debug("Response validated successfully")
            return await response.json(content_type=None)
        else:
            self.logger.error(
                "%s: Received status code %s", error_message, response.status
            )
            raise FetchError(f"{error_message}: {response.status}")

    async def fetch_all_problems(
        self,
    ) -> Dict[int, Dict[Literal["problem", "tags"], Any]]:
        self.logger.info("Fetching all problems from GitHub")
        async with aiohttp.ClientSession() as session:
            async with session.get(
                headers=self._github_headers, url=self._github_url
            ) as response:
                validated_response_json = await self._validate_response(
                    response, "Failed to fetch all problems"
                )
                self.logger.info("Fetched all problems successfully")
                self.logger.debug("All Problems JSON: %s", validated_response_json)
                return await self.parse_all_problem_response(validated_response_json)

    async def fetch_problem_by_id(
        self, id: int
    ) -> Dict[Literal["problem", "tags"], Problem | Set[TopicTags]]:
        self.logger.info(f"Fetching problem with ID {id}")
        async with aiohttp.ClientSession() as session:
            async with session.get(url=f"{self._base_url}/problem/{id}") as response:
                validated_response_json = await self._validate_response(
                    response, f"Failed to fetch problem with ID {id}"
                )
                self.logger.info(f"Fetched problem with ID {id} successfully")
                self.logger.debug(
                    f"Problem with ID {id} JSON: %s", validated_response_json
                )
                return await self.parse_single_problem_response(validated_response_json)

    async def fetch_problem_by_slug(
        self, slug: str
    ) -> Dict[Literal["problem", "tags"], Problem | Set[TopicTags]]:
        self.logger.info(f"Fetching problem with slug {slug}")
        async with aiohttp.ClientSession() as session:
            async with session.get(url=f"{self._base_url}/problem/{slug}") as response:
                validated_response_json = await self._validate_response(
                    response, f"Failed to fetch problem with slug {slug}"
                )
                self.logger.info(f"Fetched problem with slug {slug} successfully")
                self.logger.debug(
                    f"Problem with slug {slug} JSON: %s", validated_response_json
                )
                return await self.parse_single_problem_response(validated_response_json)

    async def fetch_daily(
        self,
    ) -> Dict[Literal["problem", "tags"], Problem | Set[TopicTags]]:
        self.logger.info("Fetching daily problem")
        async with aiohttp.ClientSession() as session:
            async with session.get(url=f"{self._base_url}/daily") as response:
                validated_response_json = await self._validate_response(
                    response, "Failed to fetch daily problem"
                )
                self.logger.info("Fetched daily problem successfully")
                self.logger.debug("Daily Problem JSON: %s", validated_response_json)
                return await self.parse_daily_problem_response(validated_response_json)

    async def search_problem(self, qry: str):
        pass

    async def user_info(self, username: str) -> dict:
        self.logger.info(f"Fetching user info for username {username}")
        async with aiohttp.ClientSession() as session:
            async with session.get(url=f"{self._base_url}/user/{username}") as response:
                self.logger.info(
                    f"Fetched user info for username {username} successfully"
                )
                return await self._validate_response(
                    response,
                    f"Failed to fetch user info with username {username}",
                )

    async def user_submission(self, username: str) -> dict:
        self.logger.info(f"Fetching user submissions for username {username}")
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url=f"{self._base_url}/user/{username}/submissions"
            ) as response:
                self.logger.info(
                    f"Fetched user submissions for username {username} successfully"
                )
                return await self._validate_response(
                    response,
                    f"Failed to fetch user submissions with username {username}",
                )
