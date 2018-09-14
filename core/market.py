# -*- coding: utf-8 -*-

# Copyright (c) A 2017 Adam M. Rafuse - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited.
# Proprietary and confidential.

"""
Market service.
"""

__author__ = 'Adam Rafuse <$(echo nqnz.enshfr#tznvy.pbz | tr a-z# n-za-m@)>'
__all__ = ['Market']

import math
import json
import time
import random
import asyncio
import traceback

from array import array
from typing import Any, Dict, List, Sequence, Set, Tuple

import numpy as np
import scipy.signal

import api
import utils
import common
import common.base
import common.math
import configuration

config = configuration.config
"""
Global configuration.
"""


class Market(common.base.Persistable):
    """
    Market service object.

    Encapsulates all market data and related operations.
    """

    def __init__(self, api_client: api.Client, log=utils.logging.DummyLogger()):

        super().__init__(log)

        self.api = api_client
        """
        Bittrex API client.
        """

        self.log = utils.logging.ChildLogger(parent=log, scope=self)
        """
        Object logger.
        """

        self.pairs: List[str] = []
        """
        Currency pairs currently being tracked.
        """

        self.extra_base_pairs: List[str] = []
        """
        Additional pairs for base currency conversions not part of :attr:`pairs`.
        """

        self.last_pairs: Dict[str, Dict[str, Any]] = {}
        """
        Last values for pairs used for filtering.

        ``
        {
            (str):  Currency pair name eg. 'BTC-ETH':
            {
                'change': (float):
                'delta': (float):
                'filtered': (bool):
            },
            ... for pair in all currency pairs on exchange.

        }
        ``
        """

        self.greylist_pairs: Dict[str, float] = {}
        """
        """

        self.min_trade_qtys: Dict[str, float] = {}
        """
        Minimum trade quantities for each pair as reported by the exchange.
        """

        self.min_trade_sizes: Dict[str, float] = {}
        """
        Minimum trade sizes for each pair as reported by the exchange.
        """

        self.close_times: Dict[str, array] = {}
        """
        Closing times for each currency pair.

        ``
        {
            (str):  Currency pair name eg. 'BTC-ETH':
                list(float):  The closing times for this pair.
            ... for pair in currently and previously tracked pairs
        }
        ``
        """

        self.last_adjusted_close_times: Dict[str, float] = {}
        """
        Last times for each currency pair for referencing adjusted values.

        ``
        {
            (str):  Currency pair name eg. 'BTC-ETH':
                list(float):  The closing times for this pair.
            ... for pair in currently and previously tracked pairs
        }
        ``
        """

        self.close_times_backup: Dict[str, array] = {}
        """
        Backup of recent closing times used for restoring missing ticks after a restart.
        """

        self.close_values: Dict[str, array] = {}
        """
        Closing values for each currency pair.

        ``
        {
            (str):  Currency pair name eg. 'BTC-ETH':
                list(float):  The closing values for this pair.
            ... for pair in currently and previously tracked pairs.
        }
        ``
        """

        self.close_values_backup: Dict[str, array] = {}
        """
        Backup of recent closing values used for restoring missing ticks after a restart.
        """

        self.adjusted_close_values: Dict[str, array] = {}
        """
        Closing values for each currency pair adjusted to the trade base currency.

        ``
        {
            (str):  Currency pair name eg. 'BTC-ETH':
                list(float):  The adjusted closing values for this pair.
            ... for pair in currently and previously tracked pairs.
        }
        ``
        """

        self.base_24hr_volumes: Dict[str, List[array]] = {}
        """
        24-hour volumes for each currency pair. Each list element is the nth derivate of the volume.

        ``
        [
            {
                (str):  Currency pair name eg. 'BTC-ETH':
                    list(float):  The volumes for this pair.
                ... for pair in loaded backtesting pairs
            },
            ...
        ]
        """

        self.base_24hr_volumes_backup: Dict[str, array] = {}
        """
        Backup of recent 24 hour volumes used for restoring missing ticks after a restart.
        """

        self.prev_day_values: Dict[str, List[float]] = {}
        """
        Previous day values for each currency pair.

        Currently only used in offline backtest, as normally this is pulled from the API's market summary.
        ``
        {
            (str):  Currency pair name eg. 'BTC-ETH':
                list(float):  The previous day values for this pair.
            ... for pair in loaded backtesting pairs
        }
        """

        self.back_refreshes: List[Dict[str, Any]] = []
        """
        """

        self.data_refreshing: Set[str] = set()
        """
        """

        self.source_close_value_mas: Dict[str, Dict[int, array]] = {}
        """
        Source close value moving averages for each currency pair, without processing.

        ``
        {
            (str):  Currency pair name eg. 'BTC-ETH'
            {
                (int):  Moving average window value.
                    list(float):  The MA values for this window.
                ... for window in config['ma_windows']
            }
            ... for pair in currently and previously tracked pairs
        }
        ``
        """

        self.close_value_mas: Dict[str, Dict[int, array]] = {}
        """
        Closing value moving averages for each currency pair, potenitally with processing applied.

        ``
        {
            (str):  Currency pair name eg. 'BTC-ETH'
            {
                (int):  Moving average window value.
                    list(float):  The MA values for this window.
                ... for window in config['ma_windows']
            }
            ... for pair in currently and previously tracked pairs
        }
        ``
        """

        self.source_close_value_emas: Dict[str, Dict[int, array]] = {}
        """
        Close value exponential moving averages for each currency pair, without processing.

        ``
        {
            (str):  Currency pair name eg. 'BTC-ETH'
            {
                (int):  Moving average window value.
                    list(float):  The MA values for this window.
                ... for window in config['ma_windows']
            }
            ... for pair in currently and previously tracked pairs
        }
        ``
        """

        self.close_value_emas: Dict[str, Dict[int, array]] = {}
        """
        Closing value exponential moving averages for each currency pair, potenitally with processing applied.

        ``
        {
            (str):  Currency pair name eg. 'BTC-ETH'
            {
                (int):  Moving average window value.
                    list(float):  The MA values for this window.
                ... for window in config['ma_windows']
            }`
            ... for pair in currently and previously tracked pairs
        }
        ``
        """

        self.volume_deriv_mas: Dict[str, Dict[int, array]] = {}
        """
        Volume derivative moving averages.

        ``
        {
            (str):  Currency pair name eg. 'BTC-ETH'
            {
                (int):  Moving average window value.
                    list(float):  The MA values for this window.
                ... for window in config['ma_windows']
            }
            ... for pair in currently and previously tracked pairs
        }
        ``
        """

        self.last_update_nums = {}
        """
        Number of new ticks added for each pair after the last update.
        """

        self.relative_strength_indexes = {}
        """
        Relative strength indexes for each currency pair, if config['enable_rsi'] is set.
        """

        self.bollinger_bands = {}
        """
        Bollinger bands for each currency pair.
        """

        self.base_rates = {}
        """
        Base currency rates used for base conversions.

        Eg. base coversions available with the Bittrex API are:
            USDT-BTC
            USDT-ETH
            BTC-USDT
            BTC-ETH
            ETH-USDT
            ETH-BTC

        ``
        {
            pair(str): (float):
        }
        ``
        """

        self.min_trade_size = 0.0
        """
        Minimum trade size.
        """

        self.min_safe_trade_size = 0.0
        """
        Minimum "safe" trade size (with headroom to simulate market sells).
        """

        self.min_tick_length = common.get_min_tick_length()
        """
        Minimum length of tick data needed to perform operations.
        """

        self.data_lock = asyncio.Lock()
        """
        Lock used for modify access to market data.
        """

    async def acquire_data_lock(self, waiter: str):
        """
        Acquire the :attr:`Market.data_lock` lock and print a debug message if waiting for the lock.

        Arguments:
            waiter:  The name of the waiting coroutine, used for disambiguation in logging.
        """

        if self.data_lock.locked():
            self.log.debug('{}: Waiting for market data access in progress.', waiter)

        await self.data_lock.acquire()

    async def refresh_pairs(self):
        """
        Refresh the list of watched currency pairs.

        The list attr:`market.pairs` is updated with pairs filtered according to base currency and current trading volume,
        as defined in :data:`config['min_base_volumes']`. If :data:`config['pair_change_filter']`
        is enabled, the pairs are additionally filtered accorfing to :meth:`core.Market.apply_pair_change_filter`.

        The filtered results are ordered by volume and will not exceed :data:`config['max_pairs']`. Any base pairs that
        are required for rate conversions that are not included in filtered results are set in
        :attr:`market.extra_base_pairs`.
        """

        summaries = await self.api.get_market_summaries()
        if summaries is None:
            self.log.error('Could not get market summaries data.')
            return None

        pairs = []
        pair_count = 0
        changes, volumes, min_trade_qtys, min_trade_sizes = await self._extract_filtered_summaries(summaries)
        bases = list(config['min_base_volumes'].keys())

        for pair in sorted(volumes, key=volumes.get, reverse=True):
            if await Market.apply_pair_prefer_filter(pair, bases, volumes.keys()):
                continue
            if await self._handle_greylisted(pair):
                continue

            pairs.append(pair)
            self.log.debug('Added pair {}: volume {}, change {}.', pair, volumes[pair], changes[pair], verbosity=1)

            pair_count += 1
            if config['max_pairs'] and pair_count >= config['max_pairs']:
                break

        if config['app_node_index'] is not None:
            pair_splits = list(utils.split(pairs, config['app_node_max']))
            self.pairs = pair_splits[config['app_node_index']]  # pylint: disable=E1126
        else:
            self.pairs = pairs

        self.extra_base_pairs = [pair for pair in config['base_pairs'] if pair not in pairs]
        self.min_trade_qtys = min_trade_qtys
        self.min_trade_sizes = min_trade_sizes

    async def _handle_greylisted(self, pair: str):
        """
        Check if a pair is currently greylisted and remove any greylisting that has expired.

        Arguments:
            pair:  Name of the pair eg. 'BTC-ETH'.

        Returns:
            True if the pair is currently greylisted, otherwise False.
        """

        greylisted = pair in self.greylist_pairs
        now = time.time()

        if greylisted and now >= self.greylist_pairs[pair]:
            del self.greylist_pairs[pair]
            greylisted = False

        if greylisted:
            greylist_secs = self.greylist_pairs[pair] - now
            self.log.debug("{} is still greylisted for {} seconds.", pair, greylist_secs)

        return greylisted

    @staticmethod
    async def apply_pair_prefer_filter(pair: str, bases: Sequence[str], pairs: Sequence[str]):
        """
        """

        if not config['pair_prefer_filter']:
            return False

        base, quote, _ = common.get_pair_elements(pair)
        base_index = bases.index(base)
        if base_index > 0:
            for preferred_index in range(0, base_index):
                preferred_base = bases[preferred_index]
                preferred_version = '{}-{}'.format(preferred_base, quote)
                if preferred_version in pairs:
                    return True

        return False

    async def _extract_filtered_summaries(self, summaries: Dict[str, Dict[str, Any]]) -> \
            Tuple[Dict[str, float], Dict[str, float], Dict[str, float], Dict[str, float]]:
        """
        Filter market summaries and extract filtered values.

        Values returned are filtered based on :attr:`config['min_base_volumes']` and :attr:`config['min_pair_change']`.
        Minimum trade quantities will always include :attr:`config['base_pairs']`.

        Returns:
            A tuple containing:
            dict:  A dict of currency pairs and each pair's 24-hour change.
            dict:  A dict of currency pairs and each pair's 24-hour volume.
            dict:  A dict of currency pairs and each pair's minimum trade quantities.
            dict:  A dict of currency pairs and each pair's minimum trade sizes.
        """

        changes = {}
        volumes = {}
        min_trade_qtys = {}
        min_trade_sizes = {}

        for pair, summary in summaries.items():
            try:
                active = summary['active']
                base_currency = summary['baseCurrency']
                min_trade_qty = summary['minTradeQty']
                min_trade_size = summary['minTradeSize']
                volume = summary['baseVolume']
                prev_day_value = summary['prevDay']
                current_value = summary['last']

                if pair in self.last_pairs:
                    last_value = self.last_pairs[pair]['value']
                    change = current_value / last_value - 1.0 if last_value else 0.0
                else:
                    change = current_value / prev_day_value - 1.0 if prev_day_value else 0.0

                min_base_volumes = config['min_base_volumes']
                min_volume = min_base_volumes[base_currency] if base_currency in min_base_volumes else None
                filtered = await self.apply_pair_change_filter(pair, change, current_value)

                if active and not filtered and volume and min_volume and volume >= min_volume:
                    changes[pair] = change
                    volumes[pair] = volume
                    min_trade_qtys[pair] = min_trade_qty
                    min_trade_sizes[pair] = min_trade_size
                    self.log.debug('Filtered pair {}: volume {}, change {}.', pair, volume, change, verbosity=1)

                elif pair in config['base_pairs']:
                    min_trade_qtys[pair] = min_trade_qty
                    min_trade_sizes[pair] = min_trade_size

            except (KeyError, IndexError) as e:
                self.log.error('Got {} parsing summaries: {}', type(e).__name__, e)

        return (changes, volumes, min_trade_qtys, min_trade_sizes)

    async def apply_pair_change_filter(self, pair: str, change: float, value: float):
        """
        Filter a currency pair by its percent change in value.

        The pair is initially allowed if its decimal percent change since last check is at least
        :attr:`config['pair_change_min']`. The pair is allowed to fall by :attr:`config['pair_change_dip']` before
        being filtered out. It will be allowed back if it rises again by by :attr:`config['pair_change_dip']` plus
        :attr:`config['pair_change_min']`.

        Arguments:
            pair:    The currency pair eg. 'BTC-ETH'.
            change:  The pair's change in value as a decimal percentage.
            value:

        Returns:
            True if the pair was filtered (disallowed), or False is the pair is allowed.
        """

        if not config['pair_change_filter']:
            return False

        if not config['pair_dip_filter']:
            return change < config['pair_change_min']

        change_min = config['pair_change_min']
        change_max = config['pair_change_min']
        change_dip = config['pair_change_dip']
        change_cutoff = config['pair_change_cutoff']

        if pair in self.last_pairs:
            change_delta = self.last_pairs[pair]['delta'] + change
            filtered = self.last_pairs[pair]['filtered']

            if filtered:
                if change_delta < -change_dip:
                    change_delta = -change_dip

                elif change_delta >= change_min:
                    self.log.debug("Re-added pair {}.", pair)
                    filtered = False
                    if change_delta > change_max:
                        change_delta = change_max

            else:
                if change_delta <= -change_cutoff:
                    self.log.debug("Dropped pair {}.", pair)
                    filtered = True
                    if change_delta < -change_dip:
                        change_delta = -change_dip

                elif change_delta > change_max:
                    change_delta = change_max

        else:
            if change >= change_min:
                filtered = False
                change_delta = change
                if change_delta > change_max:
                    change_delta = change_max

            else:
                filtered = True
                change_delta = change
                if change_delta < -change_dip:
                    change_delta = -change_dip

            self.last_pairs[pair] = {}

        self.last_pairs[pair]['value'] = value
        self.last_pairs[pair]['change'] = change
        self.last_pairs[pair]['delta'] = change_delta
        self.last_pairs[pair]['filtered'] = filtered
        self.save_attr('last_pairs')

        return filtered

    async def refresh_tick_data(self, pair: str) -> str:
        """
        Refresh the tick data for the specified currency pair.

        Refreshes the lists :attr:`close_values` and :attr:`close_times` from the latest API data. Rate limits
        concurrent downloads by: data: `config['api_initial_rate_limit_secs']` to avoid being throttled by the API.

        If no backup exists, initial 24-hour base volumes are all copies of the current volume, since APIs will not
        make this historical data available.

        Arguments:
            pair:  The currency pair to refresh.

        Returns:
            The same pair that was passed as an argument (for joining on coroutines) or None if the update did not
            occur due to an error.
        """

        self.base_24hr_volumes[pair] = [array('d'), array('d')]

        has_backup = (pair in self.close_times_backup and
                      pair in self.close_values_backup and
                      pair in self.base_24hr_volumes_backup and
                      self.close_times_backup[pair] and
                      self.close_values_backup[pair] and
                      self.base_24hr_volumes_backup[pair])

        if has_backup and self.close_times_backup[pair][-1] >= time.time() - config['tick_interval_secs'] * 2:
            self.close_times[pair] = self.close_times_backup[pair]
            self.close_values[pair] = self.close_values_backup[pair]
            self.base_24hr_volumes[pair][0] = self.base_24hr_volumes_backup[pair]

            self.log.info("{} Using {} ticks from backup.", pair, len(self.close_times_backup[pair]))
            return pair

        rate_limit = len(self.data_refreshing) * config['api_initial_rate_limit_secs']
        self.data_refreshing.add(pair)
        await asyncio.sleep(rate_limit)
        ticks = await self.api.get_ticks(pair)
        self.data_refreshing.remove(pair)

        if not ticks:
            self.log.error("{} API returned no tick data.", pair)
            return None

        self.log.debug("{} API ticks size {}, start {}, end {}.", pair, len(ticks), ticks[0]['T'], ticks[-1]['T'])

        try:
            _, volume = await self.api.get_last_values(pair)
            self.close_times[pair], self.close_values[pair] = await self._expand_ticks(ticks)
            self.base_24hr_volumes[pair][0] = array('d', (volume for _ in range(len(self.close_times[pair]))))

            in_backup = (pair in self.close_times_backup and
                         pair in self.close_values_backup and
                         pair in self.base_24hr_volumes_backup)

            if not in_backup:
                self.close_times_backup[pair] = array('d')
                self.close_values_backup[pair] = array('d')
                self.base_24hr_volumes_backup[pair] = array('d')

            await self._truncate_tick_data(pair)
            await self._splice_backup_tick_data(pair)
            self.log.info('{} refreshed tick data.', pair)
            return pair

        except (KeyError, IndexError, TypeError) as e:
            self.log.error('Got {} for {}: {}', type(e).__name__, pair, e)

        return None

    @staticmethod
    async def _expand_ticks(ticks: List[Dict[str, float]]):
        """
        Expand a list of sparse raw ticks to separate lists of tick data.

        TODO: Can potentially be optimized by implementing dynamically resized ndarrays.

        Arguments:
            ticks:  List of raw ticks as returned from the API.

        Returns:
            (tuple):     A tuple containing:
            list(float)  List of closing times.
            list(float)  List of closing values.
        """

        tick = ticks[0]
        close_times = array('d')
        close_values = array('d')
        last_time = tick['T']
        last_value = tick['C']
        close_times.append(last_time)
        close_values.append(last_value)

        for tick in ticks[1:]:
            close_time = tick['T']

            while int(close_time - last_time) > config['tick_interval_secs']:
                last_time += config['tick_interval_secs']
                close_times.append(last_time)
                close_values.append(last_value)

            last_time = close_time
            last_value = tick['C']
            close_times.append(last_time)
            close_values.append(last_value)

        return (close_times, close_values)

    async def _splice_backup_tick_data(self, pair: str):
        """
        Splice any backup tick data into current market data for the given pair.

        Arguments:
            pair:  Currency pair eg. 'BTC-ETH'.
        """

        if not (self.close_values_backup[pair] and
                self.close_times_backup[pair] and
                self.base_24hr_volumes_backup[pair]):

            return

        backup_volumes = self.base_24hr_volumes_backup[pair]
        backup_values = self.close_values_backup[pair]
        backup_times = self.close_times_backup[pair]
        volumes = self.base_24hr_volumes[pair][0]
        values = self.close_values[pair]
        times = self.close_times[pair]
        backup_start = backup_times[0]
        backup_end = backup_times[-1]
        start = times[0]
        end = times[-1]

        if backup_start > end:
            gap = backup_start - end
            self.log.debug("{} tick backup has a gap of {} seconds after market data.", pair, gap)
            return

        elif start > backup_end:
            gap = start - backup_end
            self.log.debug("{} tick backup has a gap of {} seconds before market data.", pair, gap)
            return

        end_time = end if end > backup_end else backup_end
        start_time = start if start < backup_start else backup_start
        if (end_time - start_time) / config['tick_interval_secs'] > self.min_tick_length:
            start_time = end_time - self.min_tick_length * config['tick_interval_secs']

        length = int((end_time - start_time) // config['tick_interval_secs'])
        num_spliced = 0
        new_volumes = array('d')
        new_values = array('d')
        new_times = array('d')

        current_time = start_time
        for _ in range(length):
            try:
                index = backup_times.index(current_time)
                volume = backup_volumes[index]
                value = backup_values[index]
                num_spliced += 1

            except ValueError:
                index = times.index(current_time)
                volume = volumes[index]
                value = values[index]

            new_volumes.append(volume)
            new_values.append(value)
            new_times.append(current_time)
            current_time += config['tick_interval_secs']

        self.base_24hr_volumes[pair][0] = new_volumes
        self.close_values[pair] = new_values
        self.close_times[pair] = new_times

        self.log.debug("{} spliced {} ticks from backup.", pair, num_spliced)

    async def refresh_adjusted_tick_data(self, pair: str):
        """
        Refresh trade-base adjusted closing values for the specified pair.

        Arguments:
            pair:  The currency pair eg. 'BTC-ETH'.
        """

        self.base_24hr_volumes[pair][1] = array('d')
        self.last_adjusted_close_times[pair] = self.close_times[pair][-1]

        trade_base = config['trade_base']
        pair_base = pair.split('-')[0]

        if trade_base == pair_base:
            self.adjusted_close_values[pair] = self.close_values[pair]
            await self._refresh_volume_derivatives(pair)
            return

        else:
            self.adjusted_close_values[pair] = array('d')

        convert_pair = '{}-{}'.format(trade_base, pair_base)

        try:
            source_index = len(self.close_times[pair]) - 1
            convert_index = self.close_times[convert_pair].index(self.close_times[pair][-1])

        except ValueError:
            try:
                convert_index = len(self.close_times[convert_pair]) - 1
                source_index = self.close_times[pair].index(self.close_times[convert_pair][-1])
                convert_value = self.close_values[convert_pair][-1]

                for index in range(len(self.close_times[pair]) - 1, source_index, -1):
                    adjusted_value = self.close_values[pair][index] * convert_value
                    self.adjusted_close_values[pair].insert(0, adjusted_value)

                self.log.debug("{} last {} adjusted values are approximate.", pair,
                               len(self.close_times[pair]) - source_index)

            except ValueError:
                self.adjusted_close_values[pair] = array('d')
                self.log.error("{} ends at {} before start of convert pair {} data at {}.",
                               pair, self.close_times[pair][-1], convert_pair, self.close_times[convert_pair][0])
                return

        for index in range(source_index, -1, -1):
            if convert_index > -1:
                convert_value = self.close_values[convert_pair][convert_index]
            else:
                convert_value = self.close_values[convert_pair][0]

            adjusted_value = self.close_values[pair][index] * convert_value
            self.adjusted_close_values[pair].insert(0, adjusted_value)
            convert_index -= 1

        if convert_index < 0:
            self.log.debug("{} first {} adjusted values are approximate.", pair, convert_index * -1)

        await self._refresh_volume_derivatives(pair)

    async def _refresh_volume_derivatives(self, pair: str):
        """
        Refresh the (discrete) derivatives of the adjusted base 24 hour volumes for the given pair.

        Non-base pair volume derivatives are averaged against their trade base pair derivaties, as operations are
        performed against the overall volume related to the trade base currency.

        Arguments:
            pair:  Pair name eg. 'BTC-ETH'.
        """

        if not self.base_24hr_volumes[pair][0]:
            return

        self.base_24hr_volumes[pair][1].append(0)
        for index in range(1, len(self.base_24hr_volumes[pair][0])):
            volume = self.base_24hr_volumes[pair][0][index]
            prev_volume = self.base_24hr_volumes[pair][0][index - 1]
            norm_derivative = (volume - prev_volume) / volume * 100.0
            self.base_24hr_volumes[pair][1].append(norm_derivative)

        convert_pair = common.get_pair_trade_base(pair)
        if not convert_pair:
            return

        try:
            source_index = len(self.close_times[pair]) - 1
            convert_index = self.close_times[convert_pair].index(self.close_times[pair][-1])

        except ValueError:
            try:
                convert_index = len(self.close_times[convert_pair]) - 1
                source_index = self.close_times[pair].index(self.close_times[convert_pair][-1])
                convert_volume = self.base_24hr_volumes[convert_pair][1][-1]

                for index in range(len(self.close_times[pair]) - 1, source_index, -1):
                    adjusted_volume = (self.base_24hr_volumes[pair][1][index] + convert_volume) / 2
                    self.base_24hr_volumes[pair][1][index] = adjusted_volume

                self.log.debug("{} last {} averaged volume derivates are approximate.", pair,
                               len(self.close_times[pair]) - source_index)

            except ValueError:
                self.log.error("{} ends at {} before start of convert pair {} data at {}.",
                               pair, self.close_times[pair][-1], convert_pair, self.close_times[convert_pair][0])
                return

        for index in range(source_index, -1, -1):
            if convert_index > -1:
                convert_volume = self.base_24hr_volumes[convert_pair][1][convert_index]
            else:
                convert_volume = self.base_24hr_volumes[convert_pair][1][0]

            adjusted_volume = (self.base_24hr_volumes[pair][1][index] + convert_volume) / 2
            self.base_24hr_volumes[pair][1][index] = adjusted_volume
            convert_index -= 1

        if convert_index < 0:
            self.log.debug("{} first {} average volume derivatives are approximate.", pair, convert_index * -1)

    async def update_tick_data(self, pair: str) -> str:
        """
        Update the tick data for the specified currency pair using the v1 API.

        Appends the latest tick data to the lists :attr:`close_values[pair]` and :attr:`close_times[pair]` if called
        after the next tick interval. Any missing ticks from the last interval are either restored from backup (as
        happens after a restart + refresh) or are interpolated.

        Arguments:
            pair:  The currency pair to refresh.

        Returns:
            The same pair that was passed as an argument (for joining on async tasks), or None if this method was called
            too early (before the next tick boundary) or an error occurred.
        """

        self.last_update_nums[pair] = 0

        close_time, tick_gap = await self._get_tick_delta(pair)
        if close_time is None:
            return None

        if tick_gap > config['tick_gap_max']:
            self.log.info("{} is missing too many ticks, removing from pairs list.", pair)

            if pair in self.pairs:
                self.pairs.remove(pair)

            if pair not in self.greylist_pairs:
                greylist_time = time.time() + config['pairs_greylist_secs']
                self.log.info("{} greylisting for {} seconds.", pair, config['pairs_greylist_secs'])
                self.greylist_pairs[pair] = greylist_time

            return None

        close_value, base_24hr_volume = await self.api.get_last_values(pair)
        if close_value is None:
            return None

        try:
            if await self._restore_ticks(pair, tick_gap, close_value, base_24hr_volume):
                await self._schedule_back_refresh(pair, tick_gap)

            self.log.debug('{} adding new tick value {} at {}.', pair, close_value, close_time, verbosity=1)
            self.close_times[pair].append(close_time)
            self.close_values[pair].append(close_value)
            self.base_24hr_volumes[pair][0].append(base_24hr_volume)
            self.last_update_nums[pair] = tick_gap + 1
            await self._truncate_tick_data(pair)
            await self._backup_tick_data(pair)

            self.log.debug('{} updated tick data.', pair, verbosity=1)
            return pair

        except (KeyError, IndexError, TypeError) as e:
            self.log.error('{} got {}: {}\n{}', pair, type(e).__name__, e,
                           ''.join(traceback.format_tb(e.__traceback__)))

        return None

    async def _get_tick_delta(self, pair: str) -> Tuple[float, int]:
        """
        Get the delta from the last tick as the current tick time and the gap in ticks since last tick.

        Arguments:
            pair:  The currency pair eg. 'BTC-ETH'

        Returns:
            A tuple containing:
            (float):  The timestamp of the closing time for the current tick, which will be on a tick boundary.
            (int):    The gap in ticks since the last tick.

            Returns (None, None) if an error occured, or this method was called too early after the last tick (before
            the next tick boundary).
        """

        try:
            last_time = self.close_times[pair][-1]

        except (KeyError, IndexError, TypeError) as e:
            self.log.error('{} {} getting previous closing time: {}', pair, type(e).__name__, e)
            return (None, None)

        current_time = time.time()
        interval_secs = config['tick_interval_secs']
        close_time = current_time - (current_time % interval_secs)

        if close_time < last_time:
            self.log.error("You are {} seconds behind, please adjust.", last_time - close_time)
            return (None, None)

        delta_seconds = int(close_time - last_time)

        if delta_seconds == 0:
            wait_time = interval_secs - (current_time % interval_secs)
            self.log.info("{} must wait {} seconds for new tick data.", pair, wait_time)
            return (None, None)

        elif delta_seconds > interval_secs:
            tick_gap = delta_seconds // interval_secs
            self.log.info("{} is missing {} ticks.", pair, tick_gap)

        else:
            tick_gap = 0

        return (close_time, tick_gap)

    async def _restore_ticks(self, pair: str, num: int, end_value: float, end_volume: float) -> int:
        """
        Restore missing ticks for a currency pair either from backup or by interpolation.

        The method exists mainly because previous tick data pulled from the API on startup is usually about 3 to 7
        minutes behind the current tick. In the case where no backup exists (new pair, network lag, or long delay
        between restarts), it will still work by interpolating the missing data.

        Tick arrays are resized by at least +1 as they will later be appended with the current tick.

        Arguments:
            pair:       The currency pair eg. 'BTC-ETH'.
            num:        Number of ticks to restore.
            end_value:  The end value in case interpolation is needed (ie. the most recent real tick value).

        Returns:
            The number of ticks that were interpolated (not found in backup)
        """

        if num == 0:
            return 0

        interval_secs = config['tick_interval_secs']
        volumes = self.base_24hr_volumes[pair][0]
        values = self.close_values[pair]
        times = self.close_times[pair]

        last_volume = volumes[-1]
        last_value = values[-1]
        interpolated = 0

        for index in range(num):
            timestamp = times[-1] + interval_secs

            try:
                time_index = self.close_times_backup[pair].index(timestamp)
                volume = self.base_24hr_volumes_backup[pair][time_index]
                value = self.close_values_backup[pair][time_index]
                self.log.debug("{} restored missing tick {} from backup.", pair, index)

            except (ValueError, KeyError):
                volume_step = (end_volume - last_volume) / (num - index + 1)
                value_step = (end_value - last_value) / (num - index + 1)
                volume = last_volume + volume_step
                value = last_value + value_step
                self.log.debug("{} interpolated missing tick {}.", pair, index)
                interpolated += 1

            volumes.append(volume)
            values.append(value)
            times.append(timestamp)

        return interpolated

    async def _schedule_back_refresh(self, pair: str, num: int):
        """
        Schedule a future refresh to backfill missing data from the API when it later becomes available.

        The refresh will occur at least num * 2 ticks and no less than config['back_refresh_min_secs'] seconds in the
        future. Some random scatter is added to avoid too many refreshes on the same tick.

        Arguments:
            pair:   The pair to refresh eg. BTC-ETH.
            num:    The number of recent ticks to refresh later.
        """

        future_secs = config['tick_interval_secs'] * num * 2
        if future_secs < config['back_refresh_min_secs']:
            future_secs = config['back_refresh_min_secs'] + future_secs / 2
        future_secs += random.random() * future_secs / 2

        if num > 0:
            self.back_refreshes.append({
                'pair': pair,
                'start': self.close_times[pair][-num],
                'end': self.close_times[pair][-1] + config['tick_interval_secs'],
                'time': time.time() + future_secs
            })

        self.log.info("{} scheduled back-refresh of {} ticks in {} seconds.", pair, num, future_secs)
        self.save_attr('back_refreshes')

    async def check_back_refreshes(self):
        """
        Check the list of back-refreshes for any that are due and process them.

        Returns:
            set(string):  Set of any pairs that had tick data changed.
        """

        remove_indexes = []
        updated_pairs = set()
        refreshes = 0

        for index, refresh in enumerate(self.back_refreshes):
            pair = refresh['pair']
            end_time = refresh['end']
            start_time = refresh['start']

            last_time = self.close_times[config['base_pairs'][0]][-1]
            if last_time > refresh['time']:
                refresh_num = int(last_time - start_time) // config['tick_interval_secs']
                remove_indexes.append(index)

                if pair in self.close_times:
                    refreshes += 1
                    ticks = await self.api.get_ticks(pair, refresh_num)
                    overwritten = await self._overwrite_tick_data(pair, start_time, end_time, ticks)
                    if overwritten:
                        self.log.info("{} back-refreshed {} ticks.", pair, overwritten)
                        updated_pairs.add(pair)

            if refreshes >= config['back_refresh_max_per_tick']:
                break

        for index in reversed(remove_indexes):
            del self.back_refreshes[index]

        if remove_indexes:
            self.save_attr('back_refreshes')

        return updated_pairs

    async def _overwrite_tick_data(self, pair: str, start_time: float, end_time: float,
                                   ticks: List[Dict[str, float]]) -> int:
        """
        Overwrite tick data for a pair with new data from a source list of raw ticks.

        Arguments:
            pair:        Currency pair name eg. 'BTC-ETH'.
            start_time:  Starting timestamp of first tick to overwrite.
            end_time:    Ending timestamp of last tick to overwrite (exclusive).
            ticks:       List of raw ticks to overwrite from as returned from the API.

        Returns:
            Number of ticks which were overwritten.
        """

        if not ticks:
            return 0

        close_times, close_values = await self._expand_ticks(ticks)

        try:
            source_index = close_times.index(start_time)
            dest_index = self.close_times[pair].index(start_time)

        except ValueError as e:
            self.log.error("{} start time not found: {}", pair, e)
            return 0

        length = int((end_time - start_time) // config['tick_interval_secs'])
        overwritten = 0

        try:
            for _ in range(length):
                self.close_values[pair][dest_index] = close_values[source_index]
                overwritten += 1
                source_index += 1
                dest_index += 1

        except IndexError as e:
            self.log.error("{} invalid index: {}", pair, e)

        return overwritten

    async def update_adjusted_tick_data(self, pair: str):
        """
        Update trade-base adjusted closing values for the specified pair.

        Arguments:
            pair:  The currency pair eg. 'BTC-ETH'.
        """

        base = config['trade_base']
        pair_base = pair.split('-')[0]

        try:
            last_time = self.last_adjusted_close_times[pair]
            start_index = self.close_times[pair].index(last_time) + 1

        except ValueError:
            self.log.error("{} has no adjusted close times.", pair)
            last_time = 0
            start_index = 0

        diff = len(self.close_times[pair]) - start_index
        if diff != 1:
            self.log.debug("{} got diff {}, source length {}, last time {}.",
                           pair, diff, len(self.close_times[pair]), last_time)

        if base == pair_base:
            self.adjusted_close_values[pair] = self.close_values[pair]
            self.last_adjusted_close_times[pair] = self.close_times[pair][-1]
            await self._update_volume_derivatives(pair, diff, start_index)
            await self._truncate_adjusted_tick_data(pair)
            return

        convert_pair = '{}-{}'.format(base, pair_base)
        missing = 0

        for index in range(diff):
            try:
                convert_value = self.close_values[convert_pair][start_index + index]
            except IndexError:
                convert_value = self.close_values[convert_pair][-1]
                missing += 1

            close_value = self.close_values[pair][start_index + index]
            self.adjusted_close_values[pair].append(close_value * convert_value)

        if missing > 0:
            self.log.debug("{} padded {} values at end.", pair, missing)

        self.last_adjusted_close_times[pair] = self.close_times[pair][-1]
        await self._update_volume_derivatives(pair, diff, start_index)
        await self._truncate_adjusted_tick_data(pair)

    async def _update_volume_derivatives(self, pair: str, diff: int, start_index: int):
        """
        Update the (discrete) derivatives of the adjusted base 24 hour volumes for the given pair.

        Arguments:
            pair:  Pair name eg. 'BTC-ETH'.
        """

        if not self.base_24hr_volumes[pair][0] or not self.base_24hr_volumes[pair][1]:
            return

        source_length = len(self.base_24hr_volumes[pair][0])
        for index in range(source_length - diff, source_length):
            volume = self.base_24hr_volumes[pair][0][index]
            prev_volume = self.base_24hr_volumes[pair][0][index - 1]
            norm_derivative = (volume - prev_volume) / volume * 100.0
            self.base_24hr_volumes[pair][1].append(norm_derivative)

        convert_pair = common.get_pair_trade_base(pair)
        if not convert_pair:
            return

        missing = 0

        for index in range(diff):
            try:
                convert_volume = self.base_24hr_volumes[convert_pair][1][start_index + index]
            except IndexError:
                convert_volume = self.base_24hr_volumes[convert_pair][1][-1]
                missing += 1

            adjusted_volume = (self.base_24hr_volumes[pair][1][start_index + index] + convert_volume) / 2
            self.base_24hr_volumes[pair][1][start_index + index] = adjusted_volume

        if missing > 0:
            self.log.debug("{} last {} averaged volume derivates are approximate.", pair, missing)

    async def _truncate_tick_data(self, pair: str):
        """
        Truncate tick data for a currency pair down to required values.

        Truncates the tick values for a pair if they exceed the required length to prevent unbounded growth.

        Arguments:
            pair:  The currency pair eg. 'BTC-ETH'.
        """

        truncate = len(self.close_times[pair]) - self.min_tick_length
        if truncate > 60:
            del self.base_24hr_volumes[pair][0][:truncate]
            del self.close_values[pair][:truncate]
            del self.close_times[pair][:truncate]

    async def _truncate_adjusted_tick_data(self, pair: str):
        """
        Truncate trade-base adjusted close values a currency pair down to required values.

        Rotates the tick values for a pair if they exceed the required length (the longest moving average window plus
        the age of charts) to prevent unbounded growth.
        """

        truncate = len(self.close_times[pair]) - self.min_tick_length
        if truncate > 60:
            del self.base_24hr_volumes[pair][1][:truncate]
            del self.adjusted_close_values[pair][:truncate]

    async def _backup_tick_data(self, pair: str):
        """
        Backup the most recent tick data for a currency pair.

        Arguments:
            pair:  The currency pair eg. 'BTC-ETH'.
        """

        def to_list(a: array):
            return a.tolist()

        self.base_24hr_volumes_backup[pair] = self.base_24hr_volumes[pair][0][-self.min_tick_length:]
        self.close_values_backup[pair] = self.close_values[pair][-self.min_tick_length:]
        self.close_times_backup[pair] = self.close_times[pair][-self.min_tick_length:]
        self.save_attr('base_24hr_volumes_backup', convert=[(array, to_list)], max_depth=1, filter_items=[pair])
        self.save_attr('close_values_backup', convert=[(array, to_list)], max_depth=1, filter_items=[pair])
        self.save_attr('close_times_backup', convert=[(array, to_list)], max_depth=1, filter_items=[pair])

    async def update_base_rate(self, pair: str):
        """
        Update the rate for a base currency pair.

        Updates the entry in :attr:` self.base_rates[pair]` with the new value and also adds an entry for
        the inverse pair's reciprocal value eg. 'BTC-ETH' will also get an 'ETH-BTC' entry.

        Arguments:
            pair:   The base pair to update.
        """

        value = self.close_values[pair][-1]

        try:
            old_value = self.base_rates[pair]
        except KeyError:
            old_value = 0.0

        if not math.isclose(old_value, value):
            self.log.debug("Updated {} base currency rate.", pair, verbosity=1)
            self.log.debug("{} new currency rate is {}", pair, value, verbosity=2)

        self.base_rates[pair] = value

        pair_split = pair.split('-')
        inverse_pair = '{}-{}'.format(pair_split[1], pair_split[0])
        self.base_rates[inverse_pair] = 1.0 / value

        self.save_attr('base_rates')

    async def update_trade_minimums(self):
        """
        Update the minumum trade size and minimum safe trade size according to the current base currency rates.
        """

        trade_base_btc_pair = '{}-BTC'.format(config['trade_base'])

        if config['trade_base'] != 'BTC':
            trade_base_rate = self.base_rates[trade_base_btc_pair]
        else:
            trade_base_rate = 1.0

        base_mult = await self.get_pair_base_mult(config['trade_base'], trade_base_btc_pair)
        self.min_trade_size = trade_base_rate * config['trade_min_size_btc'] * base_mult
        self.min_safe_trade_size = self.min_trade_size * (1.0 + config['trade_min_safe_percent'])

    async def refresh_mas(self, pair: str):
        """
        Refresh each moving average for the specified currency pair.

        Arguments:
            pair:  The currency pair eg. 'BTC-ETH'.
        """

        self.source_close_value_mas[pair] = {}
        self.close_value_mas[pair] = {}
        self.volume_deriv_mas[pair] = {}
        self.bollinger_bands[pair] = {}

        for window in config['ma_windows']:
            try:
                source = self.adjusted_close_values[pair][-(config['chart_age'] + window):]
                moving_average = common.math.ar_moving_average(source, window)[window:]
                self.source_close_value_mas[pair][window] = moving_average
                self.close_value_mas[pair][window] = moving_average

            except IndexError:
                self.log.error('Cannot refresh MA {} for {} with data length of {}!',
                               window, pair, len(self.adjusted_close_values[pair]))

        for window in config['vdma_windows']:
            try:
                source = self.base_24hr_volumes[pair][1][-(config['chart_age'] + window):]
                moving_average = common.math.ar_moving_average(source, window)[window:]
                self.volume_deriv_mas[pair][window] = moving_average

            except IndexError:
                self.log.error('Cannot refresh VDMA {} for {} with data length of {}!',
                               window, pair, len(self.base_24hr_volumes[pair][1]))

        self.log.debug('{} Refreshed moving averages.', pair, verbosity=1)

    async def refresh_bbands(self, pair: str):
        """
        Refresh Bollinger bands for the specified currency pair.

        Arguments:
            pair:  The currency pair eg. 'BTC-ETH'.
        """

        if not config['enable_bbands']:
            return

        bband_window = config['ma_windows'][config['bband_ma']]
        source = self.adjusted_close_values[pair][-(config['chart_age'] + bband_window):]
        bband_high = []
        bband_low = []
        ma_index = 0

        for index in range(bband_window, len(source)):
            bband_stdev = np.std(np.array(source[index - bband_window:index])) * config['bband_mult']
            bband_high.append(self.close_value_mas[pair][bband_window][ma_index] + bband_stdev)
            bband_low.append(self.close_value_mas[pair][bband_window][ma_index] - bband_stdev)
            ma_index += 1

        self.bollinger_bands[pair]['H'] = bband_high
        self.bollinger_bands[pair]['L'] = bband_low

        self.log.debug('{} Refreshed Bollinger bands.', pair, verbosity=1)

    async def refresh_emas(self, pair: str):
        """
        Refresh each exponential moving average for the specified currency pair.

        Arguments:
            pair:  The currency pair eg. 'BTC-ETH'.
        """

        self.source_close_value_emas[pair] = {}
        self.close_value_emas[pair] = {}

        if config['ema_trade_base_only'] and not common.is_trade_base_pair(pair):
            for window in config['ema_windows']:
                self.source_close_value_emas[pair][window] = array('d')
                self.close_value_emas[pair][window] = array('d')
            return

        for window in config['ema_windows']:
            try:
                source = self.adjusted_close_values[pair][-(config['chart_age'] + window * 2):]
                moving_average = common.math.ar_exponential_moving_average(source, window)[window * 2:]
                self.source_close_value_emas[pair][window] = moving_average
                self.close_value_emas[pair][window] = moving_average

            except IndexError:
                self.log.error('Cannot refresh MA {} for {} with data length of {}!',
                               window, pair, len(self.adjusted_close_values[pair]))

        self.log.debug('{} Refreshed exponential moving averages.', pair, verbosity=1)

    async def update_mas(self, pair: str):
        """
        Update each moving average for the specified currency pair.

        Arguments:
            pair:  The currency pair eg. 'BTC-ETH'.
        """

        for window in config['ma_windows']:
            try:
                num = self.last_update_nums[pair]
                source = self.adjusted_close_values[pair]
                ma = self.source_close_value_mas[pair][window]
                source_len = len(source)

                for index in range(source_len - num, source_len):
                    average = sum(source[index - window:index]) / window
                    ma.append(average)

                truncate = len(ma) - self.min_tick_length
                if truncate > 60:
                    del ma[:truncate]

                self.close_value_mas[pair][window] = ma

            except IndexError:
                self.log.error('Cannot update MA {} for {} with data length of {}!',
                               window, pair, len(self.adjusted_close_values[pair]))

        for window in config['vdma_windows']:
            try:
                num = self.last_update_nums[pair]
                source = self.base_24hr_volumes[pair][1]
                ma = self.volume_deriv_mas[pair][window]
                source_len = len(source)

                for index in range(source_len - num, source_len):
                    average = sum(source[index - window:index]) / window
                    ma.append(average)

                truncate = len(ma) - self.min_tick_length
                if truncate > 60:
                    del ma[:truncate]

            except IndexError:
                self.log.error('Cannot update VDMA {} for {} with data length of {}!',
                               window, pair, len(self.base_24hr_volumes[pair][1]))

        self.log.debug('{} Updated moving averages.', pair, verbosity=1)

    async def update_bbands(self, pair: str):
        """
        Update Bollinger bands for the specified currency pair.

        Arguments:
            pair:  The currency pair eg. 'BTC-ETH'.
        """

        if not config['enable_bbands']:
            return

        bband_window = config['ma_windows'][config['bband_ma']]
        source = self.adjusted_close_values[pair]
        source_ma = self.close_value_mas[pair][bband_window]
        num = self.last_update_nums[pair]
        end_index = len(source)
        end_ma_index = len(source_ma)
        ma_index = end_ma_index - num

        bband_high = []
        bband_low = []

        for index in range(end_index - num, end_index):
            bband_stdev = np.std(np.array(source[index - bband_window:index])) * config['bband_mult']
            bband_high.append(source_ma[ma_index] + bband_stdev)
            bband_low.append(source_ma[ma_index] - bband_stdev)
            ma_index += 1

        self.bollinger_bands[pair]['H'].extend(bband_high)
        self.bollinger_bands[pair]['L'].extend(bband_low)

        self.log.debug('{} Updated Bollinger bands.', pair, verbosity=1)

    async def update_emas(self, pair: str):
        """
        Update each exponential moving average for the specified currency pair.

        Arguments:
            pair:  The currency pair eg. 'BTC-ETH'.
        """

        if config['ema_trade_base_only'] and not common.is_trade_base_pair(pair):
            return

        for window in config['ema_windows']:
            try:
                num = self.last_update_nums[pair]
                source = self.adjusted_close_values[pair]
                ema = self.source_close_value_emas[pair][window]
                source_index = len(source)
                c = 2.0 / (window + 1)

                for index in range(source_index - num, source_index):
                    current_ema = sum(source[index - window * 2:index - window]) / window
                    for value in source[index - window:index]:
                        current_ema = (c * value) + ((1 - c) * current_ema)
                    ema.append(current_ema)

                truncate = len(ema) - self.min_tick_length
                if truncate > 60:
                    del ema[:truncate]

                self.close_value_emas[pair][window] = ema

            except IndexError:
                self.log.error('Cannot update MA {} for {} with data length of {}!',
                               window, pair, len(self.adjusted_close_values[pair]))

        self.log.debug('{} Updated exponential moving averages.', pair, verbosity=1)

    async def filter_mas(self, pair: str):
        """
        Apply a Savitzky-Golay filter to the set of moving averages.

        This has been shown to improve accuracy of detections by reducing noise when used with optimal parameters.

        Arguments:
            pair:  The currency pair eg. 'BTC-ETH'.
        """

        if not config['ma_filter']:
            return

        for window in config['ma_windows']:
            try:
                source = self.source_close_value_mas[pair][window]
                source_length = len(source)
                padded_length = source_length + config['ma_filter_window']
                pad_value = source[-1]

                if source:
                    source = np.resize(source, padded_length)
                    for index in range(source_length, padded_length):
                        source[index] = pad_value

                    result = scipy.signal.savgol_filter(source,
                                                        config['ma_filter_window'],
                                                        config['ma_filter_order'])

                    self.close_value_mas[pair][window] = array('d', result[:-(config['ma_filter_window'])])

            except ValueError as e:
                self.log.warning('Not enough data to filter MA {} for {}: {}', window, pair, e)

        self.log.debug('{} Filtered moving averages.', pair, verbosity=1)

    async def filter_emas(self, pair: str):
        """
        Apply a Savitzky-Golay filter to the set of moving averages.

        This has been shown to improve accuracy of detections by reducing noise when used with optimal parameters.

        TODO: See note in :meth:`filter_mas`.

        Arguments:
            pair:  The currency pair eg. 'BTC-ETH'.
        """

        if config['ema_trade_base_only'] and not common.is_trade_base_pair(pair):
            return

        if not config['ma_filter']:
            return

        for window in config['ema_windows']:
            try:
                source = self.source_close_value_emas[pair][window]

                if source:
                    source.extend([source[-1] for _ in range(config['ma_filter_window'])])
                    result = scipy.signal.savgol_filter(source,
                                                        config['ma_filter_window'],
                                                        config['ma_filter_order'])
                    self.close_value_emas[pair][window] = array('d', result[:-(config['ma_filter_window'])])

            except ValueError as e:
                self.log.warning('Not enough data to filter MA {} for {}: {}', window, pair, e)

        self.log.debug('{} Filtered moving averages.', pair, verbosity=1)

    async def refresh_indicators(self, pair: str):
        """
        Refresh trading indicators for the given pair.

        Arguments:
            pair:  The currency pair eg. 'BTC-ETH'.
        """

        if config['enable_rsi']:
            await self._refresh_rsi(pair)

    async def _refresh_rsi(self, pair: str):
        """
        Refresh the Relative Strength Index for a pair.

        Arguments:
            pair:  The currency pair eg. 'BTC-ETH'
        """

        source = self.adjusted_close_values[pair][-config['rsi_size']:]
        deltas = common.math.diff(source)

        n = config['rsi_window']
        seed = deltas[:n + 1]
        seed_ups = [value for value in seed if value >= 0]
        seed_downs = [value for value in seed if value < 0]
        up = sum(seed_ups) / n
        down = -sum(seed_downs) / n

        try:
            rs = up / down
        except ZeroDivisionError:
            rs = 0

        rsi = [0] * len(source)
        rsi[:n] = [100.0 - 100.0 / (1.0 + rs) for _ in range(n)]

        for i in range(n, len(source)):
            delta = deltas[i - 1]

            if delta > 0:
                upval = delta
                downval = 0.0
            else:
                upval = 0.0
                downval = -delta

            up = (up * (n - 1) + upval) / n
            down = (down * (n - 1) + downval) / n

            try:
                rs = up / down
            except ZeroDivisionError:
                rs = 0

            rsi[i] = 100.0 - 100.0 / (1.0 + rs)

        self.relative_strength_indexes[pair] = rsi

    async def refresh_derived_data(self, pair):
        """
        Refresh all market data derived from tick data for the specified pair.

        Arguments:
            pair:  The currency pair eg. 'BTC-ETH'.
        """

        await self.refresh_adjusted_tick_data(pair)
        await self.refresh_mas(pair)
        await self.refresh_emas(pair)
        await self.filter_mas(pair)
        await self.filter_emas(pair)
        await self.refresh_bbands(pair)
        await self.refresh_indicators(pair)

    async def update_derived_data(self, pair):
        """
        Update all market data derived from tick data for the specified pair.

        Arguments:
            pair:  The currency pair eg. 'BTC-ETH'.
        """

        await self.update_adjusted_tick_data(pair)
        await self.update_mas(pair)
        await self.update_emas(pair)
        await self.filter_mas(pair)
        await self.filter_emas(pair)
        await self.update_bbands(pair)
        await self.refresh_indicators(pair)

    async def get_pair_base_mult(self, base: str, pair: str):
        """
        Get the multiplier from a pair to a different base currency.

        Eg. _get_pair_base_mult('USDT', 'ETH-CVC') will give the value of 'USDT-ETH'.
            _get_pair_base_mult('USDT', 'USDT-BTC') will return 1.0.
        """

        pair_base = pair.split('-')[0]
        return await self.get_base_mult(base, pair_base)

    async def get_base_mult(self, base: str, other_base: str):
        """
        Get the multiplier from a base currency to a different base currency.
        """

        if base == other_base:
            return 1.0

        try:
            convert_pair = '{}-{}'.format(base, other_base)
            return self.base_rates[convert_pair]

        except KeyError:
            raise ValueError('Invalid base rate {}-{}'.format(base, other_base))

    async def convert_pair_base(self, base: str, pair: str):
        """
        Convert a pair value to a different base currency.

        Eg. _convert_pair_base('USDT', 'ETH-CVC') will give the value of the hypothetical pair USDT-CVC.
        """

        pair_value = self.close_values[pair][-1]
        pair_base, pair_quote, _ = common.get_pair_elements(pair)

        if pair_base == base:
            return pair_value

        else:
            try:
                convert_pair = '{}-{}'.format(base, pair_base)
                convert_value = self.base_rates[convert_pair]
                return pair_value * convert_value

            except (IndexError, KeyError):
                raise ValueError('Unsupported conversion: {} -> {}'.format(pair_quote, base))

    @staticmethod
    def load_pair_file(pair: str, filename: str):
        """
        Load a pair file from disk.

        Arguments:
            pair:       Name of the currency pair eg. 'BTC-ETH'.
            filename:   Path to the JSON format file containing the pair's tick data.

        Returns:
            (tuple): A tuple containing the following:
                (str):          Mame of the pair (used for joining on async tasks).
                list(float):    Closing values for each tick.
                list(float):    Closing timestamps for each tick.
                list(float):    Closing 24-hour base volumes for each tick.
        """

        with open(filename) as file:
            tick_data = json.load(file)

        if tick_data is None:
            return(pair, [], [], [], [])

        source_values, source_times, source_volumes = Market._load_source_tick_data(tick_data)
        return (pair,) + Market._parse_source_tick_data(source_values, source_times, source_volumes)

    @staticmethod
    def load_pair_dirs(pair: str, dirs: Sequence[str]):
        """
        Load a pair from disk split into multiple ordered directories.

        Arguments:
            pair:       Name of the currency pair eg. 'BTC-ETH'.
            filename:   Path to the JSON format file containing the pair's tick data.

        Returns:
            (tuple):           A tuple containing:
                (str):         Name of the pair (used for joining on async tasks).
                array(float):  Closing values for each tick.
                array(float):  Closing timestamps for each tick.
                array(float):  Closing 24-hour base volumes for each tick.
        """

        source_values = []
        source_volumes = []
        source_times = []

        for dirname in dirs:
            filename = dirname + pair + '.json'

            try:
                with open(filename) as file:
                    tick_data = json.load(file)
            except FileNotFoundError:
                continue

            if tick_data is None:
                continue

            if source_times:
                last_time = source_times[-1]
                next_time = 0.0
                start_index = 0

                for start_index, tick in enumerate(tick_data):
                    next_time = tick['T']
                    if next_time > last_time:
                        tick_data = tick_data[start_index:]
                        break

                if next_time <= last_time:
                    continue

                while int(next_time - last_time) > config['tick_interval_secs']:
                    last_time += config['tick_interval_secs']
                    source_values.append(source_values[-1])
                    source_volumes.append(source_volumes[-1])
                    source_times.append(last_time)

            next_source_values, next_source_times, next_source_volumes = Market._load_source_tick_data(tick_data)
            source_values.extend(next_source_values)
            source_times.extend(next_source_times)
            source_volumes.extend(next_source_volumes)

        return (pair,) + Market._parse_source_tick_data(source_values, source_times, source_volumes)

    @staticmethod
    def _load_source_tick_data(tick_data: Sequence[Dict[str, Any]]):
        """
        Load source tick data from raw tick data read from a file.

        As ticks are stored sparsely (intervals without any data are skipped) this expands them by repeating the same
        values for subsequent 'empty' ticks.

        Arguments:
            tick_data:  List of tick data elements read from a file.

        Returns:
            (tuple):           A tuple containing:
                array(float):  Closing values at each tick.
                array(float):  Closing UTC timestamps at each tick.
                array(float):  Closing base volumes at each tick.
        """

        source_values = array('d')
        source_volumes = array('d')
        source_times = array('d')

        tick = tick_data[0]

        last_value = tick['C']
        last_volume = tick['BV']
        last_time = tick['T']

        source_values.append(last_value)
        source_volumes.append(last_volume)
        source_times.append(last_time)

        for tick in tick_data[1:]:
            close_time = tick['T']

            while int(close_time - last_time) > config['tick_interval_secs']:
                last_time += config['tick_interval_secs']
                source_values.append(last_value)
                source_volumes.append(0.0)
                source_times.append(last_time)

            last_value = tick['C']
            last_volume = tick['BV']
            last_time = tick['T']

            source_values.append(last_value)
            source_volumes.append(last_volume)
            source_times.append(last_time)

        return (source_values, source_times, source_volumes)

    @staticmethod
    def _parse_source_tick_data(source_values: Sequence[float], source_times: Sequence[float],
                                source_volumes: Sequence[float]):
        """
        Parse source data to tick data needed by the application.

        Arguments:
            source_values:   Closing values at each tick.
            source_times:    Closing UTC timestamps at each tick.
            source_volumes:  Closing base volumes at each tick.

        Returns:
            (tuple):           A tuple containing:
                array(float):  Closing values at each tick.
                array(float):  Closing UTC timestamps at each tick.
                array(float):  24-hour rolling base volumes at each tick.
                array(float):  Previous day (24-hour) closing values at each tick.
        """

        close_values = array('d')
        close_times = array('d')
        base_volumes = array('d')
        prev_day_values = array('d')

        day_ticks = 1440 // (config['tick_interval_secs'] // 60)

        if len(source_values) > day_ticks:
            day_volume = 0.0

            for index in range(0, day_ticks):
                # weight = 2.0 * (1.0 - ((day_ticks - 1) - index) / (day_ticks - 1))
                day_volume += source_volumes[index]  # * weight

            for index in range(day_ticks, len(source_values)):
                day_volume += source_volumes[index]
                day_volume -= source_volumes[index - day_ticks]

                close_values.append(source_values[index])
                close_times.append(source_times[index])
                base_volumes.append(day_volume)
                prev_day_values.append(source_values[index - day_ticks])

        return (close_values, close_times, base_volumes, prev_day_values)
