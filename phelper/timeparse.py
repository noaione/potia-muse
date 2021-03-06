"""
This is a custom time parsing that use a format like: 3d50m / 3h / 30 seconds / etc.
Created since I need a custom one for everything that use this kinda thing.

This module will convert a string of text into `:cls:`datetime.datetime format

---

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

from datetime import datetime, timedelta
from typing import Dict, List, NamedTuple, Union

__all__ = ["TimeString", "TimeStringError", "TimeStringParseError", "TimeStringValidationError"]


_SUFFIXES = ["ms", "s", "m", "h", "w", "d", "mo", "y"]
_NAME_MAPS = {
    "ms": "Milisecond",
    "s": "Detik",
    "m": "Menit",
    "h": "Jam",
    "w": "Minggu",
    "d": "Hari",
    "mo": "Bulan",
    "y": "Tahun",
}


class TimeTuple(NamedTuple):
    t: Union[int, float]
    s: str


TimeSets = List[TimeTuple]


class TimeStringError(Exception):
    pass


class TimeStringParseError(TimeStringError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(f"Terjadi kesalahan ketika parsing data waktu, {reason}")


class TimeStringValidationError(TimeStringError):
    def __init__(self, extra_data=None):
        main_text = "Gagal memvalidasi data yang diberikan ke TimeString, mohon periksa lagi"
        if isinstance(extra_data, str):
            main_text += f"\nInfo tambahan: {extra_data}"
        super().__init__(main_text)


def normalize_suffix(suffix: str) -> Union[str, None]:
    if suffix in ["", " "]:
        # Default to seconds
        return "s"
    if suffix in ["s", "sec", "secs", "second", "seconds", "detik"]:
        return "s"
    if suffix in [
        "ms",
        "mil",
        "mill",
        "millis",
        "milli",
        "msec",
        "msecs",
        "milisec",
        "miliseconds",
        "milisecond",
    ]:
        return "ms"
    if suffix in ["m", "min", "mins", "minute", "minutes", "menit"]:
        return "m"
    if suffix in ["h", "hr", "hrs", "hour", "hours", "jam", "j"]:
        return "h"
    if suffix in ["d", "day", "days", "hari"]:
        return "d"
    if suffix in ["w", "wk", "week", "weeks", "minggu"]:
        return "w"
    if suffix in ["M", "mo", "month", "months", "b", "bulan"]:
        return "mo"
    if suffix in ["y", "year", "years", "tahun", "t"]:
        return "y"
    return None


class TimeString:
    def __init__(self, timesets: TimeSets) -> None:
        self._data: TimeSets = timesets
        self.__validate()

    def __validate(self):
        if not isinstance(self._data, list):
            raise TimeStringValidationError()
        self._data = self.__concat_dupes(self._data)
        for data in self._data:
            if not isinstance(data.t, (int, float)):
                raise TimeStringValidationError(f"{data.t} bukanlah angka!")
            if not isinstance(data.s, str):
                raise TimeStringValidationError(f"{data.s} bukanlah string!")
            if data.s not in _SUFFIXES:
                raise TimeStringValidationError(f"{data.s} bukanlah suffix yang diperlukan!")

    def __repr__(self):
        text_contents = []
        for data in self._data:
            text_contents.append(f"{_NAME_MAPS.get(data.s)}={data.t}")
        if text_contents:
            return f"<TimeString {' '.join(text_contents)}>"
        return "<TimeString NoData>"

    @staticmethod
    def __tokenize(text: str) -> List[TimeTuple]:
        time_sets = []
        texts: List[str] = list(text)  # Convert to list of string
        current_num = ""
        build_suffix = ""
        current = ""
        for t in texts:
            if t in [" ", ""]:
                if build_suffix.rstrip() and current_num.rstrip():
                    suf = normalize_suffix(build_suffix)
                    if suf is not None:
                        time_sets.append(TimeTuple(int(current_num, 10), suf))
                        current_num = ""
                        build_suffix = ""
                continue
            if t.isdigit():
                if current == "s" and build_suffix.rstrip() and current_num.rstrip():
                    suf = normalize_suffix(build_suffix)
                    if suf is not None:
                        time_sets.append(TimeTuple(int(current_num, 10), suf))
                        current_num = ""
                        build_suffix = ""
                current = "t"
                current_num += t
                continue
            else:
                current = "s"
                build_suffix += t

        if current_num.rstrip():
            suf = normalize_suffix(build_suffix)
            if suf is not None:
                time_sets.append(TimeTuple(int(current_num, 10), suf))
        return time_sets

    @staticmethod
    def __concat_dupes(time_sets: TimeSets):
        occured: Dict[str, Union[int, float]] = {}
        for time in time_sets:
            if time.s not in occured:
                occured[time.s] = time.t
            else:
                occured[time.s] += time.t
        concatted = []
        for suf, am in occured.items():
            concatted.append(TimeTuple(am, suf))
        return concatted

    @staticmethod
    def __multiplier(t: Union[int, float], s: str):
        if s == "s":
            return t
        if s == "ms":
            return t / 1000
        if s == "m":
            return t * 60
        if s == "h":
            return t * 3600
        if s == "d":
            return t * 3600 * 24
        if s == "w":
            return t * 3600 * 24 * 7
        if s == "mo":
            return t * 3600 * 24 * 30
        if s == "y":
            return t * 3600 * 24 * 365

    @classmethod
    def parse(cls, timestring: str):
        time_data = cls.__tokenize(timestring)
        if len(time_data) < 1:
            raise TimeStringParseError("hasil akhir parsing kosong, walaupun input diberikan.")
        return cls(time_data)

    def timestamp(self) -> int:
        real_seconds = 0
        for data in self._data:
            real_seconds += self.__multiplier(data.t, data.s)
        return real_seconds

    def to_datetime(self) -> datetime:
        dt_start = datetime.utcfromtimestamp(0)
        combined = dt_start + self.to_delta()
        return combined

    def to_delta(self) -> timedelta:
        delta = timedelta(seconds=self.timestamp())
        return delta
