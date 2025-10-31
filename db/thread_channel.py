from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import ForeignKey
from db.base import Base


class GuildForumChannel(Base):
    __tablename__ = "guild_forum_channel"
    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(nullable=False, unique=True)
    guild_id: Mapped[int] = mapped_column(nullable=False)


class GuildForumChannelTags(Base):
    __tablename__ = "guild_forum_channel_tags"
    id: Mapped[int] = mapped_column(primary_key=True)
    forum_channel_id: Mapped[ForeignKey] = mapped_column(
        ForeignKey(GuildForumChannel.id, ondelete="CASCADE"), nullable=False
    )
    tag_name: Mapped[str] = mapped_column(nullable=False)
