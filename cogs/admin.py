import logging

from discord.ext import commands
from discord.ext.commands import Cog, Context, ExtensionFailed, ExtensionNotFound
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
        joined yet, so a new server needs no action. `guild` copies the tree to
        the current server only, which is the fast path while developing --
        those copies shadow the global ones, so a stale guild copy hides a
        working global command until it is cleared.
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


async def setup(client):
    await client.add_cog(admin(client))
