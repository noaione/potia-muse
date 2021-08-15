from discord.ext import commands

from .timeparse import TimeString


class TimeConverter(commands.Converter):
    """
    A converter Class that will convert a string-formatted text of time into a proper time data
    that can be used.
    This will convert the string into `:class:`TimeString
    Example Usage:
    ```py
        async def to_seconds(self, ctx, timething: TimeConverter):
            print(timething.timestamp())
    ```
    """

    async def convert(self, ctx: commands.Context, argument: str) -> TimeString:
        converted = TimeString.parse(argument)
        return converted
