from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base
from db.problem import Problem


class ProblemOpen(Base):
    """One problem thread opened or reopened by a user through a command."""

    __tablename__ = "problem_opens"
    id: Mapped[int] = mapped_column(primary_key=True)
    discord_user_id: Mapped[int] = mapped_column(nullable=False)
    guild_id: Mapped[int] = mapped_column(nullable=False)
    problem_db_id: Mapped[int] = mapped_column(
        ForeignKey(Problem.id, ondelete="CASCADE"), nullable=False
    )
    command: Mapped[str] = mapped_column(nullable=False)
    opened_at: Mapped[datetime] = mapped_column(nullable=False)

    def __repr__(self) -> str:
        return f"ProblemOpen(id={self.id}, discord_user_id={self.discord_user_id}, problem_db_id={self.problem_db_id}, command={self.command}, opened_at={self.opened_at})"


class ThreadSolution(Base):
    """One message with a fenced code block, posted in a problem thread."""

    __tablename__ = "thread_solutions"
    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(nullable=False, unique=True)
    thread_id: Mapped[int] = mapped_column(nullable=False)
    discord_user_id: Mapped[int] = mapped_column(nullable=False)
    problem_db_id: Mapped[int] = mapped_column(
        ForeignKey(Problem.id, ondelete="CASCADE"), nullable=False
    )
    language: Mapped[str | None] = mapped_column(nullable=True)
    posted_at: Mapped[datetime] = mapped_column(nullable=False)

    def __repr__(self) -> str:
        return f"ThreadSolution(id={self.id}, message_id={self.message_id}, discord_user_id={self.discord_user_id}, problem_db_id={self.problem_db_id}, language={self.language})"
