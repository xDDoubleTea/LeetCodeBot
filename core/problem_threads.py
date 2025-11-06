from typing import Dict
from sqlalchemy.sql import select
from db.database_manager import DatabaseManager
from db.problem import Problem
from db.thread_channel import GuildForumChannel
from db.problem_threads import ProblemThreads
from core.leetcode_problem import LeetCodeProblemManager
from config.secrets import debug


class ProblemThreadsManager:
    def __init__(
        self,
        database_manager: DatabaseManager,
        leetcode_problem_manager: LeetCodeProblemManager,
    ) -> None:
        self.database_manager: DatabaseManager = database_manager
        self.leetcode_problem_manager: LeetCodeProblemManager = leetcode_problem_manager
        self.problem_threads: Dict[int, ProblemThreads] = {}
        self.forum_channels: Dict[int, GuildForumChannel] = {}

    async def init_cache(self):
        with self.database_manager as db:
            if debug:
                print("Initializing ProblemThreadsManager Cache...")
            stmt = select(ProblemThreads)
            result = db.execute(stmt).scalars().all()
            if debug:
                print(f"Loaded {len(result)} problem threads from the database.")
                print(result)
            for problem_thread in result:
                self.problem_threads[problem_thread.thread_id] = problem_thread
            if debug:
                print("Loading GuildForumChannels...")
            stmt = select(GuildForumChannel)
            result = db.execute(stmt).scalars().all()
            if debug:
                print(f"Loaded {len(result)} problem threads from the database.")
                print(result)
            for forum_channel in result:
                self.forum_channels[forum_channel.guild_id] = forum_channel

    async def add_forum_channel_to_db(self, guild_id: int, channel_id: int) -> None:
        with self.database_manager as db:
            stmt = select(GuildForumChannel).where(
                GuildForumChannel.guild_id == guild_id
            )
            forum_channel = db.execute(stmt).scalars().first()
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
        if res := self.problem_threads.get(thread_id, None):
            return res

        with self.database_manager as db:
            stmt = select(ProblemThreads).where(ProblemThreads.thread_id == thread_id)
            problem_thread = db.execute(stmt).scalars().first()
            if problem_thread:
                return problem_thread
        return None

    async def get_thread_by_problem_id(
        self, problem_id: int, guild_id: int
    ) -> ProblemThreads | None:
        with self.database_manager as db:
            problem = await self.leetcode_problem_manager.get_problem(problem_id)
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
            if debug:
                print(problem_thread)
            if problem_thread:
                return problem_thread
        return None

    async def create_thread_in_db(
        self, problem_id: int, guild_id: int, thread_id: int
    ) -> None:
        with self.database_manager as db:
            forum_channel = await self.get_forum_channel(guild_id)
            if not forum_channel:
                return None

            problem = await self.leetcode_problem_manager.get_problem(problem_id)
            if not problem:
                return None
            problem = problem["problem"]
            print(problem)
            assert isinstance(problem, Problem)

            problem_thread = ProblemThreads(
                thread_id=thread_id,
                problem_db_id=problem.id,
                forum_channel_db_id=forum_channel.id,
            )
            db.add(problem_thread)
            db.commit()
            self.problem_threads[thread_id] = problem_thread
