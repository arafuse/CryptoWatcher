#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (c) 2017 Adam M. Rafuse - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential

"""
Analyze snapshots.
"""

__author__ = 'Adam Rafuse <$(echo nqnz.enshfr#tznvy.pbz | tr a-z# n-za-m@)>'

import os
import re
import glob
import json
import argparse

from typing import Sequence

import utils
import defaults

from configuration import config

NODE_DIR = 'default/'

SNAPTOOL_FILTERS = [
    {'match': 'SELL', 'excludes': []}
]

SNAPTOOL_COMPARE = [
    'BUY', 'SELL'
]

config.update({
    'app_debug': defaults.APP_DEBUG,
    'app_log_level': defaults.APP_LOG_LEVEL,
    'output_log': defaults.USER_PATH + defaults.TOOL_OUTPUT_LOG,
    'debug_log': defaults.USER_PATH + defaults.TOOL_DEBUG_LOG,
    'error_log': defaults.USER_PATH + defaults.TOOL_ERROR_LOG,
    'filters': SNAPTOOL_FILTERS
})

log = utils.logging.ThreadedLogger(level=config['app_log_level'], logger_level=utils.logging.INFO, debug_verbosity=2,
                                   filename=config['output_log'], debug_filename=config['debug_log'],
                                   error_filename=config['error_log'], scope='snaptool', module_name=__name__)
"""
Module logger.
"""


def main():
    """
    Dump an importable Session Buddy session as JSON to stdout that contains windows for all the snapshot sets that
    match configured filters.
    """

    node_help = "Node name eg. 'default'."
    mode_help = "Target mode ('backtest' or 'monitor')."

    arg_parser = argparse.ArgumentParser(description=__doc__)
    arg_parser.add_argument('-n', '--node', type=str, metavar='node', default='default', help=node_help)
    arg_parser.add_argument('-m', '--mode', type=str, metavar='"backtest"|"monitor"', help=mode_help)
    args = arg_parser.parse_args()

    if not args.mode:
        log.error("Argument '--mode' is required.")
        arg_parser.print_help()
        return

    config.update({
        'snapshot_path': defaults.USER_PATH + args.node + '/' + args.mode + '/' + defaults.SNAPSHOT_DIR,
    })

    names, json_filenames = get_names()
    followed_names = get_followed_names(json_filenames)
    windows = get_session_buddy_windows(names, followed_names, json_filenames)
    print(json.dumps(windows, indent=2))


def get_names():
    """
    Get a list of all filtered snapshot names and JSON filenames.
    """

    json_filenames = []
    names = []

    for rule in config['filters']:
        for result in os.walk(config['snapshot_path']):
            dirname = result[0]
            filenames = result[2]
            match_re = "{}.*\\.json$".format(rule['match'])

            for filename in filenames:
                if not re.search(match_re, filename):
                    continue

                name = re.sub(r"\.json$", "", filename, count=1)
                filtered = False

                for exclude_re in rule['excludes']:
                    if re.search(exclude_re, name):
                        filtered = True
                        break

                if not filtered:
                    names.append(name)
                    json_filenames.append(dirname + filename)

    return (names, json_filenames)


def get_followed_names(json_filenames: list):
    """
    Get a list of all followed snapshot names.
    """

    followed_names = []

    for json_filename in json_filenames:
        followed_names.append(get_followed_name(json_filename))

    return followed_names


def get_followed_name(json_filename):
    """
    Get the name from a JSON file's 'followed' field if it exists.
    """

    try:
        with open(json_filename) as data_file:
            data = json.load(data_file)
            return data['followed'][-1]['snapshot']

    except FileNotFoundError:
        log.warning("File '{}' not found.", json_filename)
    except json.JSONDecodeError:
        log.error("Could not decode JSON file {}.", json_filename)
    except (KeyError, IndexError):
        log.warning("No 'followed' property in JSON file {}.", json_filename)

    return None


def get_session_buddy_windows(names: Sequence[str], followed_names: Sequence[str], json_filenames: Sequence[str]):
    """
    Get an object of Session Buddy windows that can be imported into that extension as JSON.
    """

    windows = []

    for index, name in enumerate(names):
        followed_name = followed_names[index]

        file_urls = []

        def followed_extend(followed_name, file_urls):
            if followed_name is not None:
                followed_json_filename = config['snapshot_path'] + followed_name + '.json'
                followed_extend(get_followed_name(followed_json_filename), file_urls)

                file_urls.extend([
                    'file://' + followed_json_filename,
                    'file://' + config['snapshot_path'] + followed_name + ' price.svg',
                    'file://' + config['snapshot_path'] + followed_name + ' volume.svg',
                ])

        followed_extend(followed_name, file_urls)

        file_urls.extend([
            'file://' + json_filenames[index],
            'file://' + config['snapshot_path'] + name + ' price.svg',
            'file://' + config['snapshot_path'] + name + ' volume.svg',
            'file://' + config['snapshot_path'] + name + ' price follow-up.svg',
            'file://' + config['snapshot_path'] + name + ' volume follow-up.svg',
        ])

        tabs = []

        for file_url in file_urls:
            tabs.append({
                'url': file_url
            })

        window = {
            'state': "maximized",
            'tabs': tabs
        }

        windows.append(window)

    return {
        'windows': windows
    }


if __name__ == '__main__':
    log.start()
    main()
    log.stop()
