import discord
from discord import Message, Interaction, Embed, SelectOption
from discord.ui import Button, View, button, Select
from typing import Any, Callable, Generic, Optional, List, TypeVar, Awaitable

from models.pagination import (
    BasePaginationMetaData,
    PaginationViewButtonLayouts,
    ProblemTitlePaginationMetaData,
)

T_meta = TypeVar("T_meta", bound=BasePaginationMetaData)


class BasePaginationView(View, Generic[T_meta]):
    def __init__(
        self,
        *,
        timeout: Optional[int] = 180,
        metadata: T_meta,
        data: List[Any],
        format_page: Callable[[T_meta, List[Any]], Embed],
        items_per_page: int = 10,
        attached_message: Optional[Message] = None,
        ephemeral=True,
        select_options_builder: Optional[
            Callable[[List[Any]], List[SelectOption]]
        ] = None,
        select_callback: Optional[
            Callable[[Interaction, "BasePaginationView", List[str]], Awaitable[None]]
        ] = None,
        select_placeholder: str = "Select an option...",
    ):
        super().__init__(timeout=timeout)
        self.metadata = metadata
        self.data = data
        self.format_page = format_page
        self.items_per_page = items_per_page
        self.attached_message = attached_message
        self.current_page = 0
        self.total_pages = (len(data) + items_per_page - 1) // items_per_page
        if self.total_pages == 0:
            self.total_pages = 1
        self.ephemeral = ephemeral

        self.select_options_builder = select_options_builder
        self.select_callback = select_callback
        self.select_menu: Optional[Select] = None

        if self.select_options_builder is None or self.select_callback is None:
            return

        self.select_menu = Select(
            placeholder=select_placeholder, min_values=1, max_values=1
        )

        async def _menu_callback(interaction: Interaction):
            assert self.select_menu and self.select_callback
            await self.select_callback(interaction, self, self.select_menu.values)

        self.select_menu.callback = _menu_callback
        self.add_item(self.select_menu)

        self._update_select_options()

    def _get_current_page_data(self) -> List[Any]:
        start = self.current_page * self.items_per_page
        end = min(start + self.items_per_page, len(self.data))
        return self.data[start:end]

    def _update_select_options(self) -> None:
        if not self.select_menu or not self.select_options_builder:
            return

        current_data = self._get_current_page_data()
        options = self.select_options_builder(current_data)

        if not options:
            self.select_menu.disabled = True
            self.select_menu.options = [
                SelectOption(label="No options available", value="none")
            ]
        else:
            self.select_menu.disabled = False
            self.select_menu.options = options

    def _get_embed(self) -> Embed:
        start = self.current_page * self.items_per_page
        end = min(start + self.items_per_page, len(self.data))
        return self.format_page(
            self.metadata,
            self.data[start:end],
        )

    async def send_initial_message(
        self, interaction: Interaction, followup: bool = False
    ):
        """Sends the initial message and stores it for later edits."""
        self._update_button_states()
        embed = self._get_embed()
        if followup:
            await interaction.followup.send(embed=embed, view=self)
        else:
            await interaction.response.send_message(
                embed=embed, view=self, ephemeral=self.ephemeral
            )
        self.attached_message = await interaction.original_response()

    def _update_button_states(self):
        for item in self.children:
            if isinstance(item, Button):
                match item.custom_id:
                    case PaginationViewButtonLayouts.FIRST_PAGE.name:
                        item.disabled = self.current_page <= 0
                    case PaginationViewButtonLayouts.PREV_PAGE.name:
                        item.disabled = self.current_page <= 0
                    case PaginationViewButtonLayouts.PAGE_DISPLAY.name:
                        item.label = f"{self.current_page + 1} / {self.total_pages}"
                    case PaginationViewButtonLayouts.NEXT_PAGE.name:
                        item.disabled = self.current_page >= self.total_pages - 1
                    case PaginationViewButtonLayouts.LAST_PAGE.name:
                        item.disabled = self.current_page >= self.total_pages - 1

    async def _update_page(self, interaction: Interaction):
        self._update_select_options()
        embed = self._get_embed()
        self._update_button_states()
        await interaction.response.edit_message(embed=embed, view=self)

    @button(
        label="First page⏮️",
        style=discord.ButtonStyle.blurple,
        disabled=True,
        custom_id=PaginationViewButtonLayouts.FIRST_PAGE.name,
    )
    async def first_callback(self, interaction: Interaction, button: Button):
        self.current_page = 0
        await self._update_page(interaction)

    @button(
        label="Prev◀️",
        style=discord.ButtonStyle.blurple,
        custom_id=PaginationViewButtonLayouts.PREV_PAGE.name,
    )
    async def pre_callback(self, interaction: Interaction, button: Button):
        self.current_page = max(self.current_page - 1, 0)
        await self._update_page(interaction)

    @button(
        label="1/1",
        style=discord.ButtonStyle.blurple,
        custom_id=PaginationViewButtonLayouts.PAGE_DISPLAY.name,
    )
    async def page_display_btn(self, interaction: Interaction, button: Button):
        await interaction.response.defer(ephemeral=self.ephemeral)

    @button(
        label="Next▶️",
        style=discord.ButtonStyle.blurple,
        custom_id=PaginationViewButtonLayouts.NEXT_PAGE.name,
    )
    async def next_callback(self, interaction: Interaction, button: Button):
        self.current_page = min(self.current_page + 1, self.total_pages - 1)
        await self._update_page(interaction)

    @button(
        label="Last page⏭️",
        style=discord.ButtonStyle.blurple,
        custom_id=PaginationViewButtonLayouts.LAST_PAGE.name,
    )
    async def last_callback(self, interaction: Interaction, button: Button):
        self.current_page = self.total_pages - 1
        await self._update_page(interaction)

    async def on_timeout(self) -> None:
        if self.attached_message:
            try:
                for item in self.children:
                    if isinstance(item, Button):
                        if (
                            item.custom_id
                            == PaginationViewButtonLayouts.PAGE_DISPLAY.name
                        ):
                            item.label = "Expired..."
                        item.style = discord.ButtonStyle.grey
                        item.disabled = True
                    if isinstance(item, Select):
                        item.disabled = True
                        item.placeholder = "Expired..."
                await self.attached_message.edit(view=self)
            except discord.NotFound:
                return


class ProblemTitlePaginationView(BasePaginationView[ProblemTitlePaginationMetaData]):
    def __init__(
        self,
        *,
        timeout: Optional[int] = 180,
        metadata: ProblemTitlePaginationMetaData,
        data: List[Any],
        format_page: Callable[[ProblemTitlePaginationMetaData, List[Any]], Embed],
        items_per_page: int = 10,
        attached_message: Optional[Message] = None,
        ephemeral=True,
        select_options_builder: Optional[
            Callable[[List[Any]], List[SelectOption]]
        ] = None,
        select_callback: Optional[
            Callable[[Interaction, "BasePaginationView", List[str]], Awaitable[None]]
        ] = None,
        select_placeholder: str = "Select an option...",
    ):
        super().__init__(
            timeout=timeout,
            metadata=metadata,
            data=data,
            format_page=format_page,
            items_per_page=items_per_page,
            attached_message=attached_message,
            ephemeral=ephemeral,
            select_callback=select_callback,
            select_options_builder=select_options_builder,
            select_placeholder=select_placeholder,
        )
