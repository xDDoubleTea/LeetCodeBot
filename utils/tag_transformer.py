import logging
from typing import TYPE_CHECKING, Any, cast

from discord import Interaction, app_commands

if TYPE_CHECKING:
    from main import LeetCodeBot

logger = logging.getLogger(__name__)


def _valid_tags(interaction: Interaction) -> list[str]:
    # Deliberately not getattr with a default. This used to read a `tag_cache`
    # attribute off the bot, and when that attribute moved onto the problem
    # manager the default silently turned every tag into "not found" instead of
    # raising. A missing attribute should break loudly here.
    bot = cast("LeetCodeBot", interaction.client)
    return bot.leetcode_problem_manger.tag_cache_literal


class TagTransformer(app_commands.Transformer):
    async def autocomplete(
        self, interaction: Interaction, value: str | int | float, /
    ) -> list[app_commands.Choice]:
        assert isinstance(value, str)
        valid_tags = _valid_tags(interaction)
        matches = [tag for tag in valid_tags if value.lower() in tag.lower()][:25]
        return [app_commands.Choice(name=tag, value=tag) for tag in matches]

    async def transform(self, interaction: Interaction, value: str, /) -> Any:
        valid_tags = _valid_tags(interaction)
        if value in valid_tags:
            return value

        value_lower = value.lower()
        for tag in valid_tags:
            if tag.lower() == value_lower:
                return tag

        raise ValueError(f"Tag '{value}' not found.")
