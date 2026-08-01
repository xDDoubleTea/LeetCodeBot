import asyncio
import inspect
import random
import logging
from typing import Dict, List, Set
from pathlib import Path

import aiohttp

from db.problem import Problem, TopicTags
from models.leetcode import (
    ProblemDifficulity,
    ProblemWithTags,
    UserInfo,
    UserProfile,
    UserSubmission,
    UserSubmissionStat,
)

logger = logging.getLogger(__name__)


class FetchError(Exception):
    pass


class QueryNotFound(Exception):
    pass


class LeetCodeAPI:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._base_url = "https://leetcode-api-pied.vercel.app"
        self._leetcode_graphql_url = "https://leetcode.com/graphql"
        self.session: aiohttp.ClientSession = session
        self._leetcode_headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Referer": "https://leetcode.com/",
            "Origin": "https://leetcode.com",
        }
        self.delay = 0.3
        self.queries: Dict[str, str] = {}

    def _load_graphql_queries(self):
        current_dir = Path(__file__).parent
        graphql_dir = current_dir.parent / "graphql"
        if not graphql_dir.exists():
            raise FileNotFoundError(f"Directory not found: {graphql_dir}")

        for filepath in graphql_dir.glob("*.graphql"):
            logger.debug(f"Loading file {filepath}")
            query_name = filepath.stem
            with open(filepath, "r", encoding="utf-8") as f:
                self.queries[query_name] = f.read()
                logger.debug(f"Query loaded {query_name} : {self.queries[query_name]}")

        logger.debug(f"All loaded graphql queries:\n {self.queries}")

    async def reload_graphql_queries(self):
        self.queries.clear()
        self._load_graphql_queries()

    async def _parse_recent_submission_list(
        self, raw_list: List[dict]
    ) -> List[UserSubmission]:
        return [
            UserSubmission(
                title=raw_submission.get("title", ""),
                title_slug=raw_submission.get("titleSlug", ""),
                timestamp=raw_submission.get("timestamp", ""),
                status_display=raw_submission.get("statusDisplay", ""),
                lang_name=raw_submission.get("langName", ""),
                runtime=raw_submission.get("runtime", ""),
                is_pending=raw_submission.get("isPending", False),
                memory=raw_submission.get("memory", ""),
                frontend_id=raw_submission.get("frontendId", 0),
                url=f"https://leetcode.com/{raw_submission.get('url', '')}",
            )
            for raw_submission in raw_list
        ]

    async def _parse_user_submission_stat(self, raw_json: dict) -> UserSubmissionStat:
        ac_submission_num = raw_json.get("acSubmissionNum", [])
        ac_submission_count = 0
        total_submissions_and_ac_count = 0
        logger.debug(ac_submission_num)
        for item in ac_submission_num:
            if item.get("difficulty", "").lower() == "all":
                ac_submission_count = item["count"]
                total_submissions_and_ac_count = item["submissions"]
                break

        return UserSubmissionStat(
            difficulity="All",
            ac_submission_count=ac_submission_count,
            total_submissions_and_ac_count=total_submissions_and_ac_count,
        )
        pass

    async def _parse_user_profile(self, raw_json: dict) -> UserProfile:
        logger.debug(raw_json.get("websites"))
        return UserProfile(
            user_avatar=raw_json.get("userAvatar", ""),
            country_name=raw_json.get("countryName", ""),
            about_me=raw_json.get("aboutMe", ""),
            company=raw_json.get("company", ""),
            job_title=raw_json.get("jobTitle", ""),
            school=raw_json.get("school", ""),
            websites=raw_json.get("websites", []),
        )

    async def _parse_user_info(self, raw_json: dict) -> UserInfo:
        logger.debug(raw_json)

        user_profile_json = raw_json.get("profile", {})
        user_profile = await self._parse_user_profile(user_profile_json)
        user_submission_stat = await self._parse_user_submission_stat(
            raw_json=raw_json.get("submitStats", {})
        )

        return UserInfo(
            user_name=raw_json.get("username", ""),
            github_url=raw_json.get("githubUrl", ""),
            twitter_url=raw_json.get("twitterUrl", ""),
            linkedin_url=raw_json.get("linkedinUrl", ""),
            user_profile=user_profile,
            ac_submission=user_submission_stat,
        )
        pass

    async def health_check(self) -> str:
        payload = {"query": "query { __typename }"}

        try:
            async with self.session.post(
                url=self._leetcode_graphql_url,
                json=payload,
                headers=self._leetcode_headers,
                timeout=aiohttp.ClientTimeout(10),
            ) as response:
                logger.info(f"LeetCode API Health Check Status: {response.status}")
                if response.status == 200:
                    return f"LeetCode API is {'||never gonna give you||' if random.randint(0, 100) % 2 == 0 else ''} up."
                else:
                    return f"LeetCode API is down. Status: {response.status}"
        except Exception as e:
            logger.error(f"LeetCode API Health check failed: {e}")
        return "LeetCode API is unreachable."

    async def _parse_single_problem_response(
        self, response_json: dict
    ) -> ProblemWithTags:
        """
        Parses the problem response from the LeetCode API and returns a Problem object.
        Not that Expensive, but don't use it too often, especially in loops.
        """
        logger.debug("Parsing single problem response")
        try:
            logger.debug("Single Problem Response: %s", response_json)
            problem = Problem(
                title=response_json.get("title", ""),
                problem_id=int(response_json.get("questionId", 0)),
                problem_frontend_id=int(response_json.get("questionFrontendId", 0)),
                url=response_json.get("url", ""),
                difficulty=ProblemDifficulity.from_str_repr(
                    response_json.get("difficulty", "")
                ).db_repr,
                description=response_json.get("content", ""),
                premium=response_json.get("isPaidOnly", False),
            )
            logger.debug("Parsed Single Problem: %s", problem)
            problem_tags: List[dict] = response_json.get("topicTags", [])
            tags: Set[TopicTags] = set(
                TopicTags(tag_name=tag.get("name", "")) for tag in problem_tags
            )
            logger.debug("Parsed Single Problem Tags: %s", tags)
            return ProblemWithTags(problem, tags)
        except ValueError:
            raise Exception("Invalid difficulty value")
        except Exception as e:
            logger.error("Error parsing single problem response: %s", e)
            raise Exception("Error parsing single problem response") from e

    async def _parse_daily_problem_response(
        self, response_json: dict
    ) -> ProblemWithTags:
        logger.info("Parsing daily problem response")
        logger.debug(f"Daily Problem Response {response_json}", response_json)
        # The https://leetcode-api-pied.vercel.app returns different formats for daily problems and single problems, which is weird but we have to deal with it unless we interact directly with leetcode graphql API.
        response_url = response_json.get("link", "")
        response_problem = response_json.get("question", {})
        try:
            assert isinstance(response_problem, dict)
            response_problem["url"] = response_url
            logger.debug(f"Raw daily problem: {response_problem}")
            problem_with_tags = await self._parse_single_problem_response(
                response_problem
            )
            logger.debug(f"Parsed Daily Problem: {problem_with_tags.problem}")
            logger.debug(f"Parsed Daily Problem Tags: {problem_with_tags.tags}")
            return problem_with_tags
        except AssertionError:
            raise Exception("Raw problem object is not a dictionary")
        except Exception as e:
            logger.error("Error parsing daily problem response: %s", e)
            raise Exception("Error parsing daily problem response") from e

    async def _parse_all_problem_dict(
        self, temp_questions: Dict[int, dict]
    ) -> Dict[int, ProblemWithTags]:
        logger.info("Parsing dictionary of all problems")
        return {
            key: await self._parse_single_problem_response(val)
            for key, val in temp_questions.items()
        }

    async def _validate_response(
        self, response: aiohttp.ClientResponse, error_message: str
    ) -> dict:
        if response.status == 200:
            logger.debug("Response validated successfully")
            return await response.json()
        else:
            logger.error("%s: Received status code %s", error_message, response.status)
            raise FetchError(f"{error_message}: {response.status}")

    async def fetch_all_problems(
        self,
    ) -> Dict[int, ProblemWithTags]:
        logger.info("Fetching all problems from LeetCode")

        cur_frame = inspect.currentframe()
        assert cur_frame is not None
        method_name = cur_frame.f_code.co_name
        query = self.queries.get(method_name, "")
        if not query:
            raise QueryNotFound(f"Query not found for method: {method_name}")
        limit_per_req = 100

        skip = 0
        total_questions = -1
        temp_questions: Dict[int, dict] = {}

        while True:
            try:
                variables = {
                    "categorySlug": "",
                    "limit": limit_per_req,
                    "skip": skip,
                    "filters": {},
                }
                response = await self.session.post(
                    headers=self._leetcode_headers,
                    url=self._leetcode_graphql_url,
                    json={"query": query, "variables": variables},
                )
                validated_response_json = await self._validate_response(
                    response, "Failed to fetch all problems"
                )
                res_list = validated_response_json["data"]["problemsetQuestionList"]
                questions_batch = res_list["questions"]
                total_questions = res_list["total"]

                if not questions_batch:
                    break

                for q in questions_batch:
                    q["url"] = f"https://leetcode.com/problems/{q['titleSlug']}"
                    temp_questions[int(q["questionId"])] = q

                logger.debug(
                    f"Fetched questions : {len(temp_questions)} / {total_questions}"
                )
                logger.debug("Question batch: %s", questions_batch)
                skip += limit_per_req
                if len(temp_questions) >= total_questions:
                    break

                await asyncio.sleep(self.delay)
            except Exception as e:
                logger.error(f"Error at skip {skip}", exc_info=e)
                raise FetchError(e)

        logger.info("Fetched all problems successfully")
        return await self._parse_all_problem_dict(temp_questions)

    async def fetch_daily(
        self,
    ) -> ProblemWithTags:
        logger.info("Fetching daily problem")

        cur_frame = inspect.currentframe()
        assert cur_frame is not None
        method_name = cur_frame.f_code.co_name
        query = self.queries.get(method_name, "")
        if not query:
            raise QueryNotFound(f"Query not found for method: {method_name}")

        response = await self.session.post(
            url=self._leetcode_graphql_url, json={"query": query}
        )

        validated_response_json = await self._validate_response(
            response, "Failed to fetch daily problem"
        )
        logger.info("Fetched daily problem successfully")
        logger.debug("Daily Problem JSON: %s", validated_response_json)
        return await self._parse_daily_problem_response(
            validated_response_json["data"]["activeDailyCodingChallengeQuestion"]
        )

    async def search_problem(self, qry: str):
        pass

    async def user_info(self, username: str) -> UserInfo:
        logger.info(f"Fetching user info for username {username}")

        cur_frame = inspect.currentframe()
        assert cur_frame is not None
        method_name = cur_frame.f_code.co_name
        query = self.queries.get(method_name, "")
        if not query:
            raise QueryNotFound(f"Query not found for method: {method_name}")

        response = await self.session.post(
            url=self._leetcode_graphql_url,
            json={"query": query, "variables": {"username": username}},
        )
        logger.info(f"Fetched user info for username {username} successfully")
        validated_response_json = await self._validate_response(
            response,
            f"Failed to fetch user info with username {username}",
        )
        return await self._parse_user_info(
            validated_response_json["data"]["matchedUser"]
        )

    async def user_submission(
        self, username: str, limit: int = 20
    ) -> List[UserSubmission]:
        logger.info(f"Fetching user submissions for username {username}")

        cur_frame = inspect.currentframe()
        assert cur_frame is not None
        method_name = cur_frame.f_code.co_name
        query = self.queries.get(method_name, "")
        if not query:
            raise QueryNotFound(f"Query not found for method: {method_name}")

        limit = min(limit, 100)
        limit = max(limit, 1)

        response = await self.session.post(
            url=self._leetcode_graphql_url,
            json={"query": query, "variables": {"username": username, "limit": limit}},
        )
        logger.info(f"Fetched user submissions for username {username} successfully")
        validated_response_json = await self._validate_response(
            response,
            f"Failed to fetch user submissions with username {username}",
        )
        logger.debug(f"user submission {validated_response_json}")

        return await self._parse_recent_submission_list(
            validated_response_json["data"]["recentSubmissionList"]
        )
