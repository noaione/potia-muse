import fnmatch
import logging

import discord
from discord.ext import commands
from phelper.bot import PotiaBot


class OwnerPandoraBox(commands.Cog):
    def __init__(self, bot: PotiaBot) -> None:
        self.bot = bot
        self.logger = logging.getLogger("Cogs.PandoraBox")

    def match_pattern(self, pattern: str):
        if pattern.startswith("cogs."):
            return pattern.replace("cogs.", "")
        if not pattern:
            return []
        all_cogs = self.bot.available_extensions()
        all_cogs = list(map(lambda x: x.replace("cogs.", ""), all_cogs))
        return list(filter(lambda x: fnmatch.fnmatch(x, pattern), all_cogs))

    @commands.command()
    @commands.is_owner()
    async def reserve(self, ctx: commands.Context, text: str):
        channel_data: discord.TextChannel = ctx.channel
        text = text.lower()
        if "embed" in text:
            embed = discord.Embed()
            embed.description = "*Reserved for later usage*"
            await channel_data.send(embed=embed)
        else:
            await channel_data.send(content="*Reserved for later usage*")

    @commands.command(name="reload")
    @commands.is_owner()
    async def _bbmod_reload(self, ctx: commands.Context, *, cog_match: str = None):
        if not cog_match:
            ALL_COGS = self.bot.available_extensions()
            helpcmd = self.bot.create_help(ctx, "Reload", desc="Reload a bot module")
            helpcmd.embed.add_field(
                name="Module/Cogs list", value="\n".join(["- " + cl for cl in ALL_COGS]), inline=False
            )
            return await ctx.send(embed=helpcmd.get())

        matched_cogs = self.match_pattern(cog_match)
        if not matched_cogs:
            return await ctx.send("No match found!")

        reloaded_module = []
        msg: discord.Message = await ctx.send(f"Please wait, reloading {len(matched_cogs)} module...")
        for cogs in matched_cogs:
            if not cogs.startswith("cogs."):
                cogs = "cogs." + cogs
            self.logger.info(f"Trying to reload {cogs}")

            try:
                self.bot.reload_extension(cogs)
                reloaded_module.append(cogs)
            except (commands.ExtensionNotFound, ModuleNotFoundError):
                self.logger.warning(f"{cogs} doesn't exist")
            except commands.ExtensionNotLoaded:
                self.logger.warning(f"{cogs} is not loaded yet, trying to load it...")
                try:
                    self.bot.load_extension(cogs)
                except (commands.ExtensionNotFound, ModuleNotFoundError):
                    pass
                except commands.ExtensionError as cer:
                    self.logger.error(f"Failed to load {cogs}")
                    self.bot.echo_error(cer)
            except commands.ExtensionError as cef:
                self.logger.error(f"Failed to reload {cogs}")
                self.bot.echo_error(cef)

        if not reloaded_module:
            await msg.edit(content="No module reloaded, what the hell?")
        else:
            reloaded_module = list(map(lambda x: f"`{x}`", reloaded_module))
            await msg.edit(content=f"Successfully (re)loaded {', '.join(reloaded_module)} modules.")
            if len(reloaded_module) != len(matched_cogs):
                await msg.edit(content="But some modules failed to reload, check the logs.")

    @commands.command(name="load")
    @commands.is_owner()
    async def _bbmod_load(self, ctx: commands.Context, *, cogs: str = None):
        if not cogs:
            ALL_COGS = self.bot.available_extensions()
            helpcmd = self.bot.create_help(ctx, "Load", desc="Load a bot module")
            helpcmd.embed.add_field(
                name="Module/Cogs list", value="\n".join(["- " + cl for cl in ALL_COGS]), inline=False
            )
            return await ctx.send(embed=helpcmd.get())

        if not cogs.startswith("cogs."):
            cogs = "cogs." + cogs
        self.logger.info(f"Trying to load {cogs}")
        msg: discord.Message = await ctx.send("Please wait, loading module...")

        try:
            self.bot.load_extension(cogs)
        except commands.ExtensionAlreadyLoaded:
            self.logger.warning(f"{cogs} already loaded")
            return await msg.edit(content="The module is already loaded!")
        except (commands.ExtensionNotFound, ModuleNotFoundError):
            self.logger.warning(f"{cogs} doesn't exist")
            return await msg.edit(content="Unable to find that module!")
        except commands.ExtensionError as cef:
            self.logger.error(f"Failed to load {cogs}")
            self.bot.echo_error(cef)
            return await msg.edit(content="Failed to load module, please check bot log!")

        await msg.edit(content=f"Successfully loaded `{cogs}` module.")

    @commands.command(name="unload")
    @commands.is_owner()
    async def _bbmod_unload(self, ctx: commands.Context, *, cogs: str = None):
        if not cogs:
            ALL_COGS = self.bot.available_extensions()
            helpcmd = self.bot.create_help(ctx, "Unload", desc="Unload a bot module")
            helpcmd.embed.add_field(
                name="Module/Cogs list", value="\n".join(["- " + cl for cl in ALL_COGS]), inline=False
            )
            return await ctx.send(embed=helpcmd.get())

        if not cogs.startswith("cogs."):
            cogs = "cogs." + cogs
        self.logger.info(f"Trying to load {cogs}")
        msg: discord.Message = await ctx.send("Please wait, unloading module...")

        try:
            self.bot.unload_extension(cogs)
        except commands.ExtensionNotLoaded:
            self.logger.warning(f"{cogs} already unloaded")
            return await msg.edit(content="The module is not yet loaded! (already unloaded)")
        except (commands.ExtensionNotFound, ModuleNotFoundError):
            self.logger.warning(f"{cogs} doesn't exist")
            return await msg.edit(content="Unable to find that module!")
        except commands.ExtensionError as cef:
            self.logger.error(f"Failed to reload {cogs}")
            self.bot.echo_error(cef)
            return await msg.edit(content="Failed to unload module, please check bot log!")

        await msg.edit(content=f"Successfully unloaded `{cogs}` module.")


def setup(bot: PotiaBot):
    bot.add_cog(OwnerPandoraBox(bot))
