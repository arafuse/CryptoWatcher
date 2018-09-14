#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Various I/O utilities.
"""

__author__ = 'Adam Rafuse <$(echo nqnz.enshfr#tznvy.pbz | tr a-z# n-za-m@)>'
__version__ = "0.0.1a"
__license__ = "http://opensource.org/licenses/MIT"
__all__ = ['save_split', 'load_split']

import os
import re
import glob
import json

from typing import Callable, Sequence, Tuple

import utils


def save_split(obj_data: object, obj_name: str, root_dir='', convert: Sequence[Tuple[type, Callable]]=None,
               max_depth: int=0, filter_items: Sequence[str]=None, filter_keys: Sequence[str]=None,
               exclude_items: Sequence[str]=None):
    """
    Save an object to disk, potentially splitting it across different subdirectories and files.

    Useful for sharding dict items across multiple threads and/or processes.

    Arguments:
        obj_data:       The object to save.
        obj_name:       The name of the object to save as (corresponds to the top-level subdirectory or file name).
        root_dir:       The root directory to start in (default: '' for the current directory).
        convert:        Optional Sequence of (type, Callable) tuples. If any item matches a type in the list,
                        save the result of Callable(item) instead of the item itself.
        max_depth:      If > 0, treats the object as a dict and splits into subdirectories up to this depth, with
                        level 0 being the top-level name of the object. Assumes each additional level is a nested
                        dict, otherwise an AttributeError will be raised.
        filter_items:   If not None, only these lowest-depth items will be saved and others will be ignored.
        filter_keys:    If not None, only these higher-level keys will be saved and others will be ignored.
        exclude_items:  If specified, these lowest-depth items will be excluded.
    """

    def save_recursive(item_data: object, item_name: str, path: str='', depth: int=0):
        """
        Save an object by recursively splitting into subdirectories and files.
        """

        if depth == max_depth:
            save_item(item_data, item_name, path)

        else:
            if depth > 0 and filter_keys is not None and item_name not in filter_keys:
                return

            next_path = path + item_name + '/'
            next_full_path = root_dir + next_path

            if not os.path.exists(next_full_path):
                try:
                    os.mkdir(next_full_path)
                except FileExistsError:
                    pass  # Can happen due concurrency contention.

            for name, data in item_data.items():
                save_recursive(data, name, next_path, depth + 1)

    def save_item(item_data: object, item_name: str, path: str):
        """
        Save one object item to a split JSON file.
        """

        if exclude_items is not None and item_name in exclude_items:
            return

        if filter_items is not None and item_name not in filter_items:
            return

        filename = '{}{}{}.json'.format(root_dir, path, item_name)

        try:
            with open(filename, 'w') as item_file:
                if convert is not None:
                    for convert_tuple in convert:
                        if isinstance(item_data, convert_tuple[0]):
                            item_data = convert_tuple[1](item_data)

                json.dump(item_data, item_file, indent=2)
                utils.log.debug("Saved '{}' item '{}' to file.",
                                obj_name, item_name, verbosity=1)
                utils.log.debug("Saved '{}' item '{}' data:\n{}",
                                obj_name, item_name, item_data, verbosity=2)

        except OSError:
            utils.log.error('Error saving state file {}, check state directory for issues.', filename)

    save_recursive(obj_data, obj_name)


def load_split(obj_name: str, root_dir='', convert: Sequence[Tuple[type, Callable]]=None, max_depth: int=0,
               filter_items: Sequence[str]=None, filter_keys: Sequence[str]=None, exclude_items: Sequence[str]=None):
    """
    Load a value that was saved with with :func:`save_split`.

    Arguments:
        obj_name:      The name of the object to load (corresponds to the top-level subdirectory name).
        root_dir:      The root directory to start in (default: '' for the current directory).
        convert:       Optional Sequence of (type, Callable) tuples. If any loaded item matches a type in the list,
                       return the result of Callable(item) instead of the item itself.
        max_depth:     The max_depth the object was saved with (corresponding to the lowest depth at which items
                       are split into subdirectories). See 'max_depth' in :func:`save_split`.
        filter_items:  If not None, only these lowest-depth items will be loaded and others will be ignored.
        filter_keys:   If not None, only these higher-level keys will be loaded and others will be ignored.
    """

    def load_recursive(item_name: str, path: str='', depth: int=0):
        """
        Load an object by recursively looking for split files in a directory structure.
        """

        if depth == max_depth:
            return load_item(item_name, path)

        else:
            if depth > 0 and filter_keys is not None and item_name not in filter_keys:
                return None

            next_path = path + item_name + '/'
            next_full_path = root_dir + next_path

            if not os.path.exists(next_full_path):
                utils.log.debug('No object directory {} exists.', next_full_path)
                return None

            result = {}

            for name in glob.iglob(next_full_path + '*'):
                name = name.split('/')[-1]                    # Just the filename
                name = re.sub(r'\.json$', '', name, count=1)  # Without the extension

                load_recursive_to(result, name, next_path, depth + 1)

            return result

    def load_recursive_to(result: dict, item_name: str, path: str, depth):
        """
        Append the result of a recursive load to a dict if it is not filtered or missing.
        """

        data = load_recursive(item_name, path, depth)

        if data is not None:
            result[item_name] = data
            utils.log.debug("Loaded '{}' item '{}' from file.", obj_name, item_name, verbosity=1)
            utils.log.debug("Loaded '{}' item '{}' data:\n{}", obj_name, item_name, data, verbosity=2)

        else:
            if (not (exclude_items is not None and item_name in exclude_items) and not
                    (filter_items is not None and item_name not in filter_items) and not
                    (filter_keys is not None and item_name not in filter_keys)):

                utils.log.error("Failed to load '{}' item '{}' from file, " +
                                "incorrect depth or file is corrupt.", obj_name, item_name)

    def load_item(item_name: str, path: str):
        """
        Load one item from a split JSON item file.
        """

        if exclude_items is not None and item_name in exclude_items:
            return None

        if filter_items is not None and item_name not in filter_items:
            return None

        filename = '{}{}{}.json'.format(root_dir, path, item_name)

        try:
            with open(filename) as item_file:
                item_data = json.load(item_file)

                if convert is not None:
                    for convert_tuple in convert:
                        if isinstance(item_data, convert_tuple[0]):
                            return convert_tuple[1](item_data)

                return item_data

        except OSError:
            utils.log.debug('No object item file {} exists.', filename)
            return None

        except json.JSONDecodeError:
            utils.log.error('JSON format error reading object item file {}.', filename)
            return None

    return load_recursive(obj_name)
