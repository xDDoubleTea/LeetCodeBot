from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import Column, ForeignKey, Table
from db.base import Base

problem_tags_association = Table(
    "problem_tags",
    Base.metadata,
    Column(
        "problem_id", ForeignKey("problems.id", ondelete="CASCADE"), primary_key=True
    ),
    Column("tag_id", ForeignKey("topic_tags.id", ondelete="CASCADE"), primary_key=True),
)


class Problem(Base):
    __tablename__ = "problems"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(nullable=False)
    problem_id: Mapped[int] = mapped_column(nullable=False, unique=True)
    url: Mapped[str] = mapped_column(nullable=False)
    difficulty: Mapped[int] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(nullable=True)

    tags: Mapped[list["TopicTags"]] = relationship(
        secondary=problem_tags_association,
        back_populates="problems",
        cascade="all, delete",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "problem_id": self.problem_id,
            "url": self.url,
            "difficulty": self.difficulty,
            "description": self.description,
            "tags": [tag.to_dict() for tag in self.tags],
        }

    def __repr__(self) -> str:
        return f"Problem(id={self.id}, title={self.title}, problem_id={self.problem_id}, url={self.url}, difficulty={self.difficulty}, description={self.description})"


class TopicTags(Base):
    __tablename__ = "topic_tags"
    id: Mapped[int] = mapped_column(primary_key=True)
    tag_name: Mapped[str] = mapped_column(nullable=False, unique=True)
    problems: Mapped[list["Problem"]] = relationship(
        secondary=problem_tags_association, back_populates="tags"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tag_name": self.tag_name,
        }

    def __repr__(self) -> str:
        return f"TopicTags(id={self.id}, tag_name={self.tag_name})"
