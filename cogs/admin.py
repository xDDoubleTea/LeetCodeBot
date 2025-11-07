from discord import TextChannel
from discord.ext import commands
import discord
from discord.ext.commands import Context, Cog, ExtensionNotFound
from discord.ext.commands.core import ExtensionFailed
from discord.ext.commands.errors import (
    ExtensionAlreadyLoaded,
    ExtensionNotLoaded,
    CommandError,
)
from utils.checks import is_me_command, IsNotDev


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
        finally:
            return None

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
        finally:
            return None

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
        finally:
            return None

    @commands.command(name="ext_list", hidden=True)
    @is_me_command()
    async def ext_list(self, ctx: Context):
        await ctx.send("All loaded extensions list:\n")
        return await ctx.send(
            "\n".join(s.split("cogs.")[1] for s in self.bot.extensions)
        )

    @commands.command(name="sync_app_commands", hidden=True)
    @is_me_command()
    async def sync_app_commands(self, ctx: Context):
        assert ctx.guild is not None
        self.bot.tree.copy_global_to(guild=discord.Object(id=ctx.guild.id))
        synced = await self.bot.tree.sync(guild=ctx.guild)
        await ctx.send(f"Synced {len(synced)} app commands globally.")

    @commands.command(name="purge_msg", hidden=True, aliases=["purge"])
    @commands.has_permissions(administrator=True)
    async def purge_msg(self, ctx: Context, limit: int):
        try:
            assert isinstance(ctx.channel, TextChannel)
            await ctx.channel.purge(limit=limit)
        except AssertionError:
            return
        else:
            return

    @load.error
    async def load_error(self, ctx: Context, error: CommandError):
        if isinstance(error, IsNotDev):
            await ctx.send(error.message)

    @unload.error
    async def unload_error(self, ctx: Context, error: CommandError):
        if isinstance(error, IsNotDev):
            await ctx.send(error.message)

    @reload.error
    async def reload_error(self, ctx: Context, error: CommandError):
        if isinstance(error, IsNotDev):
            await ctx.send(error.message)

    @ext_list.error
    async def ext_list_error(self, ctx: Context, error: CommandError):
        if isinstance(error, IsNotDev):
            await ctx.send(error.message)


async def setup(client):
    await client.add_cog(admin(client))
