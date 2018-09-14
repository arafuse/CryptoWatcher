# -*- coding: utf-8 -*-

"""
Utility module.
"""

__author__ = 'Adam Rafuse <$(echo nqnz.enshfr#tznvy.pbz | tr a-z# n-za-m@)>'
__version__ = "0.0.1a"
__license__ = "http://opensource.org/licenses/MIT"
__all__ = ['Singleton', 'async_task', 'logging', 'io', 'log']

import collections
import traceback
import asyncio

from typing import Sequence, Any

from utils import logging
from utils import io

log: logging.Logger = logging.DummyLogger()
"""
Module logger, which is also used by all submodules. Any instance of utils.logging.Logger can be injected here to
enable logging of utils methods.
"""


def async_task(coro, loop=asyncio.get_event_loop(), error_cb=None):
    """
    Wrapper to always print exceptions for asyncio tasks.
    """

    future = asyncio.ensure_future(coro)

    def exception_logging_done_cb(future):
        try:
            e = future.exception()
        except asyncio.CancelledError:
            return

        if e is not None:
            log.critical('Unhandled exception in async future: {}: {}\n{}',
                         type(e).__name__, e, ''.join(traceback.format_tb(e.__traceback__)))

            if error_cb is not None:
                error_cb()

            loop.call_exception_handler({
                'message': 'Unhandled exception in async future',
                'future': future,
                'exception': e,
            })

    future.add_done_callback(exception_logging_done_cb)
    return future


def merge_dict(dest: dict, source: dict):
    """
    Recursively merge one dict into another (like dict.update() but for arbitrary depth keys).

    Arguments:
        dest:    Destination dict to merge into.
        source:  Source dict to merge from.
    """

    for key, value in source.items():
        if isinstance(value, collections.Mapping):
            dest[key] = merge_dict(dest.get(key, {}), value)
        else:
            dest[key] = value

    return dest


def reverse_enumerate(iterable: Sequence[Any]):
    """
    Enumerate over an iterable in reverse order while retaining proper indexes.

    Arguments:
        iterable:  Iterable to enumerate over.
    """
    return zip(reversed(range(len(iterable))), reversed(iterable))


def split(sliceable: object, num: int):
    """
    Split an object that supports slice notation into a number of roughly equal parts.

    Arguments:
        sliceable:  Sliceable object to split.
        num:        Number of splits.

    Returns:
        generator(slice):  A generator producing each slice of the object.
    """

    quot, rem = divmod(len(sliceable), num)
    return (sliceable[i * quot + min(i, rem):(i + 1) * quot + min(i + 1, rem)] for i in range(num))


class Singleton():
    """
    Allows singleton classes with nicer syntax through inheritance.
    """

    _shared_state = {}

    def __init__(self):
        self.__dict__ = self._shared_state
