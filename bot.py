import argparse
import asyncio
import logging
import os
import pathlib
import sys

import coloredlogs
import discord

from phelper.bot import PotiaBot, StartupError
from phelper.config import PotiaBotConfig
from phelper.utils import __version__, blocking_read_files

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

discord_ver_tuple = (discord.version_info.major, discord.version_info.minor, discord.version_info.micro)
DISCORD_INTENTS = None
if discord_ver_tuple >= (1, 5, 0):
    logger.info("Detected discord.py version 1.5.0, using the new Intents system...")
    # Enable all except Presences.
    DISCORD_INTENTS = discord.Intents.all()

parser = argparse.ArgumentParser(description="PotiaBot")
parser.add_argument("-dcog", "--disable-cogs", default=[], action="append", dest="cogs_skip")
args_parsed = parser.parse_args()

logger.info(f"Initiating bot v{__version__}")
logger.info("Setting up a new loop...")
async_loop = asyncio.ProactorEventLoop()
asyncio.set_event_loop(async_loop)
logger.info("Looking up config...")
cwd = str(pathlib.Path(__file__).parent.absolute())
raw_config_file = blocking_read_files(os.path.join(cwd, "config.json"))
if raw_config_file is None:
    logger.critical("Could not find config file, exiting...")
    exit(69)

bot_config = PotiaBotConfig.parse_config(raw_config_file, args_parsed)

bot_description = "Sebuah bot pemantau server official Muse Indonesia\nDibuat oleh N4O#8868"

bot_kwargs = {
    "base_path": cwd,
    "bot_config": bot_config,
    "command_prefix": bot_config.default_prefix,
    "description": bot_description,
    "case_insensitive": True,
    "loop": async_loop,
}
if discord_ver_tuple >= (1, 5, 0):
    bot_kwargs["intents"] = DISCORD_INTENTS

try:
    bot = PotiaBot(**bot_kwargs)
    bot.remove_command("help")
    logger.info("Bot loaded, starting bot...")
    bot.run(bot_config.token)
    logger.info("Bot shutting down...")
    async_loop.close()
except StartupError as e:
    logger.critical(f"Fatal error while starting bot: {str(e)}")
    exit(69)
