#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (c) 2017 Adam M. Rafuse - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential

"""
Tool for performing various operations with the crypto exchange API.
"""

import os
import sys
import glob
import json
import asyncio
import argparse
import multiprocessing

from typing import Dict, Sequence
from datetime import datetime, timezone

sys.path.insert(0, 'lib/')
import aiohttp

import api
import utils
import common
import defaults

from configuration import config

config.update({
    'output_log': defaults.USER_PATH + defaults.TOOL_OUTPUT_LOG,
    'debug_log': defaults.USER_PATH + defaults.TOOL_DEBUG_LOG,
    'error_log': defaults.USER_PATH + defaults.TOOL_ERROR_LOG,
})

log = utils.logging.ThreadedLogger(scope='apitool', level=config['app_log_level'], logger_level=config['app_log_level'],
                                   debug_verbosity=0, filename=config['output_log'], debug_filename=config['debug_log'],
                                   error_filename=config['error_log'])

common.log = utils.logging.ChildLogger(parent=log, scope='common')


def execute():
    """
    Execute this script.
    """

    api_help = "API to use."
    summary_help = "Dump current market summary as JSON."
    download_help = "Download data for the specified currency pair or all currency pairs."
    merge_help = "Merge pair data from split directories into single files."
    output_help = "Destination directory for output."
    input_help = "Source directory for input."
    num_help = "Maximum number of recent ticks to download if supported by the API."
    start_help = "Starting timestamp of tick range in seconds if supported by the API."
    end_help = "End timestamp of tick range in seconds if supported by the API."

    arg_parser = argparse.ArgumentParser(description=__doc__)
    arg_parser.add_argument('-api', type=str, metavar='"bittrex"|"binance"', help=api_help)
    arg_parser.add_argument('-s', '--summary', action="store_true", help=summary_help)
    arg_parser.add_argument('-d', '--download', type=str, metavar='PAIR|"all"', help=download_help)
    arg_parser.add_argument('-m', '--merge', action="store_true", help=merge_help)
    arg_parser.add_argument('-i', '--input', type=str, metavar='DIR', help=output_help)
    arg_parser.add_argument('-o', '--output', type=str, metavar='DIR', help=input_help)
    arg_parser.add_argument('-n', '--num', type=int, help=num_help)
    arg_parser.add_argument('-st', '--start_time', type=int, help=start_help)
    arg_parser.add_argument('-et', '--end_time', type=int, help=end_help)
    arg_parser.add_argument('--fix-timestamps', action="store_true")
    arg_parser.add_argument('--sparsify', action="store_true")
    args = arg_parser.parse_args()

    client = _get_client(arg_parser, args)
    if client is None:
        return

    method, params = _get_action(arg_parser, args, client)
    if method is None:
        return

    loop = asyncio.get_event_loop()
    loop.run_until_complete(method(loop, params))


def _get_client(arg_parser: argparse.ArgumentParser, args: argparse.Namespace):
    """
    Get the API client based on the provided arguments.
    """

    if args.api is None:
        log.error("Argument '-api' is required.")
        arg_parser.print_help()
        return None

    args.api = args.api.lower()

    if args.api == 'bittrex':
        from api import bittrex
        client = bittrex.Client

    elif args.api == 'binance':
        from api import binance
        client = binance.Client

    elif args.api == 'okex':
        from api import okex
        client = okex.Client

    else:
        log.error("Invalid API specified: {}.", args.api)
        arg_parser.print_help()
        return None

    return client


def _get_action(arg_parser: argparse.ArgumentParser, args: argparse.Namespace, client: api.Client):
    """
    Get the method to execute and its parameters based on the provided arguments.
    """

    if args.summary:
        params = {'client': client}
        method = dump_summary

    elif args.download:
        params = {'pair': args.download, 'dir': args.output, 'num': args.num,
                  'start': args.start_time, 'end': args.end_time, 'client': client}
        method = download

    elif args.merge:
        params = {'in_dir': args.input, 'out_dir': args.output}
        method = merge_data

    elif args.fix_timestamps:
        params = {'in_dir': args.input, 'out_dir': args.output, 'action': 'fix_timestamps'}
        method = process_single_files

    elif args.sparsify:
        params = {'in_dir': args.input, 'out_dir': args.output, 'action': 'sparsify'}
        method = process_single_files

    else:
        arg_parser.print_help()
        return (None, None)

    return (method, params)


async def dump_summary(loop: asyncio.AbstractEventLoop, params: Dict[str, str]):
    """
    Dump the current market summary as formatted JSON.

    Arguments:
        loop:  The :mod:`asyncio` event loop to use for coroutines.
        params:  A dictionary containing the following items:
            'client': (class):  The API client implementation to use.
    """

    conn = aiohttp.TCPConnector(limit_per_host=config['http_host_conn_limit'])
    async with aiohttp.ClientSession(loop=loop, connector=conn) as session:
        client = params['client'](session, log=log)
        summaries = await client.get_market_summaries()
        print(json.dumps(summaries, indent=2))


async def download(loop: asyncio.AbstractEventLoop, params: Dict[str, str]):
    """
    Download tick data for a currency pair or all pairs.

    Arguments:
        loop:  The :mod:`asyncio` event loop to use for coroutines.
        params:  A dictionary containing the following items:
            'pair': (str):  The currency pair to download, or 'all' to download all pairs.
            'dir': (str):   The directory to save downloaded data to.
            'client': (class):  The API client implementation to use.
    """

    if not params['dir']:
        log.error("Output directory must be specified.")
        return

    conn = aiohttp.TCPConnector(limit_per_host=config['http_host_conn_limit'])
    async with aiohttp.ClientSession(loop=loop, connector=conn) as session:
        client = params['client'](session, log=log)

        out_dir = params['dir']
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)

        pairs = await _get_pairs(client, params['pair'])
        await _download_tick_data(loop, client, pairs, out_dir, params['num'], params['start'], params['end'])


async def _get_pairs(client: api.Client, pair_param: str):
    """
    Get the list of pairs to download.

    Currently gets a list of all active pairs from the API, or a one-element list of the pair specified.
    TODO: Support parsing a comma-separated list of pairs.

    Arguments:
        client:      API client instance.
        pair_param:  The pair parameter, either the name of a pair or "ALL" (case insensitive).
    """

    pair_param = pair_param.upper()

    if pair_param == 'ALL':
        pairs = []

        summaries = await client.get_market_summaries()
        for pair, summary in summaries.items():
            if summary['active']:
                pairs.append(pair)

    else:
        pairs = [pair_param]

    return pairs


async def _download_tick_data(loop: asyncio.AbstractEventLoop, client: api.Client,
                              pairs: Sequence[str], out_dir: str, num: int, start_time: float, end_time: float):
    """
    Download tick data for the given list of pairs.

    Arguments:
        loop:     The :mod:`asyncio` event loop to use for coroutines.
        client:   API client instance.
        pairs:    List of pairs to download.
        out_dir:  Output directory to save downloaded files.
    """

    futures = []
    completed_pairs = []

    if start_time:
        # Based on Binance limits, which is currently the only API that works for range downloads.
        ticks_per_pair = (end_time - start_time) / config['tick_interval_secs']
        calls_per_pair = ticks_per_pair / 500
        pairs_per_min = 1200 / calls_per_pair
        rate_limit_secs = 120 / pairs_per_min
    else:
        rate_limit_secs = config['api_initial_rate_limit_secs']

    async def _download_task():
        for pair in pairs:
            log.info("Starting download for {}.", pair)
            futures.append(utils.async_task(_get_tick_data(pair, client, num, start_time, end_time), loop=loop))
            await asyncio.sleep(rate_limit_secs)

    utils.async_task(_download_task(), loop=loop)

    while len(completed_pairs) < len(pairs):
        for future in asyncio.as_completed(futures):
            pair, ticks = await future

            if pair not in completed_pairs and ticks is not None:
                if start_time and ticks[0]['T'] > start_time + 60 * 60 * 24 * 7:
                    log.warning("{} is ahead by {} seconds, discarding.", pair, ticks[0]['T'] - start_time)
                else:
                    await _save_sparse_tick_file(pair, out_dir, ticks)

                completed_pairs.append(pair)

        await asyncio.sleep(0)


async def _get_tick_data(pair: str, client: api.Client, num: int, start_time: float, end_time: float):
    """
    Return the current market tick data for the specified pair from the API.

    Arguments:
        pair:    The currency pair.
        client:  API client instance.

    Returns:
        (tuple):  A tuple containing:
          (str):       The passed pair (for joining on tasks).
          list(dict):  The list of ticks for this pair.
    """

    if start_time:
        try:
            ticks = await client.get_tick_range(pair, start_time, end_time)
        except NotImplementedError:
            log.error("API does not support downloading ticks by range.")
            return (None, None)

    else:
        ticks = await client.get_ticks(pair, length=num)

    return (pair, ticks)


async def _save_sparse_tick_file(pair: str, out_dir: str, ticks: Sequence[Dict[str, float]]):
    """
    Save ticks for a pair to a sparse file (zero base volume ticks omitted).

    Arguments:
        pair:     The currency pair.
        out_dir:  Output directory to save sparse file.
        ticks:    List of ticks to save.
    """

    sparse_ticks = []

    for tick in ticks:
        if tick['BV'] > 0.0:
            sparse_ticks.append(tick)

    filename = out_dir + '/' + pair + '.json'
    with open(filename, 'w') as file:
        json.dump(sparse_ticks, file)

    log.info("Saved {} data to {}.", pair, filename)


async def merge_data(_: asyncio.AbstractEventLoop, params: Dict[str, str]):
    """
    Merge pair data from split directories into single files.

    Arguments:
        params:  A dictionary containing the following items:
            'in_dir': (str):   The input directory containing split source file subdirectories.
            'out_dir': (str):  The directory to save the merged files to.
    """

    if not (params['in_dir'] and params['out_dir']):
        log.error("Both input and output directories must be specified.")
        return

    if params['in_dir'] == params['out_dir']:
        log.error("Input and output directories must be different.")
        return

    task_pool = multiprocessing.Pool()
    dirnames = sorted(glob.glob(params['in_dir'] + '*' + os.sep))

    filenames = []
    for dirname in dirnames:
        filenames.extend(glob.glob(dirname + '*.json'))

    pairs = {os.path.splitext(os.path.basename(filename))[0] for filename in filenames}

    futures = []
    for pair in pairs:
        futures.append(task_pool.apply_async(_load_pair_dirs, [pair, dirnames]))

    for future in futures:
        pair, ticks = future.get()
        log.info("Loaded data for {}.", pair)

        out_filename = params['out_dir'] + pair + '.json'
        with open(out_filename, 'w') as out_file:
            json.dump(ticks, out_file)
            log.info("Saved merged data for {} to {}.", pair, out_filename)


def _load_pair_dirs(pair: str, dirs: Sequence[str]):
    """
    Load pair data from disk split into multiple ordered directories.

    This is a simplified version of Market.load_pair_dirs that doesn't do sparse tick expansion.

    Arguments:
        pair:  The currency pair to load data for.
        dirs:  A list of ordered directories containing the split data for the pair*.

    Returns:
        (tuple):  A tuple containing:
            (str):       The pair that was passed, for joining on async tasks.
            list(dict):  A list of the loaded pair data.

    *Directories are assumed to be in sequential order with respect to the data, otherwise large gaps will appear in
    the loaded data.
    """

    ticks = []

    for dirname in dirs:
        filename = dirname + pair + '.json'

        try:
            with open(filename) as file:
                new_ticks = json.load(file)
        except FileNotFoundError:
            continue

        if new_ticks is None:
            continue

        if ticks:
            last_time = ticks[-1]['T']
            next_time = 0.0
            start_index = 0

            for start_index, tick in enumerate(new_ticks):
                next_time = tick['T']
                if next_time > last_time:
                    new_ticks = new_ticks[start_index:]
                    break

            if next_time <= last_time:
                continue

        ticks.extend(new_ticks)

    return (pair, ticks)


async def process_single_files(_: asyncio.AbstractEventLoop, params: Dict[str, str]):
    """
    Process single tick data files bases on the provided parameters.

    Arguments:
        params:  A dictionary containing the following items:
            'in_dir': (str):   The input directory to read tick data files from.
            'out_dir': (str):  The output directory to save the modified files to.
    """

    if not (params['in_dir'] and params['out_dir']):
        log.error("Both input and output directories must be specified.")
        return

    if params['in_dir'] == params['out_dir']:
        log.error("Input and output directories must be different.")
        return

    if params['action'] == 'fix_timestamps':
        method = _load_with_fixed_timestamps
        warning = "{} had non-convertible timestamps, possibly already converted."

    elif params['action'] == 'sparsify':
        method = _load_with_sparse_ticks
        warning = "{}"

    else:
        log.error("Unrecognized action '{}'.", params['action'])
        return

    task_pool = multiprocessing.Pool()
    filenames = glob.glob(params['in_dir'] + '*.json')

    futures = []
    for filename in filenames:
        futures.append(task_pool.apply_async(method, [filename]))

    for future in futures:
        pair, ticks, has_errors = future.get()
        log.info("Loaded data for {}.", pair)

        if has_errors:
            log.warning(warning, pair)

        out_filename = params['out_dir'] + pair + '.json'
        with open(out_filename, 'w') as out_file:
            json.dump(ticks, out_file)
            log.info("Saved converted data for {} to {}.", pair, out_filename)


def _load_with_fixed_timestamps(filename: str):
    """
    Load pair data and convert timestamps from string format to epoch seconds.

    Used for converting older tick data that was saved in this format.

    Arguments:
        pair:  The pair filename to load tick data from.

    Returns:
        (tuple):  A tuple containing:
            (str):       The pair that was passed, for joining on async tasks (taken from the filename base).
            list(dict):  A list of the loaded pair data.
            (bool):      True if any errors occurred while parsing timestamps (data may be already converted).

    """

    with open(filename) as file:
        ticks = json.load(file)

    errors = False

    for tick in ticks:
        try:
            next_datetime = datetime.strptime(tick['T'], config['time_format'])
            next_time = next_datetime.replace(tzinfo=timezone.utc).timestamp()
            tick['T'] = next_time

        except ValueError:
            errors = True

    pair = os.path.splitext(os.path.basename(filename))[0]
    return (pair, ticks, errors)


def _load_with_sparse_ticks(filename: str):
    """
    Load pair data and remove ticks with zero base volume.

    Arguments:
        pair:  The pair filename to load tick data from.

    Returns:
        (tuple):  A tuple containing:
            (str):       The pair that was passed, for joining on async tasks (taken from the filename base).
            list(dict):  A list of the loaded pair data.
            (bool):      Always False.

    """

    with open(filename) as file:
        ticks = json.load(file)

    sparse_ticks = []

    for tick in ticks:
        if tick['BV'] > 0.0:
            sparse_ticks.append(tick)

    pair = os.path.splitext(os.path.basename(filename))[0]
    return (pair, ticks, False)


if __name__ == '__main__':
    log.start()
    execute()
    log.stop()
