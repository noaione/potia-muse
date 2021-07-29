import argparse
import asyncio
import functools
import logging
import os
import pathlib
import sys
import time
from datetime import timedelta, timezone

import coloredlogs
import discord
from discord.ext import commands

from phelper.bot import PotiaBot
from phelper.puppeeter import PuppeeterGenerator
from phelper.redis import RedisBridge
from phelper.utils import (
    HelpGenerator,
    __version__,
    explode_filepath_into_pieces,
    prefixes_with_data,
    read_files,
)
from phelper.welcomer import WelcomeGenerator

logging.getLogger("websockets").setLevel(logging.WARNING)

ALL_COGS_LIST = []
for (dirpath, dirnames, filenames) in os.walk(os.path.join(os.path.dirname(__file__), "cogs")):
    for filename in filenames:
        if filename.endswith(".py"):
            dirpath = dirpath.replace("\\", "/")
            if dirpath.startswith("./"):
                dirpath = dirpath[2:]
            expanded_path = ".".join(explode_filepath_into_pieces(dirpath))
            just_the_name = filename.replace(".py", "")
            ALL_COGS_LIST.append(f"{expanded_path}.{just_the_name}")


logger = logging.getLogger()
logging.basicConfig(
    level=logging.DEBUG,
    handlers=[],
    format="[%(asctime)s] - (%(name)s)[%(levelname)s](%(funcName)s): %(message)s",  # noqa: E501
    datefmt="%Y-%m-%d %H:%M:%S",
)

coloredlogs.install(
    fmt="[%(asctime)s %(hostname)s][%(levelname)s] (%(name)s[%(process)d]): %(funcName)s: %(message)s",
    level=logging.INFO,
    logger=logger,
    stream=sys.stdout,
)
logging.getLogger("discord").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("chardet").setLevel(logging.WARNING)
logging.getLogger("async_rediscache").setLevel(logging.WARNING)

# Set back to the default of INFO even if asyncio's debug mode is enabled.
logging.getLogger("asyncio").setLevel(logging.INFO)

# Check if Python3.7+
# Refer: https://docs.python.org/3/whatsnew/3.7.html#asyncio
PY37 = sys.version_info >= (3, 7)

# Handle the new Intents.
discord_ver_tuple = tuple([int(ver) for ver in discord.__version__.split(".")])
DISCORD_INTENTS = None
if discord_ver_tuple >= (1, 5, 0):
    logger.info("Detected discord.py version 1.5.0, using the new Intents system...")
    # Enable all except Presences.
    DISCORD_INTENTS = discord.Intents.all()


parser = argparse.ArgumentParser(description="PotiaBot")
parser.add_argument("-dcog", "--disable-cogs", default=[], action="append", dest="cogs_skip")
args_parsed = parser.parse_args()


async def initialize_bot(loop: asyncio.AbstractEventLoop):
    logger.info("Looking up config...")
    config = await read_files("config.json")

    if "redisdb" not in config:
        logger.error("Redis DB is not setup, please setup Redis before continuing!")
        return sys.exit(1)
    if not config["redisdb"]:
        logger.error("Redis DB is not setup, please setup Redis before continuing!")
        return sys.exit(1)
    redis_conf = config["redisdb"]
    if "ip_hostname" not in redis_conf or "port" not in redis_conf:
        logger.error("Redis DB is not setup, please setup Redis before continuing!")
        return sys.exit(1)
    if not redis_conf["ip_hostname"] or not redis_conf["port"]:
        logger.error("Redis DB is not setup, please setup Redis before continuing!")
        return sys.exit(1)

    default_prefix = config["prefix"]
    redis_conn = RedisBridge(
        redis_conf["ip_hostname"], redis_conf["port"], redis_conf.get("password", None), loop
    )
    logger.info("Connecting to RedisDB...")
    await redis_conn.connect()
    logger.info("Connected to RedisDB!")
    logger.info("Fetching prefixes data...")
    srv_prefixes = await redis_conn.getalldict("potiapre_*")
    fmt_prefixes = {}
    for srv, pre in srv_prefixes.items():
        fmt_prefixes[srv[9:]] = pre

    logger.info("Preparing puppeeter")
    puppet_gen = PuppeeterGenerator(loop)
    await puppet_gen.init()
    await puppet_gen.bind(WelcomeGenerator)
    # Bind another...
    # await puppet_gen.bind(...)

    cwd = str(pathlib.Path(__file__).parent.absolute())

    bot_description = "Sebuah bot pemantau server official Muse Indonesia\nDibuat oleh N4O#8868"
    prefixes = functools.partial(prefixes_with_data, prefixes_data=fmt_prefixes, default=default_prefix)
    if discord_ver_tuple >= (1, 5, 0):
        bot = PotiaBot(
            command_prefix=prefixes,
            description=bot_description,
            intents=DISCORD_INTENTS,
            case_insensitive=True,
            loop=loop,
        )
    else:
        bot = PotiaBot(command_prefix=prefixes, description=bot_description, case_insensitive=True, loop=loop)
    bot.remove_command("help")
    bot.logger.info("Bot is now loaded, now using bot internal logger for loggin.")
    bot.bot_config = config
    bot.semver = __version__
    bot.fcwd = cwd
    bot.prefix = default_prefix
    bot.logger.info("Binding Redis...")
    bot.redis = redis_conn
    bot.logger.info("Binding Puppeeter...")
    bot.puppet = puppet_gen
    return bot


# Initiate everything
logger.info(f"Initiating bot v{__version__}...")
logger.info("Setting up loop")
async_loop = asyncio.get_event_loop()
bot: PotiaBot = async_loop.run_until_complete(initialize_bot(async_loop))
wib_tz = timezone(timedelta(hours=7))
if bot is None:
    sys.exit(1)


@bot.event
async def on_ready():
    bot.logger.info("---------------------------------------------------------------")
    bot.logger.info("Bot has now established connection with Discord!")
    await bot.modify_activity("🥐 | @author N4O")
    bot.logger.info("> Loading all avaialble cogs...")
    skipped_cogs = []
    for cogs in args_parsed.cogs_skip:
        if not cogs.startswith("cogs."):
            cogs = "cogs." + cogs
        skipped_cogs.append(cogs)
    for load_this in ALL_COGS_LIST:
        if load_this in skipped_cogs:
            bot.logger.warning(f"> Skipping {load_this}...")
            continue
        try:
            bot.logger.info(f"Loading module/cog: {load_this}")
            bot.load_extension(load_this)
            bot.logger.info(f"{load_this} module/cog is now loaded!")
        except commands.ExtensionError as enoff:
            bot.logger.error(f"Failed to load {load_this} module/cogs.")
            bot.echo_error(enoff)
    bot.logger.info("> All availabel cogs/modules are now loaded!")
    bot.logger.info("---------------------------------------------------------------")
    bot.logger.info("Binding modlog...")
    modlog_channel = bot.get_channel(bot.bot_config["modlog_channel"])
    if isinstance(modlog_channel, discord.TextChannel):
        bot.set_modlog(modlog_channel)
        bot.logger.info(f"Modlog binded to: #{modlog_channel.name} ({modlog_channel.id})")
    else:
        bot.logger.error("Failed to bind modlog, cannot find the target channel")
    bot.logger.info("---------------------------------------------------------------")
    bot.logger.info("Bot Ready!")
    bot.logger.info("Using Python {}".format(sys.version))
    bot.logger.info("And Using Discord.py v{}".format(discord.__version__))
    bot.logger.info("---------------------------------------------------------------")
    bot.logger.info("Bot Info:")
    bot.logger.info("Username: {}".format(bot.user.name))
    bot.logger.info("Client ID: {}".format(bot.user.id))
    bot.logger.info("Running PotiaBot version: {}".format(__version__))
    bot.logger.info("---------------------------------------------------------------")


def ping_emote(t_t):
    if t_t < 50:
        emote = ":race_car:"
    elif t_t >= 50 and t_t < 200:
        emote = ":blue_car:"
    elif t_t >= 200 and t_t < 500:
        emote = ":racehorse:"
    elif t_t >= 200 and t_t < 500:
        emote = ":runner:"
    elif t_t >= 500 and t_t < 3500:
        emote = ":walking:"
    elif t_t >= 3500:
        emote = ":snail:"
    return emote


@bot.command()
async def ping(ctx):
    """
    pong!
    """
    channel = ctx.message.channel
    bot.logger.info("checking websocket...")
    ws_ping = bot.latency
    irnd = lambda t: int(round(t))  # noqa: E731

    text_res = ":satellite: Ping Results :satellite:"
    bot.logger.info("checking discord itself.")
    t1_dis = time.perf_counter()
    async with channel.typing():
        t2_dis = time.perf_counter()
        dis_ping = irnd((t2_dis - t1_dis) * 1000)
        bot.logger.info("generating results....")
        bot.logger.debug("generating discord res")
        text_res += f"\n{ping_emote(dis_ping)} Discord: `{dis_ping}ms`"

        bot.logger.debug("generating websocket res")
        if ws_ping != float("nan"):
            ws_time = irnd(ws_ping * 1000)
            ws_res = f"{ping_emote(ws_time)} Websocket `{ws_time}ms`"
        else:
            ws_res = ":x: Websocket: `nan`"
        text_res += f"\n{ws_res}"
        await channel.send(content=text_res)


@bot.command()
@commands.is_owner()
async def reload(ctx, *, cogs=None):
    """
    Restart salah satu module bot, owner only
    """
    if not cogs:
        helpcmd = HelpGenerator(
            bot,
            ctx,
            "Reload",
            desc="Reload module bot.",
        )
        helpcmd.embed.add_field(
            name="Module/Cogs List",
            value="\n".join(["- " + cl for cl in ALL_COGS_LIST]),
            inline=False,
        )
        return await ctx.send(embed=helpcmd.get())
    if not cogs.startswith("cogs."):
        cogs = "cogs." + cogs
    bot.logger.info(f"trying to reload {cogs}")
    msg = await ctx.send("Please wait, reloading module...")
    try:
        bot.logger.info(f"Re-loading {cogs}")
        bot.reload_extension(cogs)
        bot.logger.info(f"reloaded {cogs}")
    except commands.ExtensionNotLoaded:
        await msg.edit(content="Failed to reload module, trying to load it...")
        bot.logger.warning(f"{cogs} haven't been loaded yet...")
        try:
            bot.logger.info(f"trying to load {cogs}")
            bot.load_extension(cogs)
            bot.logger.info(f"{cogs} loaded")
        except commands.ExtensionFailed as cer:
            bot.logger.error(f"failed to load {cogs}")
            bot.echo_error(cer)
            return await msg.edit(content="Failed to (re)load module, please check bot logs.")
        except commands.ExtensionNotFound:
            bot.logger.warning(f"{cogs} doesn't exist.")
            return await msg.edit(content="Cannot find that module.")
    except commands.ExtensionNotFound:
        bot.logger.warning(f"{cogs} doesn't exist.")
        return await msg.edit(content="Cannot find that module.")
    except commands.ExtensionFailed as cef:
        bot.logger.error(f"failed to reload {cogs}")
        bot.echo_error(cef)
        return await msg.edit(content="Failed to (re)load module, please check bot logs.")

    await msg.edit(content=f"Successfully (re)loaded `{cogs}` module.")


@bot.command()
@commands.is_owner()
async def load(ctx, *, cogs=None):
    """
    Load salah satu module bot, owner only
    """
    if not cogs:
        helpcmd = HelpGenerator(
            bot,
            ctx,
            "Load",
            desc="Load module bot.",
        )
        helpcmd.embed.add_field(
            name="Module/Cogs List",
            value="\n".join(["- " + cl for cl in ALL_COGS_LIST]),
            inline=False,
        )
        return await ctx.send(embed=helpcmd.get())
    if not cogs.startswith("cogs."):
        cogs = "cogs." + cogs
    bot.logger.info(f"trying to load {cogs}")
    msg = await ctx.send("Please wait, loading module...")
    try:
        bot.logger.info(f"loading {cogs}")
        bot.load_extension(cogs)
        bot.logger.info(f"loaded {cogs}")
    except commands.ExtensionAlreadyLoaded:
        bot.logger.warning(f"{cogs} already loaded.")
        return await msg.edit(content="Module already loaded.")
    except commands.ExtensionNotFound:
        bot.logger.warning(f"{cogs} doesn't exist.")
        return await msg.edit(content="Cannot find that module.")
    except commands.ExtensionFailed as cef:
        bot.logger.error(f"failed to load {cogs}")
        bot.echo_error(cef)
        return await msg.edit(content="Failed to load module, please check bot logs.")

    await msg.edit(content=f"Successfully loaded `{cogs}` module.")


@bot.command()
@commands.is_owner()
async def unload(ctx, *, cogs=None):
    """
    Unload salah satu module bot, owner only
    """
    if not cogs:
        helpcmd = HelpGenerator(
            bot,
            ctx,
            "Unload",
            desc="Unload module bot.",
        )
        helpcmd.embed.add_field(
            name="Module/Cogs List",
            value="\n".join(["- " + cl for cl in ALL_COGS_LIST]),
            inline=False,
        )
        return await ctx.send(embed=helpcmd.get())
    if not cogs.startswith("cogs."):
        cogs = "cogs." + cogs
    bot.logger.info(f"trying to unload {cogs}")
    msg = await ctx.send("Please wait, unloading module...")
    try:
        bot.logger.info(f"unloading {cogs}")
        bot.unload_extension(cogs)
        bot.logger.info(f"unloaded {cogs}")
    except commands.ExtensionNotFound:
        bot.logger.warning(f"{cogs} doesn't exist.")
        return await msg.edit(content="Cannot find that module.")
    except commands.ExtensionNotLoaded:
        bot.logger.warning(f"{cogs} aren't loaded yet.")
        return await msg.edit(content="Module not loaded yet.")
    except commands.ExtensionFailed as cef:
        bot.logger.error(f"failed to unload {cogs}")
        bot.echo_error(cef)
        return await msg.edit(content="Failed to unload module, please check bot logs.")

    await msg.edit(content=f"Successfully unloaded `{cogs}` module.")


# All of the code from here are mainly a copy of discord.Client.run()
# function, which have been readjusted to fit my needs.
async def run_bot(*args, **kwargs):
    try:
        await bot.start(*args, **kwargs)
    finally:
        await bot.close()


def stop_stuff_on_completion(loop: asyncio.AbstractEventLoop):
    bot.logger.info("Closing queue loop...")
    if hasattr(bot, "puppet") and bot.puppet is not None:
        loop.run_until_complete(bot.puppet.close())
    bot.logger.info("Closing Redis Connection...")
    loop.run_until_complete(bot.redis.close())
    loop.stop()


def cancel_all_tasks(loop):
    """A copy of discord.Client _cancel_tasks function

    :param loop: [description]
    :type loop: [type]
    """
    try:
        try:
            if PY37:
                # Silence the deprecation notice
                task_retriever = asyncio.all_tasks
            else:
                task_retriever = asyncio.Task.all_tasks
        except AttributeError:
            # future proofing for 3.9 I guess
            task_retriever = asyncio.all_tasks

        tasks = {t for t in task_retriever(loop=loop) if not t.done()}

        if not tasks:
            return

        bot.logger.info("Cleaning up after %d tasks.", len(tasks))
        for task in tasks:
            task.cancel()

        loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
        bot.logger.info("All tasks finished cancelling.")

        for task in tasks:
            if task.cancelled():
                continue
            if task.exception() is not None:
                loop.call_exception_handler(
                    {
                        "message": "Unhandled exception during Client.run shutdown.",
                        "exception": task.exception(),
                        "task": task,
                    }
                )
        if sys.version_info >= (3, 6):
            loop.run_until_complete(loop.shutdown_asyncgens())
    finally:
        bot.logger.info("Closing the event loop.")


future = asyncio.ensure_future(run_bot(bot.bot_config["token"], bot=True, reconnect=True))
try:
    async_loop.run_forever()
    # bot.run()
except (KeyboardInterrupt, SystemExit, SystemError):
    bot.logger.info("Received signal to terminate bot.")
finally:
    bot.logger.info("Cleaning up tasks.")
    cancel_all_tasks(async_loop)
    stop_stuff_on_completion(async_loop)

if not future.cancelled():
    try:
        future.result()
    except KeyboardInterrupt:
        pass
