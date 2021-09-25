from typing import Any, Callable, Coroutine, Tuple, TypeVar, Protocol, Union, overload
from discord import Embed, Message, Emoji, PartialEmoji


T = TypeVar("T")
IT = TypeVar("IT")
GeneratorOutput = Union[
    Tuple[Embed, str],
    Tuple[str, Embed],
    Embed,
    str,
]

Coro = Coroutine[Any, Any, T]
Emote = Union[Emoji, PartialEmoji, str]


class PaginatorGenerator(Protocol[IT]):
    """A protocol implementation or typing for paginator generator"""

    @overload
    def __call__(self, item: IT) -> Coro[GeneratorOutput]:
        ...

    @overload
    def __call__(self, item: IT, position: int) -> Coro[GeneratorOutput]:
        ...

    @overload
    def __call__(self, item: IT, position: int, message: Message) -> Coro[GeneratorOutput]:
        ...

    def __call__(self, item: IT, position: int, message: Message, emote: Emote) -> Coro[GeneratorOutput]:
        ...


PaginatorValidator = Callable[[IT], bool]
