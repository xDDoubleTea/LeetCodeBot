from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import ForeignKey

from db.base import Base


class Problem(Base):
    __tablename__ = "problems"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(nullable=False)
    problem_id: Mapped[int] = mapped_column(nullable=False, unique=True)
    url: Mapped[str] = mapped_column(nullable=False)
    difficulty: Mapped[int] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "problem_id": self.problem_id,
            "url": self.url,
            "difficulty": self.difficulty,
            "description": self.description,
        }


class TopicTags(Base):
    __tablename__ = "topic_tags"
    id: Mapped[int] = mapped_column(primary_key=True)
    tag_name: Mapped[str] = mapped_column(nullable=False, unique=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tag_name": self.tag_name,
        }


class ProblemTags(Base):
    __tablename__ = "problem_tags"
    id: Mapped[int] = mapped_column(primary_key=True)
    problem_id: Mapped[ForeignKey] = mapped_column(
        ForeignKey(Problem.id, ondelete="CASCADE"), nullable=False
    )
    tag_id: Mapped[ForeignKey] = mapped_column(
        ForeignKey(TopicTags.id, ondelete="CASCADE"), nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "problem_id": self.problem_id,
            "tag_id": self.tag_id,
        }
