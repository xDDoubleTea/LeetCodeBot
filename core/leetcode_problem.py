import logging
import random
from collections.abc import Sequence
from typing import Literal

import re2
from discord import Client, Embed
from discord.ext.commands import Bot
from sqlalchemy import ColumnElement, select
from sqlalchemy.dialects.sqlite import insert as sqlite_upsert
from sqlalchemy.orm import selectinload

from core.leetcode_api import LeetCodeAPI
from db.async_db_manager import AsyncDatabaseManager
from db.problem import Problem, TopicTags, problem_tags_association
from models.leetcode import ProblemDifficulity, ProblemWithTags
from utils.custom_exceptions import CacheInitError
from utils.embed_presenters import get_problem_desc_embed

logger = logging.getLogger(__name__)


class ProblemNotFound(Exception):
    pass


class LeetCodeProblemManager:
    def __init__(
        self,
        leetcode_api: LeetCodeAPI,
        async_database_manager: AsyncDatabaseManager,
    ) -> None:
        self.all_problem_cache: dict[int, Problem] = dict()
        self.free_problem_cache: dict[int, Problem] = dict()
        self.tag_cache_literal: list[str] = []
        self.daily_problem: ProblemWithTags | None = None
        self.leetcode_api: LeetCodeAPI = leetcode_api
        self.async_database_manager: AsyncDatabaseManager = async_database_manager

    async def _bulk_upsert_problems(self, api_problems: dict[int, Problem]) -> None:
        async with self.async_database_manager as db:
            logger.info(f"Upserting {len(api_problems)} problems into the database.")
            mappings = [problem.to_dict() for problem in api_problems.values()]
            logger.debug(f"Problem mappings: {mappings[:2]} ...")
            insert_stmt = sqlite_upsert(Problem)
            insert_stmt = insert_stmt.on_conflict_do_update(
                index_elements=["problem_id"],
                set_={
                    "title": insert_stmt.excluded.title,
                    "url": insert_stmt.excluded.url,
                    "difficulty": insert_stmt.excluded.difficulty,
                    "description": insert_stmt.excluded.description,
                    "problem_frontend_id": insert_stmt.excluded.problem_frontend_id,
                    "premium": insert_stmt.excluded.premium,
                },
            )
            await db.execute(insert_stmt, mappings)
            logger.info("Bulk upsert of problems completed.")

    async def _bulk_upsert_topic_tags(self, topic_tags: set[TopicTags]) -> None:
        async with self.async_database_manager as db:
            logger.info(f"Upserting {len(topic_tags)} topic tags into the database.")
            insert_stmt = sqlite_upsert(TopicTags)
            mappings = [tag.to_dict() for tag in topic_tags]
            logger.debug(f"Topic tag mappings: {mappings[:2]} ...")
            insert_stmt = insert_stmt.on_conflict_do_nothing(
                index_elements=["tag_name"],
            )
            await db.execute(insert_stmt, mappings)
            logger.info("Bulk upsert of topic tags completed.")

    async def _create_problem_tag_associations(
        self,
        all_api_problems_data: dict[int, ProblemWithTags],
    ) -> None:
        """Creates associations based on the API data."""
        async with self.async_database_manager as db:
            logger.info("Creating problem-tag associations.")
            db_select_problems = await db.scalars(select(Problem))
            db_select_tags = await db.scalars(select(TopicTags))
            db_problem_id_problem_map = {
                p.problem_frontend_id: p.id for p in db_select_problems.all()
            }
            db_tag_name_tags_map = {t.tag_name: t.id for t in db_select_tags.all()}
            logger.debug(
                f"DB Problems: {list(db_problem_id_problem_map.items())[:2]} ..."
            )
            logger.debug(f"DB Tags: {list(db_tag_name_tags_map.items())[:2]} ...")
            associations = []
            for data in all_api_problems_data.values():
                data_problem = data.problem
                data_tags = data.tags
                problem_db_id = db_problem_id_problem_map[
                    int(data_problem.problem_frontend_id)
                ]
                if not problem_db_id:
                    raise Exception(
                        f"Problem ID {data_problem.problem_frontend_id} not found in DB."
                    )
                for tag in data_tags:
                    tag_db_id = db_tag_name_tags_map.get(tag.tag_name)
                    if not tag_db_id:
                        raise Exception(f"Tag {tag.tag_name} not found in DB.")

                    associations.append(
                        {"problem_id": problem_db_id, "tag_id": tag_db_id}
                    )
            logger.debug(f"Problem-Tag Associations: {associations[:2]} ...")
            if associations:
                await db.execute(problem_tags_association.delete())

                insert_stmt = sqlite_upsert(
                    problem_tags_association
                ).on_conflict_do_nothing(index_elements=["problem_id", "tag_id"])
                await db.execute(insert_stmt, associations)
            logger.info("Problem-tag associations created.")
            await db.commit()

    async def init_cache(self):
        """
        Initializes the problem cache from the local database.
        Very Expensive! Use it only once at startup.
        """
        try:
            problems = await self.get_problems_from_db()
            self.daily_problem = await self.fetch_daily_problem()
            all_topics_dict = await self.get_all_topics_from_db()

            logger.info("Initializing problem cache with %d problems.", len(problems))

            all_problem_cache_tmp = {
                problem.problem_frontend_id: problem for problem in problems
            }

            free_problem_cache_tmp = {
                problem.problem_frontend_id: problem
                for problem in problems
                if not problem.premium
            }

            self.all_problem_cache = all_problem_cache_tmp
            self.free_problem_cache = free_problem_cache_tmp
            self.tag_cache_literal = [
                topic.tag_name for topic in all_topics_dict.values()
            ]
        except Exception as e:
            raise CacheInitError(f"Failed to initialize cache: {e}") from e

    async def refresh_cache(self):
        """
        Fetches all problems from LeetCode and updates the local database and cache.
        Expensive! Use it once a day or less frequently.
        """
        logger.info("Refreshing problem cache from LeetCode API.")
        try:
            logger.info("Fetching all problems from LeetCode API...")
            api_problems = await self.leetcode_api.fetch_all_problems()
            all_problems: dict[int, Problem] = {
                problem_frontend_id: problem_with_tags.problem
                for problem_frontend_id, problem_with_tags in api_problems.items()
            }
            all_problem_tags: dict[int, set[TopicTags]] = {
                problem_frontend_id: problem_with_tags.tags
                for problem_frontend_id, problem_with_tags in api_problems.items()
            }
            logger.info(f"Fetched {len(all_problems)} problems from LeetCode API.")
            await self._bulk_upsert_problems(all_problems)
            all_topic_tags: set[TopicTags] = set()
            for tags in all_problem_tags.values():
                all_topic_tags.update(tags)
            logger.debug(
                f"All Topic Tags: {[tag.tag_name for tag in list(all_topic_tags)[:5]]} ..."
            )
            await self._bulk_upsert_topic_tags(all_topic_tags)
            await self._create_problem_tag_associations(api_problems)
            await self.init_cache()

            logger.info("Problem cache refresh completed.")
        except Exception as e:
            raise CacheInitError(f"Failed to refresh cache: {e}") from e

    async def get_problems_from_db(self) -> Sequence[Problem]:
        async with self.async_database_manager as db:
            logger.info("Fetching all problems from the database.")
            stmt = select(Problem).options(selectinload(Problem.tags))
            results = await db.scalars(stmt)
            return results.all()

    async def get_all_tags_literal(self) -> list[str]:
        return self.tag_cache_literal

    async def get_all_topics_from_db(self) -> dict[int, TopicTags]:
        async with self.async_database_manager as db:
            stmt = select(TopicTags)
            logger.info("Fetching all topic tags from the database.")
            result = await db.scalars(stmt)
            all_topics = result.all()
            return {topic.id: topic for topic in all_topics}

    async def get_problems_with_tag_name(self, tag_name: str) -> Sequence[Problem]:
        return await self.get_problems_by_criteria(
            Problem.tags.any(TopicTags.tag_name == tag_name)
        )

    async def get_problems_by_criteria(
        self, *criteria: ColumnElement[bool]
    ) -> Sequence[Problem]:
        """Retrieves multiple problems matching the given SQLAlchemy criteria."""
        stmt = select(Problem).options(selectinload(Problem.tags)).where(*criteria)
        logger.info("Fetching multiple problems with custom criteria")

        async with self.async_database_manager as db:
            result = await db.scalars(stmt)
            problems = result.all()
            for problem in problems:
                self.all_problem_cache[problem.problem_frontend_id] = problem
                if not problem.premium:
                    self.free_problem_cache[problem.problem_frontend_id] = problem
            return problems

    async def get_problem_from_db(
        self,
        problem_frontend_id: int | None = None,
        problem_db_id: int | None = None,
    ) -> Problem | None:
        """
        Retrieves problem from database. Provide exactly one of the front end id or the backend id for the problem.
        """
        if problem_frontend_id and problem_db_id:
            raise Exception(
                "Don't provide front end id and database id at the same time when calling this method"
            )
        if not problem_frontend_id and not problem_db_id:
            raise Exception(
                "Please provide at least one of front end id or database id for a problem"
            )
        stmt = select(Problem)
        if problem_frontend_id:
            stmt = stmt.where(Problem.problem_frontend_id == problem_frontend_id)
            logger.info(
                f"Fetching problem with frontend ID {problem_frontend_id} from the database."
            )
        elif problem_db_id:
            stmt = stmt.where(Problem.id == problem_db_id)
            logger.info(
                f"Fetching problem with database ID {problem_db_id} from the database."
            )

        stmt = stmt.options(selectinload(Problem.tags))
        async with self.async_database_manager as db:
            result = await db.scalars(stmt)
            if problem := result.first():
                logger.debug(f"Problem object {problem}")
                self.all_problem_cache[problem.problem_frontend_id] = problem
                if not problem.premium:
                    self.free_problem_cache[problem.problem_frontend_id] = problem

                return problem
        return None

    async def get_random_problem(
        self, difficulty: Literal["Easy", "Medium", "Hard"] | None, premium: bool
    ) -> ProblemWithTags:
        if not difficulty:
            problem_pool = list(
                self.all_problem_cache.keys()
                if premium
                else self.free_problem_cache.keys()
            )
            problem_frontend_id = random.choice(problem_pool)
            return await self.get_problem_with_frontend_id(
                problem_frontend_id=problem_frontend_id
            )

        async with self.async_database_manager as db:
            logger.info(f"Fetching problem with difficulty {difficulty} from database")

            stmt = (
                select(Problem)
                .where(
                    Problem.difficulty
                    == ProblemDifficulity.from_str_repr(difficulty).db_repr,
                )
                .options(selectinload(Problem.tags))
            )
            if not premium:
                stmt = stmt.where(Problem.premium.is_(False))
            result = await db.scalars(stmt)
            problems = result.all()
            problem = random.choice(problems)
            return ProblemWithTags(problem, set(problem.tags))

    async def get_problem_with_title_regex(
        self, problem_title_regex: str
    ) -> Sequence[Problem]:
        try:
            logger.debug("Try compiling regex")
            re2.compile(problem_title_regex)
            logger.debug("Compiled regex")
            return await self.get_problems_by_criteria(
                Problem.title.regexp_match(f"(?i){problem_title_regex}")
            )
        except re2.error as e:
            raise ValueError("Invalid regular expression provided.") from e

        except Exception:
            logger.error(
                f"Error retrieving problem with title regex {problem_title_regex}"
            )
            raise

    async def get_problem_with_frontend_id(
        self, problem_frontend_id: int
    ) -> ProblemWithTags:
        """
        Retrieves a problem by its ID from the cache or fetches it from LeetCode if not present.
        """
        if problem_in_cache := self.all_problem_cache.get(problem_frontend_id, None):
            logger.debug(f"Problem with ID {problem_frontend_id} found in cache.")
            logger.debug(
                f"Problem Tags: {[tag.tag_name for tag in problem_in_cache.tags]}"
            )
            logger.debug(f"Problem Details: {problem_in_cache}")
            return ProblemWithTags(problem_in_cache, set(problem_in_cache.tags))
        try:
            logger.info(
                f"Problem with ID {problem_frontend_id} not found in cache. Fetching from DB or LeetCode API."
            )
            problem = await self.get_problem_from_db(
                problem_frontend_id=problem_frontend_id
            )
            logger.debug(f"DB Problem: {problem}")
            if problem:
                self.all_problem_cache[problem_frontend_id] = problem
                return ProblemWithTags(problem, set(problem.tags))
            raise ProblemNotFound(
                f"Problem with ID {problem_frontend_id} not found in cache nor DB"
            )

        except Exception:
            logger.error(f"Error retrieving problem with ID {problem_frontend_id}")
            raise

    async def get_daily_problem(self) -> ProblemWithTags:
        if self.daily_problem is not None:
            return self.daily_problem
        return await self.fetch_daily_problem()

    async def fetch_daily_problem(
        self,
    ) -> ProblemWithTags:
        """
        Retrieves the daily problem from LeetCode.
        """
        logger.info("Fetching daily problem from LeetCode API.")
        problem_data = await self.leetcode_api.fetch_daily()
        if not problem_data:
            raise ProblemNotFound("Daily problem not found.")
        logger.debug(f"Daily Problem Data: {problem_data}")
        problem = problem_data.problem
        tags = problem_data.tags

        logger.debug(f"Daily Problem: {problem}")
        if problem.problem_frontend_id in self.all_problem_cache:
            return ProblemWithTags(
                self.all_problem_cache[problem.problem_frontend_id],
                set(self.all_problem_cache[problem.problem_frontend_id].tags),
            )
        logger.info(
            f"Daily problem with ID {problem.problem_frontend_id} not found in cache. Checking DB."
        )
        if db_problem := await self.get_problem_from_db(problem.problem_frontend_id):
            self.all_problem_cache[problem.problem_frontend_id] = db_problem
            return ProblemWithTags(db_problem, set(db_problem.tags))

        logger.info(
            f"Daily problem with ID {problem.problem_frontend_id} not found in DB. Adding to DB."
        )
        new_problem = await self.add_problem_to_db(problem, tags)

        logger.debug(f"New Daily Problem Added: {new_problem}")
        self.all_problem_cache[problem.problem_frontend_id] = new_problem
        logger.debug(
            f"Daily Problem Tags: {[tag.tag_name for tag in new_problem.tags]}"
        )
        return ProblemWithTags(new_problem, set(new_problem.tags))

    async def add_problem_to_db(
        self, problem: Problem, tags: set[TopicTags]
    ) -> Problem:
        async with self.async_database_manager as db:
            logger.info(f"Adding problem with ID {problem.problem_id} to the database.")
            # Check for existing problem. The tags are eager loaded because the
            # loop below reads db_problem.tags: a lazy load there would emit IO
            # from plain attribute access, which raises MissingGreenlet on the
            # async engine.
            result = await db.scalars(
                select(Problem)
                .options(selectinload(Problem.tags))
                .where(Problem.problem_id == problem.problem_id)
            )
            db_problem = result.first()
            if not db_problem:
                db.add(problem)
                await db.flush()
                db_problem = problem
                # After the flush the problem is persistent with an unloaded
                # tags collection, so it needs the same treatment.
                await db.refresh(db_problem, attribute_names=["tags"])

            logger.info(f"Associating tags with problem ID {db_problem.problem_id}.")
            for tag in tags:
                stmt = select(TopicTags).where(TopicTags.tag_name == tag.tag_name)
                result = await db.scalars(stmt)
                db_tag = result.first()
                if not db_tag:
                    db.add(tag)
                    await db.flush()
                    db_tag = tag

                if db_tag not in db_problem.tags:
                    db_problem.tags.append(db_tag)

            await db.commit()
            await db.refresh(db_problem, attribute_names=["tags"])
            logger.info(
                f"Problem with ID {db_problem.problem_id} added/updated successfully."
            )
            return db_problem

    async def get_problem_desc(
        self, problem_frontend_id: int, bot: Bot | Client
    ) -> list[Embed]:
        problem_with_tags = await self.get_problem_with_frontend_id(
            problem_frontend_id=problem_frontend_id
        )

        if not problem_with_tags:
            logger.info(f"Problem with id {problem_frontend_id} not found.")
            return []

        problem_obj = problem_with_tags.problem

        logger.debug(f"Problem object: {problem_obj}")
        logger.info(f"Sending problem description for problem ID {problem_frontend_id}")
        return get_problem_desc_embed(
            problem=problem_obj, problem_tags=problem_with_tags.tags, bot=bot
        )
