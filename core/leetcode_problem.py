from core.leetcode_api import LeetCodeAPI
from db.database_manager import DatabaseManager
from db.problem import Problem, TopicTags, problem_tags_association
from typing import Dict, Literal, Set, Sequence
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from config.secrets import debug
from sqlalchemy.dialects.sqlite import insert as sqlite_upsert


class ProblemNotFound(Exception):
    pass


class LeetCodeProblemManager:
    def __init__(
        self, leetcode_api: LeetCodeAPI, database_manager: DatabaseManager
    ) -> None:
        self.problem_cache: Dict[int, Problem] = dict()
        self.leetcode_api: LeetCodeAPI = leetcode_api
        self.database_mananger: DatabaseManager = database_manager

    async def _bulk_upsert_problems(self, api_problems: Dict[int, Problem]) -> None:
        with self.database_mananger as db:
            mappings = [problem.to_dict() for problem in api_problems.values()]
            insert_stmt = sqlite_upsert(Problem)
            insert_stmt = insert_stmt.on_conflict_do_update(
                index_elements=["problem_id"],
                set_={
                    "title": insert_stmt.excluded.title,
                    "url": insert_stmt.excluded.url,
                    "difficulty": insert_stmt.excluded.difficulty,
                    "description": insert_stmt.excluded.description,
                },
            )
            db.execute(insert_stmt, mappings)

    async def _bulk_upsert_topic_tags(self, topic_tags: Set[TopicTags]) -> None:
        with self.database_mananger as db:
            insert_stmt = sqlite_upsert(TopicTags)
            mappings = [tag.to_dict() for tag in topic_tags]
            insert_stmt = insert_stmt.on_conflict_do_nothing(
                index_elements=["tag_name"],
            )
            db.execute(insert_stmt, mappings)

    async def _create_problem_tag_associations(
        self,
        all_api_problems_data: Dict[
            int, Dict[Literal["problem", "tags"], Problem | Set[TopicTags]]
        ],
    ) -> None:
        """Correctly creates associations based on the API data."""
        with self.database_mananger as db:
            db_problems = {p.problem_id: p.id for p in db.query(Problem).all()}
            db_tags = {t.tag_name: t.id for t in db.query(TopicTags).all()}
            associations = []
            print(db_problems)
            for data in all_api_problems_data.values():
                assert isinstance(data["problem"], Problem)
                problem_db_id = db_problems[int(data["problem"].problem_id)]
                print(problem_db_id)
                if not problem_db_id:
                    raise Exception(
                        f"Problem ID {data['problem'].problem_id} not found in DB."
                    )
                assert isinstance(data["tags"], set)
                for tag in data["tags"]:
                    tag_db_id = db_tags.get(tag.tag_name)
                    if not tag_db_id:
                        raise Exception(f"Tag {tag.tag_name} not found in DB.")

                    associations.append(
                        {"problem_id": problem_db_id, "tag_id": tag_db_id}
                    )
            if debug:
                print(f"Creating {len(associations)} problem-tag associations.")
            if associations:
                # First, clear all existing associations to ensure a clean slate
                db.execute(problem_tags_association.delete())

                # Use the imported problem_tags_association Table object
                insert_stmt = sqlite_upsert(
                    problem_tags_association
                ).on_conflict_do_nothing(index_elements=["problem_id", "tag_id"])
                db.execute(insert_stmt, associations)
            db.commit()

    async def init_cache(self):
        """
        Initializes the problem cache from the local database.
        Very Expensive! Use it only once at startup.
        """
        try:
            problems = await self.get_problems_from_db()
            print(f"Loaded {len(problems)} problems from the database into cache.")
            self.problem_cache = {problem.problem_id: problem for problem in problems}
        except Exception as e:
            raise Exception(f"Failed to initialize cache: {e}")

    async def refresh_cache(self):
        """
        Fetches all problems from LeetCode and updates the local database and cache.
        Expensive! Use it once a day or less frequently.
        """
        try:
            api_problems = await self.leetcode_api.fetch_all_problems()
            all_problems: Dict[int, Problem] = {
                problem_id: problem["problem"]
                for problem_id, problem in api_problems.items()
            }
            all_problem_tags: Dict[int, Set[TopicTags]] = {
                problem_id: problem["tags"]
                for problem_id, problem in api_problems.items()
            }
            await self._bulk_upsert_problems(all_problems)
            all_topic_tags: Set[TopicTags] = set()
            for tags in all_problem_tags.values():
                all_topic_tags.update(tags)

            await self._bulk_upsert_topic_tags(all_topic_tags)
            await self._create_problem_tag_associations(api_problems)
            await self.init_cache()
        except Exception as e:
            raise Exception(e)

    async def get_problems_from_db(self) -> Sequence[Problem]:
        with self.database_mananger as db:
            stmt = select(Problem).options(selectinload(Problem.tags))
            results = db.execute(stmt).scalars().all()
            return results

    async def get_all_topics_from_db(self) -> Dict[int, TopicTags]:
        with self.database_mananger as db:
            stmt = select(TopicTags)
            all_topics = db.execute(stmt).scalars().all()
            return {topic.id: topic for topic in all_topics}

    async def get_problem_from_db(self, problem_id: int) -> Problem | None:
        with self.database_mananger as db:
            stmt = (
                select(Problem)
                .where(Problem.problem_id == problem_id)
                .options(selectinload(Problem.tags))
            )
            problem = db.execute(stmt).scalars().first()
            return problem

    async def get_problem(
        self, problem_id: int
    ) -> Dict[Literal["problem", "tags"], Problem | Set[TopicTags]] | None:
        """
        Retrieves a problem by its ID from the cache or fetches it from LeetCode if not present.
        """
        if problem_in_cache := self.problem_cache.get(problem_id, None):
            return {"problem": problem_in_cache, "tags": set(problem_in_cache.tags)}
        try:
            problem = await self.get_problem_from_db(problem_id=problem_id)
            if problem:
                self.problem_cache[problem_id] = problem
                return {"problem": problem, "tags": set(problem.tags)}

            problem_data = await self.leetcode_api.fetch_problem_by_id(problem_id)
            if not problem_data:
                raise ProblemNotFound(f"Problem with ID {problem_id} not found.")
            problem = problem_data["problem"]
            tags = problem_data["tags"]
            assert isinstance(tags, set) and isinstance(problem, Problem)
            problem = await self.add_problem_to_db(problem, tags)
            self.problem_cache[problem_id] = problem
            return {"problem": problem, "tags": set(problem.tags)}
        except Exception as e:
            raise Exception(e)

    async def get_daily_problem(
        self,
    ) -> Dict[Literal["problem", "tags"], Problem | Set[TopicTags]] | None:
        """
        Retrieves the daily problem from LeetCode.
        """
        try:
            problem_data = await self.leetcode_api.fetch_daily()
            if not problem_data:
                raise ProblemNotFound("Daily problem not found.")
            problem = problem_data["problem"]
            tags = problem_data["tags"]
            assert isinstance(tags, set) and isinstance(problem, Problem)
            if problem.problem_id in self.problem_cache.keys():
                return {
                    "problem": self.problem_cache[problem.problem_id],
                    "tags": set(self.problem_cache[problem.problem_id].tags),
                }
            if db_problem := await self.get_problem_from_db(problem.problem_id):
                self.problem_cache[problem.problem_id] = db_problem
                return {"problem": db_problem, "tags": set(db_problem.tags)}

            new_problem = await self.add_problem_to_db(problem, tags)

            self.problem_cache[problem.problem_id] = new_problem
            return {
                "problem": new_problem,
                "tags": set(new_problem.tags),
            }

        except Exception as e:
            raise Exception(e)

    async def add_problem_to_db(
        self, problem: Problem, tags: Set[TopicTags]
    ) -> Problem:
        with self.database_mananger as db:
            # Check for existing problem
            db_problem = (
                db.query(Problem).filter_by(problem_id=problem.problem_id).first()
            )
            if not db_problem:
                db.add(problem)
                db.flush()  # Flush to get problem.id
                db_problem = problem

            # Handle tags
            for tag in tags:
                db_tag = db.query(TopicTags).filter_by(tag_name=tag.tag_name).first()
                if not db_tag:
                    db.add(tag)
                    db.flush()  # Flush to get tag.id
                    db_tag = tag

                if db_tag not in db_problem.tags:
                    db_problem.tags.append(db_tag)

            db.commit()
            db.refresh(db_problem, attribute_names=["tags"])
            return db_problem
