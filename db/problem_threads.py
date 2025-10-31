from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from db.problem import Problem
from db.base import Base
from db.thread_channel import GuildForumChannel


class ProblemThreads(Base):
    __tablename__ = "problem_threads"
    id: Mapped[int] = mapped_column(primary_key=True)
    problem_db_id: Mapped[ForeignKey] = mapped_column(
        ForeignKey(Problem.id, ondelete="CASCADE"), nullable=False
    )
    forum_channel_db_id: Mapped[ForeignKey] = mapped_column(
        ForeignKey(GuildForumChannel.id, ondelete="CASCADE"), nullable=False
    )
    thread_id: Mapped[int] = mapped_column(nullable=False, unique=True)
