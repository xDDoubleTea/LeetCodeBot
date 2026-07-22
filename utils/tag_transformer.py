from discord import app_commands, Interaction


from typing import List, Any, Union
import logging

logger = logging.getLogger(__name__)


class TagTransformer(app_commands.Transformer):
    async def autocomplete(
        self, interaction: Interaction, value: Union[str, int, float], /
    ) -> List[app_commands.Choice]:
        assert isinstance(value, str)
        valid_tags: List[str] = getattr(interaction.client, "tag_cache", [])
        matches = [tag for tag in valid_tags if value.lower() in tag.lower()][:25]
        return [app_commands.Choice(name=tag, value=tag) for tag in matches]

    async def transform(self, interaction: Interaction, value: str, /) -> Any:
        valid_tags: List[str] = getattr(interaction.client, "tag_cache", [])
        if value in valid_tags:
            return value

        value_lower = value.lower()
        for tag in valid_tags:
            if tag.lower() == value_lower:
                return tag

        raise ValueError(f"Tag '{value}' not found.")
