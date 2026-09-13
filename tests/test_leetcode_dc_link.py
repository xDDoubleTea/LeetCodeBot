from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, select

from config.constants import (
    LEETCODE_VERIFY_TOKEN_PREFIX,
    VERIFY_TOKEN_EXPIRATION_PERIOD,
)
from core.leetcode_api import LeetCodeAPI
from core.leetcode_dc_link import LeetCodeDCLinkManager
from db.leetcode_dc_link import LeetCodeDCLink
from models.leetcode import (
    UserInfo,
    UserProfile,
    UserSubmissionStat,
    VerificationEntry,
    VerificationStatus,
)
from utils.custom_exceptions import (
    LeetCodeUserNameNotFound,
    NotLinkedError,
    VerificationAlreadyFailed,
    VerificationTokenAlreadyCompleted,
    VerificationTokenExpired,
    VerificationTokenNotFound,
    VerificationTokenNotGenerated,
)

DISCORD_ID = 398444155132575756
LEETCODE_NAME = "some_leetcoder"


def make_user_info(about_me: str, user_name: str = LEETCODE_NAME) -> UserInfo:
    """A `UserInfo` carrying `about_me`, which is the only field verification reads."""
    return UserInfo(
        user_name=user_name,
        github_url="",
        twitter_url="",
        linkedin_url="",
        ac_submission=UserSubmissionStat(
            difficulity="All",
            ac_submission_count=0,
            total_submissions_and_ac_count=0,
        ),
        user_profile=UserProfile(
            user_avatar="",
            country_name="",
            about_me=about_me,
            company="",
            job_title="",
            school="",
            websites=[],
        ),
    )


def make_entry(
    status: VerificationStatus = VerificationStatus.PENDING,
    age: timedelta = timedelta(0),
    token: str = f"{LEETCODE_VERIFY_TOKEN_PREFIX}-deadbeefdeadbeef",
    discord_user_id: int = DISCORD_ID,
    leetcode_user_name: str = LEETCODE_NAME,
) -> VerificationEntry:
    return VerificationEntry(
        discord_user_id=discord_user_id,
        leetcode_user_name=leetcode_user_name,
        verification_token=token,
        timestamp=datetime.now(UTC) - age,
        status=status,
    )


@pytest.fixture
def mock_api():
    return AsyncMock(spec=LeetCodeAPI)


@pytest.fixture
def manager(database_manager, mock_api):
    """The manager under test, over a real in-memory database."""
    return LeetCodeDCLinkManager(
        async_db_manager=database_manager, leetcode_api=mock_api
    )


async def drop_every_row(database_manager) -> None:
    """Leave the caches as they are, so a later hit can only come from them."""
    async with database_manager as db:
        await db.execute(delete(LeetCodeDCLink))


async def rows(database_manager) -> list[LeetCodeDCLink]:
    async with database_manager as db:
        return list((await db.execute(select(LeetCodeDCLink))).scalars().all())


class TestIsExpired:
    """Tests for the expiry window shared by verification and cleanup."""

    @pytest.mark.parametrize(
        "age,expected",
        [
            pytest.param(timedelta(0), False, id="just_created"),
            pytest.param(
                timedelta(minutes=VERIFY_TOKEN_EXPIRATION_PERIOD - 1),
                False,
                id="a_minute_left",
            ),
            pytest.param(
                timedelta(minutes=VERIFY_TOKEN_EXPIRATION_PERIOD, seconds=1),
                True,
                id="a_second_past",
            ),
            pytest.param(timedelta(days=1), True, id="long_gone"),
        ],
    )
    def test_expiry_window(self, age, expected):
        assert LeetCodeDCLinkManager._is_expired(make_entry(age=age)) is expected


class TestCleanUpStaleVerifications:
    """Tests for dropping verification entries that can no longer be used."""

    @pytest.mark.parametrize(
        "status",
        [
            VerificationStatus.FAILED,
            VerificationStatus.COMPLETE,
            VerificationStatus.EXPIRED,
        ],
    )
    async def test_terminal_statuses_are_dropped(self, manager, status):
        manager.pending_verification[DISCORD_ID] = make_entry(status=status)

        await manager.clean_up_stale_verifications()

        assert manager.pending_verification == {}

    async def test_timed_out_pending_entry_is_dropped(self, manager):
        manager.pending_verification[DISCORD_ID] = make_entry(age=timedelta(hours=1))

        await manager.clean_up_stale_verifications()

        assert manager.pending_verification == {}

    async def test_live_pending_entry_is_kept(self, manager):
        entry = make_entry()
        manager.pending_verification[DISCORD_ID] = entry

        await manager.clean_up_stale_verifications()

        assert manager.pending_verification == {DISCORD_ID: entry}

    async def test_only_the_stale_entries_go(self, manager):
        live = make_entry(discord_user_id=1)
        manager.pending_verification = {
            1: live,
            2: make_entry(discord_user_id=2, status=VerificationStatus.FAILED),
            3: make_entry(discord_user_id=3, age=timedelta(hours=1)),
        }

        await manager.clean_up_stale_verifications()

        assert manager.pending_verification == {1: live}

    async def test_empty_mapping_is_a_no_op(self, manager):
        await manager.clean_up_stale_verifications()

        assert manager.pending_verification == {}


class TestInitCache:
    """Tests for loading both directions of the link cache from the database."""

    async def test_both_caches_are_populated(self, manager, database_manager):
        async with database_manager as db:
            db.add(
                LeetCodeDCLink(
                    discord_user_id=DISCORD_ID, leetcode_user_name=LEETCODE_NAME
                )
            )

        await manager.init_cache()

        assert manager.dc_to_lc_cache[DISCORD_ID].leetcode_user_name == LEETCODE_NAME
        assert manager.lc_to_dc_cache[LEETCODE_NAME].discord_user_id == DISCORD_ID

    async def test_empty_database_gives_empty_caches(self, manager):
        await manager.init_cache()

        assert manager.dc_to_lc_cache == {}
        assert manager.lc_to_dc_cache == {}

    async def test_stale_cache_contents_are_replaced(self, manager):
        manager.dc_to_lc_cache[1] = LeetCodeDCLink(
            discord_user_id=1, leetcode_user_name="gone"
        )
        manager.lc_to_dc_cache["gone"] = manager.dc_to_lc_cache[1]

        await manager.init_cache()

        assert manager.dc_to_lc_cache == {}
        assert manager.lc_to_dc_cache == {}


class TestUpsertLink:
    """Tests for creating and re-pointing a link."""

    async def test_new_link_is_written_and_cached(self, manager, database_manager):
        link = await manager.upsert_link(DISCORD_ID, LEETCODE_NAME)

        assert link.leetcode_user_name == LEETCODE_NAME
        assert [
            (r.discord_user_id, r.leetcode_user_name)
            for r in await rows(database_manager)
        ] == [(DISCORD_ID, LEETCODE_NAME)]
        assert manager.dc_to_lc_cache[DISCORD_ID].leetcode_user_name == LEETCODE_NAME
        assert manager.lc_to_dc_cache[LEETCODE_NAME].discord_user_id == DISCORD_ID

    async def test_relinking_drops_the_old_name_from_the_cache(self, manager):
        await manager.upsert_link(DISCORD_ID, LEETCODE_NAME)

        await manager.upsert_link(DISCORD_ID, "someone_else")

        assert LEETCODE_NAME not in manager.lc_to_dc_cache
        assert manager.lc_to_dc_cache["someone_else"].discord_user_id == DISCORD_ID

    async def test_relinking_replaces_the_name_without_adding_a_row(
        self, manager, database_manager
    ):
        await manager.upsert_link(DISCORD_ID, LEETCODE_NAME)

        await manager.upsert_link(DISCORD_ID, "someone_else")

        assert [
            (r.discord_user_id, r.leetcode_user_name)
            for r in await rows(database_manager)
        ] == [(DISCORD_ID, "someone_else")]
        assert manager.dc_to_lc_cache[DISCORD_ID].leetcode_user_name == "someone_else"


class TestGetLinkWithDiscordUserId:
    """Tests for the Discord-side lookup."""

    async def test_cache_hit_skips_the_database(self, manager, mock_api):
        cached = LeetCodeDCLink(
            discord_user_id=DISCORD_ID, leetcode_user_name=LEETCODE_NAME
        )
        manager.dc_to_lc_cache[DISCORD_ID] = cached

        assert await manager.get_link_with_discord_user_id(DISCORD_ID) is cached
        mock_api.user_info.assert_not_called()

    async def test_cache_miss_reads_the_database(self, manager, database_manager):
        async with database_manager as db:
            db.add(
                LeetCodeDCLink(
                    discord_user_id=DISCORD_ID, leetcode_user_name=LEETCODE_NAME
                )
            )

        link = await manager.get_link_with_discord_user_id(DISCORD_ID)

        assert link.leetcode_user_name == LEETCODE_NAME

    async def test_a_database_hit_warms_both_caches(self, manager, database_manager):
        async with database_manager as db:
            db.add(
                LeetCodeDCLink(
                    discord_user_id=DISCORD_ID, leetcode_user_name=LEETCODE_NAME
                )
            )

        await manager.get_link_with_discord_user_id(DISCORD_ID)

        assert manager.dc_to_lc_cache[DISCORD_ID].leetcode_user_name == LEETCODE_NAME
        assert manager.lc_to_dc_cache[LEETCODE_NAME].discord_user_id == DISCORD_ID

    async def test_a_second_lookup_is_served_from_the_cache(
        self, manager, database_manager
    ):
        async with database_manager as db:
            db.add(
                LeetCodeDCLink(
                    discord_user_id=DISCORD_ID, leetcode_user_name=LEETCODE_NAME
                )
            )
        await manager.get_link_with_discord_user_id(DISCORD_ID)
        await drop_every_row(database_manager)

        link = await manager.get_link_with_discord_user_id(DISCORD_ID)

        assert link.leetcode_user_name == LEETCODE_NAME

    async def test_unknown_user_raises_not_linked(self, manager):
        with pytest.raises(NotLinkedError):
            await manager.get_link_with_discord_user_id(DISCORD_ID)

    async def test_a_miss_leaves_the_caches_empty(self, manager):
        with pytest.raises(NotLinkedError):
            await manager.get_link_with_discord_user_id(DISCORD_ID)

        assert manager.dc_to_lc_cache == {}
        assert manager.lc_to_dc_cache == {}


class TestGetLinkWithLeetCodeUserName:
    """Tests for the LeetCode-side lookup."""

    async def test_cache_hit_skips_the_database(self, manager):
        cached = LeetCodeDCLink(
            discord_user_id=DISCORD_ID, leetcode_user_name=LEETCODE_NAME
        )
        manager.lc_to_dc_cache[LEETCODE_NAME] = cached

        assert await manager.get_link_with_leetcode_user_name(LEETCODE_NAME) is cached

    async def test_cache_miss_reads_the_database(self, manager, database_manager):
        async with database_manager as db:
            db.add(
                LeetCodeDCLink(
                    discord_user_id=DISCORD_ID, leetcode_user_name=LEETCODE_NAME
                )
            )

        link = await manager.get_link_with_leetcode_user_name(LEETCODE_NAME)

        assert link.discord_user_id == DISCORD_ID

    async def test_a_database_hit_warms_both_caches(self, manager, database_manager):
        async with database_manager as db:
            db.add(
                LeetCodeDCLink(
                    discord_user_id=DISCORD_ID, leetcode_user_name=LEETCODE_NAME
                )
            )

        await manager.get_link_with_leetcode_user_name(LEETCODE_NAME)

        assert manager.dc_to_lc_cache[DISCORD_ID].leetcode_user_name == LEETCODE_NAME
        assert manager.lc_to_dc_cache[LEETCODE_NAME].discord_user_id == DISCORD_ID

    async def test_the_other_direction_is_warmed_too(self, manager, database_manager):
        async with database_manager as db:
            db.add(
                LeetCodeDCLink(
                    discord_user_id=DISCORD_ID, leetcode_user_name=LEETCODE_NAME
                )
            )
        await manager.get_link_with_leetcode_user_name(LEETCODE_NAME)
        await drop_every_row(database_manager)

        link = await manager.get_link_with_discord_user_id(DISCORD_ID)

        assert link.leetcode_user_name == LEETCODE_NAME

    async def test_unknown_name_raises_not_linked(self, manager):
        with pytest.raises(NotLinkedError):
            await manager.get_link_with_leetcode_user_name("nobody")

    async def test_a_miss_leaves_the_caches_empty(self, manager):
        with pytest.raises(NotLinkedError):
            await manager.get_link_with_leetcode_user_name("nobody")

        assert manager.dc_to_lc_cache == {}
        assert manager.lc_to_dc_cache == {}


class TestDeleteLink:
    """Tests for unlinking."""

    async def test_row_and_cache_entry_both_go(self, manager, database_manager):
        await manager.upsert_link(DISCORD_ID, LEETCODE_NAME)
        await manager.init_cache()

        await manager.delete_link(DISCORD_ID)

        assert await rows(database_manager) == []
        assert DISCORD_ID not in manager.dc_to_lc_cache

    async def test_deleting_a_link_the_caches_never_saw(
        self, manager, database_manager
    ):
        await manager.upsert_link(DISCORD_ID, LEETCODE_NAME)
        manager.dc_to_lc_cache.clear()
        manager.lc_to_dc_cache.clear()

        await manager.delete_link(DISCORD_ID)

        assert await rows(database_manager) == []

    async def test_deleting_an_unlinked_user_raises_not_linked(self, manager):
        with pytest.raises(NotLinkedError):
            await manager.delete_link(DISCORD_ID)

    async def test_the_leetcode_side_cache_entry_also_goes(self, manager):
        await manager.upsert_link(DISCORD_ID, LEETCODE_NAME)
        await manager.init_cache()

        await manager.delete_link(DISCORD_ID)

        with pytest.raises(NotLinkedError):
            await manager.get_link_with_leetcode_user_name(LEETCODE_NAME)


class TestCreateLinkVerification:
    """Tests for issuing a verification token."""

    async def test_token_carries_the_prefix(self, manager):
        token = await manager.create_link_verification(DISCORD_ID, LEETCODE_NAME)

        assert token.startswith(f"{LEETCODE_VERIFY_TOKEN_PREFIX}-")

    async def test_entry_is_recorded_as_pending(self, manager):
        token = await manager.create_link_verification(DISCORD_ID, LEETCODE_NAME)

        entry = manager.pending_verification[DISCORD_ID]
        assert entry.status == VerificationStatus.PENDING
        assert (entry.verification_token, entry.leetcode_user_name) == (
            token,
            LEETCODE_NAME,
        )

    async def test_each_call_issues_a_fresh_token(self, manager):
        first = await manager.create_link_verification(DISCORD_ID, LEETCODE_NAME)
        second = await manager.create_link_verification(DISCORD_ID, LEETCODE_NAME)

        assert first != second
        assert manager.pending_verification[DISCORD_ID].verification_token == second

    async def test_a_second_call_repoints_at_the_new_name(self, manager):
        await manager.create_link_verification(DISCORD_ID, LEETCODE_NAME)
        await manager.create_link_verification(DISCORD_ID, "someone_else")

        assert (
            manager.pending_verification[DISCORD_ID].leetcode_user_name
            == "someone_else"
        )


class TestLinkVerifyRejections:
    """Tests for the checks `link_verify` runs before it calls the API."""

    async def test_no_entry_raises_not_generated(self, manager, mock_api):
        with pytest.raises(VerificationTokenNotGenerated):
            await manager.link_verify(DISCORD_ID)

        mock_api.user_info.assert_not_called()

    async def test_another_users_entry_does_not_count(self, manager):
        manager.pending_verification[1] = make_entry(discord_user_id=1)

        with pytest.raises(VerificationTokenNotGenerated):
            await manager.link_verify(DISCORD_ID)

    async def test_timed_out_entry_raises_expired(self, manager, mock_api):
        manager.pending_verification[DISCORD_ID] = make_entry(age=timedelta(hours=1))

        with pytest.raises(VerificationTokenExpired):
            await manager.link_verify(DISCORD_ID)

        mock_api.user_info.assert_not_called()

    async def test_timed_out_entry_is_marked_expired(self, manager):
        manager.pending_verification[DISCORD_ID] = make_entry(age=timedelta(hours=1))

        with pytest.raises(VerificationTokenExpired):
            await manager.link_verify(DISCORD_ID)

        assert (
            manager.pending_verification[DISCORD_ID].status
            == VerificationStatus.EXPIRED
        )

    @pytest.mark.parametrize(
        "status,expected",
        [
            pytest.param(
                VerificationStatus.COMPLETE,
                VerificationTokenAlreadyCompleted,
                id="already_linked",
            ),
            pytest.param(
                VerificationStatus.FAILED,
                VerificationAlreadyFailed,
                id="already_failed",
            ),
        ],
    )
    async def test_settled_entry_is_refused(self, manager, mock_api, status, expected):
        manager.pending_verification[DISCORD_ID] = make_entry(status=status)

        with pytest.raises(expected):
            await manager.link_verify(DISCORD_ID)

        mock_api.user_info.assert_not_called()


class TestLinkVerifyAgainstLeetCode:
    """Tests for the part of `link_verify` that reads the LeetCode profile."""

    async def test_the_pending_name_is_the_one_looked_up(self, manager, mock_api):
        entry = make_entry(leetcode_user_name="pending_name")
        manager.pending_verification[DISCORD_ID] = entry
        mock_api.user_info.return_value = make_user_info(entry.verification_token)

        await manager.link_verify(DISCORD_ID)

        mock_api.user_info.assert_awaited_once_with("pending_name")

    async def test_unknown_leetcode_user_propagates(self, manager, mock_api):
        manager.pending_verification[DISCORD_ID] = make_entry()
        mock_api.user_info.side_effect = LeetCodeUserNameNotFound

        with pytest.raises(LeetCodeUserNameNotFound):
            await manager.link_verify(DISCORD_ID)

    async def test_unknown_leetcode_user_fails_the_entry(self, manager, mock_api):
        manager.pending_verification[DISCORD_ID] = make_entry()
        mock_api.user_info.side_effect = LeetCodeUserNameNotFound

        with pytest.raises(LeetCodeUserNameNotFound):
            await manager.link_verify(DISCORD_ID)

        assert (
            manager.pending_verification[DISCORD_ID].status == VerificationStatus.FAILED
        )

    @pytest.mark.parametrize(
        "about_me",
        [
            pytest.param("", id="empty_profile"),
            pytest.param("I love leetcode", id="unrelated_text"),
            pytest.param(
                f"{LEETCODE_VERIFY_TOKEN_PREFIX}-0000000000000000",
                id="someone_elses_token",
            ),
            pytest.param("deadbeefdeadbeef", id="prefix_dropped"),
            pytest.param(
                f"{LEETCODE_VERIFY_TOKEN_PREFIX}-deadbeefdeadbee", id="truncated"
            ),
        ],
    )
    async def test_missing_token_is_refused(self, manager, mock_api, about_me):
        manager.pending_verification[DISCORD_ID] = make_entry()
        mock_api.user_info.return_value = make_user_info(about_me)

        with pytest.raises(VerificationTokenNotFound):
            await manager.link_verify(DISCORD_ID)

    async def test_missing_token_fails_the_entry(self, manager, mock_api):
        manager.pending_verification[DISCORD_ID] = make_entry()
        mock_api.user_info.return_value = make_user_info("nothing here")

        with pytest.raises(VerificationTokenNotFound):
            await manager.link_verify(DISCORD_ID)

        assert (
            manager.pending_verification[DISCORD_ID].status == VerificationStatus.FAILED
        )

    async def test_no_link_is_written_when_the_token_is_missing(
        self, manager, mock_api, database_manager
    ):
        manager.pending_verification[DISCORD_ID] = make_entry()
        mock_api.user_info.return_value = make_user_info("nothing here")

        with pytest.raises(VerificationTokenNotFound):
            await manager.link_verify(DISCORD_ID)

        assert await rows(database_manager) == []
        assert manager.dc_to_lc_cache == {}


class TestLinkVerifySuccess:
    """Tests for a verification that finds the token."""

    @pytest.fixture
    def entry(self, manager):
        entry = make_entry()
        manager.pending_verification[DISCORD_ID] = entry
        return entry

    @pytest.mark.parametrize(
        "about_me_template",
        [
            pytest.param("{token}", id="token_only"),
            pytest.param("verifying: {token}", id="token_with_a_prefix_line"),
            pytest.param("{token}\nthanks!", id="token_with_trailing_text"),
            pytest.param("  {token}  ", id="token_surrounded_by_whitespace"),
        ],
    )
    async def test_token_is_found_anywhere_in_about_me(
        self, manager, mock_api, entry, about_me_template
    ):
        mock_api.user_info.return_value = make_user_info(
            about_me_template.format(token=entry.verification_token)
        )

        link = await manager.link_verify(DISCORD_ID)

        assert link.leetcode_user_name == LEETCODE_NAME

    async def test_the_link_is_persisted(
        self, manager, mock_api, entry, database_manager
    ):
        mock_api.user_info.return_value = make_user_info(entry.verification_token)

        await manager.link_verify(DISCORD_ID)

        assert [
            (r.discord_user_id, r.leetcode_user_name)
            for r in await rows(database_manager)
        ] == [(DISCORD_ID, LEETCODE_NAME)]

    async def test_the_entry_is_marked_complete(self, manager, mock_api, entry):
        mock_api.user_info.return_value = make_user_info(entry.verification_token)

        await manager.link_verify(DISCORD_ID)

        assert entry.status == VerificationStatus.COMPLETE

    async def test_verifying_twice_is_refused(self, manager, mock_api, entry):
        mock_api.user_info.return_value = make_user_info(entry.verification_token)
        await manager.link_verify(DISCORD_ID)

        with pytest.raises(VerificationTokenAlreadyCompleted):
            await manager.link_verify(DISCORD_ID)

        assert mock_api.user_info.await_count == 1

    async def test_relinking_to_another_account_moves_the_link(
        self, manager, mock_api, entry, database_manager
    ):
        mock_api.user_info.return_value = make_user_info(entry.verification_token)
        await manager.link_verify(DISCORD_ID)

        second = make_entry(leetcode_user_name="someone_else")
        manager.pending_verification[DISCORD_ID] = second
        mock_api.user_info.return_value = make_user_info(
            second.verification_token, user_name="someone_else"
        )
        await manager.link_verify(DISCORD_ID)

        assert [
            (r.discord_user_id, r.leetcode_user_name)
            for r in await rows(database_manager)
        ] == [(DISCORD_ID, "someone_else")]
