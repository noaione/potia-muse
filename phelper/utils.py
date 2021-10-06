import asyncio
import functools
import logging
import os
import typing as T

import aiofiles
import discord
import orjson
from discord.ext import commands

__version__ = "1.0.0b"
main_log = logging.getLogger("phelper.utils")


def sync_wrap(func):
    @asyncio.coroutine
    @functools.wraps(func)
    def run(*args, loop=None, executor=None, **kwargs):
        if loop is None:
            loop = asyncio.get_event_loop()
        pfunc = functools.partial(func, *args, **kwargs)
        return loop.run_in_executor(executor, pfunc)

    return run


def get_indexed(data: list, n: int):
    try:
        return data[n]
    except (ValueError, IndexError):
        return None


def rounding(number: float):
    return int(round(number))


def complex_walk(dictionary: T.Union[dict, list], paths: str):
    expanded_paths = paths.split(".")
    skip_it = False
    for n, path in enumerate(expanded_paths):
        if skip_it:
            skip_it = False
            continue
        if path.isdigit():
            path = int(path)
        if path == "*" and isinstance(dictionary, list):
            new_concat = []
            next_path = get_indexed(expanded_paths, n + 1)
            if next_path is None:
                return None
            skip_it = True
            for content in dictionary:
                try:
                    new_concat.append(content[next_path])
                except (TypeError, ValueError, IndexError, KeyError, AttributeError):
                    pass
            if len(new_concat) < 1:
                return new_concat
            dictionary = new_concat
            continue
        try:
            dictionary = dictionary[path]
        except (TypeError, ValueError, IndexError, KeyError, AttributeError):
            return None
    return dictionary


async def read_files(fpath: str) -> T.Any:
    """Read a files
    ---

    :param fpath: file path
    :type fpath: str
    :return: file contents, parsed with orjson if it's list or dict
             if file doesn't exist, return None
    :rtype: Any
    """
    if not os.path.isfile(fpath):
        return None
    async with aiofiles.open(fpath, "r", encoding="utf-8") as fp:
        data = await fp.read()
    try:
        data = orjson.loads(data)
    except ValueError:
        pass
    return data


async def write_files(data: T.Any, fpath: str):
    """Write data to files
    ---

    :param data: data to write, can be any
    :type data: Any
    :param fpath: file path
    :type fpath: str
    """
    if isinstance(data, (dict, list, tuple)):
        data = orjson.dumps(
            data,
            option=orjson.OPT_INDEN_2,
        )
    elif isinstance(data, int):
        data = str(data)
    wmode = "w"
    if isinstance(data, bytes):
        wmode = "wb"
    async with aiofiles.open(fpath, wmode, encoding="utf-8") as fpw:
        await fpw.write(data)


def blocking_read_files(fpath: str) -> T.Any:
    """Read a files with blocking
    ---
    :param fpath: file path
    :type fpath: str
    :return: file contents, parsed with orjson if it's list or dict
             if file doesn't exist, return None
    :rtype: Any
    """
    if not os.path.isfile(fpath):
        return None
    with open(fpath, "r", encoding="utf-8") as fp:
        data = fp.read()
    try:
        data = orjson.loads(data)
    except ValueError:
        pass
    return data


def explode_filepath_into_pieces(filepath: str) -> T.List[str]:
    """Split a filepath into pieces
    ---
    :param filepath: file path
    :type filepath: str
    :return: file path pieces
    :rtype: list
    """
    filepath = filepath.replace("\\", "/")
    filepath = filepath.split("/")
    return filepath


def prefixes_with_data(
    bot,
    context: T.Union[discord.Message, discord.TextChannel, discord.Guild, commands.Context],
    prefixes_data: dict,
    default: str,
) -> list:
    """
    A modified version of discord.ext.command.when_mentioned_or
    """
    pre_data = []
    pre_data.append(default)

    guild: discord.Guild = None
    if isinstance(context, (discord.Message, discord.TextChannel)):
        if hasattr(context, "guild"):
            try:
                guild = context.guild
            except AttributeError:
                pass
    elif isinstance(context, discord.Guild):
        guild = context
    elif isinstance(context, commands.Context):
        if hasattr(context, "guild"):
            try:
                guild = context.guild
            except AttributeError:
                pass
        elif hasattr(context, "message"):
            try:
                if hasattr(context.message, "guild"):
                    guild = context.message.guild
            except AttributeError:
                pass
    elif hasattr(context, "guild"):
        guild = context.guild
    elif hasattr(context, "message"):
        msg = context.message
        if hasattr(msg, "guild"):
            guild = msg.guild

    if guild is not None and hasattr(guild, "id"):
        srv_pre = prefixes_data.get(str(guild.id))
        if srv_pre:
            pre_data.remove(default)
            pre_data.append(srv_pre)
    if "ntd." not in pre_data:
        pre_data.append("ntd.")
    pre_data.extend([bot.user.mention + " ", "<@!%s> " % bot.user.id])

    return pre_data


# Message utils
async def send_timed_msg(ctx: commands.Context, message: str, delay: T.Union[int, float] = 5):
    """Send a timed message to a discord channel.
    ---

    :param ctx: context manager of the channel
    :type ctx: Any
    :param message: message to send
    :type message: str
    :param delay: delay before deleting the message, defaults to 5
    :type delay: Union[int, float], optional
    """
    main_log.debug(f"sending message with {delay} delay")
    msg = await ctx.send(message)
    await asyncio.sleep(delay)
    await msg.delete()


async def confirmation_dialog(
    bot, ctx: commands.Context, message: str, reference: discord.Message = None
) -> bool:
    """Send a confirmation dialog.

    :param bot: the bot itself
    :type bot: naoTimesBot
    :param ctx: context manager of the channel
    :type ctx: Any
    :param message: message to verify
    :type message: str
    :return: a true or false using the reaction picked.
    """
    channel = None
    if isinstance(ctx, discord.Message):
        channel = ctx.channel
    else:
        channel = ctx
    dis_msg = await channel.send(message, reference=reference)
    to_react = ["✅", "❌"]
    for react in to_react:
        await dis_msg.add_reaction(react)

    def check_react(reaction, user):
        if reaction.message.id != dis_msg.id:
            return False
        if user != ctx.author:
            return False
        if str(reaction.emoji) not in to_react:
            return False
        return True

    dialog_tick = True
    while True:
        res, user = await bot.wait_for("reaction_add", check=check_react)
        if user != ctx.author:
            pass
        elif "✅" in str(res.emoji):
            await dis_msg.delete()
            break
        elif "❌" in str(res.emoji):
            dialog_tick = False
            await dis_msg.delete()
            break
    return dialog_tick


class HelpGenerator:
    """A class to generate a help
    -----

    Example:
    ```
    # Assuming this is on a async function of a command
    helpcmd = HelpGenerator(bot, ctx, "add", desc="do an addition")
    await helpcmd.generate_field(
        "add"
        [
            {"name": "num1", "type": "r"},
            {"name": "num2", "type": "r"},
        ],
        desc="Do an addition between `num1` and `num2`",
        examples=["1 1", "2 4"],
        inline=True
    )
    await helpcmd.generate_aliases(["tambah", "plus"], False)
    await ctx.send(embed=helpcmd()) # or await ctx.send(embed=helpcmd.get())
    ```
    """

    def __init__(
        self, bot: commands.Bot, ctx: commands.Context, cmd_name: str = "", desc: str = "", color=None
    ):
        self.bot: commands.Bot = bot
        self.logger = logging.getLogger("nthelper.utils.HelpGenerator")

        self._ver = getattr(self.bot, "semver", "UNKNOWN")
        commit = getattr(self.bot, "get_commit", {"hash": None})
        if commit["hash"] is not None:
            self._ver += f" ({commit['hash']})"
        self._pre = self.bot.prefixes(ctx)
        self._no_pre = False

        if cmd_name.endswith("[*]"):
            cmd_name = cmd_name.replace("[*]", "").strip()
            self._no_pre = True
        self.cmd_name = cmd_name
        self.color = color
        if self.color is None:
            self.color = 0xCEBDBD  # rgb(206, 189, 189) / HEX #CEBDBD
        self.desc_cmd = desc

        self.embed: discord.Embed = None
        self.__start_generate()

    def __call__(self) -> discord.Embed:
        if not isinstance(self.embed, discord.Embed):
            self.logger.warning("Embed are not generated yet.")
            raise ValueError("Embed are not generated yet.")
        self.logger.info("sending embed results")
        return self.embed

    def get(self) -> discord.Embed:
        """Return the final embed.
        -----

        :raises ValueError: If the embed attrs is empty
        :return: Final embed
        :rtype: discord.Embed
        """
        if not isinstance(self.embed, discord.Embed):
            self.logger.warning("Embed are not generated yet.")
            raise ValueError("Embed are not generated yet.")
        self.logger.info("sending embed results")
        return self.embed

    @staticmethod
    def __encapsule(name: str, t: str) -> str:
        """Encapsulate the command name with <> or []
        -----

        This is for internal use only

        :param name: command name
        :type name: str
        :param t: command type (`r` or `o`, or `c`)
                  `r` for required command.
                  `o` for optional command.
        :type t: str
        :return: encapsuled command name
        :rtype: str
        """
        tt = {"r": ["`<", ">`"], "o": ["`[", "]`"], "c": ["`[", "]`"]}
        pre, end = tt.get(t, ["`", "`"])
        return pre + name + end

    def __start_generate(self):
        """
        Start generating embed
        """
        self.logger.info(f"start generating embed for: {self.cmd_name}")
        embed = discord.Embed(color=self.color)
        embed.set_author(
            name=self.bot.user.display_name,
            icon_url=self.bot.user.avatar,
        )
        embed.set_footer(text=f"Dibuat oleh N4O#8868 | Versi {self._ver}")
        title = "Bantuan Perintah"
        if self.cmd_name != "":
            title += " ("
            if not self._no_pre:
                title += self._pre
            title += f"{self.cmd_name})"
        embed.title = title
        if self.desc_cmd != "":
            embed.description = self.desc_cmd
        self.embed = embed

    async def generate_field(
        self,
        cmd_name: str,
        opts: T.List[T.Dict[str, str]] = [],
        desc: str = "",
        examples: T.List[str] = [],
        inline: bool = False,
        use_fullquote: bool = False,
    ):
        """Generate a help fields
        ---

        :param cmd_name: command name
        :type cmd_name: str
        :param opts: command options, defaults to []
        :type opts: List[Dict[str, str]], optional
        :param desc: command description, defaults to ""
        :type desc: str, optional
        :param examples: command example, defaults to []
        :type examples: List[str], optional
        :param inline: put field inline with previous field, defaults to False
        :type inline: bool, optional
        :param use_fullquote: Use block quote, defaults to False
        :type use_fullquote: bool, optional
        """
        self.logger.debug(f"generating field: {cmd_name}")
        gen_name = self._pre + cmd_name
        final_desc = ""
        if desc:
            final_desc += desc
            final_desc += "\n"
        opts_list = []
        if opts:
            for opt in opts:
                a_t = opt["type"]
                a_n = opt["name"]
                try:
                    a_d = opt["desc"]
                except KeyError:
                    a_d = ""
                capsuled = self.__encapsule(a_n, a_t)
                opts_list.append(capsuled)

                if a_d:
                    if a_t == "o":
                        if final_desc != "":
                            final_desc += "\n"
                        final_desc += capsuled
                        final_desc += " itu **`[OPSIONAL]`**"
                    final_desc += f"\n{a_d}"
        if final_desc == "":
            final_desc = cmd_name

        if opts_list:
            opts_final = " ".join(opts_list)
            gen_name += f" {opts_final}"

        if use_fullquote:
            final_desc = "```\n" + final_desc + "\n```"

        self.embed.add_field(
            name=gen_name,
            value=final_desc,
            inline=inline,
        )
        if examples:
            examples = [f"- **{self._pre}{cmd_name}** {ex}" for ex in examples]
            self.embed.add_field(
                name="Contoh",
                value="\n".join(examples),
                inline=False,
            )

    async def generate_aliases(self, aliases: T.List[str] = [], add_note: bool = True):
        """Generate end part and aliases
        ---

        :param aliases: aliases for command, defaults to []
        :type aliases: List[str], optional
        :param add_note: add ending note or not, defaults to True
        :type add_note: bool, optional
        """
        self.logger.debug(f"generating for {self.cmd_name}")
        aliases = [f"{self._pre}{alias}" for alias in aliases]
        if aliases:
            self.embed.add_field(name="Aliases", value=", ".join(aliases), inline=False)
        if add_note:
            self.embed.add_field(
                name="*Note*",
                value="Semua perintah memiliki bagian bantuannya sendiri!\n"
                f"Gunakan `{self._pre}help [nama perintah]` untuk melihatnya!",
                inline=False,
            )
