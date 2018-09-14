# -*- coding: utf-8 -*-

# Copyright (c) A 2017 Adam M. Rafuse - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited.
# Proprietary and confidential.

"""
Common methods and classes.
"""

__author__ = 'Adam Rafuse <$(echo nqnz.enshfr#tznvy.pbz | tr a-z# n-za-m@)>'
__all__ = ['math', 'interrupt', 'loop', 'log', 'backoff', 'get_task_pool', 'set_default_signal_handler',
           'utctime_str', 'get_rollover_time_str', 'init_config_paths', 'create_user_dirs', 'get_pair_elements',
           'is_trade_base_pair', 'is_trade_base', 'render_svg_chart', 'play_sound']

import os
import sys
import time
import random
import signal
import asyncio
import subprocess
import multiprocessing
import multiprocessing.pool

from datetime import datetime
from typing import Any, Dict, Sequence, Tuple

import pygal

import utils
import defaults
import configuration

# import uvloop
# asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

config = configuration.config
"""
Global configuration.
"""

interrupt = multiprocessing.Event()
"""
Shared interrupt event.
"""

loop = asyncio.get_event_loop()
"""
Shared event loop.
"""

log: utils.logging.Logger = utils.logging.DummyLogger()
"""
Module logger.
"""


async def backoff(attempt: int, caller: str, reason: str):
    """
    Backoff for a delay based on the retry attempt, and log the reason.

    Sleeps the event loop for 2**attempt seconds plus 0-2 seconds of random jitter and logs a warning indicating
    a backoff if this is higher than the zeroth retry attempt.

    Arguments:
        attempt:  Number of the retry attempt.
        caller:   Name of the caller for logging.
        reason:   Sentence fragment to log as the retry reason.
    """

    if attempt > 0:
        seconds = 2 ** attempt
        if seconds > config['http_max_backoff_secs']: seconds = config['http_max_backoff_secs']
        seconds += random.random() * 2
        log.warning('{} retrying for {}, attempt {}', caller, reason, attempt)
        await asyncio.sleep(seconds)


def get_task_pool(thread=False):
    """
    Get a new task pool, which is either a single-thread or process pool depending on the current config.

    Returns:
        A new :class:`multiprocessing.pool.Pool` instance.
    """

    if thread or not config['app_multicore'] or config['enable_backtest'] and config['backtest_multicore']:
        task_pool = multiprocessing.pool.ThreadPool(processes=1)

    else:
        processes = config['backtest_processes'] if config['enable_backtest'] else config['app_processes']
        task_pool = multiprocessing.Pool(processes=processes)
        task_pool.daemon = True

    return task_pool


def set_default_signal_handler():
    """
    Set a minimal signal handler that just sets the global interrupt event.

    Used for overriding the default user interrupt handler inherited by spawed processes to play nice with interruptable
    code instead of hard-terminating.
    """

    def signal_handler(_, __):
        interrupt.set()

    signal.signal(signal.SIGINT, signal_handler)


def utctime_str(timestamp: float, fmt: str) -> str:
    """
    Convert a UTC timestamp to a string representation based on the given format.

    The result has any ':' characters converted to '-' to remain filesystem-friendly.

    Arguments:
        timestamp:  UTC timestamp to convert, in seconds.

    Returns:
        String version of the provided timestamp.
    """

    return datetime.utcfromtimestamp(timestamp).strftime(fmt).replace(':', '-')


def get_rollover_time_str(timestamp: float):
    """
    Get the current rollover time string.

    This is a string representation of the curent time in UTC which changes every
    :data:`config['output_rollover_secs']` seconds.
    """

    rollover_secs = config['output_rollover_secs']
    rollover_time = float((timestamp // rollover_secs) * rollover_secs)
    return utctime_str(rollover_time, config['time_format'])


def init_config_paths():
    """
    Initialize path entries in the shared config according to the current rollover time string.
    """

    time_prefix = get_rollover_time_str(time.time())

    config['mode_dir'] = 'backtest/' if config['enable_backtest'] else 'monitor/'
    config['mode_path'] = config['user_path'] + config['node_dir'] + config['mode_dir']
    config['logs_path'] = config['mode_path'] + defaults.LOGS_DIR + time_prefix + '/'
    config['charts_path'] = config['mode_path'] + defaults.CHARTS_DIR + time_prefix + '/'
    config['snapshot_path'] = config['mode_path'] + defaults.SNAPSHOT_DIR + time_prefix + '/'
    config['state_path'] = config['mode_path'] + defaults.STATE_DIR
    config['alert_log'] = config['mode_path'] + defaults.LOGS_DIR + defaults.ALERT_LOG
    config['output_log'] = config['logs_path'] + defaults.OUTPUT_LOG
    config['debug_log'] = config['logs_path'] + defaults.DEBUG_LOG
    config['error_log'] = config['logs_path'] + defaults.ERROR_LOG


def create_user_dirs():
    """
    Create user data directories that don't already exist.
    """

    for directory in [config['user_path'], config['mode_path'],
                      config['logs_path'], config['charts_path'], config['snapshot_path'], config['state_path']]:

        if not os.path.exists(directory):
            try:
                os.makedirs(directory)
            except FileExistsError:
                pass  # Can happen due concurrency contention during multicore backtest.


def get_pair_elements(pair: str) -> Tuple[str, str, str]:
    """
    Get a currency pair's base, quote, and trade base pair.

    Eg. If the global trade base is 'USDT' and the pair is 'BTC-ETH', returns ('BTC', 'ETH', 'USDT-BTC').

    Arguments:
        pair:   The currency pair eg. 'BTC-ETH'

    Returns:
        A tuple containing:
        (str):  The pair's base currency.
        (str):  The pair's quote currency.
        (str):  The pair's trade base pair.
    """

    pair_split = pair.split('-')
    base = pair_split[0]
    quote = pair_split[1]
    trade_base_pair = '{}-{}'.format(config['trade_base'], base)

    return (base, quote, trade_base_pair)


def get_pair_split(pair: str) -> Tuple[str, str, str]:
    """
    Get a currency pair's base and quote currency.

    Eg. If the global trade base is 'USDT' and the pair is 'BTC-ETH', returns ('BTC', 'ETH').

    Arguments:
        pair:   The currency pair eg. 'BTC-ETH'

    Returns:
        A tuple containing:
        (str):  The pair's base currency.
        (str):  The pair's quote currency.
    """

    pair_split = pair.split('-')
    base = pair_split[0]
    quote = pair_split[1]

    return (base, quote)


def get_pair_trade_base(pair: str) -> str:
    """
    Get a currency pair's trade base pair.

    Eg. If the global trade base is 'USDT' and the pair is 'BTC-ETH', returns 'USDT-BTC'. If the pair is 'USDT-ETH',
    returns None (already a trade base pair).

    Arguments:
        pair:   The currency pair name.

    Returns:
        The pair's trade base pair if it has one, else None.
    """

    base = pair.split('-')[0]
    return '{}-{}'.format(config['trade_base'], base) if base != config['trade_base'] else None


def is_trade_base_pair(pair: str) -> bool:
    """
    Check if a pair is a trade base pair.

    A trade base pair is a pair whose base currency is the trade base currency eg 'USDT' and the quote currency
    is another base currency eg. 'BTC' or 'ETH'.

    Arguments:
        pair:  The currency pair, eg. BTC-ETH.

    Returns:
        True if the pair is a trade base pair, otherwise False.
    """

    pair_split = pair.split('-')
    return is_trade_base(pair_split[0], pair_split[1])


def is_trade_base(base: str, quote: str):
    """
    Check if a base and quote currency form trade base pair.

    A trade base pair is a pair whose base currency is the trade base currency eg 'USDT' and the quote currency
    is another base currency eg. 'BTC' or 'ETH'.

    Arguments:
        base:   The base currency eg. 'BTC'.
        quote:  The quote currency eg. 'ETH'.

    Returns:
        True if the pair is a trade base pair, otherwise False.
    """

    if base == config['trade_base'] and quote in config['min_base_volumes']:
        return True

    return False


def get_min_tick_length():
    """
    Get the minimum length of tick data needed to perform all defined functions.

    We need enough data to compute the slowest (exponential) moving average, plus the sampling size (the length of the
    next fastest moving average) or the chart age, whichever is the highest.
    """

    if config['ema_windows']:
        ema_base = config['ema_windows'][-1] * 2
        ema_append = config['ema_windows'][-2]
    else:
        ema_base = 0
        ema_append = 0

    ma_base = config['ma_windows'][-1]
    ma_append = config['ma_windows'][-2]

    base = ema_base if ema_base > ma_base else ma_base
    append = ema_append if ema_append > ma_append else ma_append
    if config['chart_age'] > append: append = config['chart_age']

    return base + append


def render_svg_chart(pair: str, data: Dict[Any, Sequence[float]], filename: str):
    """
    Render a chart for the given pair and data to an SVG file.

    Arguments:
        pair:      Name of the currency pair eg 'BTC-ETH'.
        data:      Dictionary of lists of chart data to output.
        filename:  The filename including path of the chart file to output.
    """

    line_chart = pygal.Line(style=pygal.style.DarkStyle)
    line_chart.title = pair
    line_chart.margin = 0
    line_chart.width = config['chart_width']
    line_chart.height = config['chart_height']
    line_chart.show_x_labels = False
    line_chart.show_dots = False
    line_chart.show_y_guides = True

    for key, values in data.items():
        values_len = len(values)

        if values_len < config['chart_age'] and values_len > 0:
            out_values = [values[0] for _ in range(config['chart_age'] - values_len)]
            out_values += values
        else:
            out_values = values[-config['chart_age']:]

        line_chart.add(str(key), out_values)

    line_chart.render_to_file(filename)


def play_sound(filename: str):
    """
    Play a sound file by invoking the configured sound player for the current platform.

    Arguments:
        filename:   The relative or absolute path to the sound file to play.
    """

    if config['enable_sound']:
        try:
            platform = sys.platform.lower()

            if platform.startswith('linux'):
                subprocess.Popen(config['play_sound_cmd_linux'] + [filename])
            elif platform.startswith('win32') or platform.startswith('cygwin'):
                subprocess.Popen(config['play_sound_cmd_windows'] + [filename])
            elif platform.startswith('darwin'):
                subprocess.Popen(config['play_sound_cmd_darwin'] + [filename])
            else:
                subprocess.Popen(config['play_sound_cmd_default'] + [filename])

        except FileNotFoundError:
            log.error('Missing sound player executable!')
