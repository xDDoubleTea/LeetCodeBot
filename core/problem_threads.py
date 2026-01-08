from typing import Dict, Literal, Set, Tuple
from discord import ForumChannel, Guild, Thread
from discord.channel import ThreadWithMessage
from discord.ext import commands
from sqlalchemy.sql import select
from db.database_manager import DatabaseManager
from db.problem import Problem, TopicTags
from db.thread_channel import GuildForumChannel
from db.problem_threads import ProblemThreads
from core.leetcode_problem import LeetCodeProblemManager
from sqlalchemy.dialects.sqlite import insert as sqlite_upsert
import logging
from models.leetcode import ThreadCreationEnum

from utils.discord_utils import try_get_channel
from utils.embed_presenters import (
    get_difficulty_str_repr,
    get_problem_desc_embed,
)
from utils.custom_exceptions import ForumChannelNotFound


class ProblemThreadsManager:
    def __init__(
        self,
        database_manager: DatabaseManager,
        leetcode_problem_manager: LeetCodeProblemManager,
        logger: logging.Logger,
    ) -> None:
        self.database_manager: DatabaseManager = database_manager
        self.leetcode_problem_manager: LeetCodeProblemManager = leetcode_problem_manager
        self.problem_threads: Dict[int, ProblemThreads] = {}
        self.forum_channels: Dict[int, GuildForumChannel] = {}
        self.logger = logger

    async def init_cache(self):
        with self.database_manager as db:
            self.logger.info("Initializing ProblemThreadsManager Cache...")
            stmt = select(ProblemThreads)
            result = db.execute(stmt).scalars().all()
            self.logger.info(f"Loaded {len(result)} problem threads from the database.")
            self.logger.debug(result)
            for problem_thread in result:
                self.problem_threads[problem_thread.thread_id] = problem_thread
            self.logger.info("ProblemThreadsManager Cache initialized.")
            self.logger.info("Initializing GuildForumChannels Cache...")
            stmt = select(GuildForumChannel)
            result = db.execute(stmt).scalars().all()
            self.logger.info(f"Loaded {len(result)} forum channels from the database.")
            self.logger.debug(result)
            for forum_channel in result:
                self.forum_channels[forum_channel.guild_id] = forum_channel

    async def add_forum_channel_to_db(self, guild_id: int, channel_id: int) -> None:
        with self.database_manager as db:
            self.logger.info(
                f"Adding/Updating forum channel for guild {guild_id} with channel {channel_id}."
            )
            stmt = select(GuildForumChannel).where(
                GuildForumChannel.guild_id == guild_id
            )
            forum_channel = db.execute(stmt).scalars().first()
            self.logger.debug(f"Existing forum channel: {forum_channel}")
            if forum_channel:
                forum_channel.channel_id = channel_id
            else:
                forum_channel = GuildForumChannel(
                    guild_id=guild_id, channel_id=channel_id
                )
            db.add(forum_channel)
            db.commit()
            self.forum_channels[guild_id] = forum_channel

    async def get_forum_channel(self, guild_id: int) -> GuildForumChannel | None:
        self.logger.debug(
            f"Fetching forum channel for guild {guild_id} from cache/database."
        )
        if res := self.forum_channels.get(guild_id, None):
            return res

        with self.database_manager as db:
            stmt = select(GuildForumChannel).where(
                GuildForumChannel.guild_id == guild_id
            )
            forum_channel = db.execute(stmt).scalars().first()
            if forum_channel:
                return forum_channel
        return None

    async def get_thread_by_thread_id(self, thread_id: int) -> ProblemThreads | None:
        self.logger.debug(
            f"Fetching problem thread for thread ID {thread_id} from cache."
        )
        if res := self.problem_threads.get(thread_id, None):
            return res

        with self.database_manager as db:
            stmt = select(ProblemThreads).where(ProblemThreads.thread_id == thread_id)
            problem_thread = db.execute(stmt).scalars().first()
            if problem_thread:
                return problem_thread
        self.logger.debug(f"Problem thread for thread ID {thread_id} not found.")
        return None

    async def get_thread_by_problem_id(
        self, problem_frontend_id: int, guild_id: int
    ) -> ProblemThreads | None:
        self.logger.debug(
            f"Fetching problem thread for problem ID {problem_frontend_id} in guild {guild_id} from database."
        )
        with self.database_manager as db:
            problem = await self.leetcode_problem_manager.get_problem_with_frontend_id(
                problem_frontend_id
            )
            if not problem:
                return None
            problem = problem["problem"]
            assert isinstance(problem, Problem)

            stmt = select(GuildForumChannel).where(
                GuildForumChannel.guild_id == guild_id
            )
            forum_channel = db.execute(stmt).scalars().first()
            if not forum_channel:
                return None

            stmt = select(ProblemThreads).where(
                ProblemThreads.problem_db_id == problem.id,
                ProblemThreads.forum_channel_db_id == forum_channel.id,
            )
            problem_thread = db.execute(stmt).scalars().first()
            self.logger.debug(problem_thread)
            if problem_thread:
                return problem_thread
        return None

    async def create_thread_in_db(
        self, problem_frontend_id: int, guild_id: int, thread_id: int
    ) -> None:
        self.logger.info(
            f"Creating problem thread in DB for problem ID {problem_frontend_id} in guild {guild_id} with thread ID {thread_id}."
        )
        with self.database_manager as db:
            problem_threads_instance = await self.create_thread_instance(
                problem_frontend_id=problem_frontend_id,
                guild_id=guild_id,
                thread_id=thread_id,
            )
            if not problem_threads_instance:
                raise ValueError(
                    f"Could not create ProblemThreads instance for problem ID {problem_frontend_id} in guild {guild_id} with thread ID {thread_id}."
                )
            db.add(problem_threads_instance)
        problem_thread = await self.get_thread_by_thread_id(thread_id)
        assert problem_thread is not None
        self.problem_threads[thread_id] = problem_thread

    async def create_thread_instance(
        self, problem_frontend_id: int, guild_id: int, thread_id: int
    ) -> ProblemThreads | None:
        self.logger.debug(
            f"Creating ProblemThreads instance for problem ID {problem_frontend_id} in guild {guild_id} with thread ID {thread_id}."
        )
        forum_channel = await self.get_forum_channel(guild_id)
        if not forum_channel:
            raise ForumChannelNotFound(f"Forum channel for guild {guild_id} not found.")
        problem = await self.leetcode_problem_manager.get_problem_with_frontend_id(
            problem_frontend_id
        )
        if not problem:
            return None
        problem = problem["problem"]
        self.logger.debug(f"Fetched problem from LeetCodeProblemManager: {problem}")
        assert isinstance(problem, Problem)
        problem_thread = ProblemThreads(
            thread_id=thread_id,
            problem_db_id=problem.id,
            forum_channel_db_id=forum_channel.id,
        )
        return problem_thread

    async def bulk_upsert_thread_to_db(
        self, problem_threads: Dict[int, ProblemThreads]
    ) -> None:
        if not problem_threads:
            self.logger.warning("No problem threads to upsert.")
            raise ValueError("No problem threads to upsert.")
        self.logger.info(
            f"Bulk upserting {len(problem_threads)} problem threads to DB."
        )
        with self.database_manager as db:
            self.logger.debug(
                f"Problem threads to upsert: {[pt.to_dict() for pt in problem_threads.values()]}"
            )
            upsert_stmt = sqlite_upsert(ProblemThreads)
            upsert_stmt = upsert_stmt.on_conflict_do_update(
                index_elements=["thread_id"],
                set_={
                    "problem_db_id": upsert_stmt.excluded.problem_db_id,
                    "forum_channel_db_id": upsert_stmt.excluded.forum_channel_db_id,
                },
            )
            db.execute(upsert_stmt, [pt.to_dict() for pt in problem_threads.values()])

        await self.init_cache()

    async def delete_thread_from_db(self, thread_id: int) -> None:
        self.logger.info(f"Deleting problem thread with thread ID {thread_id} from DB.")
        with self.database_manager as db:
            stmt = select(ProblemThreads).where(ProblemThreads.thread_id == thread_id)
            problem_thread = db.execute(stmt).scalars().first()
            if problem_thread:
                self.logger.debug(f"Deleting problem thread: {problem_thread}")
                db.delete(problem_thread)
                db.commit()
                if thread_id in self.problem_threads:
                    del self.problem_threads[thread_id]

    async def _create_thread(
        self,
        channel: ForumChannel,
        problem: Problem,
        problem_tags: Set[TopicTags],
        bot: commands.Bot,
    ) -> ThreadWithMessage:
        self.logger.info(
            f"Creating thread in channel {channel.id} for problem {problem.problem_frontend_id}"
        )
        thread_name = f"{problem.problem_frontend_id}. {problem.title}"
        thread_content = f"{problem.url}\n"
        if problem.premium:
            thread_content += (
                "This problem is premium only, so there is no description available."
            )
        thread_embed = get_problem_desc_embed(
            problem=problem, problem_tags=problem_tags, bot=bot
        )
        available_tags = channel.available_tags
        available_tag_names = {tag.name for tag in channel.available_tags}

        self.logger.debug(
            f"Available tags in channel {channel.id}: {available_tag_names}"
        )

        tags_to_create = {
            "LeetCode",
            "Easy",
            "Medium",
            "Hard",
        } - available_tag_names
        for tag_name in tags_to_create:
            await channel.create_tag(name=tag_name)

        tags_to_assign = {
            "LeetCode",
            get_difficulty_str_repr(problem.difficulty),
        }

        thread = await channel.create_thread(
            name=thread_name,
            content=thread_content,
            embed=thread_embed,
            applied_tags=[tag for tag in available_tags if tag.name in tags_to_assign],
        )
        await self.create_thread_in_db(
            problem_frontend_id=problem.problem_frontend_id,
            guild_id=channel.guild.id,
            thread_id=thread.thread.id,
        )
        return thread

    async def reopen_or_create_problem_thread(
        self,
        problem: Dict[Literal["problem", "tags"], Problem | Set[TopicTags]],
        guild: Guild,
        bot: commands.Bot,
        is_daily: bool,
    ) -> Tuple[ThreadWithMessage | Thread, ThreadCreationEnum]:
        """
        Reopen an existing thread for the problem in the guild's forum channel, or create a new one if it doesn't exist.
        Raises:
        ForumChannelNotFound if the forum channel is not set for the guild.
        FetchError if there is an error fetching the channel or thread.

        Returns: A tuple containing the thread and a ThreadCreationEnum indicating whether the thread was created or reopened.
        """

        problem_obj = problem["problem"]
        assert isinstance(problem_obj, Problem)
        assert isinstance(problem["tags"], Set)
        channel = await self.get_forum_channel(guild_id=guild.id)
        self.logger.debug(f"Forum channel fetched: {channel}")
        if not channel:
            raise ForumChannelNotFound(
                "The bot doesn't know which Fourm Channel should the problem be created! Please use /set_thread_channel first to set the Fourm Channel!"
            )
        forum_channel = await try_get_channel(
            guild=guild, channel_id=channel.channel_id
        )

        self.logger.debug(f"Forum channel object: {forum_channel}")

        if not isinstance(forum_channel, ForumChannel):
            raise ForumChannelNotFound(
                "Something went wrong! The forum channel is not found or not a valid forum channel. Contact the developer for help."
            )
        problem_stat = "today's problem" if is_daily else f"problem {problem_obj.id}"
        forum_thread = await self.get_thread_by_problem_id(
            problem_obj.problem_frontend_id, guild.id
        )
        self.logger.debug(f"Forum thread fetched: {forum_thread}")

        self.logger.info(
            f"Creating or fetching thread for {problem_stat} in guild {guild.id}"
        )
        if not forum_thread:
            thread = await self._create_thread(
                channel=forum_channel,
                problem=problem_obj,
                problem_tags=problem["tags"],
                bot=bot,
            )
            return thread, ThreadCreationEnum.CREATE
        thread_channel = await try_get_channel(
            guild=guild, channel_id=forum_thread.thread_id
        )
        if not thread_channel:
            self.logger.warning(
                "The thread for today's problem was supposed to exist but cannot be found."
            )

            await self.delete_thread_from_db(thread_id=forum_thread.thread_id)
            thread = await self._create_thread(
                channel=forum_channel,
                problem=problem_obj,
                problem_tags=problem["tags"],
                bot=bot,
            )
            self.logger.info(
                f"Created new thread in channel {forum_channel.id} for {problem_stat}"
            )
            return thread, ThreadCreationEnum.CREATE
        assert isinstance(thread_channel, Thread)
        return thread_channel, ThreadCreationEnum.REOPEN
