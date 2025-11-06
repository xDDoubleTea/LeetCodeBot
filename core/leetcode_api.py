import re
from typing import Dict, List, Set, Literal, Any

import aiohttp
from bs4 import BeautifulSoup

from config.constants import preview_len
from db.problem import Problem, TopicTags
from models.leetcode import ProblemDifficulity
from config.secrets import debug


class FetchError(Exception):
    pass


class LeetCodeAPI:
    def __init__(self) -> None:
        self._base_url = "https://leetcode-api-pied.vercel.app"
        self._github_url = "https://raw.githubusercontent.com/noworneverev/leetcode-api/refs/heads/main/data/leetcode_questions.json"
        self._github_headers = {
            "content-type": "application/json",
        }

    async def health_check(self) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(url=self._base_url) as response:
                if response.status == 200:
                    return "LeetCode API is healthy."
                else:
                    return "LeetCode API is down."

    def _parse_problem_desc(self, content: str) -> str:
        """
        Parses the problem description from the LeetCode API response.
        """
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
        response_url = response_json.get("link", "")
        response_problem = response_json.get("question", {})
        if debug:
            print(response_url)
            print(response_problem)
        try:
            problem = Problem(
                title=response_problem.get("title", ""),
                problem_id=response_problem.get("questionId", 0),
                url=response_url,
                difficulty=ProblemDifficulity.from_str_repr(
                    response_problem.get("difficulty", "")
                ).db_repr,
                description=self._parse_problem_desc(
                    response_problem.get("content", "")
                ),
            )
            if debug:
                print(problem)
            problem_tags: List[dict] = response_problem.get("topicTags", [])
            tags: Set[TopicTags] = set()
            for tag in problem_tags:
                tag_obj = TopicTags(tag_name=tag.get("name", ""))
                tags.add(tag_obj)
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
        try:
            problem = Problem(
                title=response_json.get("title", ""),
                problem_id=response_json.get("questionId", 0),
                url=response_json.get("url", ""),
                difficulty=ProblemDifficulity.from_str_repr(
                    response_json.get("difficulty", "")
                ).db_repr,
                description=self._parse_problem_desc(response_json.get("content", "")),
            )
            problem_tags: List[dict] = response_json.get("topicTags", [])
            tags: Set[TopicTags] = set()
            for tag in problem_tags:
                tag_obj = TopicTags(tag_name=tag.get("name", ""))
                tags.add(tag_obj)
            return {"problem": problem, "tags": tags}
        except ValueError:
            raise Exception("Invalid difficulty value")

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
        for item in response_json:
            problem_data = item.get("data", {})
            problem_data_question = problem_data.get("question", {})
            if not problem_data or not problem_data_question:
                continue
            try:
                problem = Problem(
                    title=problem_data_question.get("title", ""),
                    problem_id=problem_data_question.get("questionId", 0),
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
                result[problem.problem_id] = {"problem": problem, "tags": cur_tags}

            except ValueError:
                raise Exception("Invalid difficulty value")
        return result

    async def _validate_response(
        self, response: aiohttp.ClientResponse, error_message: str
    ) -> dict:
        if response.status == 200:
            return await response.json(content_type=None)
        else:
            raise FetchError(f"{error_message}: {response.status}")

    async def fetch_all_problems(
        self,
    ) -> Dict[int, Dict[Literal["problem", "tags"], Any]]:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                headers=self._github_headers, url=self._github_url
            ) as response:
                validated_response_json = await self._validate_response(
                    response, "Failed to fetch all problems"
                )
                return await self.parse_all_problem_response(validated_response_json)

    async def fetch_problem_by_id(
        self, id: int
    ) -> Dict[Literal["problem", "tags"], Problem | Set[TopicTags]]:
        async with aiohttp.ClientSession() as session:
            async with session.get(url=f"{self._base_url}/problem/{id}") as response:
                validated_response_json = await self._validate_response(
                    response, f"Failed to fetch problem with ID {id}"
                )
                return await self.parse_single_problem_response(validated_response_json)

    async def fetch_problem_by_slug(
        self, slug: str
    ) -> Dict[Literal["problem", "tags"], Problem | Set[TopicTags]]:
        async with aiohttp.ClientSession() as session:
            async with session.get(url=f"{self._base_url}/problem/{slug}") as response:
                validated_response_json = await self._validate_response(
                    response, f"Failed to fetch problem with slug {slug}"
                )
                return await self.parse_single_problem_response(validated_response_json)

    async def fetch_daily(
        self,
    ) -> Dict[Literal["problem", "tags"], Problem | Set[TopicTags]]:
        async with aiohttp.ClientSession() as session:
            async with session.get(url=f"{self._base_url}/daily") as response:
                validated_response_json = await self._validate_response(
                    response, "Failed to fetch daily problem"
                )
                return await self.parse_daily_problem_response(validated_response_json)

    async def search_problem(self, qry: str):
        pass

    async def user_submission(self, username: str) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url=f"{self._base_url}/user/{username}/submissions"
            ) as response:
                return await self._validate_response(
                    response,
                    f"Failed to fetch user submissions with username {username}",
                )
