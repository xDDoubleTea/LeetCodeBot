import logging

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_upsert
from sqlalchemy.exc import IntegrityError

from db.async_db_manager import AsyncDatabaseManager
from db.leetcode_dc_link import LeetCodeDCLink
from utils.custom_exceptions import DuplicateLinkName, NotLinkedError

logger = logging.getLogger(__name__)


class LeetCodeDCLinkManager:
    def __init__(self, async_db_manager: AsyncDatabaseManager) -> None:
        self.cache: dict[int, str] = dict()
        self.async_db_manager: AsyncDatabaseManager = async_db_manager

    def _create_leetcode_dclink_instance(
        self, discord_user_id: int, leetcode_user_name: str
    ) -> LeetCodeDCLink:
        instance = LeetCodeDCLink(
            discord_user_id=discord_user_id, leetcode_user_name=leetcode_user_name
        )
        logger.debug(f"Creating LeetCodeDCLink instance: {instance}")
        return instance

    async def upsert_link(
        self, discord_user_id: int, leetcode_user_name: str
    ) -> LeetCodeDCLink:
        instance = self._create_leetcode_dclink_instance(
            discord_user_id=discord_user_id, leetcode_user_name=leetcode_user_name
        )
        try:
            logger.debug(f"Upserting link for discord_user_id: {discord_user_id}")
            async with self.async_db_manager as db:
                insert_stmt = sqlite_upsert(LeetCodeDCLink).values(
                    discord_user_id=discord_user_id,
                    leetcode_user_name=leetcode_user_name,
                )
                insert_stmt = insert_stmt.on_conflict_do_update(
                    index_elements=[LeetCodeDCLink.discord_user_id],
                    set_=dict(leetcode_user_name=leetcode_user_name),
                )
                await db.execute(insert_stmt)
        except IntegrityError as e:
            raise DuplicateLinkName from e
        except Exception:
            raise

        return instance

    async def delete_link(self, discord_user_id: int) -> None:
        try:
            link = await self.get_link_with_discord_user_id(discord_user_id)
        except NotLinkedError as e:
            raise NotLinkedError from e
        except Exception:
            raise

        async with self.async_db_manager as db:
            logger.debug(f"Deleting link for discord_user_id: {discord_user_id}")
            await db.delete(link)
            await db.commit()

    async def get_link_with_discord_user_id(
        self, discord_user_id: int
    ) -> LeetCodeDCLink:
        link = None
        async with self.async_db_manager as db:
            stmt = select(LeetCodeDCLink).where(
                LeetCodeDCLink.discord_user_id == discord_user_id
            )
            link = (await db.execute(stmt)).scalars().all()
        if link is None:
            raise NotLinkedError
        logger.debug(f"Link found for discord_user_id: {discord_user_id}")
        return link[0]

    async def get_link_with_leetcode_user_name(
        self, leetcode_user_name: str
    ) -> LeetCodeDCLink:
        link = None
        async with self.async_db_manager as db:
            stmt = select(LeetCodeDCLink).where(
                LeetCodeDCLink.leetcode_user_name == leetcode_user_name
            )
            link = (await db.execute(stmt)).scalars().all()
        if link is None:
            raise NotLinkedError
        logger.debug(f"Link found for leetcode_user_name: {leetcode_user_name}")
        return link[0]
