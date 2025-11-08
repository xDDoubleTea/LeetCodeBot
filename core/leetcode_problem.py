import logging
from core.leetcode_api import LeetCodeAPI
from db.database_manager import DatabaseManager
from db.problem import Problem, TopicTags, problem_tags_association
from typing import Dict, Literal, Set, Sequence
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.dialects.sqlite import insert as sqlite_upsert


class ProblemNotFound(Exception):
    pass


class LeetCodeProblemManager:
    def __init__(
        self,
        leetcode_api: LeetCodeAPI,
        database_manager: DatabaseManager,
        logger: logging.Logger,
    ) -> None:
        self.problem_cache: Dict[int, Problem] = dict()
        self.leetcode_api: LeetCodeAPI = leetcode_api
        self.database_mananger: DatabaseManager = database_manager
        self.logger: logging.Logger = logger

    async def _bulk_upsert_problems(self, api_problems: Dict[int, Problem]) -> None:
        with self.database_mananger as db:
            self.logger.info(
                f"Upserting {len(api_problems)} problems into the database."
            )
            mappings = [problem.to_dict() for problem in api_problems.values()]
            self.logger.debug(f"Problem mappings: {mappings[:2]} ...")
            insert_stmt = sqlite_upsert(Problem)
            insert_stmt = insert_stmt.on_conflict_do_update(
                index_elements=["problem_id"],
                set_={
                    "title": insert_stmt.excluded.title,
                    "url": insert_stmt.excluded.url,
                    "difficulty": insert_stmt.excluded.difficulty,
                    "description": insert_stmt.excluded.description,
                    "problem_frontend_id": insert_stmt.excluded.problem_frontend_id,
                },
            )
            db.execute(insert_stmt, mappings)
            self.logger.info("Bulk upsert of problems completed.")

    async def _bulk_upsert_topic_tags(self, topic_tags: Set[TopicTags]) -> None:
        with self.database_mananger as db:
            self.logger.info(
                f"Upserting {len(topic_tags)} topic tags into the database."
            )
            insert_stmt = sqlite_upsert(TopicTags)
            mappings = [tag.to_dict() for tag in topic_tags]
            self.logger.debug(f"Topic tag mappings: {mappings[:2]} ...")
            insert_stmt = insert_stmt.on_conflict_do_nothing(
                index_elements=["tag_name"],
            )
            db.execute(insert_stmt, mappings)
            self.logger.info("Bulk upsert of topic tags completed.")

    async def _create_problem_tag_associations(
        self,
        all_api_problems_data: Dict[
            int, Dict[Literal["problem", "tags"], Problem | Set[TopicTags]]
        ],
    ) -> None:
        """Correctly creates associations based on the API data."""
        with self.database_mananger as db:
            self.logger.info("Creating problem-tag associations.")
            db_problems = {p.problem_frontend_id: p.id for p in db.query(Problem).all()}
            db_tags = {t.tag_name: t.id for t in db.query(TopicTags).all()}
            self.logger.debug(f"DB Problems: {list(db_problems.items())[:2]} ...")
            self.logger.debug(f"DB Tags: {list(db_tags.items())[:2]} ...")
            associations = []
            for data in all_api_problems_data.values():
                assert isinstance(data["problem"], Problem)
                problem_db_id = db_problems[int(data["problem"].problem_frontend_id)]
                if not problem_db_id:
                    raise Exception(
                        f"Problem ID {data['problem'].problem_frontend_id} not found in DB."
                    )
                assert isinstance(data["tags"], set)
                for tag in data["tags"]:
                    tag_db_id = db_tags.get(tag.tag_name)
                    if not tag_db_id:
                        raise Exception(f"Tag {tag.tag_name} not found in DB.")

                    associations.append(
                        {"problem_id": problem_db_id, "tag_id": tag_db_id}
                    )
            self.logger.debug(f"Problem-Tag Associations: {associations[:2]} ...")
            if associations:
                # First, clear all existing associations to ensure a clean slate
                db.execute(problem_tags_association.delete())

                # Use the imported problem_tags_association Table object
                insert_stmt = sqlite_upsert(
                    problem_tags_association
                ).on_conflict_do_nothing(index_elements=["problem_id", "tag_id"])
                db.execute(insert_stmt, associations)
            self.logger.info("Problem-tag associations created.")
            db.commit()

    async def init_cache(self):
        """
        Initializes the problem cache from the local database.
        Very Expensive! Use it only once at startup.
        """
        try:
            problems = await self.get_problems_from_db()
            self.logger.info(
                "Initializing problem cache with %d problems.", len(problems)
            )
            self.problem_cache = {
                problem.problem_frontend_id: problem for problem in problems
            }
        except Exception as e:
            self.logger.error("Error initializing cache", exc_info=e)
            raise Exception(f"Failed to initialize cache: {e}")

    async def refresh_cache(self):
        """
        Fetches all problems from LeetCode and updates the local database and cache.
        Expensive! Use it once a day or less frequently.
        """
        self.logger.info("Refreshing problem cache from LeetCode API.")
        try:
            self.logger.info("Fetching all problems from LeetCode API...")
            api_problems = await self.leetcode_api.fetch_all_problems()
            all_problems: Dict[int, Problem] = {
                problem_frontend_id: problem["problem"]
                for problem_frontend_id, problem in api_problems.items()
            }
            all_problem_tags: Dict[int, Set[TopicTags]] = {
                problem_frontend_id: problem["tags"]
                for problem_frontend_id, problem in api_problems.items()
            }
            self.logger.info(f"Fetched {len(all_problems)} problems from LeetCode API.")
            await self._bulk_upsert_problems(all_problems)
            all_topic_tags: Set[TopicTags] = set()
            for tags in all_problem_tags.values():
                all_topic_tags.update(tags)
            self.logger.debug(
                f"All Topic Tags: {[tag.tag_name for tag in list(all_topic_tags)[:5]]} ..."
            )
            await self._bulk_upsert_topic_tags(all_topic_tags)
            await self._create_problem_tag_associations(api_problems)
            await self.init_cache()
            self.logger.info("Problem cache refresh completed.")
        except Exception as e:
            self.logger.error("Error refreshing cache", exc_info=e)
            raise Exception(e)

    async def get_problems_from_db(self) -> Sequence[Problem]:
        with self.database_mananger as db:
            self.logger.info("Fetching all problems from the database.")
            stmt = select(Problem).options(selectinload(Problem.tags))
            results = db.execute(stmt).scalars().all()
            return results

    async def get_all_topics_from_db(self) -> Dict[int, TopicTags]:
        with self.database_mananger as db:
            stmt = select(TopicTags)
            self.logger.info("Fetching all topic tags from the database.")
            all_topics = db.execute(stmt).scalars().all()
            return {topic.id: topic for topic in all_topics}

    async def get_problem_from_db(self, problem_frontend_id: int) -> Problem | None:
        with self.database_mananger as db:
            self.logger.info(
                f"Fetching problem with frontend ID {problem_frontend_id} from the database."
            )
            stmt = (
                select(Problem)
                .where(Problem.problem_frontend_id == problem_frontend_id)
                .options(selectinload(Problem.tags))
            )
            problem = db.execute(stmt).scalars().first()
            return problem

    async def get_problem(
        self, problem_frontend_id: int
    ) -> Dict[Literal["problem", "tags"], Problem | Set[TopicTags]] | None:
        """
        Retrieves a problem by its ID from the cache or fetches it from LeetCode if not present.
        """
        if problem_in_cache := self.problem_cache.get(problem_frontend_id, None):
            self.logger.debug(f"Problem with ID {problem_frontend_id} found in cache.")
            self.logger.debug(
                f"Problem Tags: {[tag.tag_name for tag in problem_in_cache.tags]}"
            )
            self.logger.debug(f"Problem Details: {problem_in_cache}")
            return {"problem": problem_in_cache, "tags": set(problem_in_cache.tags)}
        try:
            self.logger.info(
                f"Problem with ID {problem_frontend_id} not found in cache. Fetching from DB or LeetCode API."
            )
            problem = await self.get_problem_from_db(
                problem_frontend_id=problem_frontend_id
            )
            self.logger.debug(f"DB Problem: {problem}")
            if problem:
                self.problem_cache[problem_frontend_id] = problem
                return {"problem": problem, "tags": set(problem.tags)}

            self.logger.info(
                f"Problem with ID {problem_frontend_id} not found in DB. Fetching from LeetCode API."
            )
            problem_data = await self.leetcode_api.fetch_problem_by_id(
                problem_frontend_id
            )
            self.logger.debug(f"API Problem Data: {problem_data}")
            if not problem_data:
                raise ProblemNotFound(
                    f"Problem with ID {problem_frontend_id} not found."
                )
            problem = problem_data["problem"]
            tags = problem_data["tags"]
            assert isinstance(tags, set) and isinstance(problem, Problem)
            problem = await self.add_problem_to_db(problem, tags)
            self.problem_cache[problem_frontend_id] = problem
            self.logger.debug(f"New Problem Added: {problem}")
            return {"problem": problem, "tags": set(problem.tags)}
        except Exception as e:
            self.logger.error(
                f"Error retrieving problem with ID {problem_frontend_id}",
                exc_info=e,
            )
            raise Exception(e)

    async def get_daily_problem(
        self,
    ) -> Dict[Literal["problem", "tags"], Problem | Set[TopicTags]] | None:
        """
        Retrieves the daily problem from LeetCode.
        """
        try:
            self.logger.info("Fetching daily problem from LeetCode API.")
            problem_data = await self.leetcode_api.fetch_daily()
            if not problem_data:
                raise ProblemNotFound("Daily problem not found.")
            self.logger.debug(f"Daily Problem Data: {problem_data}")
            problem = problem_data["problem"]
            tags = problem_data["tags"]
            assert isinstance(tags, set) and isinstance(problem, Problem)
            self.logger.debug(f"Daily Problem: {problem}")
            if problem.problem_frontend_id in self.problem_cache.keys():
                return {
                    "problem": self.problem_cache[problem.problem_frontend_id],
                    "tags": set(self.problem_cache[problem.problem_frontend_id].tags),
                }
            self.logger.info(
                f"Daily problem with ID {problem.problem_frontend_id} not found in cache. Checking DB."
            )
            if db_problem := await self.get_problem_from_db(
                problem.problem_frontend_id
            ):
                self.problem_cache[problem.problem_frontend_id] = db_problem
                return {"problem": db_problem, "tags": set(db_problem.tags)}

            self.logger.info(
                f"Daily problem with ID {problem.problem_frontend_id} not found in DB. Adding to DB."
            )
            new_problem = await self.add_problem_to_db(problem, tags)

            self.logger.debug(f"New Daily Problem Added: {new_problem}")
            self.problem_cache[problem.problem_frontend_id] = new_problem
            self.logger.debug(
                f"Daily Problem Tags: {[tag.tag_name for tag in new_problem.tags]}"
            )
            return {
                "problem": new_problem,
                "tags": set(new_problem.tags),
            }

        except Exception as e:
            self.logger.error("Error retrieving daily problem", exc_info=e)
            raise Exception(e)

    async def add_problem_to_db(
        self, problem: Problem, tags: Set[TopicTags]
    ) -> Problem:
        with self.database_mananger as db:
            self.logger.info(
                f"Adding problem with ID {problem.problem_id} to the database."
            )
            # Check for existing problem
            db_problem = (
                db.query(Problem).filter_by(problem_id=problem.problem_id).first()
            )
            if not db_problem:
                db.add(problem)
                db.flush()  # Flush to get problem.id
                db_problem = problem

            # Handle tags
            self.logger.info(
                f"Associating tags with problem ID {db_problem.problem_id}."
            )
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
            self.logger.info(
                f"Problem with ID {db_problem.problem_id} added/updated successfully."
            )
            return db_problem

    async def delete_problem_from_db(self, problem_frontend_id: int) -> None:
        self.logger.info(
            f"Deleting problem with frontend ID {problem_frontend_id} from the database."
        )
        with self.database_mananger as db:
            db_problem = (
                db.query(Problem)
                .filter_by(problem_frontend_id=problem_frontend_id)
                .first()
            )
            if db_problem:
                db.delete(db_problem)
                db.commit()
                if problem_frontend_id in self.problem_cache:
                    del self.problem_cache[problem_frontend_id]
