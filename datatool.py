#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (c) 2017 Adam M. Rafuse - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential

"""
Tool for dealing with chart and snapshot data.
"""

import os
import sys
import json
import pickle
import asyncio
import argparse
import multiprocessing

from typing import Dict

sys.path.insert(0, 'lib/')

import utils
import common
import defaults

from configuration import config

config.update({
    'output_log': defaults.USER_PATH + defaults.TOOL_OUTPUT_LOG,
    'debug_log': defaults.USER_PATH + defaults.TOOL_DEBUG_LOG,
    'error_log': defaults.USER_PATH + defaults.TOOL_ERROR_LOG,
})

for directory in [config['user_path']]:
    if not os.path.exists(directory):
        os.makedirs(directory)

log = utils.logging.ThreadedLogger(scope='datatool', level=config['app_log_level'],
                                   logger_level=config['app_log_level'], debug_verbosity=0,
                                   filename=config['output_log'], debug_filename=config['debug_log'],
                                   error_filename=config['error_log'])


def main():
    """
    Main entry point.
    """

    expand_help = "Expand chart and snapshot data."
    node_help = "Node name eg. 'default'."
    mode_help = "Target mode ('backtest' or 'monitor')."
    format_help = "Source format ('json' or 'pickle')."

    arg_parser = argparse.ArgumentParser(description=__doc__)
    arg_parser.add_argument('-e', '--expand', action="store_true", help=expand_help)
    arg_parser.add_argument('-n', '--node', type=str, metavar='node', default='default', help=node_help)
    arg_parser.add_argument('-m', '--mode', type=str, metavar='"backtest"|"monitor"', help=mode_help)
    arg_parser.add_argument('-f', '--format', type=str, metavar='"json"|"pickle"', help=format_help)
    args = arg_parser.parse_args()

    if not args.mode:
        log.error("Argument '--mode' is required.")
        arg_parser.print_help()
        return

    if not args.format:
        log.error("Argument '--format' is required.")
        arg_parser.print_help()
        return

    if not args.expand:
        arg_parser.print_help()
        return

    args.format = args.format.lower()
    params = {'format': args.format}
    method = expand_data

    config['node_dir'] = args.node + '/'
    config['mode_dir'] = args.mode + '/'
    config['mode_path'] = config['user_path'] + config['node_dir'] + config['mode_dir']
    config['charts_path'] = config['mode_path'] + defaults.CHARTS_DIR
    config['snapshot_path'] = config['mode_path'] + defaults.SNAPSHOT_DIR

    if not os.path.exists(config['mode_path']):
        log.error("No such path exists: {}", config['mode_path'])
    elif args.format not in ['json', 'pickle']:
        log.error("Invalid format: {}", args.format)
    else:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(method(loop, params))


async def expand_data(_: asyncio.AbstractEventLoop, params: Dict[str, str]):
    """
    Expand data stored in a compact format (JSON or pickle).

    Arguments:
        _:       Event loop (unused, placehold for method signature).
        params:  Dictionary of parameters:
            'format' (str):  The format to expand from ('json' or 'pickle').
    """

    log.debug("Got expand data request for format {}.", params['format'])
    in_module = pickle if params['format'] == 'pickle' else json
    task_pool = multiprocessing.Pool()

    for result in os.walk(config['charts_path']):
        dirname = result[0]
        filenames = result[2]

        for in_filename in filenames:
            basename, extension = os.path.splitext(in_filename)
            if extension[1:] != params['format']:
                continue

            out_filename = "{}.{}".format(basename, 'svg')
            in_filepath = "{}/{}".format(dirname, in_filename)
            out_filepath = "{}/{}".format(dirname, out_filename)

            with open(in_filepath, 'rb') as in_file:
                data = in_module.load(in_file)
                log_text = "Expanded chart {} to SVG.".format(in_filename)
                task_pool.apply_async(_render_svg_chart, [basename, data, out_filepath, log_text],
                                      callback=_log_svg_completed)

    for result in os.walk(config['snapshot_path']):
        dirname = result[0]
        filenames = result[2]

        for in_filename in filenames:
            basename, extension = os.path.splitext(in_filename)
            if extension[1:] != params['format']:
                continue

            in_filepath = "{}/{}".format(dirname, in_filename)

            if any(word in in_filename for word in ['price', 'volume']):
                out_filename = "{}.{}".format(basename, 'svg')
                out_filepath = "{}/{}".format(dirname, out_filename)

                with open(in_filepath, 'rb') as in_file:
                    data = in_module.load(in_file)
                    log_text = "Expanded chart {} to SVG.".format(in_filename)
                    task_pool.apply_async(_render_svg_chart, [basename, data, out_filepath, log_text],
                                          callback=_log_svg_completed)

            elif params['format'] != 'json':
                out_filename = "{}.{}".format(basename, 'json')
                out_filepath = "{}/{}".format(dirname, out_filename)

                with open(in_filepath, 'rb') as in_file:
                    data = in_module.load(in_file)
                with open(out_filepath, 'w') as out_file:
                    json.dump(data, out_file, indent=2)
                log.info("Expanded metadata {} to JSON.", in_filename)

    task_pool.close()
    task_pool.join()


def _render_svg_chart(basename: str, data: dict, out_filepath: str, log_text: str):
    """
    """

    common.render_svg_chart(basename, data, out_filepath)
    return log_text


def _log_svg_completed(log_text: str):
    """
    """
    log.info(log_text)


if __name__ == '__main__':
    log.start()
    main()
    log.stop()
