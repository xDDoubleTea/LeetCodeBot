from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class ProblemList(Base):
    __tablename__ = "problem_list"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False, unique=True)
    problem_frontend_id: Mapped[list[int]] = mapped_column(nullable=False, unique=True)
    discord_user_id: Mapped[int] = mapped_column(nullable=False)
