import logging

import discord
from discord.ext import commands
from discord.ext.commands import Cog, Context, ExtensionNotFound
from discord.ext.commands.core import ExtensionFailed
from discord.ext.commands.errors import ExtensionAlreadyLoaded, ExtensionNotLoaded

from utils.checks import is_me_command

logger = logging.getLogger(__name__)


class admin(Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="load", hidden=True)
    @is_me_command()
    async def load(self, ctx: Context, ext_name: str):
        try:
            await self.bot.load_extension("cogs." + ext_name)
        except ExtensionAlreadyLoaded:
            await ctx.send(f"{ext_name} has already been loaded!")
        except ExtensionFailed:
            await ctx.send(f"{ext_name} failed loading!")
        except ExtensionNotFound:
            await ctx.send(f"{ext_name} is not a legal extension name!")
        else:
            await ctx.send(f"{ext_name} has been sucessfully loaded!")

    @commands.command(name="unload", hidden=True)
    @is_me_command()
    async def unload(self, ctx: Context, ext_name: str):
        if ext_name == "admin":
            return await ctx.send(
                "You cannot unload the admin cog as it contains the load extension command"
            )
        try:
            await self.bot.unload_extension("cogs." + ext_name)
        except ExtensionNotLoaded:
            await ctx.send(f"{ext_name} wasn't loaded!")
        except ExtensionFailed:
            await ctx.send(f"{ext_name} failed unloading!")
        except ExtensionNotFound:
            await ctx.send(f"{ext_name} is not a legal extension name!")
        else:
            await ctx.send(f"{ext_name} has been sucessfully unloaded!")

    @commands.command(name="reload", hidden=True)
    @is_me_command()
    async def reload(self, ctx: Context, ext_name: str):
        try:
            await self.bot.reload_extension("cogs." + ext_name)
        except ExtensionFailed:
            await ctx.send(f"{ext_name} failed loading!")
        except ExtensionNotFound:
            await ctx.send(f"{ext_name} is not a legal extension name!")
        else:
            await ctx.send(f"{ext_name} has been sucessfully reloaded!")

    @commands.command(name="ext_list", hidden=True)
    @is_me_command()
    async def ext_list(self, ctx: Context):
        await ctx.send("All loaded extensions list:\n")
        return await ctx.send(
            "\n".join(s.split("cogs.")[1] for s in self.bot.extensions)
        )

    @commands.command(name="sync_app_commands", hidden=True)
    @is_me_command()
    async def sync_app_commands(self, ctx: Context, scope: str = "global"):
        """
        Publish the command tree.

        `global` is what every guild sees, including guilds the bot has not
        joined yet, so a new server needs no action.

        `guild` copies the tree into the current server, which appears
        immediately and is the fast path while developing. It does not replace
        the global commands: Discord lists guild-scoped and global commands side
        by side, so running both leaves two of everything in the picker. Use it
        on a development server only, and clear it with clear_guild_commands.
        """
        if scope == "guild":
            assert ctx.guild is not None
            self.bot.tree.copy_global_to(guild=ctx.guild)
            synced = await self.bot.tree.sync(guild=ctx.guild)
            await ctx.send(f"Synced {len(synced)} app commands to this guild.")
            return

        if scope != "global":
            await ctx.send("Scope must be `global` or `guild`.")
            return

        synced = await self.bot.tree.sync()
        await ctx.send(f"Synced {len(synced)} app commands globally.")

    @commands.command(name="clear_guild_commands", hidden=True)
    @is_me_command()
    async def clear_guild_commands(self, ctx: Context, target: str = "here"):
        """
        Remove the guild-scoped copies that duplicate the global commands.

        `here` for this server, `all` for every server the bot is in, or a guild
        id. The global commands are untouched, so nothing is lost -- the copies
        were only ever a faster path to the same tree.
        """
        if target == "all":
            guilds: list[discord.abc.Snowflake] = list(self.bot.guilds)
        elif target == "here":
            if ctx.guild is None:
                await ctx.send("Run this in a server, or pass a guild id.")
                return
            guilds = [ctx.guild]
        else:
            try:
                guilds = [discord.Object(id=int(target))]
            except ValueError:
                await ctx.send("Target must be `here`, `all`, or a guild id.")
                return

        cleared = 0
        for guild in guilds:
            self.bot.tree.clear_commands(guild=guild)
            await self.bot.tree.sync(guild=guild)
            cleared += 1
        await ctx.send(
            f"Cleared guild-scoped commands from {cleared} server(s). "
            "The global commands are unaffected."
        )

    @commands.command(name="app_commands_audit", hidden=True)
    @is_me_command()
    async def app_commands_audit(self, ctx: Context):
        """
        Report which servers still hold guild-scoped copies.

        One HTTP call per server, so it is worth running once rather than in a
        loop.
        """
        global_commands = await self.bot.tree.fetch_commands()
        lines = [f"{len(global_commands)} global command(s)."]

        for guild in self.bot.guilds:
            guild_commands = await self.bot.tree.fetch_commands(guild=guild)
            if guild_commands:
                lines.append(
                    f"- {guild.name} ({guild.id}): {len(guild_commands)} "
                    "guild-scoped, showing as duplicates"
                )

        if len(lines) == 1:
            lines.append("No server holds guild-scoped copies.")
        await ctx.send("\n".join(lines))


async def setup(client):
    await client.add_cog(admin(client))
