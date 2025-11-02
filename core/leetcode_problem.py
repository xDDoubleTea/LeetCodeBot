from core.leetcode_api import LeetCodeAPI
from db.database_manager import DatabaseManager
from db.problem import Problem, ProblemTags, TopicTags
from typing import Dict, Set
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError


class LeetCodeProblemManager:
    def __init__(
        self, leetcode_api: LeetCodeAPI, database_manager: DatabaseManager
    ) -> None:
        self.problem_cache: Dict[int, Dict[str, Problem | Set[TopicTags]]] = dict()
        self.leetcode_api: LeetCodeAPI = leetcode_api
        self.database_mananger: DatabaseManager = database_manager

    async def init_cache(self):
        """
        Initializes the problem cache from the local database.
        Very Expensive! Use it only once at startup.
        """
        try:
            problems = await self.get_problems_from_db()
            print(f"Loaded {len(problems)} problems from the database into cache.")
            for problem in problems:
                self.problem_cache[problem.problem_id] = {
                    "problem": problem,
                    "tags": set(await self.get_problem_tags_from_db(problem.id)),
                }
                problem_tags = self.problem_cache[problem.problem_id]["tags"]
                assert isinstance(problem_tags, set)
                await self.add_problem_to_db(problem, problem_tags)
        except Exception as e:
            raise Exception(e)

    async def refresh_cache(self):
        """
        Fetches all problems from LeetCode and updates the local database and cache.
        Expensive! Use it once a day or less frequently.
        """
        try:
            problems = await self.leetcode_api.fetch_all_problems()
            for problem_id, problem in problems.items():
                try:
                    assert isinstance(problem["tags"], set) and isinstance(
                        problem["problem"], Problem
                    )
                    await self.add_problem_to_db(problem["problem"], problem["tags"])
                except IntegrityError:
                    print("Problem already exists in the database.")
                    continue
                self.problem_cache[problem_id] = problem
        except Exception as e:
            raise Exception(e)

    async def get_problems_from_db(self):
        with self.database_mananger as db:
            stmt = select(Problem)
            results = db.execute(stmt).scalars().all()
            return results

    async def get_problem_tags_from_db(self, problem_id: int):
        with self.database_mananger as db:
            stmt = select(ProblemTags).where(ProblemTags.problem_id == problem_id)
            problem_tag_with_id = db.execute(stmt).scalars().all()
            results = []
            for pt in problem_tag_with_id:
                tag_stmt = select(TopicTags).where(TopicTags.id == pt.tag_id)
                tag = db.execute(tag_stmt).scalar_one()
                results.append(tag)

            return results

    async def get_problem_from_db(self, problem_id: int) -> Problem | None:
        with self.database_mananger as db:
            stmt = select(Problem).where(Problem.problem_id == problem_id)
            problem = db.execute(stmt).scalars().first()
            return problem

    async def get_problem(
        self, problem_id: int
    ) -> Dict[str, Problem | Set[TopicTags]] | None:
        """
        Retrieves a problem by its ID from the cache or fetches it from LeetCode if not present.
        """
        result = self.problem_cache.get(problem_id, None)
        if not result:
            try:
                problem = await self.get_problem_from_db(problem_id)
                if problem:
                    tags = set(await self.get_problem_tags_from_db(problem.id))
                    result = {"problem": problem, "tags": tags}
                    self.problem_cache[problem_id] = result
                    return result

                problem_data = await self.leetcode_api.fetch_problem_by_id(problem_id)
                if not problem_data:
                    return None
                problem = problem_data["problem"]
                tags = problem_data["tags"]
                assert isinstance(tags, set) and isinstance(problem, Problem)
                await self.add_problem_to_db(problem, tags)
                result = {"problem": problem, "tags": tags}
                self.problem_cache[problem_id] = result
            except Exception as e:
                raise Exception(e)
        return result

    async def get_daily_problem(self) -> Dict[str, Problem | Set[TopicTags]] | None:
        """
        Retrieves the daily problem from LeetCode.
        """
        try:
            problem_data = await self.leetcode_api.fetch_daily()
            if not problem_data:
                return None
            problem = problem_data["problem"]
            tags = problem_data["tags"]
            assert isinstance(tags, set) and isinstance(problem, Problem)
            if problem_db := await self.get_problem(problem.problem_id):
                print(problem_db)
                return problem_db
            await self.add_problem_to_db(problem, tags)

            result = {"problem": problem, "tags": tags}
            self.problem_cache[problem.problem_id] = result
            return result
        except Exception as e:
            raise Exception(e)

    async def add_problem_to_db(self, problem: Problem, tags: Set[TopicTags]) -> None:
        with self.database_mananger as db:
            try:
                db.add(problem)
                db.flush()  # Ensure problem.id is populated
            except IntegrityError:
                db.rollback()
                existing_problem = (
                    db.query(Problem)
                    .filter(Problem.problem_id == problem.problem_id)
                    .first()
                )
                if existing_problem:
                    problem = existing_problem
                db.flush()
            for tag in tags:
                existing_tag = (
                    db.query(TopicTags)
                    .filter(TopicTags.tag_name == tag.tag_name)
                    .first()
                )
                if not existing_tag:
                    db.add(tag)
                    db.flush()  # Ensure tag.id is populated
                    existing_tag = tag
                problem_tag = ProblemTags(problem_id=problem.id, tag_id=existing_tag.id)
                db.add(problem_tag)
