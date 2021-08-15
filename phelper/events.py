"""
MIT License

Copyright (c) 2019-2021 Aiman Maharana

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import asyncio
import inspect
import logging
from inspect import signature
from typing import Any, Callable, Dict, List, Optional, TypeVar

from .utils import get_indexed

__all__ = ["EventManager"]

T = TypeVar("T")
EventFunc = Callable[..., Any]


async def maybe_asyncute(func: EventFunc, *args, **kwargs):
    """
    Try to execute function
    """
    result = func(*args, **kwargs)
    if inspect.isawaitable(result):
        result = await result
    return result


class EventManager:
    """A simple event manager to dispatch a event to another cogs"""

    def __init__(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        """A simple event manager to dispatch a event to another cogs"""
        self.logger = logging.getLogger("naoTimes.EventManager")
        self._event_map: Dict[str, List[EventFunc]] = {}

        self._loop = loop or asyncio.get_event_loop()
        self._blocking = False

        self._waiters = asyncio.Queue()
        self._taskers = asyncio.Task(self._internal_loop(), loop=self._loop)

    async def _internal_loop(self):
        try:
            callback, kwargs = await self._waiters.get()
            try:
                await maybe_asyncute(callback, **kwargs)
            except Exception:
                pass
            self._waiters.task_done()
        except asyncio.CancelledError:
            pass

    async def close(self):
        self._blocking = True
        await self._waiters.join()
        self._taskers.cancel()

    def __extract_event(self, event: str):
        event = event.lower()
        extracted = event.split("_")
        if len(extracted) < 2:
            return event, None
        last_one = extracted[-1]
        if last_one.isdigit():
            digit = int(extracted.pop())
            return "_".join(extracted), digit
        return event, None

    def __find_callback(self, event: str, numbering: int = None):
        event_map = []
        is_realfn = False
        if event not in self._event_map:
            if "realfn_" + event not in self._event_map:
                return None
            else:
                event_map = self._event_map["realfn_" + event]
                is_realfn = True

        if is_realfn:
            return event_map[0]

        if numbering is not None:
            callback = get_indexed(event_map, numbering)
            if callback is not None:
                return callback
            return None

        return event_map

    def __create_kwarguments(self, callback: EventFunc, *args, **kwargs):
        valid_kwargs = {}
        missing_kwargs = []
        sigmaballs = signature(callback)
        for idx, param in enumerate(sigmaballs.parameters.values()):
            kw = kwargs.get(param.name)
            if param.default != param.empty:
                if kw is not None:
                    valid_kwargs[param.name] = kw
                else:
                    valid_kwargs[param.name] = param.default
                continue

            args_index = get_indexed(args, idx)
            if args_index is not None:
                valid_kwargs[param.name] = args_index
            else:
                missing_kwargs.append(
                    {
                        "index": idx,
                        "name": param.name,
                    }
                )

        if len(missing_kwargs) > 0:
            return False, None

        return True, valid_kwargs

    def dispatch(self, event: str, *args, **kwargs) -> None:
        """Dispatch an event to all registered callbacks"""
        if self._blocking:
            # The event is shutting down, dont try to add more dispatch
            return
        event, digit = self.__extract_event(event)
        callbacks = self.__find_callback(event, digit)
        if callbacks is None:
            self.logger.warning(f"event {event} not found, ignoring...")
            return

        if isinstance(callbacks, list):
            for callback in callbacks:
                valid, real_kwargs = self.__create_kwarguments(callback, *args, **kwargs)
                if not valid:
                    continue
                self._waiters.put_nowait([callback, real_kwargs])
        else:
            valid, real_kwargs = self.__create_kwarguments(callbacks, *args, **kwargs)
            if valid:
                self._waiters.put_nowait([callbacks, real_kwargs])

    @staticmethod
    def __extract_fn_name(fn: EventFunc):
        def _naming():
            if hasattr(fn, "func"):
                return fn.func.__name__
            return fn.__name__

        name = _naming()

        if name == "<lambda>":
            return f"lambda_{hash(fn)}"
        return name

    def on(self, event: str, callback: EventFunc) -> None:
        """Bind an event to a callback"""
        event = event.lower()
        if event.startswith("realfn_"):
            raise ValueError("Cannot use `realfn_` as starting event name because it's reserved!")
        event_map = self._event_map.get(event, [])
        event_map.append(callback)
        fn_name = self.__extract_fn_name(callback)
        self._event_map[event] = event_map
        self._event_map["realfn_" + fn_name] = [callback]

    def off(self, event: str) -> None:
        """Unbind event, if it's doesnt exist log and do nothing"""
        event = event.lower()
        if event not in self._event_map:
            self.logger.warning(f"event {event} not found, ignoring...")
            return
        self.logger.warning(f"unbinding event {event}")
        del self._event_map[event]
