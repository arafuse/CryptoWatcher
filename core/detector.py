# -*- coding: utf-8 -*-

# Copyright (c) A 2017 Adam M. Rafuse - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited.
# Proprietary and confidential.

"""
Detector service.

TODO: Possibly refactor into further components.
"""

__author__ = 'Adam Rafuse <$(echo nqnz.enshfr#tznvy.pbz | tr a-z# n-za-m@)>'
__all__ = ['Detector']

import math
import traceback
import asyncio

from typing import Any, Dict, List, Sequence, Tuple

import core
import utils
import common
import common.base
import common.math
import configuration

config = configuration.config
"""
Global configuration.
"""


class Detector(common.base.Persistable):
    """
    Detector service object.

    Handles detection of events in market data and dispatching of appropriate actions.
    """

    def __init__(self, market: core.Market, reporter: core.Reporter, trader: core.Trader,
                 time_prefix: str, log=utils.logging.DummyLogger()):

        super().__init__(log=log)

        self.market = market
        """
        Shared :class:`Market` service.
        """

        self.reporter = reporter
        """
        Shared :class:`Reporter` service.
        """

        self.trader = trader
        """
        Shared :class:`Trader` service.
        """

        self.time_prefix = time_prefix
        """
        Current time prefix, used for separating stat directories by time.
        """

        self.log = utils.logging.ChildLogger(parent=log, scope=self)
        """
        Object logger.
        """

        self.detection_triggers: Dict[str, List[List[Dict[str, Any]]]] = {}
        """
        Detection triggers for each currency pair. A trigger is a state and associated metadata for each condition in
        a detection rule. A detection is considered hit when all its conditions' triggers have been set.

        ``
        {
            (str):  Currency pair name eg. 'BTC-ETH'.
            {
                (str): Unique detection name.
                [
                    {
                        'time': (float):                UTC timestamp of last trigger check.
                        'set': (int):                   1 if this condition was triggered, else 0.
                        'ma_values': list(float):       Moving average values used for range checking.
                        'ma_distances': list(float):    Moving average distances used for range checking.
                        'ma_positions': list(int):      Relative MA positions used for crossover checking (0 or 1).
                        'ma_curves': list(float):       MA curves for surface rule checks.
                        'ma_slopes': list(float):       MA slopes for surface rule checks.
                        'vdma_values': list(float):     Volume derivative moving average values used for range checking.
                        'vdma_positions': list(int):    Relative VDMA positions used for crossover checking (0 or 1).
                        'vdma_y_positions': list(int):  Relative VDMA positions to Y axis (0 or 1).
                    },
                    ... for condition in config['detections'][detection]['conditions']
                ],
                ... for detection in config['detections']
            }
            ... for pair in currently and previously tracked pairs
        }
        ``
        """

        self.detection_stats: Dict[str, Dict[int, Dict[str, Any]]] = {self.time_prefix: {}}
        """
        Statistics on detections intended for export.

        ``
        {
            (str):  Currency pair name eg. 'BTC-ETH'.
            {
                (str):  Name of the detection.
                {
                    'count': (int):  The total number of times this detection was triggered.
                },
                ... for index in config['detections']
            },
            ... for pair in currently and previously tracked pairs
        }
        ``
        """

        self.last_detections: Dict[str, Dict[str, Dict[str, Any]]] = {}
        """
        Data on previous detections for each currency pair.

        ``
        {
            (str):  Currency pair name eg. 'BTC-ETH'.
            {
                (str):  Detection group name eg. 'breakout'.
                {
                    'name': (str):     Name of the last detection.
                    'type': (str):     Type of the last detection eg. 'confirm'.
                    'count': (int):    Number of consecutive occurrences of the last detection.
                    'value': (float):  Price value at the last detection.
                    'time': (float):   UTC timestamp in seconds at the last detection.
                }
                ... for group in previously triggered detection groups
            }
            ... for pair in currently and previously tracked pairs
        }
        ``
        """

        self.pair_states = {}
        """
        States for each currency pair.
        {
            (str):  Currency pair name eg. 'BTC-ETH'.
            {
                'newly_added': (bool):  True if this is a newly added pair.
                'startup_added': (bool):  True if this is a pair added on startup.
            }
        }
        """

        self.detection_states = {}
        """
        Detection states for each currency pair.
        {
            (str):  Currency pair name eg. 'BTC-ETH'.
            {
                (str):  Detection name.
                {
                    'occurrence': (int):       Occurrence of this detection.
                    'last_occurrence': (int):  Last occurrence of this detection.
                }
            }
        }
        """

        self.indicator_states = {}
        """
        Indicator states for each currency pair. The state of indicators for a pair globally affect the trading
        disposition for that pair.

        {
            (str):  Currency pair name eg. 'BTC-ETH'.
            {
                'RSI':
                {
                    'overbought': (bool):   True if overbought.
                    'oversold': (bool):     True if oversold.
                    'cross': (bool):        True if last crossed into oversold, False if last crossed into overbought.
                }
            }
        }
        """

        self.cache = {}
        """
        Cache of previous operation results. These are intended to only last within a given context (eg updating
        detection triggers).

        ``
        {
            (str): Currency pair name eg. 'BTC-ETH'.
            {
               (str): Item name eg. 'rule'.
               {
                    ... any number of key / value pairs or sub-dicts etc.
               }
               ... for item in any number of items
            }
            ... for pair in currently and previously tracked pairs
        }
        ``
        """

        self.action_lock = asyncio.Lock()
        """
        Lock used to serialize detection actions (buy / sell triggers etc.)
        """

        # Map of methods for detection rule checks.
        self.check_methods = {
            'ma_position': self._check_ma_position,
            'ma_crossover': self._check_ma_crossover,
            'ma_distance_min': self._check_ma_distances,
            'ma_distance_max': self._check_ma_distances,
            'ma_slope_min': self._check_ma_surfaces,
            'ma_slope_max': self._check_ma_surfaces,
            'ma_curve_min': self._check_ma_surfaces,
            'ma_curve_max': self._check_ma_surfaces,
            'ema_position': self._check_ma_position,
            'ema_crossover': self._check_ma_crossover,
            'ema_distance_min': self._check_ma_distances,
            'ema_distance_max': self._check_ma_distances,
            'ema_slope_min': self._check_ma_surfaces,
            'ema_slope_max': self._check_ma_surfaces,
            'ema_curve_min': self._check_ma_surfaces,
            'ema_curve_max': self._check_ma_surfaces,
            'vdma_crossover': self._check_vdma_crossover,
            'vdma_yposition': self._check_vdma_yposition,
            'vdma_xcrossover': self._check_vdma_xcrossover,
            'new_pair': self._check_new_pair,
            'startup_pair': self._check_startup_pair,
            'pair': self._check_pair,
            'pair_base': self._check_pair_base,
        }

        # Map of methods for detection filters. Order matters here, eg. 'occurrence' should be last.
        self.filter_methods = {
            'value_range_min': self._detection_filter_values,
            'value_range_max': self._detection_filter_values,
            'time_frame_min': self._detection_filter_time_frame,
            'distance_range': self._detection_filter_distances,
            'max_consecutive': self._detection_filter_consecutive,
            'follow': self._detection_filter_follow,
            'follow_all': self._detection_filter_follow_all,
            'follow_trade': self._detection_filter_follow_trade,
            'overlap': self._detection_filter_overlap,
            'occurrence': self._detection_filter_occurrence
        }

        # Map of methods for detection actions.
        self.action_methods = {
            'none': lambda *_: asyncio.sleep(0),
            'alert': self._alert_wrapper,
            'buy': self.trader.buy,
            'holdbuy': self.trader.hold,
            'rebuy': self.trader.rebuy,
            'sellpush': self.trader.sell_push,
            'pushrelease': self.trader.push_release,
            'softsell': self.trader.soft_sell,
            'hardsell': self.trader.hard_sell,
            'dumpsell': self.trader.dump_sell,
            'softstop': self.trader.soft_stop,
            'hardstop': self.trader.hard_stop,
            'stophold': self.trader.stop_hold,
            'refillon': self.trader.enable_refill,
            'refilloff': self.trader.disable_refill,
            'buyon': self.trader.enable_buy,
            'buyoff': self.trader.disable_buy,
            'pullout': self.trader.pullout,
            'reset': self._reset_detection_state
        }

    async def acquire_action_lock(self, waiter: str):
        """
        Acquire the :attr:`Detector.action_lock` lock and print a debug message if waiting for the lock.

        Arguments:
            waiter:  The name of the waiting coroutine, used for disambiguation in logging.
        """

        if self.action_lock.locked():
            self.log.debug('{}: Waiting for detection action in progress.', waiter)

        await self.action_lock.acquire()

    async def sync_pairs(self):
        """
        Synchronize currency pairs.

        This must be called after each time the list of market pairs is refreshed. Prepares any dicts that use pairs,
        and removes any stale detection data for pairs that are not currently being tracked to avoid false triggers.
        """

        for pair in self.market.pairs:
            await self._prepare_cache(pair)
            await self._prepare_pair_states(pair)
            await self._prepare_detection_states(pair)
            await self._prepare_indicator_states(pair)
            await self._prepare_detection_stats(pair)
            await self._prepare_last_detections(pair)

        remove_pairs = []

        for pair in self.detection_triggers:
            if pair not in self.market.pairs:
                remove_pairs.append(pair)

        for pair in remove_pairs:
            del self.detection_triggers[pair]

        remove_pairs = []

        for pair in self.last_detections:
            if pair not in self.market.pairs:
                remove_pairs.append(pair)

        for pair in remove_pairs:
            del self.last_detections[pair]

    async def sync_time_prefix(self, time_prefix: str):
        """
        Synchronize time prefix.

        Creates new :attr:`detection_stats` on the new prefix.
        """

        self.time_prefix = time_prefix
        self.detection_stats[time_prefix] = {}

        for pair in self.market.pairs:
            await self._prepare_detection_stats(pair)

    async def _prepare_cache(self, pair: str):
        """
        Prepare cache for the specified pair.

        Ensures that the necessary keys exist in :attr:`cache` before any operations are performed on them.

        Arguments:
            pair:  Name of the currency pair eg 'BTC-ETH'.
        """

        if pair not in self.cache:
            self.cache[pair] = {}

    async def _prepare_pair_states(self, pair: str):
        """
        Prepare general states for the specified pair.

        Ensures that the necessary keys exist in :attr:`pair_states` before any operations are performed on them.

        Arguments:
            pair:  Name of the currency pair eg 'BTC-ETH'.
        """

        if pair not in self.pair_states:
            self.pair_states[pair] = {
                'newly_added': False,
                'startup_added': False,
            }

    async def _prepare_detection_states(self, pair: str):
        """
        Prepare detection states for the specified pair.

        Ensures that the necessary keys exist in :attr:`detection_states` before any operations are performed on them.

        Arguments:
            pair:  Name of the currency pair eg 'BTC-ETH'.
        """

        if pair not in self.detection_states:
            self.detection_states[pair] = {}

        for detection_name in config['detections']:
            if detection_name not in self.detection_states[pair]:
                self.detection_states[pair][detection_name] = {
                    'occurrence': 0
                }

    async def _prepare_indicator_states(self, pair: str):
        """
        Prepare indicator states for the specified pair.

        Ensures that the necessary keys exist in :attr:`indicator_states` before any operations are performed on them.

        Arguments:
            pair:  Name of the currency pair eg 'BTC-ETH'.
        """

        if pair not in self.indicator_states:
            self.indicator_states[pair] = {
                'RSI': {
                    'overbought': False,
                    'oversold': False,
                    'descending': False
                }
            }

    async def _prepare_detection_stats(self, pair: str):
        """
        Prepare detection statistics for the specified pair.

        Ensures that the necessary keys exist in :attr:`detection_stats` before any operations are performed on them.

        Arguments:
            pair:  Name of the currency pair eg 'BTC-ETH'.
        """

        if pair not in self.detection_stats[self.time_prefix]:
            self.detection_stats[self.time_prefix][pair] = {}
            self.detection_stats[self.time_prefix][pair]['global'] = {
                'last_update_time': 0.0
            }

        for detection_name in config['detections']:
            if detection_name not in self.detection_stats[self.time_prefix][pair]:
                self.detection_stats[self.time_prefix][pair][detection_name] = {
                    'count': 0
                }

    async def _prepare_last_detections(self, pair: str):
        """
        Prepare last detections for the specified pair.

        Ensures that the necessary keys exist in :attr:`last_detections` before any operations are performed on them.

        Arguments:
            pair:  Name of the currency pair eg 'BTC-ETH'.
        """

        if pair not in self.last_detections:
            self.last_detections[pair] = {}

    async def _alert_wrapper(self, pair: str, detection_name: str, trigger_data: Dict[str, Any]):
        """
        Wrap :meth:`Reporter.send_alert` to adapt method signature for :attr:`action_methods`.
        """

        await self.reporter.send_alert(pair, trigger_data, detection_name, follow_up=False)

    async def update_detection_triggers(self, pair: str):
        """
        Update detection triggers for the specified pair based on configured detection rules.

        Arguments:
            pair:  Name of the currency pair eg 'BTC-ETH'.
        """

        self.cache[pair]['property'] = {}
        self.cache[pair]['rule'] = {}
        detections = {}

        for detection_name, detection in config['detections'].items():
            triggers = []

            for condition_index in range(len(detection['conditions'])):
                try:
                    old_trigger = self.detection_triggers[pair][detection_name][condition_index]
                    already_set = old_trigger['set']

                except (KeyError, IndexError):
                    already_set = 0

                if already_set:
                    test_trigger = await self._get_detection_trigger(pair, detection_name, condition_index)
                    trigger = old_trigger

                    if test_trigger['set']:
                        trigger['time'] = test_trigger['time']
                        self.log.debug("{} updating fulfilled detection '{}' condition {} time on re-trigger.",
                                       pair, detection_name, condition_index, verbosity=1)

                    self.log.debug("{} keeping fulfilled detection '{}' condition {}.",
                                   pair, detection_name, condition_index, verbosity=1)

                else:
                    trigger = await self._get_detection_trigger(pair, detection_name, condition_index)

                triggers.append(trigger)

            detections[detection_name] = triggers

        self.detection_stats[self.time_prefix][pair]['global']['last_update_time'] = self.market.close_times[pair][-1]
        self.detection_triggers[pair] = detections

        self.save_attr('detection_stats', max_depth=2, filter_items=[pair], filter_keys=[self.time_prefix])
        self.save_attr('detection_triggers', max_depth=1, filter_items=[pair])

    async def update_indicator_states(self, pair: str):
        """
        Update indicator states for the specified pair based on configured indicators.

        Arguments:
            pair:  Name of the currency pair eg 'BTC-ETH'.
        """

        if config['enable_rsi']:
            await self._update_rsi_states(pair)

    async def _update_rsi_states(self, pair: str):
        """
        Update states for the Relative Strength Index indicator.

        Arguments:
            pair:  Name of the currency pair eg 'BTC-ETH'.
        """

        was_overbought = self.indicator_states[pair]['RSI']['overbought']
        was_oversold = self.indicator_states[pair]['RSI']['oversold']

        overbought = bool(self.market.relative_strength_indexes[pair][-1] > config['rsi_overbought'])
        oversold = bool(self.market.relative_strength_indexes[pair][-1] < config['rsi_oversold'])

        self.indicator_states[pair]['RSI']['overbought'] = overbought
        self.indicator_states[pair]['RSI']['oversold'] = oversold

        if was_overbought and not overbought:
            self.indicator_states[pair]['RSI']['descending'] = True
            self.log.debug('{} RSI is descending.', verbosity=1)

        elif not was_oversold and oversold:
            self.indicator_states[pair]['RSI']['descending'] = False
            self.log.debug('{} RSI is ascending.', verbosity=1)

    async def process_detections(self, pair: str):
        """
        Update and dispatch any events based on detection triggers for the specified currency pair.

        Arguments:
            pair:  Name of the currency pair eg 'BTC-ETH'.
        """

        futures = []

        for detection_name, triggers in self.detection_triggers[pair].items():
            params = await self._get_detection_process_params(detection_name)
            await self._timeout_triggers(pair, detection_name, params, triggers)

            trigger_data = await self._aggregate_trigger_data(triggers)
            await self._normalize_trigger_values(trigger_data)
            trigger_data['current_time'] = self.market.close_times[pair][-1]

            if not await self._filter_detection(pair, detection_name, params, triggers, trigger_data):
                value_diff_percent = self.market.close_times[pair][-1] / self.market.close_times[pair][-2]
                if value_diff_percent <= config['detection_flash_crash_sens']:
                    self.log.warning("{} deferring action due to possible FLASH CRASH.")
                    continue

                coro = self._dispatch_detection_action(pair, detection_name, params, trigger_data)
                future = utils.async_task(coro, loop=common.loop)
                futures.append(future)

                await self._update_detection_stats(pair, detection_name)
                self.detection_triggers[pair][detection_name] = []

        for result in asyncio.as_completed(futures):
            await result

        self.log.debug('{} processed {} detections.', pair, len(self.detection_triggers[pair]), verbosity=1)

    async def _get_detection_process_params(self, detection_name: str) -> Dict[str, Any]:
        """
        Get the parameters from a detection needed for detection processing.

        Arguments:
            detection_name:  Name of the detection.

        Returns:
            The detection's processing parameters.
        """

        params = self.get_detection_params(detection_name, {
            'action': 'alert',
            'occurrence': 1,
            'groups': ['default'],
            'time_frame_min': None,
            'time_frame_max': None,
            'value_range_min': None,
            'value_range_max': None,
            'distance_range': None,
            'max_consecutive': None,
            'overlap': None,
            'follow': None,
            'follow_all': None,
            'follow_trade': None,
        })

        return params

    @staticmethod
    def get_detection_params(detection_name: str, params: dict) -> Dict[str, Any]:
        """
        Get specific parameters for a detection.

        Most parameters are optional and fall back to defaults to avoid spurious KeyErrors.

        Arguments:
            detection_name:  Name of the detection.
            params:          Dictionary of desired parameters with default values set.

        Returns:
            Dictionary of parameters with real values set. The original params dict passed as an argument is not
            modified.
        """

        set_params = {}

        for param in params:
            try:
                set_params[param] = config['detections'][detection_name][param]
            except KeyError:
                set_params[param] = params[param]

        return set_params

    async def restore_detection_triggers(self):
        """
        Restores persisted detection triggers.

        Discards any that are older than config['detection_restore_timeout'] or not in the list of market pairs,
        as these would be missing events and could lead to false triggers. This gives a short window to preserve some
        state for fast restarts or migrations (mostly to avoid missing key crossovers).
        """

        self.restore_attr('detection_triggers', max_depth=1, filter_items=self.market.pairs)

        for pair in self.market.pairs:
            if pair in self.market.close_times:
                current_time = self.market.close_times[pair][-1]
                last_update_time = self.detection_stats[self.time_prefix][pair]['global']['last_update_time']
                timeout = config['detection_restore_timeout_secs']

                if pair in self.detection_triggers:
                    if current_time - last_update_time > timeout:
                        self.log.warning("Dropping stale triggers for {}.", pair)
                        del self.detection_triggers[pair]

                    else:
                        self.log.info("Keeping restored triggers for {}.", pair)

    async def _get_detection_trigger(self, pair: str, detection_name: str, condition_index: int):
        """
        Get a detection trigger for a given pair, detection index, and condition index.

        Arguments:
            pair:             Name of the currency pair eg 'BTC-ETH'.
            detection_name:   Name of the detection.
            condition_index:  Index of the condition in the detection.

        Returns:
            trigger (dict):  Trigger data, see :attr:`detection_triggers`.
        """

        trigger = {
            'time': self.market.close_times[pair][-1],
            'ma_values': [],
            'ma_distances': [],
            'ma_norm_distances': [],
            'ma_positions': [],
            'vdma_values': [],
            'vdma_positions': [],
            'vdma_y_positions': [],
            'ma_curves': [],
            'ma_slopes': [],
            'newly_added': [],
            'startup_added': []
        }

        states = []

        for rule in config['detections'][detection_name]['conditions'][condition_index]:
            try:
                rule_name = rule[0]
                state, meta = await self.check_methods[rule_name](pair, rule, condition_index, detection_name)

                if state is not None:
                    states.append(state)
                    for key in meta or {}:
                        trigger[key].extend(meta[key])

            except (KeyError, IndexError) as e:
                self.log.warning("{} ignoring detection '{}' condition {} rule {}: {}: {}",
                                 pair, detection_name, condition_index, rule, type(e).__name__, e,)

        trigger['set'] = int(sum(states) == len(states))
        self.log.debug("{} states on detection '{}' condition {} are {}.",
                       pair, detection_name, condition_index, states, verbosity=1)

        return trigger

    async def _timeout_triggers(self, pair: str, detection_name: str, params: dict, triggers: Sequence[dict]):
        """
        Unset any triggers that have exceeded their timeout as specified in the detection parameters.

        Arguments:
            pair:      Name of the currency pair eg 'BTC-ETH'.
            params:    Detection processing parameters as returned by :meth:`_get_detection_process_params`.
            triggers:  Detection triggers to timeout, see :meth:`_get_detection_trigger`.
        """

        if params['time_frame_max'] is not None:
            current_time = self.market.close_times[pair][-1]

            for index, trigger in enumerate(triggers):
                if current_time - trigger['time'] > params['time_frame_max']:
                    trigger['set'] = 0

                    current_time_str = common.utctime_str(current_time, config['time_format'])
                    self.log.debug("{} detection '{}' trigger {} timed out at {}.",
                                   pair, detection_name, index, current_time_str)

    async def _aggregate_trigger_data(self, triggers: Sequence[dict]) -> Dict[str, Any]:
        """
        Aggregate the data for a list of detection triggers.

        Arguments:
            triggers:  Detection triggers to aggregate, see :meth:`_get_detection_trigger`.

        Returns:
            An aggregate of the data from the given triggers.
        """

        data = {
            'set_triggers': [],
            'times': [],
            'ma_values': [],
            'ma_distances': [],
            'ma_norm_distances': [],
            'ma_curves': [],
            'ma_slopes': [],
            'newly_added': [],
            'startup_added': [],
            'followed': [],
        }

        for trigger in triggers:
            data['times'].append(trigger['time'])
            data['set_triggers'].append(trigger['set'])
            data['ma_values'].extend(trigger['ma_values'])
            data['ma_distances'].extend(trigger['ma_distances'])
            data['ma_norm_distances'].extend(trigger['ma_norm_distances'])
            data['ma_curves'].extend(trigger['ma_curves'])
            data['ma_slopes'].extend(trigger['ma_slopes'])
            data['newly_added'].extend(trigger['newly_added'])
            data['startup_added'].extend(trigger['startup_added'])

        return data

    async def _normalize_trigger_values(self, trigger: Dict[str, Any]):
        """
        Add a field 'ma_norm_values' to trigger data from 'ma_values'

        Arguments:
            trigger:  Detection trigger to add normalized values to. Can also be an aggregate.
        """

        ma_values_max = max(trigger['ma_values']) if trigger['ma_values'] else 1.0
        if ma_values_max == 0.0: ma_values_max = 1.0  # Avoid division by zero
        trigger['ma_norm_values'] = [value / ma_values_max for value in trigger['ma_values']]

    @staticmethod
    async def _set_triggers_time_frame(triggers: List[Dict[str, Any]], trigger_data: Dict[str, Any]):
        """
        Set the field 'time_frame' to trigger data from the max and min trigger times.

        Arguments:
            triggers:      List of triggers.
            trigger_data:  Aggregate of trigger data as returned by :meth:`_aggregate_trigger_data`.
        """

        trigger_times = []

        for trigger in triggers:
            trigger_times.append(trigger['time'])

        if trigger_times:
            trigger_data['time_frame'] = max(trigger_times) - min(trigger_times)

    async def _filter_detection(self, pair: str, detection_name: str, params: Dict[str, Any],
                                triggers: List[Dict[str, Any]], trigger_data: Dict[str, Any]):
        """
        Filter a detection according to set triggers and any optional filters that may be defined.

        Arguments:
            pair:            Name of the currency pair eg 'BTC-ETH'.
            detection_name:  Name of the detection.
            params:          Detection processing parameters as returned by :meth:`_get_detection_process_params`.
            trigger_data:    Aggregate of trigger data as returned by :meth:`_aggregate_trigger_data`.

        Returns:
            True if the detection was filtered out, False if not.
        """

        triggered = bool(sum(trigger_data['set_triggers']) == len(trigger_data['set_triggers']))

        if triggered:
            await self._set_triggers_time_frame(triggers, trigger_data)

        for param, method in self.filter_methods.items():
            if triggered:
                if params[param] is not None:
                    if await method(pair, detection_name, trigger_data):
                        self.detection_triggers[pair][detection_name] = []
                        triggered = False
            else:
                break

        if triggered and config['trade_use_indicators'] and params['action'] in ['buy', 'rebuy']:
            if config['enable_rsi'] and self.indicator_states[pair]['RSI']['descending']:
                await self.reporter.send_alert(pair, trigger_data, detection_name, prefix='RSI SKIP BUY')
                self.detection_triggers[pair][detection_name] = []
                triggered = False

        if triggered:
            self._log_passed_detection(pair, detection_name)

        return not triggered

    def _log_passed_detection(self, pair: str, detection_name: str):
        """
        Emit a debug log message indicating the given detection passed the filter.

        Arguments:
            pair:            The currency pair eg 'BTC-ETH'.
            detection_name:  Name of the detection.
        """

        current_time = self.market.close_times[pair][-1]
        current_time_str = common.utctime_str(current_time, config['time_format'])
        self.log.debug("{} detection '{}' passed filtering at {}.",
                       pair, detection_name, current_time_str, stack_depth=1)

    async def _detection_filter_values(self, pair: str, detection_name: str, trigger_data: Dict[str, Any]) -> bool:
        """
        Filter a detection for the specified currency pair based on the 'value_range_min' and 'value_range_max'
        parameters.

        Arguments:
            pair:            Name of the currency pair eg 'BTC-ETH'.
            detection_name:  Name of the detection.
            trigger_data:    Aggregate of trigger data as returned by :meth:`_aggregate_trigger_data`.

        Returns:
            True if the detection was filtered, False if not.
        """

        if sum(trigger_data['set_triggers']) <= 1:
            return False

        values = trigger_data['ma_norm_values']
        params = self.get_detection_params(detection_name, {
            'value_range_min': None,
            'value_range_max': None,
        })

        if values:
            value_range = max(values) - min(values)
            trigger_data['value_range'] = value_range

            if params['value_range_max'] and value_range >= params['value_range_max']:
                self.log.debug("{} detection '{}' MA value range {} outside maximum {}.",
                               pair, detection_name, value_range, params['value_range_max'])
                return True

            if params['value_range_min'] and value_range < params['value_range_min']:
                self.log.debug("{} detection '{}' MA value range {} outside minimum {}.",
                               pair, detection_name, value_range, params['value_range_min'])
                return True

        return False

    async def _detection_filter_time_frame(self, _: str, detection_name: str,
                                           trigger_data: Dict[str, Any]) -> bool:
        """
        Filter a detection for the specified currency pair based on the 'time_frame_min' parameter.

        Arguments:
            pair:            Name of the currency pair eg 'BTC-ETH'.
            detection_name:  Name of the detection.
            trigger_data:    Aggregate of trigger data as returned by :meth:`_aggregate_trigger_data`.

        Returns:
            True if the detection was filtered, False if not.
        """

        if sum(trigger_data['set_triggers']) <= 1:
            return False

        params = self.get_detection_params(detection_name, {
            'time_frame_min': None,
        })

        if params['time_frame_min'] and trigger_data['time_frame'] < params['time_frame_min']:
            return True

        return False

    async def _detection_filter_distances(self, pair: str, detection_name: str,
                                          trigger_data: Dict[str, Any]) -> bool:
        """
        Filter a detection for the specified currency pair based on the 'distance_range' parameter.

        Arguments:
            pair:            Name of the currency pair eg 'BTC-ETH'.
            detection_name:  Name of the detection.
            trigger_data:    Aggregate of trigger data as returned by :meth:`_aggregate_trigger_data`.

        Returns:
            True if the detection was filtered, False if not.
        """

        if sum(trigger_data['set_triggers']) <= 1:
            return False

        params = self.get_detection_params(detection_name, {
            'distance_range': None,
        })

        distances = trigger_data['ma_norm_distances']
        if params['distance_range'] and max(distances) - min(distances) > params['distance_range']:
            self.log.debug("{} detection '{}' MA distances were outside the given range.", pair, detection_name)
            return True

        return False

    async def _detection_filter_consecutive(self, pair: str, detection_name: str, _: Dict[str, Any]) -> bool:
        """
        Filter a detection for the specified currency pair based on the 'max_consecutive' parameter.

        Arguments:
            pair:            Name of the currency pair eg 'BTC-ETH'.
            detection_name:  Name of the detection.

        Returns:
            True if the detection was filtered, False if not.
        """

        params = self.get_detection_params(detection_name, {
            'groups': ['default'],
            'max_consecutive': None
        })

        try:
            count = self.last_detections[pair][params['groups'][0]]['count']
            max_count = params['max_consecutive']
            if max_count and count > max_count:
                self.log.debug("{} detection '{}' exceeded {} consecutive occurences.", pair, detection_name, max_count)
                return True

        except KeyError:
            # No previous detections for this pair exist.
            pass

        return False

    async def _detection_filter_follow(self, pair: str, detection_name: str, trigger_data: Dict[str, Any]) -> bool:
        """
        Filter a detection for the specified currency pair based on the 'follow' parameter.

        Arguments:
            pair:            Name of the currency pair eg 'BTC-ETH'.
            detection_name:  Name of the detection.
            trigger_data:    Aggregate of trigger data as returned by :meth:`_aggregate_trigger_data`.

        Returns:
            True if the detection was filtered, False if not.
        """

        params = self.get_detection_params(detection_name, {
            'follow': [],
        })

        for index, item in enumerate(params['follow']):
            follow = {
                'groups': [],
                'types': [],
                'min_delta': None,
                'max_delta': None,
                'min_ma_delta': None,
                'max_ma_delta': None,
                'min_secs': config['detection_min_follow_secs'],
                'max_secs': config['detection_max_follow_secs'],
            }

            for rule in item:
                try:
                    follow[rule] = item[rule]
                except KeyError:
                    pass

            params['follow'][index] = follow  # pylint: disable=E1137

        for rule in params['follow']:
            for group in rule['groups']:
                if not await self._filter_follow_rule_group(pair, detection_name, rule, group, params, trigger_data):
                    return False

        return True

    async def _detection_filter_follow_all(self, pair: str, detection_name: str, trigger_data: Dict[str, Any]) -> bool:
        """
        Filter a detection for the specified currency pair based on the 'follow' parameter.

        Arguments:
            pair:            Name of the currency pair eg 'BTC-ETH'.
            detection_name:  Name of the detection.
            trigger_data:    Aggregate of trigger data as returned by :meth:`_aggregate_trigger_data`.

        Returns:
            True if the detection was filtered, False if not.
        """

        params = self.get_detection_params(detection_name, {
            'follow_all': [],
        })

        for index, item in enumerate(params['follow_all']):
            follow = {
                'groups': [],
                'types': [],
                'min_delta': None,
                'max_delta': None,
                'min_ma_delta': None,
                'max_ma_delta': None,
                'min_secs': config['detection_min_follow_secs'],
                'max_secs': config['detection_max_follow_secs'],
            }

            for rule in item:
                try:
                    follow[rule] = item[rule]
                except KeyError:
                    pass

            params['follow_all'][index] = follow  # pylint: disable=E1137

        num_passed = 0
        for rule in params['follow_all']:
            for group in rule['groups']:
                if not await self._filter_follow_rule_group(pair, detection_name, rule, group, params, trigger_data):
                    num_passed += 1
                    break

        return not num_passed == len(params['follow_all'])

    async def _filter_follow_rule_group(self, pair: str, detection_name: str, rule: Dict[str, Any], group: str,
                                        _: Dict[str, Any], trigger_data: Dict[str, Any]):
        """
        Filter a detection follow rule by the given group and current time and delta conditions.

        TODO: Explain the algorithm in more detail.

        Appends the additional fields 'name', 'time', and 'delta' to the list of followed detections in the passed
        trigger data.

        Arguments:
            pair:          Name of the currency pair eg 'BTC-ETH'.
            rule:          The follow rule dict from the detection to filter on.
            group:         Name of the detection group to filter on
            params:        Filter parameters for the detection.
            trigger_data:  Aggregate of trigger data as returned by :meth:`_aggregate_trigger_data`.

        Returns:
            True if the detection was filtered, False if not.
        """

        current_value = self.market.adjusted_close_values[pair][-1]
        current_time = self.market.close_times[pair][-1]
        current_time_str = common.utctime_str(current_time, config['time_format'])

        try:
            if None in rule['types'] and group not in self.last_detections[pair]:
                return False

            if self.last_detections[pair][group]['type'] in rule['types']:
                last_name = self.last_detections[pair][group]['name']
                last_time = self.last_detections[pair][group]['time']
                last_time_str = common.utctime_str(last_time, config['time_format'])
                last_norm_value = self.last_detections[pair][group]['value'] / current_value
                last_ma_norm_value = self.last_detections[pair][group]['ma_value'] / current_value
                follow_delta = 1.0 - last_norm_value
                follow_ma_delta = 1.0 - last_ma_norm_value

                if rule['min_secs'] is not None and current_time < last_time + rule['min_secs']:
                    self.log.debug("{} detection '{}' at {} occurred too soon after '{}' at {}.",
                                   pair, detection_name, current_time_str, last_name, last_time_str)

                elif rule['max_secs'] is not None and current_time > last_time + rule['max_secs']:
                    self.log.debug("{} detection '{}' at {} occurred too late after '{}' at {}.",
                                   pair, detection_name, current_time_str, last_name, last_time_str)

                elif rule['min_delta'] is not None and follow_delta < rule['min_delta']:
                    self.log.debug("{} detection '{}' at {} occurred too far below '{}' at {}.",
                                   pair, detection_name, current_time_str, last_name, last_time_str)

                elif rule['max_delta'] is not None and follow_delta >= rule['max_delta']:
                    self.log.debug("{} detection '{}' at {} occurred too far above '{}' at {}.",
                                   pair, detection_name, current_time_str, last_name, last_time_str)

                elif rule['min_ma_delta'] is not None and follow_ma_delta < rule['min_ma_delta']:
                    self.log.debug("{} detection '{}' at {} occurred too far below '{}' at {}.",
                                   pair, detection_name, current_time_str, last_name, last_time_str)

                elif rule['max_ma_delta'] is not None and follow_ma_delta >= rule['max_ma_delta']:
                    self.log.debug("{} detection '{}' at {} occurred too far above '{}' at {}.",
                                   pair, detection_name, current_time_str, last_name, last_time_str)

                else:
                    trigger_data['followed'].append({
                        'snapshot': '{} {} {}'.format(pair, last_name, last_time_str),
                        'name': last_name,
                        'time': last_time,
                        'delta': follow_delta,
                    })
                    return False

        except KeyError:
            # No previous detection group for this pair exists.
            pass

        return True

    async def _detection_filter_follow_trade(self, pair: str, detection_name: str,
                                             _: Dict[str, Any]) -> bool:
        """
        Filter a detection for the specified currency pair based on the 'follow_trade' parameter.

        Arguments:
            pair:            Name of the currency pair eg 'BTC-ETH'.
            detection_name:  Name of the detection.

        Returns:
            True if the detection was filtered, False if not.
        """

        params = self.get_detection_params(detection_name, {
            'follow_trade': [],
        })

        for index, item in enumerate(params['follow_trade']):
            follow = {
                'types': [],
                'min_delta': None,
                'max_delta': None,
                'min_secs': config['detection_min_follow_secs'],
                'max_secs': config['detection_max_follow_secs']
            }

            for rule in item:
                try:
                    follow[rule] = item[rule]
                except KeyError:
                    pass

            params['follow_trade'][index] = follow

        for rule in params['follow_trade']:
            if not await self._filter_follow_trade_rule(pair, detection_name, rule, params):
                return False

        return True

    async def _filter_follow_trade_rule(self, pair: str, detection_name: str, rule: Dict[str, Any],
                                        _: Dict[str, Any]) -> bool:
        """
        Filter a detection follow trade rule by the last trade time and values.

        Arguments:
            pair:  Name of the currency pair eg 'BTC-ETH'.
            rule:  The follow trade rule dict from the detection to filter on.

        Returns:
            True if the detection was filtered, False if not.
        """

        current_value = self.market.adjusted_close_values[pair][-1]
        current_time = self.market.close_times[pair][-1]
        current_time_str = common.utctime_str(current_time, config['time_format'])

        for follow_type in rule['types']:
            last_value = self.trader.last_trades[pair][follow_type]['value']
            last_norm_value = last_value / current_value if last_value is not None else None
            follow_delta = 1.0 - last_norm_value if last_norm_value is not None else None
            last_time = self.trader.last_trades[pair][follow_type]['time']

            if rule['min_secs'] is not None:
                if last_time is None:
                    continue
                if current_time < last_time + rule['min_secs']:
                    last_time_str = common.utctime_str(last_time, config['time_format'])
                    self.log.debug("{} detection '{}' at {} occurred too soon after '{}' at {}.",
                                   pair, detection_name, current_time_str, follow_type, last_time_str)
                    continue

            if rule['max_secs'] is not None:
                if last_time is None:
                    continue
                if current_time > last_time + rule['max_secs']:
                    last_time_str = common.utctime_str(last_time, config['time_format'])
                    self.log.debug("{} detection '{}' at {} occurred too late after '{}' at {}.",
                                   pair, detection_name, current_time_str, follow_type, last_time_str)
                    continue

            if rule['min_delta'] is not None:
                if follow_delta is None:
                    continue
                if follow_delta < rule['min_delta']:
                    last_time_str = common.utctime_str(last_time, config['time_format'])
                    self.log.debug("{} detection '{}' at {} occurred too far below after '{}' at {}.",
                                   pair, detection_name, current_time_str, follow_type, last_time_str)
                    continue

            if rule['max_delta'] is not None:
                if follow_delta is None:
                    continue
                if follow_delta >= rule['max_delta']:
                    last_time_str = common.utctime_str(last_time, config['time_format'])
                    self.log.debug("{} detection '{}' at {} occurred too far above after '{}' at {}.",
                                   pair, detection_name, current_time_str, follow_type, last_time_str)
                    continue

            return False

        return True

    async def _detection_filter_overlap(self, pair: str, detection_name: str, trigger_data: Dict[str, Any]) -> bool:
        """
        Filter a detection for the specified currency pair based on the 'overlap' parameter.

        Arguments:
            pair:            Name of the currency pair eg 'BTC-ETH'.
            detection_name:  Name of the detection.
            trigger_data:    Aggregate of trigger data as returned by :meth:`_aggregate_trigger_data`.

        Returns:
            True if the detection was filtered, False if not.
        """

        params = self.get_detection_params(detection_name, {
            'overlap': None,
            'action': None
        })

        if not params['action'] in ['buy', 'rebuy']:
            return False

        min_time = params['overlap']
        current_time = self.market.close_times[pair][-1]
        last_open_time = self.trader.trades[pair]['last_open_time']
        has_open_trades = self.trader.trades[pair]['open']

        if min_time and has_open_trades and (current_time - last_open_time) / 60 < min_time:
            self.log.info("{} Cannot overlap new buy trade before {} minutes.", pair, min_time)
            await self._update_detection_stats(pair, detection_name, detection_type='skip')
            await self.reporter.send_alert(pair, trigger_data, detection_name, prefix='OVERLAP SKIP BUY')
            return True

        return False

    async def _detection_filter_occurrence(self, pair: str, detection_name: str, _: Dict[str, Any]) -> bool:
        """
        Filter a detection for the specified currency pair based on the 'occurrence' parameter.

        Arguments:
            pair:            Name of the currency pair eg 'BTC-ETH'.
            detection_name:  Index of the detection.
            trigger_data:    Aggregate of trigger data as returned by :meth:`_aggregate_trigger_data`.

        Returns:
            True if the detection was filtered, False if not.
        """

        params = self.get_detection_params(detection_name, {
            'occurrence': 1,
        })

        self.detection_states[pair][detection_name]['occurrence'] += 1
        if self.detection_states[pair][detection_name]['occurrence'] < params['occurrence']:
            await self._update_detection_stats(pair, detection_name, detection_type='skip')
            self.log.info("{} detection '{}' must occur at least {} times.", pair, detection_name, params['occurrence'])
            return True

        self.detection_states[pair][detection_name]['occurrence'] = 0
        return False

    async def _dispatch_detection_action(self, pair: str, detection_name: str, params: Dict[str, Any],
                                         trigger_data: Dict[str, Any]):
        """
        Dispatch appropriate action for a triggered detection.

        Arguments:
            pair:            Name of the currency pair eg 'BTC-ETH'.
            detection_name:  Name of the detection.
            params:          Detection processing parameters as returned by :meth:`_get_detection_process_params`.
            trigger_data:    Aggregate of trigger data as returned by :meth:`_aggregate_trigger_data`.
        """

        await self.acquire_action_lock("{} detection action dispatch".format(pair))

        try:
            await self.action_methods[params['action']](pair, detection_name, trigger_data)
        except KeyError as e:
            await self.reporter.send_alert(pair, trigger_data, detection_name)
            self.log.error("KeyError: {}\n{}", e, ''.join(traceback.format_tb(e.__traceback__)))
            self.log.warning("{} detection '{}' invalid action '{}', defaulting to 'alert'.",
                             pair, detection_name, params['action'])

        self.save_attr('detection_states', max_depth=1, filter_items=[pair])

        self.action_lock.release()

    async def _update_detection_stats(self, pair: str, detection_name: str, detection_type: str=None):
        """
        Update the statistics for the specified pair and detection index for a positive detection.

        Arguments:
            pair:            Name of the currency pair eg 'BTC-ETH'.
            detection_name:  Name of the detection.
            detection_type:  Override detection type set if not None.
        """

        self.detection_stats[self.time_prefix][pair][detection_name]['count'] += 1

        params = self.get_detection_params(detection_name, {
            'groups': ['default'],
            'type': 'default'
        })

        current_time = self.market.close_times[pair][-1]
        last_value = self.market.adjusted_close_values[pair][-1]

        try:
            ma_value = self.detection_triggers[pair][detection_name][0]['ma_values'][0]
        except (KeyError, IndexError):
            ma_value = last_value

        for group in params['groups']:
            try:
                last_detections = self.last_detections[pair][group]

                if last_detections['name'] == detection_name:
                    last_detections['count'] += 1
                    last_detections['value'] = self.market.adjusted_close_values[pair][-1]
                    last_detections['ma_value'] = ma_value
                    last_detections['time'] = current_time
                    reset = False

                else:
                    reset = True

            except KeyError:
                self.last_detections[pair][group] = {}
                last_detections = self.last_detections[pair][group]
                last_detections['type'] = None
                reset = True

            if reset:
                if last_detections['type'] != params['type']:
                    last_detections['orig_name'] = detection_name
                    last_detections['type'] = detection_type or params['type']

                last_detections['name'] = detection_name
                last_detections['count'] = 1
                last_detections['value'] = self.market.adjusted_close_values[pair][-1]
                last_detections['ma_value'] = ma_value
                last_detections['time'] = current_time

        self.save_attr('detection_stats', max_depth=2, filter_items=[pair], filter_keys=[self.time_prefix])
        self.save_attr('last_detections', max_depth=1, filter_items=[pair])

        self.log.debug('{} updated detection statistics.', pair, verbosity=2)

    async def _check_ma_distances(self, pair: str, rule: tuple,
                                  condition_index: int, detection_name: str) -> Tuple[int, dict]:
        """
        Check moving average distances for the ma_distance_min' and 'ma_distance_max' detection rules.

        The moving average distances checked are normalized. Rule tuples for this method have the following format:
            ('ma_distance_(min|max)', first_ma_value:int, second_ma_value:int, norm_distance:float)

        Arguments:
            pair:             Currency pair for this rule to check eg. 'BTC-ETH'.
            rule:             Rule tuple to check against.
            condition_index:  Name of the condition this rule belongs to.
            detection_name:   Name of the detection this rule belongs to.

        Returns:
            (tuple):  A tuple containing:

            state (int):       1 if the mas meet the constraint, 0 if not, or None if the rule was invalid.
            metadata (dict):   A dict containing the following metadata values (or None if the rule was invalid):
                'ma_values': list(float):          The values of each moving average.
                'ma_distances': list(float):       The distance between the moving averages.
                'ma_norm_distances': list(float):  The normalized distance between the moving averages.
        """

        try:
            return self.cache[pair]['rule'][rule]
        except KeyError:
            pass

        try:
            rule_name = rule[0]
            ma_type = rule_name.split('_', 1)[0]

            if ma_type == 'ema':
                rule_name = rule_name[1:]
                ma_windows = config['ema_windows']
                mas = self.market.close_value_emas
            else:
                ma_windows = config['ma_windows']
                mas = self.market.close_value_mas

            bounds_index = ['ma_distance_min', 'ma_distance_max'].index(rule_name)

            first_ma_value = ma_windows[rule[1]]
            second_ma_value = ma_windows[rule[2]]
            first_ma = mas[pair][first_ma_value]
            second_ma = mas[pair][second_ma_value]

        except (IndexError, ValueError) as e:
            self.log.warning(("{} ignoring invalid rule '{}' in detection '{}' condition {}: {}"),
                             pair, rule, detection_name, condition_index, str(e))

            return (None, None)

        try:
            if math.isclose(first_ma[-1], 0.0) or math.isclose(second_ma[-1], 0.0):
                raise IndexError()

            ma_values = [first_ma[-1], second_ma[-1]]
            ma_norm_values = [value / max(ma_values) for value in ma_values]

            norm_distance_range = rule[3]
            distance = abs(ma_values[0] - ma_values[1])
            norm_distance = abs(ma_norm_values[0] - ma_norm_values[1])

            metadata = {'ma_values': ma_values, 'ma_distances': [distance], 'ma_norm_distances': [norm_distance]}

            if bounds_index == 0:
                result = (int(norm_distance >= norm_distance_range), metadata)
            else:
                result = (int(norm_distance <= norm_distance_range), metadata)

            self.cache[pair]['rule'][rule] = result
            return result

        except IndexError:
            if not (not common.is_trade_base_pair(pair) and ma_type == 'ema' and config['ema_trade_base_only']):
                self.log.debug(("{} not enough MA data yet for detection '{}', condition {}, rule {}: "
                                "value {} size {}, value {} size {}."),
                               pair, detection_name, condition_index, rule,
                               first_ma_value, len(first_ma), second_ma_value, len(second_ma))

            return (0, None)

    async def _check_ma_position(self, pair: str, rule: tuple,
                                 condition_index: int, detection_name: str) -> Tuple[int, dict]:
        """
        Check the relative position of two moving averages for the 'ma_position' detection rule.

        Rule tuples for this method have the following format:
            ('ma_position', first_ma_value:int, second_ma_value:int)

        Arguments:
            pair:             Currency pair to check this rule against eg. 'BTC-ETH'.
            rule:             The rule tuple to check against.
            condition_index:  Index of the condition this rule belongs to.
            detection_name:   Name of the detection this rule belongs to.

        Returns:
            (tuple):  A tuple containing:

            state (int):       1 if the first ma is above the second, 0 if not, or None if the rule was invalid.
            metadata (dict):   A dict containing the following metadata values (or None if the rule was invalid):
                'ma_values': (float):  The values of each moving average.
        """

        try:
            return self.cache[pair]['rule'][rule]
        except KeyError:
            pass

        try:
            rule_name = rule[0]
            ma_type = rule_name.split('_', 1)[0]

            if ma_type == 'ema':
                rule_name = rule_name[1:]
                ma_windows = config['ema_windows']
                mas = self.market.close_value_emas
            else:
                ma_windows = config['ma_windows']
                mas = self.market.close_value_mas

            first_ma_value = ma_windows[rule[1]]
            second_ma_value = ma_windows[rule[2]]
            first_ma = mas[pair][first_ma_value]
            second_ma = mas[pair][second_ma_value]

        except IndexError as e:
            self.log.warning(("{} ignoring invalid rule '{}' in detection '{}' condition {}: {}"),
                             pair, rule, detection_name, condition_index, str(e))

            return (None, None)

        try:
            if math.isclose(first_ma[-1], 0.0) or math.isclose(second_ma[-1], 0.0):
                raise IndexError()

            if first_ma[-1] < second_ma[-1]:
                ma_position_text = 'below'
                ma_position = 0

            else:
                ma_position_text = 'above'
                ma_position = 1

            metadata = {'ma_values': [first_ma[-1], second_ma[-1]]}

            self.log.debug("{} MA {} is {} MA {} in detection '{}', condition {}, rule {}.",
                           pair, first_ma_value, ma_position_text, second_ma_value, detection_name, condition_index,
                           rule, verbosity=1)

        except IndexError:
            if not (not common.is_trade_base_pair(pair) and ma_type == 'ema' and config['ema_trade_base_only']):
                self.log.debug(("{} not enough MA data yet for detection '{}', condition {}, rule {}: "
                                "value {} size {}, value {} size {}."),
                               pair, detection_name, condition_index, rule,
                               first_ma_value, len(first_ma), second_ma_value, len(second_ma))

            return (0, None)

        result = (ma_position, metadata)
        self.cache[pair]['rule'][rule] = result
        return result

    async def _check_ma_crossover(self, pair: str, rule: tuple,
                                  condition_index: int, detection_name: str) -> Tuple[int, dict]:
        """
        Check for the upward crossover of two moving averages for the 'ma_crossover' detection rule.

        Rule tuples for this method have the following format:
            ('ma_crossover', first_ma_value:int, second_ma_value:int)

        Arguments:
            pair:             Currency pair to check this rule against eg. 'BTC-ETH'.
            rule:             The rule tuple to check against.
            condition_index:  Index of the condition this rule belongs to.
            detection_name:   Name of the detection this rule belongs to.

        Returns:
            (tuple):  A tuple containing:

            state (int):      1 if the first ma just crossed over the second, 0 if not, or None if the rule was invalid.
            metadata (dict):  A dict containing the following metadata values (or None if the rule was invalid):
                'ma_values' list(float):   The midpoint between the two moving averages (cross point if crossed).
                'ma_positions' list(int):  1 if the first moving average is above or at the second, 0 if not.

        """

        try:
            return self.cache[pair]['rule'][rule]
        except KeyError:
            pass

        try:
            rule_name = rule[0]
            ma_type = rule_name.split('_', 1)[0]

            if ma_type == 'ema':
                rule_name = rule_name[1:]
                ma_windows = config['ema_windows']
                mas = self.market.close_value_emas
            else:
                ma_windows = config['ma_windows']
                mas = self.market.close_value_mas

            first_ma_value = ma_windows[rule[1]]
            second_ma_value = ma_windows[rule[2]]
            first_ma = mas[pair][first_ma_value]
            second_ma = mas[pair][second_ma_value]

        except (IndexError, TypeError) as e:
            self.log.warning(("{} ignoring invalid rule '{}' in detection '{}' condition {}: {}"),
                             pair, rule, detection_name, condition_index, str(e))

            return (None, None)

        try:
            if math.isclose(first_ma[-2], 0.0) or math.isclose(second_ma[-2], 0.0):
                raise IndexError()

            if first_ma[-1] < second_ma[-1]:
                ma_position_text = 'below'
                ma_position = 0
                ma_crossover = 0

            else:
                ma_position_text = 'above'
                ma_position = 1

                try:
                    trigger = self.detection_triggers[pair][detection_name][condition_index]

                    if trigger['ma_positions'][0] == 0:
                        ma_crossover = 1
                        self.log.debug("{} MA {} crossed over MA {} in detection '{}' condition {} rule {}.",
                                       pair, first_ma_value, second_ma_value, detection_name, condition_index, rule,
                                       verbosity=1)

                    else:
                        ma_crossover = 0

                except (KeyError, IndexError):
                    # No previous MA position exists yet to check against.
                    ma_crossover = 0

        except IndexError:
            if not (not common.is_trade_base_pair(pair) and ma_type == 'ema' and config['ema_trade_base_only']):
                self.log.debug(("{} not enough MA data yet for detection '{}', condition {}, rule {}: "
                                "value {} size {}, value {} size {}."),
                               pair, detection_name, condition_index, rule,
                               first_ma_value, len(first_ma), second_ma_value, len(second_ma))

            return (0, {'ma_values': [0.0], 'ma_positions': [0]})

        self.log.debug("{} MA {} is {} MA {} in detection '{}', condition {}, rule {}.",
                       pair, first_ma_value, ma_position_text, second_ma_value,
                       detection_name, condition_index, rule, verbosity=1)

        result = (ma_crossover, {'ma_values': [first_ma[-1], second_ma[-1]], 'ma_positions': [ma_position]})
        self.cache[pair]['rule'][rule] = result

        return result

    async def _check_ma_surfaces(self, pair: str, rule: tuple,
                                 condition_index: int, detection_name: str) -> Tuple[int, dict]:
        """
        Check moving average surfaces.

        Checks properties of a moving average surface (slope, curvature) for detection rules ma_slope_min,
        ma_slope_max, ma_curve_min, and ma_curve_max.

        Rule tuples for this method have the following format:
            ('ma_(slope|curve)_(min|max)', ma_value:int, value:float)

        Arguments:
            pair:             Currency pair for this rule to check eg. 'BTC-ETH'.
            rule:             Rule tuple to check against.
            condition_index:  Index of the condition this rule belongs to.
            detection_name:   Name of the detection this rule belongs to.

        Returns:
            (tuple):  A tuple containing:

            state (int):  1 if the ma meets the constraint, 0 if not, or None if the rule was invalid.
            meta (dict):
                'ma_*s': list(float):  The values of each slope or curve, depending on the rule passed.
        """

        try:
            return self.cache[pair]['rule'][rule]
        except KeyError:
            pass

        methods = {
            'slope': common.math.norm_slope_avg,
            'curve': common.math.curvature_avg
        }

        try:
            rule_name = rule[0]
            name_parts = rule_name.split('_')
            ma_type = name_parts[0]

            if ma_type == 'ema':
                rule_name = rule_name[1:]
                ma_windows = config['ema_windows']
                mas = self.market.close_value_emas
            else:
                ma_windows = config['ma_windows']
                mas = self.market.close_value_mas

            prop_name = name_parts[1]
            bounds_name = name_parts[2]
            bounds_index = ['min', 'max'].index(bounds_name)
            _ = ['slope', 'curve'].index(prop_name)

            ma_value_index = rule[1]
            value_range = rule[2]

        except (IndexError, ValueError) as e:
            self.log.warning(("{} ignoring invalid rule '{}' in detection '{}' condition {}: {}"),
                             pair, rule, detection_name, condition_index, str(e))

            return (None, None)

        try:
            ma_value = ma_windows[ma_value_index]
            prop_cache_key = (ma_type + prop_name, ma_value)

            try:
                prop_value = self.cache[pair]['property'][prop_cache_key]

            except KeyError:
                if ma_value_index < 1:
                    sample_size = ma_windows[0]
                elif ma_value_index > 6:
                    sample_size = ma_windows[5]
                else:
                    sample_size = ma_windows[ma_value_index - 1]

                ma = mas[pair][ma_value]
                ma_sample = ma[-(sample_size):]

                if math.isclose(ma_sample[0], 0.0):
                    raise IndexError("Sample contains padding data.")

                if len(ma_sample) < sample_size:
                    raise IndexError("Not enough data in sample.")

                prop_value = methods[prop_name](ma_sample) * 1000
                self.cache[pair]['property'][prop_cache_key] = prop_value

            if bounds_index == 0:
                is_set = int(prop_value >= value_range)
            else:
                is_set = int(prop_value <= value_range)

            meta_name = 'ma_{}s'.format(prop_name)
            metadata = {meta_name: [prop_value]}

            self.log.debug("{} MA {} {} is {} in detection '{}', condition {}, rule {}.",
                           pair, ma_value, prop_name, prop_value, detection_name, condition_index, rule,
                           verbosity=1)

            result = (is_set, metadata)
            self.cache[pair]['rule'][rule] = result

            return result

        except (ValueError, IndexError):
            if not (not common.is_trade_base_pair(pair) and ma_type == 'ema' and config['ema_trade_base_only']):
                self.log.debug(("{} not enough MA data yet for detection '{}', condition {}, rule {}: "
                                "value {} size {}."),
                               pair, detection_name, condition_index, rule, ma_value, len(ma))

            return (0, None)

    async def _check_vdma_yposition(self, pair: str, rule: tuple,
                                    condition_index: int, detection_name: str) -> Tuple[int, dict]:
        """
        Check the relative position of a volume derivative moving average to a y-axis value.

        Rule tuples for this method have the following format:
            ('vdma_yposition', vdma_value:int, yaxis_value:float, gt_or_equal:bool)

        Arguments:
            pair:             Currency pair to check this rule against eg. 'BTC-ETH'.
            rule:             The rule tuple to check against.
            condition_index:  Index of the condition this rule belongs to.
            detection_name:   Name of the detection this rule belongs to.

        Returns:
            (tuple):  A tuple containing:
              (int):    1 if the first ma is above the second, 0 if not, or None if the rule was invalid.
              (dict):   A dict containing the following metadata values (or None if the rule was invalid):
                'ma_values': (float):  The values of each moving average.
        """

        try:
            return self.cache[pair]['rule'][rule]
        except KeyError:
            pass

        try:
            ma_windows = config['vdma_windows']
            mas = self.market.volume_deriv_mas
            first_ma_value = ma_windows[rule[1]]
            yaxis_value = rule[2]
            gt_or_equal = rule[3]
            first_ma = mas[pair][first_ma_value]

        except IndexError as e:
            log_format = "{} ignoring invalid rule '{}' in detection '{}' condition {}: {}"
            self.log.warning(log_format, pair, rule, detection_name, condition_index, str(e))
            return (None, None)

        try:
            if gt_or_equal:
                is_set = int(first_ma[-1] >= yaxis_value)
            else:
                is_set = int(first_ma[-1] < yaxis_value)

            if first_ma[-1] >= yaxis_value:
                ma_position_text = 'above'
            else:
                ma_position_text = 'below'

            metadata = {'vdma_values': [first_ma[-1]]}

            log_format = "{} VDMA {} is {} {} in detection '{}', condition {}, rule {}."
            self.log.debug(log_format, pair, first_ma_value, ma_position_text, yaxis_value,
                           detection_name, condition_index, rule, verbosity=1)

        except IndexError:
            log_format = "{} not enough VDMA data yet for detection '{}', condition {}, rule {}: value {} size {}."
            self.log.debug(log_format, pair, detection_name, condition_index, rule, first_ma_value, len(first_ma))
            return (0, None)

        result = (is_set, metadata)
        self.cache[pair]['rule'][rule] = result
        return result

    async def _check_vdma_xcrossover(self, pair: str, rule: tuple,
                                     condition_index: int, detection_name: str) -> Tuple[int, dict]:
        """
        Check for the crossover of a volume derivative moving average over the X axis for the 'vdma_xcrossover'
        detection rule.

        Rule tuples for this method have the following format:
            ('vdma_xcrossover', ma_value:int, upward: bool)

        Arguments:
            pair:             Currency pair to check this rule against eg. 'BTC-ETH'.
            rule:             The rule tuple to check against.
            condition_index:  Index of the condition this rule belongs to.
            detection_name:   Name of the detection this rule belongs to.

        Returns:
            (tuple):  A tuple containing:
              (int):    1 if a crossover occurred, 0 if not, or None if the rule was invalid.
              (dict):   A dict containing the following metadata values (or None if the rule was invalid)
                'vdma_values' list(float):     The current value of the moving average.
                'vdma_y_positions' list(int):  1 if the first moving average is above or at the second, 0 if not.
        """

        try:
            return self.cache[pair]['rule'][rule]
        except KeyError:
            pass

        try:
            ma_windows = config['vdma_windows']
            mas = self.market.volume_deriv_mas
            ma_window = ma_windows[rule[1]]
            ma = mas[pair][ma_window]
            upward = rule[2]

        except (IndexError, TypeError) as e:
            self.log.warning(("{} ignoring invalid rule '{}' in detection '{}' condition {}: {}"),
                             pair, rule, detection_name, condition_index, str(e))

            result = (None, None)
            self.cache[pair]['rule'][rule] = result
            return result

        try:
            ma_value = ma[-1]
            ma_crossover = 0

        except IndexError:
            self.log.debug(("{} VDMA {} has no data yet for detection '{}', condition {}, rule {}."),
                           pair, ma_window, detection_name, condition_index, rule)

            result = (0, None)
            self.cache[pair]['rule'][rule] = result
            return result

        try:
            if ma_value < 0.0:
                ma_position = 0
                ma_pos_text = 'below'
                trigger = self.detection_triggers[pair][detection_name][condition_index]
                if not upward and trigger['vdma_y_positions'][0] == 1:
                    ma_crossover = 1

            else:
                ma_position = 1
                ma_pos_text = 'above'
                trigger = self.detection_triggers[pair][detection_name][condition_index]
                if upward and trigger['vdma_y_positions'][0] == 0:
                    ma_crossover = 1

            if ma_crossover:
                self.log.debug("{} VDMA {} crossed {} X axis in detection '{}' condition {} rule {}.",
                               pair, ma_window, ma_pos_text, detection_name, condition_index, rule, verbosity=1)

        except (KeyError, IndexError):
            self.log.debug("{} no previous VDMA {} position to check in detection '{}' condition {} rule {}.",
                           pair, ma_window, detection_name, condition_index, rule, verbosity=2)

        result = (ma_crossover, {'vdma_values': [ma_value], 'vdma_y_positions': [ma_position]})
        self.cache[pair]['rule'][rule] = result
        return result

    async def _check_vdma_crossover(self, pair: str, rule: tuple,
                                    condition_index: int, detection_name: str) -> Tuple[int, dict]:
        """
        Check for the upward crossover of two volume derivative moving averages for the 'vdma_crossover' detection rule.

        Rule tuples for this method have the following format:
            ('vdma_crossover', first_ma_value:int, second_ma_value:int)

        Arguments:
            pair:             Currency pair to check this rule against eg. 'BTC-ETH'.
            rule:             The rule tuple to check against.
            condition_index:  Index of the condition this rule belongs to.
            detection_name:   Name of the detection this rule belongs to.

        Returns:
            (tuple):  A tuple containing:
              (int):    1 if the first ma just crossed over the second, 0 if not, or None if the rule was invalid.
              (dict):   A dict containing the following metadata values (or None if the rule was invalid):
                'ma_values' list(float):   The midpoint between the two moving averages (cross point if crossed).
                'ma_positions' list(int):  1 if the first moving average is above or at the second, 0 if not.
        """

        try:
            return self.cache[pair]['rule'][rule]
        except KeyError:
            pass

        try:
            ma_windows = config['vdma_windows']
            mas = self.market.volume_deriv_mas
            first_ma_value = ma_windows[rule[1]]
            second_ma_value = ma_windows[rule[2]]
            first_ma = mas[pair][first_ma_value]
            second_ma = mas[pair][second_ma_value]

        except (IndexError, TypeError) as e:
            self.log.warning(("{} ignoring invalid rule '{}' in detection '{}' condition {}: {}"),
                             pair, rule, detection_name, condition_index, str(e))

            return (None, None)

        try:
            if first_ma[-1] < second_ma[-1]:
                ma_position_text = 'below'
                ma_position = 0
                ma_crossover = 0

            else:
                ma_position_text = 'above'
                ma_position = 1

                try:
                    trigger = self.detection_triggers[pair][detection_name][condition_index]
                    if trigger['vdma_positions'][0] == 0:
                        ma_crossover = 1
                        self.log.debug("{} VDMA {} crossed over VDMA {} in detection '{}' condition {} rule {}.",
                                       pair, first_ma_value, second_ma_value, detection_name, condition_index, rule,
                                       verbosity=1)

                    else:
                        ma_crossover = 0

                except (KeyError, IndexError):
                    # No previous MA position exists yet to check against.
                    ma_crossover = 0

        except IndexError:
            self.log.debug(("{} not enough VDMA data yet for detection '{}', condition {}, rule {}: "
                            "value {} size {}, value {} size {}."),
                           pair, detection_name, condition_index, rule,
                           first_ma_value, len(first_ma), second_ma_value, len(second_ma))

            return (0, {'vdma_values': [0.0], 'vdma_positions': [0]})

        ma_midpoint = (second_ma[-2] + second_ma[-1] + first_ma[-2] + first_ma[-1]) / 4

        self.log.debug("{} MA {} is {} MA {} with midpoint {} in detection '{}', condition {}, rule {}.",
                       pair, first_ma_value, ma_position_text, second_ma_value,
                       ma_midpoint, detection_name, condition_index, rule, verbosity=1)

        result = (ma_crossover, {'vdma_values': [ma_midpoint], 'vdma_positions': [ma_position]})
        self.cache[pair]['rule'][rule] = result
        return result

    async def _check_new_pair(self, pair: str, rule: tuple, _: int, __: int) -> Tuple[int, dict]:
        """
        Check newly added state of a pair for the 'new_pair' detection rule.

        Rule tuples for this method have the following format:
            ('new_pair', True | False)

        Returns:
            (tuple):  A tuple containing:

            state (int):       1 if the state meets the constraint, 0 if not.
            metadata (dict):   A dict containing the following metadata values:
                'newly_added': list(bool):  [True | False] if the pair is new since last refresh or not.
        """

        rule_truth = rule[1]
        check_state = self.pair_states[pair]['newly_added'] == rule_truth

        return (int(check_state), {'newly_added': [self.pair_states[pair]['newly_added']]})

    async def _check_startup_pair(self, pair: str, rule: tuple, _: int, __: int) -> Tuple[int, dict]:
        """
        Check added on startup state of a pair for the 'startup_pair' detection rule.

        Rule tuples for this method have the following format:
            ('startup_pair', True | False)

        Returns:
            (tuple):  A tuple containing:

            state (int):       1 if the state meets the constraint, 0 if not.
            metadata (dict):   A dict containing the following metadata values:
                'startup_added': list(bool):  [True | False] if the pair was added on startup.
        """

        rule_truth = rule[1]
        check_state = self.pair_states[pair]['startup_added'] == rule_truth

        return (int(check_state), {'startup_added': [self.pair_states[pair]['startup_added']]})

    async def _check_pair(self, pair: str, rule: tuple, _: int, __: int) -> Tuple[int, dict]:
        """
        Check the base of a pair for the 'pair' detection rule.

        Rule tuples for this method have the following format:
            ('pair', (str))

        Returns:
            (tuple):  A tuple containing:

            state (int):  1 if the state meets the constraint, 0 if not.
            None          Placeholder for empty metadata.
        """

        return (int(pair == rule[1]), None)

    async def _check_pair_base(self, pair: str, rule: tuple, _: int, __: int) -> Tuple[int, dict]:
        """
        Check the base of a pair for the 'pair_base' detection rule.

        Rule tuples for this method have the following format:
            ('pair_base', (str))

        Returns:
            (tuple):  A tuple containing:

            state (int):  1 if the state meets the constraint, 0 if not.
            None          Placeholder for empty metadata.
        """

        match_base = rule[1]
        check_state = pair.split('-')[0] == match_base

        return (int(check_state), None)

    async def _reset_detection_state(self, pair: str, detection_name: str, trigger_data: dict):
        """
        Reset detection state for the given pair and detection index.

        TODO: Make this more crash-proof with appropriate defaults.

        Arguments:
            pair:            Name of the currency pair eg 'BTC-ETH'.
            detection_name:  Name of the detection.
        """

        params = self.get_detection_params(detection_name, {
            'apply': {'names': []}
        })

        for name in config['detections']:
            try:
                if name in params['apply']['names']:
                    if self.detection_states[pair][name]['occurrence'] != 0:
                        self.detection_states[pair][name]['occurrence'] = 0
                        prefix = 'RESET {}'.format(name)
                        await self.reporter.send_alert(pair, trigger_data, name, prefix=prefix)

            except KeyError:
                pass
