# -*- coding: utf-8 -*-

# Copyright (c) A 2017 Adam M. Rafuse - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited.
# Proprietary and confidential.

"""
Common base classes.
"""

__author__ = 'Adam Rafuse <$(echo nqnz.enshfr#tznvy.pbz | tr a-z# n-za-m@)>'
__all__ = ['Persistable']

from typing import Callable, Sequence, Tuple

import utils
import configuration

config = configuration.config
"""
Global configuration.
"""


class Persistable:
    """
    Persistable object.

    Represents an object whose attributes can be saved and restored to disk.
    """

    def __init__(self, log=utils.logging.DummyLogger()):
        self.log = utils.logging.ChildLogger(parent=log, scope=self)
        """
        Object logger.
        """

    def save_attr(self, attr_name: str, alt_name: str=None, convert: Sequence[Tuple[type, Callable]]=None,
                  max_depth: int=0, filter_items: Sequence[str]=None, filter_keys: Sequence[str]=None, force=False):
        """
        Save the specified attribute to disk.

        Arguments:
            attr_name:     Name of the attribute to persist, as per `getattr(self, attr_name)`.
            convert:       Optional Sequence of (type, Callable) tuples. If any item matches a type in the list,
                           save the result of Callable(item) instead of the item itself.            
            max_depth:     If > 0, treats the attribute as a dict and splits into subdirectories up to this depth, with
                           level 0 being the top-level name of the attribute. Assumes each additional level is a nested
                           dict, otherwise an AttributeError will be raised.
            filter_items:  If not None, only these lowest-depth dict items will be saved and others will be ignored.
            filter_keys:   If not None, only these higher-level dict keys will be saved and other will be ignored.
        """

        if not force and config['enable_backtest']:
            return

        save_name = alt_name if alt_name else attr_name
        utils.io.save_split(getattr(self, attr_name), save_name, config['state_path'], convert=convert,
                            max_depth=max_depth, filter_items=filter_items, filter_keys=filter_keys)
        self.log.debug("Saved'{}' to file(s).", attr_name, verbosity=1)

    def restore_attr(self, attr_name: str, alt_name: str=None, convert: Sequence[Tuple[type, Callable]]=None,
                     max_depth: int=0, filter_items: Sequence[str]=None, filter_keys: Sequence[str]=None):
        """
        Restore the specified attribute from disk, if any saved state exists.

        Arguments:
            attr_name:     The name of the attribute to restore, as per `getattr(self, attr_name)`.
            convert:       Optional Sequence of (type, Callable) tuples. If any loaded item matches a type in the list,
                           return the result of Callable(item) instead of the item itself.            
            max_depth:     The max depth the attribute was saved with as passed to :meth:`save_state`, representing the
                           lowest depth at which dict items are split into subdirectories.
            filter_items:  If not None, only these lowest-depth dict items will be restored and others will be ignored.
            filter_keys:   If not None, only these top-level dict keys will be restored and other will be ignored.
        """

        load_name = alt_name if alt_name else attr_name
        values = utils.io.load_split(load_name, config['state_path'], convert=convert, max_depth=max_depth,
                                     filter_items=filter_items, filter_keys=filter_keys)

        if values is not None:
            orig = getattr(self, attr_name)

            if isinstance(orig, dict):
                orig = utils.merge_dict(orig, values)
                setattr(self, attr_name, orig)

            else:
                setattr(self, attr_name, values)

            self.log.debug("Restored '{}' from file(s).", attr_name)
            self.log.debug("Restored '{}' value:\n{}", attr_name, values, verbosity=2)

        else:
            self.log.debug("No state for '{}' found in file(s).", attr_name, verbosity=1)
