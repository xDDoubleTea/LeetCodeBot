from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class LeetCodeDCLink(Base):
    __tablename__ = "leetcode_discord_link"

    discord_user_id: Mapped[int] = mapped_column(primary_key=True)
    leetcode_user_name: Mapped[str] = mapped_column(nullable=False, unique=True)

    def to_dict(self) -> dict:
        return {
            "discord_user_id": self.discord_user_id,
            "leetcode_user_name": self.leetcode_user_name,
        }

    def __repr__(self) -> str:
        return f"LeetCodeDCLinkDB(leetcode_user_name={self.leetcode_user_name}, discord_user_id={self.discord_user_id})"
