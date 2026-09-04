import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_upsert
from sqlalchemy.exc import IntegrityError

from config.constants import LEETCODE_VERIFY_TOKEN_PREFIX
from core.leetcode_api import LeetCodeAPI
from db.async_db_manager import AsyncDatabaseManager
from db.leetcode_dc_link import LeetCodeDCLink
from models.leetcode import VerificationEntry, VerificationStatus
from utils.custom_exceptions import (
    DuplicateLinkName,
    LeetCodeUserNameNotFound,
    NotLinkedError,
    VerificationAlreadyFailed,
    VerificationTokenAlreadyCompleted,
    VerificationTokenExpired,
    VerificationTokenNotFound,
    VerificationTokenNotGenerated,
)

logger = logging.getLogger(__name__)


class LeetCodeDCLinkManager:
    def __init__(
        self, async_db_manager: AsyncDatabaseManager, leetcode_api: LeetCodeAPI
    ) -> None:
        self.dc_to_lc_cache: dict[int, LeetCodeDCLink] = dict()
        self.lc_to_dc_cache: dict[str, LeetCodeDCLink] = dict()
        self.pending_verification: dict[int, VerificationEntry] = dict()
        self.async_db_manager: AsyncDatabaseManager = async_db_manager
        self.leetcode_api: LeetCodeAPI = leetcode_api

    @staticmethod
    def _is_expired(verification_entry: VerificationEntry) -> bool:
        return datetime.now(UTC) - verification_entry.timestamp > timedelta(minutes=15)

    async def _create_leetcode_dclink_instance(
        self, discord_user_id: int, leetcode_user_name: str
    ) -> LeetCodeDCLink:
        instance = LeetCodeDCLink(
            discord_user_id=discord_user_id, leetcode_user_name=leetcode_user_name
        )
        logger.debug(f"Creating LeetCodeDCLink instance: {instance}")
        return instance

    async def clean_up_stale_verifications(self):
        keys_to_del = [
            key
            for key, entry in self.pending_verification.items()
            if (
                entry.status == VerificationStatus.FAILED
                or entry.status == VerificationStatus.COMPLETE
                or entry.status == VerificationStatus.EXPIRED
            )
        ]

        for key in keys_to_del:
            del self.pending_verification[key]

    async def init_cache(self):
        result = []
        async with self.async_db_manager as db:
            stmt = select(LeetCodeDCLink)
            result = list((await db.execute(stmt)).scalars().all())

        dc_to_lc_tmp = {link_entry.discord_user_id: link_entry for link_entry in result}
        lc_to_dc_tmp = {
            link_entry.leetcode_user_name: link_entry for link_entry in result
        }

        self.dc_to_lc_cache = dc_to_lc_tmp
        self.lc_to_dc_cache = lc_to_dc_tmp

    async def upsert_link(
        self, discord_user_id: int, leetcode_user_name: str
    ) -> LeetCodeDCLink:
        instance = await self._create_leetcode_dclink_instance(
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

        self.dc_to_lc_cache[discord_user_id] = instance
        return instance

    async def delete_link(self, discord_user_id: int) -> None:
        try:
            link = await self.get_link_with_discord_user_id(discord_user_id)
            async with self.async_db_manager as db:
                logger.debug(f"Deleting link for discord_user_id: {discord_user_id}")
                await db.delete(link)
                await db.commit()
        except NotLinkedError as e:
            raise NotLinkedError from e
        except Exception:
            raise

        self.dc_to_lc_cache.pop(discord_user_id)

    async def get_link_with_discord_user_id(
        self, discord_user_id: int
    ) -> LeetCodeDCLink:
        link = self.dc_to_lc_cache.get(discord_user_id)
        if link:
            return link

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
        link = self.lc_to_dc_cache.get(leetcode_user_name)
        if link:
            return link
        async with self.async_db_manager as db:
            stmt = select(LeetCodeDCLink).where(
                LeetCodeDCLink.leetcode_user_name == leetcode_user_name
            )
            link = (await db.execute(stmt)).scalars().all()
        if link is None:
            raise NotLinkedError
        logger.debug(f"Link found for leetcode_user_name: {leetcode_user_name}")
        return link[0]

    async def create_link_verification(
        self, discord_user_id: int, leetcode_user_name: str
    ) -> str:
        tkn = f"{LEETCODE_VERIFY_TOKEN_PREFIX}-{secrets.token_hex(8)}"

        self.pending_verification[discord_user_id] = VerificationEntry(
            discord_user_id=discord_user_id,
            leetcode_user_name=leetcode_user_name,
            verification_token=tkn,
            timestamp=datetime.now(UTC),
            status=VerificationStatus.PENDING,
        )

        return tkn

    async def link_verify(self, discord_user_id: int) -> LeetCodeDCLink:
        """
        # Raises:
        - VerificationTokenNotGenerated
        - VerificationTokenExpired
        - VerificationTokenAlreadyCompleted
        - VerificationAlreadyFailed
        - VerificationTokenNotFound
        - LeetCodeUserNameNotFound
        """
        verification_entry = self.pending_verification.get(discord_user_id, None)
        logger.debug(f"Verification Entry: {verification_entry}")
        if verification_entry is None:
            raise VerificationTokenNotGenerated

        if self._is_expired(verification_entry):
            verification_entry.status = VerificationStatus.EXPIRED
            raise VerificationTokenExpired

        if verification_entry.status == VerificationStatus.COMPLETE:
            raise VerificationTokenAlreadyCompleted

        if verification_entry.status == VerificationStatus.FAILED:
            raise VerificationAlreadyFailed

        try:
            user_info = await self.leetcode_api.user_info(
                verification_entry.leetcode_user_name
            )
        except LeetCodeUserNameNotFound as e:
            verification_entry.status = VerificationStatus.FAILED
            logger.error(e.message, exc_info=e)
            raise LeetCodeUserNameNotFound from e

        logger.debug(f"User Info: {user_info}")

        if verification_entry.verification_token not in user_info.user_profile.about_me:
            verification_entry.status = VerificationStatus.FAILED
            raise VerificationTokenNotFound

        # All failure paths has been checked, meaning the verification succeeded.

        link = await self.upsert_link(
            verification_entry.discord_user_id, verification_entry.leetcode_user_name
        )
        logger.debug(f"Link: {link}")

        verification_entry.status = VerificationStatus.COMPLETE

        return link
