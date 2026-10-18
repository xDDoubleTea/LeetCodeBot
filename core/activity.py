import logging
from datetime import datetime

from sqlalchemy.dialects.sqlite import insert as sqlite_upsert

from db.activity import ProblemOpen, ThreadSolution
from db.async_db_manager import AsyncDatabaseManager

logger = logging.getLogger(__name__)


class ActivityManager:
    """
    Records what users do with problems, as data for the `/suggest` ranking.

    Recording is best-effort: a database error is logged and swallowed, so it
    never fails the command or message that triggered it.
    """

    def __init__(self, async_database_manager: AsyncDatabaseManager) -> None:
        self.async_database_manager = async_database_manager

    async def record_problem_open(
        self,
        discord_user_id: int,
        guild_id: int,
        problem_db_id: int,
        command: str,
        opened_at: datetime,
    ) -> None:
        try:
            async with self.async_database_manager as db:
                db.add(
                    ProblemOpen(
                        discord_user_id=discord_user_id,
                        guild_id=guild_id,
                        problem_db_id=problem_db_id,
                        command=command,
                        opened_at=opened_at,
                    )
                )
        except Exception as e:
            logger.error("Failed to record a problem open", exc_info=e)

    async def record_thread_solution(
        self,
        message_id: int,
        thread_id: int,
        discord_user_id: int,
        problem_db_id: int,
        language: str | None,
        posted_at: datetime,
    ) -> None:
        """Record a code block message once; a repeated `message_id` is ignored."""
        try:
            async with self.async_database_manager as db:
                stmt = (
                    sqlite_upsert(ThreadSolution)
                    .values(
                        message_id=message_id,
                        thread_id=thread_id,
                        discord_user_id=discord_user_id,
                        problem_db_id=problem_db_id,
                        language=language,
                        posted_at=posted_at,
                    )
                    .on_conflict_do_nothing(index_elements=[ThreadSolution.message_id])
                )
                await db.execute(stmt)
        except Exception as e:
            logger.error("Failed to record a thread solution", exc_info=e)
