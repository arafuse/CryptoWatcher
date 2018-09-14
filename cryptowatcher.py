#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (c) A 2017 Adam M. Rafuse - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential

"""
Watch charts. Make trades. Get money.

TODO: *** General ***
TODO: Use type aliases from the 'typing' module (in progress).
TODO: Move to Cython (pxd) for speedups (eg. math functions).
TODO: Log floats with specific significant digits.
TODO: Use sets where set operations are appropriate instead of lists.
TODO: Use configparser and command line arguments.
TODO: Use @property accessors for read-only class attributes.
TODO: Support ccxt library.
TODO: * Remove dead code and unused features.

TODO: *** Market ***
TODO: Support different time resolutions (in progress).
TODO: Add market capture option.

TODO: *** Backtesting ***
TODO: C / OpenCL math functions.
TODO: Better multicore support (market sim service process).

TODO *** Detections ***
TODO: Higher follow_min_delta for continuations?
TODO: Channel-based detection heuristics (eg. bollinger bands)?
TODO: * Fix restore detection triggers miss on rollover interval (uses detection_stats).

TODO: *** Trading ***
TODO: Auto-tweak tool for simulation.
TODO: Set trade size as percentage of total balance.
TODO: * Filter by minimum price to avoid large swings.
"""

__author__ = 'Adam Rafuse <$(echo nqnz.enshfr#tznvy.pbz | tr a-z# n-za-m@)>'

import gc
import os
import sys
import glob
import json
import time
import signal
import asyncio
import importlib
import traceback
import multiprocessing
import multiprocessing.pool

from array import array
from typing import Any, Callable, Sequence, List, Dict, Tuple, Set

sys.path.insert(0, 'lib/')
import aiohttp

import api
import core
import utils
import common
import defaults
import detections
import configuration

from common import interrupt, loop

config = configuration.config
"""
Global configuration.
"""


class Application(utils.Singleton, common.base.Persistable):
    """
    Application object.
    """

    def __init__(self):
        utils.Singleton.__init__(self)
        common.base.Persistable.__init__(self)

        self.market: core.Market
        """
        Shared :class:`Market` service.
        """

        self.reporter: core.Reporter
        """
        Shared :class:`Reporter` service.
        """

        self.balancer: core.Balancer
        """
        Shared :class:`Balancer` service.
        """

        self.trader: core.Trader
        """
        Shared :class:`Trader` service.
        """

        self.detector: core.Detector
        """
        Shared :class:`Detector` service.
        """

        self.time_prefix: str = common.get_rollover_time_str(time.time())
        """
        Current time prefix, used for separating log, stat, and snapshot directories by time.
        """

        self.backtest_close_values: Dict[str, array] = {}
        """
        Closing values used for backtest source data (see :attr:`Market.close_values`)
        """

        self.backtest_close_times: Dict[str, array] = {}
        """
        Closing times used for backtest source data (see :attr:`Market.close_times`)
        """

        self.backtest_base_volumes: Dict[str, array] = {}
        """
        24-hour base volumes used for backtest source data (see :attr:`Market.close_times`)
        """

        self.backtest_prev_day_values: Dict[str, array] = {}
        """
        Previous day values used for backtest source data (see :attr:`Market.close_times`)
        """

        self.pairs_refreshed = asyncio.Event()
        """
        Event which when set signals the completion of a currency pairs refresh cycle.
        """

        self.data_refreshed = asyncio.Event()
        """
        Event which when set signals the completion of a market data refresh cycle.
        """

        self.first_refresh_completed = asyncio.Event()
        """
        Event which when set signals the completion of the first data refresh on startup.
        """

        self.startup_init_completed = asyncio.Event()
        """
        Event which when set signals that startup initialization during first update has been completed.
        """

        self.log = utils.logging.ThreadedLogger(scope=self, level=config['app_log_level'], module_name=__name__,
                                                logger_level=config['app_log_level'], debug_verbosity=0,
                                                filename=config['output_log'], debug_filename=config['debug_log'],
                                                error_filename=config['error_log'])
        """
        Application logger.
        """

        common.log = utils.logging.ChildLogger(parent=self.log, scope='common')
        utils.log = utils.logging.ChildLogger(parent=self.log, scope='utils')

        self.task_pool: multiprocessing.pool.Pool = common.get_task_pool()
        """
        Application task pool.
        """

        self.tasks: List[asyncio.Future] = []
        """
        Async application tasks.
        """

        self.interrupts = 0
        """
        Application interrupt counter.
        """

        self.crash_report = None
        """
        Log report of last crash.
        """

    async def execute(self, backtest: bool=False, backtest_pairs: List[str]=None):
        """
        Execute this application.

        Arguments:
            backtest:        If True, runs the app in backtest mode against historical data. Otherwise, runs the app
                             in live mode.
            backtest_pairs:  The currency pairs to run the backtest on, if backtest is True. If pair refresh is enabled,
                             the pairs are instead updated dynamically based on the simulated pair filter.
        """

        self.log.start()
        self._hook_user_interrupt()
        self._hook_reload_interrupt()
        self._hook_sys_excepthook()

        timeout = config['http_timeout_secs']
        read_timeout = config['http_read_timeout_secs']
        conn = aiohttp.TCPConnector(limit_per_host=config['http_host_conn_limit'])

        async with aiohttp.ClientSession(loop=loop, connector=conn,
                                         read_timeout=read_timeout, conn_timeout=timeout) as session:

            if config['coin_exchange'] == 'bittrex':
                from api import bittrex
                client = bittrex.Client(session, log=self.log)
            elif config['coin_exchange'] == 'binance':
                from api import binance
                client = binance.Client(session, log=self.log)
            elif config['coin_exchange'] == 'okex':
                from api import okex
                client = okex.Client(session, log=self.log)
            else:
                raise ValueError("Unsupported coin exchange: {}".format(config['coin_exchange']))

            self.market = core.Market(client, log=self.log)
            self.reporter = core.Reporter(self.market, log=self.log)
            self.trader = core.Trader(client, self.market, self.reporter, self.time_prefix, log=self.log)
            self.detector = core.Detector(self.market, self.reporter, self.trader, self.time_prefix, log=self.log)

            if backtest:
                await self._backtest(backtest_pairs)
            else:
                await self._live()

        self._shutdown()

    def _hook_user_interrupt(self):
        """
        Hook the user interrupt signal to attempt clean shutdown.

        Sets the :data:`interrupt` event on user interrupt to allow the app to start shutting down. Performs a hard
        exit if the number of user interrupts exceeds :data:`config['app_max_interrupts']`.
        """

        def signal_handler(_, __):
            print()
            self.log.info('Got user interrupt.')

            interrupt.set()
            self.interrupts += 1

            if self.interrupts >= config['app_max_interrupts']:
                self.task_pool.terminate()
                self.reporter.render_pool.terminate()
                self._shutdown()

        signal.signal(signal.SIGINT, signal_handler)

    def _hook_reload_interrupt(self):
        """
        Hook the reload interrupt signal to reload config.
        """

        def signal_handler(_, __):
            print()
            self.log.info('Got reload interrupt.')
            self._reload_config()

        signal.signal(signal.SIGHUP, signal_handler)

    def _reload_config(self):
        """
        Hot-reload the configuration.

        (Experimental) not all reloaded settings have an effect, specifically those that are used for object creation
        such as logging, core / thread settings, and crypto exchange.
        """

        exchange = config['coin_exchange']

        importlib.reload(detections)
        importlib.reload(defaults)
        importlib.reload(configuration)

        from core import market
        from core import reporter
        from core import balancer
        from core import trader
        from core import detector
        from common import base

        globals()['config'] = configuration.config
        market.config = configuration.config
        reporter.config = configuration.config
        balancer.config = configuration.config
        trader.config = configuration.config
        detector.config = configuration.config
        common.config = configuration.config
        base.config = configuration.config

        if exchange == 'bittrex':
            from api import bittrex
            bittrex.config = configuration.config
        elif exchange == 'binance':
            from api import binance
            binance.config = configuration.config
        elif exchange == 'okex':
            from api import okex
            okex.config = configuration.config

        common.init_config_paths()
        common.create_user_dirs()

        config_for_log = config.copy()
        del config_for_log['detections']
        self.log.info("Reloaded configuration:\n{}", json.dumps(config_for_log, skipkeys=True, indent=2))

    def _hook_sys_excepthook(self):
        """
        Hook the uncaught exception handler to redirect errors to the logger and attempt a clean shutdown.

        Only logs the crash report if a previously persisted one doesn't exist to avoid spamming alerts on crash loops
        and busting email quota.
        """

        def uncaught_handler(exc_type, value, tb):
            crash_report = '\n{}', ''.join(traceback.format_exception(exc_type, value, tb))
            if self.crash_report is None:
                self.log.critical(crash_report)
            self.crash_report = crash_report
            self.save_attr('crash_report')
            self._error_cb()

        sys.excepthook = uncaught_handler

    def _error_cb(self):
        """
        Signal a critical error and shut down the app.

        This is intended for use as a callback function for various error handlers.
        """

        common.play_sound(config['critical_sound'])
        interrupt.set()
        self._shutdown()

    def _shutdown(self):
        """
        Shut down this application.

        Cancels all application tasks and waits for all pending async operations to complete, then stops the logger.
        """

        for task in self.tasks:
            task.cancel()

        self.task_pool.close()
        self.reporter.render_pool.close()
        self.task_pool.join()
        self.reporter.render_pool.join()

        self.log.stop()

    async def _live(self):
        """
        Run in live mode.

        Launches background tasks that perform analysis and trading on new data. Live trading will only occur if
        :data:`config['trade_simulate']` is False, otherwise trading will be simulated. Exits when a user interrupt
        (Ctrl+C) is caught.

        Attempts to first restore any state for services that has been persisted to disk.
        """

        def to_array(l: Sequence[float]):
            return array('d', l)

        self.log.config(filename=config['output_log'], debug_filename=config['debug_log'],
                        error_filename=config['error_log'], callback=self.reporter.email_report)

        self.restore_attr('crash_report')
        self.market.restore_attr('last_pairs')
        self.market.restore_attr('back_refreshes')
        self.market.restore_attr('close_times_backup', convert=[(list, to_array)], max_depth=1)
        self.market.restore_attr('close_values_backup', convert=[(list, to_array)], max_depth=1)
        self.market.restore_attr('base_24hr_volumes_backup', convert=[(list, to_array)], max_depth=1)
        self.reporter.restore_attr('follow_up_snapshots')
        self.trader.restore_attr('trades', max_depth=1)
        self.trader.restore_attr('last_trades', max_depth=1)
        self.trader.restore_attr('trade_sizes', max_depth=1)
        self.trader.restore_attr('trade_proceeds', max_depth=1)
        self.trader.restore_attr('trade_stats', max_depth=2, filter_keys=[self.time_prefix])
        self.trader.balancer.restore_attr('refill_orders', max_depth=1)
        self.detector.restore_attr('last_detections', max_depth=1)
        self.detector.restore_attr('detection_stats', max_depth=2, filter_keys=[self.time_prefix])

        self.tasks = [
            utils.async_task(self._refresh_pairs_task(), loop=loop, error_cb=self._error_cb),
            utils.async_task(self._refresh_data_task(), loop=loop, error_cb=self._error_cb),
            utils.async_task(self._update_data_task(), loop=loop, error_cb=self._error_cb),
            utils.async_task(self._update_rollover_task(), loop=loop, error_cb=self._error_cb)
        ]

        if config['enable_snapshots']:
            self.tasks.append(utils.async_task(self._follow_up_snapshots_task(), loop=loop, error_cb=self._error_cb))

        while not interrupt.is_set():
            await asyncio.sleep(1.0)

    async def _backtest(self, pairs: Sequence[str]):
        """
        Run in backtest mode.

        Performs analysis and simulated trading against a window of past data. The window size and time offset are
        controlled by :data:`config['backtest_window']` and :data:`config['backtest_offset']` respectively.

        Arguments:
            pairs:  List of currency pairs to use for the backtest data.
        """

        self.market.pairs = pairs
        self.market.extra_base_pairs = [pair for pair in config['base_pairs'] if pair not in pairs]

        await self._init_backtest()
        await self._run_backtest()

        self.detector.save_attr('detection_stats', max_depth=2, force=True)
        self.trader.save_attr('trade_stats', max_depth=2, force=True)
        self.trader.save_attr('last_trades', max_depth=1, force=True)
        self.trader.save_attr('trades', max_depth=1, force=True)
        self.market.save_attr('base_rates', force=True)

    async def _init_backtest(self):
        """
        Bootstrap all initial data and state for backtesting.

        Loads the historical tick data from the API for all backtest pairs from disk, prepares the backtesting data
        windows from the tick data, and sets up the initial derived market data, detector states, and reporter charts.
        """

        await self._load_backtest_data(config['backtest_data_dir'])
        begin_time, end_time = await self._get_backtest_times()

        for pair in self.market.close_values:
            if self.market.close_values[pair]:
                await self._prepare_backtest_data(pair, begin_time, end_time)

        for pair in list(self.market.close_values.keys()):
            await self._init_backtest_data(pair)

        if not config['backtest_multicore']:
            await self._refresh_backtest_pairs()

        await self._init_backtest_services()

    async def _load_backtest_data(self, source_dir: str) -> Tuple[float, float]:
        """
        Load data for an backtest.

        An backtest is a backtest using historical tick data saved to disk, as opposed to pulling the latest
        tick data from the API. This allows for simulation of more features like pair filtering and backtesting over
        a longer timeframes.

        If pair filtering is enabled, data for the entire market must be loaded which can take time and be limited
        by memory constraints. Depending on the :data:`config['app_multicore']` and
        :data:`config['backtest_multicore']` options the load will be done in a process pool to improve speed.

        Arguments:
            source_dir:   Path to the source directory containing saved tick data for all market currency pairs.
        """

        load_method, params = await self._get_backtest_load_params(source_dir)
        params = await self._filter_backtest_load_params(params)

        futures = []

        for pair, param in params:
            if interrupt.is_set(): break
            futures.append(self.task_pool.apply_async(load_method, [pair, param]))

        for future in futures:
            if interrupt.is_set(): break
            pair, close_values, close_times, base_volumes, prev_day_values = future.get()
            if close_values and close_times and base_volumes and prev_day_values:
                self.market.base_24hr_volumes[pair] = [array('d'), array('d')]
                self.market.close_values[pair] = close_values
                self.market.close_times[pair] = close_times
                self.market.base_24hr_volumes[pair][0] = base_volumes
                self.market.prev_day_values[pair] = prev_day_values

            self.log.info("{} loaded backtest data.", pair)

        self.task_pool.terminate()

    async def _get_backtest_load_params(self, source_dir: str) -> Tuple[Callable, List[Tuple[str, Any]]]:
        """
        Get appropriate method and parameters for loading backtest data.

        Looks at the structure of data on disk to load and decides whether to just load the base directory
        (contains JSON files) or to load from files split across subdirectories (contains only other directories).

        Directory splits should be by time or otherwise by alphanumeric order, otherwise large gaps will appear in the
        loaded data.

        Returns:
            (tuple):           A tuple containing:
                (callable):    The method used for loading the data.
                list(tuple):   A list containing tuples:
                    (str):     The name of the currency pair being loaded.
                    (object):  Parameters for the load method to load this pair's data. May be a string path to a data
                               file or a list of string paths pointing to split directories.
        """

        params = []
        filenames = glob.glob(source_dir + '*.json')

        if not filenames:
            load_method = core.Market.load_pair_dirs
            dirnames = sorted(glob.glob(source_dir + '*' + os.sep))
            filenames = glob.glob(dirnames[0] + '*.json')
            for filename in filenames:
                pair = os.path.splitext(os.path.basename(filename))[0]
                base = pair.split('-')[0]
                if base in config['min_base_volumes']:
                    params.append((pair, dirnames))

        else:
            load_method = core.Market.load_pair_file
            for filename in filenames:
                pair = os.path.splitext(os.path.basename(filename))[0]
                base = pair.split('-')[0]
                if base in config['min_base_volumes']:
                    params.append((pair, filename))

        if config['backtest_multicore']:
            used_pairs = self.market.pairs + self.market.extra_base_pairs
            remove_indexes = []
            for index, param in enumerate(params):
                if param[0] not in used_pairs:
                    remove_indexes.append(index)
            for index in reversed(remove_indexes):
                del params[index]

        return (load_method, params)

    async def _filter_backtest_load_params(self, params: Sequence[Tuple[str, Any]]) -> List[Tuple[str, Any]]:
        """
        Filter a list of offline load parameters.

        Arguments:
            params:  Parameter list as returned by :meth:`_get_backtest_load_params`.

        Returns:
            list(tuple):  Filtered parameter list with unneeded pairs removed.
        """

        filtered_params = []
        params_pairs = []

        if config['backtest_limit_pairs']:
            for param in params:
                pair = param[0]
                params_pairs.append(pair)
                if pair in config['backtest_limit_pairs']:
                    filtered_params.append(param)

        else:
            for param in params:
                pair = param[0]
                base = pair.split('-')[0]
                params_pairs.append(pair)
                if base in config['min_base_volumes'] and config['min_base_volumes'][base]:
                    filtered_params.append(param)
                elif pair in config['base_pairs']:
                    filtered_params.append(param)

        invalid_pairs = []
        for pair in self.market.pairs:
            if pair not in params_pairs:
                invalid_pairs.append(pair)

        for pair in invalid_pairs:
            self.market.pairs.remove(pair)

        return filtered_params

    async def _get_backtest_times(self):
        """
        Get the begin time and end time of the backtest.

        The begin time is calculated as the latest starting tick in the list of tick data for all pairs. Pairs
        that start too late (greater than :data:`config['backtest_max_begin_skew']`) are dropped. The end time is the
        latest ending tick in the list of tick data for all remaining pairs.

        Returns:
            (tuple):      A tuple containing:
                (float):  The begin time.
                (float):  The end time.
        """

        begin_times = [self.market.close_times[pair][0] for pair in self.market.close_times]
        begin_min = min(begin_times)
        skewed_pairs = []

        for pair in self.market.close_times:
            begin = self.market.close_times[pair][0]
            skew = begin - begin_min
            if skew > config['backtest_max_begin_skew']:
                self.log.warning("{} is skewed too much by {}, removing from backtest.", pair, skew)
                begin_times.remove(begin)
                skewed_pairs.append(pair)

        for pair in skewed_pairs:
            if pair in self.market.pairs:
                self.market.pairs.remove(pair)
            del self.market.close_times[pair]
            del self.market.close_values[pair]
            del self.market.base_24hr_volumes[pair]
            del self.market.prev_day_values[pair]

        begin_time = max(begin_times)
        end_times = [self.market.close_times[pair][-1] for pair in self.market.close_times]
        end_time = max(end_times)

        return (begin_time, end_time)

    async def _prepare_backtest_data(self, pair: str, begin_time: float, end_time: float):
        """
        Prepare backtest data for the specified pair, assuming historical tick data for that pair exists.

        Prepares the backtesting data windows from the tick data and moves the tick data back to the backtest
        start time.

        Arguments:
            pair: The currency pair eg. 'BTC-ETH'.
            begin_time: The timestamp of the beginning of the backtest data.
            end_time: The timestamp of the end of the backtest data.
        """

        mins = config['backtest_window']
        offset = config['backtest_offset'] + config['ma_windows'][-1] + config['ma_windows'][-2]
        interval_secs = config['tick_interval_secs']

        begin_aligned = begin_time - (begin_time % interval_secs)
        begin_offset = self.market.close_times[pair].index(begin_aligned)

        del self.market.close_times[pair][:begin_offset]
        del self.market.close_values[pair][:begin_offset]

        if pair in self.market.base_24hr_volumes and pair in self.market.prev_day_values:
            del self.market.base_24hr_volumes[pair][0][:begin_offset]
            del self.market.prev_day_values[pair][:begin_offset]

        start = offset
        end = offset + mins

        self.backtest_close_times[pair] = self.market.close_times[pair][start:end]
        self.backtest_close_values[pair] = self.market.close_values[pair][start:end]
        del self.market.close_times[pair][start:]
        del self.market.close_values[pair][start:]

        if pair in self.market.base_24hr_volumes and pair in self.market.prev_day_values:
            self.backtest_base_volumes[pair] = self.market.base_24hr_volumes[pair][0][start:end]
            self.backtest_prev_day_values[pair] = self.market.prev_day_values[pair][start:end]
            del self.market.base_24hr_volumes[pair][0][start:]
            del self.market.prev_day_values[pair][start:]

        self.log.debug("{} prepared backtest data.", pair)

    async def _init_backtest_data(self, pair: str):
        """
        Initialize backtest data for the given pair, or drop the pair if it cannot be initialized.

        Filters the pair from the market pairs list if no valid tick data remains for it. Otherwise updates
        the base rate for the pair if the pair is a base pair.

        The module :data:`interrupt` event is set to signal a critical error if there is no
        valid tick data for a trade base pair, as these pairs are required for conversions and thus no backtesting can
        occur without them.

        Arguments:
            pair: The currency pair eg. 'BTC-ETH'.
        """

        if not await self._screen_backtest_data(pair):
            if common.is_trade_base_pair(pair):
                self.log.error('{} has no tick data but is a base pair needed for conversions.', pair)
                interrupt.set()
            return

        if pair in config['base_pairs']:
            await self.market.update_base_rate(pair)

        self.market.last_update_nums[pair] = 1

    async def _screen_backtest_data(self, pair: str) -> bool:
        """
        Screen any invalid or missing backtest tick data for a pair.

        Deletes the pair from tick data lists if no valid tick data exists for the pair.

        Arguments:
            pair:  The currency pair eg. 'BTC-ETH'.

        Returns:
            True if tick data still exists for the pair, otherwise False.
        """

        if not self.market.close_values[pair]:
            self.log.warning('{} has no tick data, cannot be used in backtest.', pair)
            del self.market.close_values[pair]
            del self.market.close_times[pair]
            del self.market.base_24hr_volumes[pair]
            del self.market.prev_day_values[pair]
            return False

        return True

    async def _refresh_backtest_pairs(self):
        """
        Refresh the list of watched currency pairs for backtesting.

        The list attr:`market.pairs` is updated with pairs filtered according to base currency and current trading volume,
        as defined in :data:`config['min_base_volumes']` If :data:`config['pair_change_filter']` is enabled, the pairs
        are additionally filtered according to :meth:`core.Market.apply_pair_change_filter`.

        The filtered results are ordered by volume and will not exceed :data:`config['max_pairs']`. Any base pairs that
        are required for data conversions that are not included in filtered results are set in
        :attr:`market.extra_base_pairs`.
        """

        pairs = await self._get_backtest_filtered_pairs()
        remove_pairs = []

        bases = list(config['min_base_volumes'].keys())
        for pair in pairs:
            if await core.Market.apply_pair_prefer_filter(pair, bases, pairs):
                remove_pairs.append(pair)

        for pair in remove_pairs:
            pairs.remove(pair)

        self.market.pairs = pairs
        self.market.extra_base_pairs = [pair for pair in config['base_pairs'] if pair not in pairs]
        self.log.info('Added pairs: {}', self.market.pairs)
        self.log.info('Added extra base pairs: {}', self.market.extra_base_pairs)

    async def _get_backtest_filtered_pairs(self) -> List[str]:
        """
        Get filtered pairs from offline data.

        Pairs are filtered by volume and change constraints as defined by :data:`config['min_base_volumes']` and
        config['pair_change_*'] as they would be for a live run.

        Returns:
            List of filtered currency pairs.
        """

        pairs = []
        min_base_volumes = config['min_base_volumes']

        for pair in self.backtest_base_volumes:
            base = pair.split('-')[0]
            volume = self.market.base_24hr_volumes[pair][0][-1]
            min_volume = min_base_volumes[base] if base in min_base_volumes else None

            if min_volume and volume > min_volume:
                current_value = self.market.close_values[pair][-1]
                prev_day_value = self.market.prev_day_values[pair][-1]

                if pair in self.market.last_pairs:
                    last_value = self.market.last_pairs[pair]['value']
                    change = current_value / last_value - 1.0 if last_value else 0.0
                else:
                    change = current_value / prev_day_value - 1.0 if prev_day_value > 0.0 else 0.0

                if not await self.market.apply_pair_change_filter(pair, change, current_value):
                    pairs.append(pair)

        return pairs

    async def _init_backtest_services(self):
        """
        Bootstrap all services for backtesting.

        Does the initial sync of pairs between the market, trader, and detector services. Refreshes all derived market
        data, detector indicator states and triggers, and outputs initial reporter charts. Initializes the simulated
        balances used by the trader's balancer service.

        Trade base pairs are refreshed first, because other pairs have a dependency on their data.
        """

        await self.trader.sync_pairs()
        await self.detector.sync_pairs()

        pairs = self.market.pairs + self.market.extra_base_pairs
        trade_base_pairs, non_base_pairs = await self._split_trade_base_pairs(pairs)

        for pair in trade_base_pairs:
            if interrupt.is_set(): break
            await self.market.refresh_derived_data(pair)
            if pair not in self.market.extra_base_pairs:
                await self.detector.update_indicator_states(pair)
                await self.detector.update_detection_triggers(pair)
                await self._output_charts(pair)

        for pair in non_base_pairs:
            if interrupt.is_set(): break
            await self.market.refresh_derived_data(pair)
            if pair not in self.market.extra_base_pairs:
                await self.detector.update_indicator_states(pair)
                await self.detector.update_detection_triggers(pair)
                await self._output_charts(pair)

        await self.trader.balancer.init_sim_balances()

    async def _run_backtest(self):
        """
        Run an backtest against all loaded pairs until completed.

        Stops early and cleans up if the: data: `interrupt` event is set(either critical error or user Ctrl + C).
        """

        follow_up_interval = 0

        async def check_follow_up_snapshots():
            nonlocal follow_up_interval
            follow_up_interval += 1
            if follow_up_interval > config['backtest_follow_up_ticks']:
                await self.reporter.check_follow_up_snapshots()
                follow_up_interval = 0

        async def check_remaining_follow_up_snapshots():
            for snapshot in self.reporter.follow_up_snapshots:
                snapshot['follow_up_time'] = 0
            await self.reporter.check_follow_up_snapshots()

        all_pairs = [pair for pair in self.market.close_times]

        while not interrupt.is_set() and all_pairs:
            await self._update_backtest_rollover()

            finished_pairs = await self._process_backtest_tick(all_pairs)
            for pair in finished_pairs:
                await self._clean_finished_backtest_pair(pair)
                all_pairs.remove(pair)

            if finished_pairs:
                self.log.info("Finished backtest data for {}", finished_pairs)

            await self._process_market_data()

            if config['backtest_refresh_pairs']:
                await self._refresh_backtest_pairs()
                await self.trader.sync_pairs()
                await self.detector.sync_pairs()

            await self._refresh_backtest_services()
            await self._process_trading()
            await check_follow_up_snapshots()

        await check_remaining_follow_up_snapshots()

    async def _update_backtest_rollover(self):
        """
        Update backtest rollover time and dependent data.

        Re - synchronizes the time prefix if the rollover time changes. Restores the trade and detection statistics for
        the new day, since backtesting starts in the past and will add to previous backtesting statistics.
        """

        backtest_time = self.market.close_times[config['base_pairs'][0]][-1]
        time_prefix = common.get_rollover_time_str(backtest_time)

        if self.time_prefix != time_prefix:
            await self._sync_time_prefix(time_prefix)

            self.trader.restore_attr('trade_stats', max_depth=2, filter_items=self.market.pairs,
                                     filter_keys=[self.time_prefix])
            self.detector.restore_attr('detection_stats', max_depth=2, filter_items=self.market.pairs,
                                       filter_keys=[self.time_prefix])

            if not config['backtest_multicore']:
                filter_items = [base_currency for base_currency in config['min_base_volumes']] + ['global']
                self.trader.restore_attr('trade_stats', max_depth=2, filter_items=filter_items,
                                         filter_keys=[self.time_prefix])

    async def _process_backtest_tick(self, pairs: Sequence[str]):
        """
        Process one tick for a list of pairs for backtesting.

        This also advances the backtest data for each pair ahead by one tick.

        Arguments:
            pairs: The list of currency pairs to process.

        Returns:
            list(str): The currency pairs which have no remaining backtest data.
        """

        finished_pairs = []

        for pair in pairs:
            if not self.backtest_close_values[pair]:
                finished_pairs.append(pair)
                del self.backtest_close_times[pair]
                del self.backtest_close_values[pair]
                del self.backtest_base_volumes[pair]
                del self.backtest_prev_day_values[pair]
                continue

            await self._advance_backtest_tick(pair)

            if pair in config['base_pairs']:
                await self.market.update_base_rate(pair)

        return finished_pairs

    async def _advance_backtest_tick(self, pair: str):
        """
        Advance the backtest data ahead by one tick for a pair, simulating the passing of real time.

        Arguments:
            pair: The currency pair eg. 'BTC-ETH'.
        """

        next_value = self.backtest_close_values[pair].pop(0)
        next_time = self.backtest_close_times[pair].pop(0)

        if next_value is not None:
            self.market.close_values[pair].append(next_value)
            self.market.close_times[pair].append(next_time)

            truncate = len(self.market.close_values[pair]) - self.market.min_tick_length
            if truncate > 60:
                del self.market.close_values[pair][:truncate]
                del self.market.close_times[pair][:truncate]

        if pair in self.market.base_24hr_volumes and pair in self.market.prev_day_values:
            next_volume = self.backtest_base_volumes[pair].pop(0)
            next_prev_day_value = self.backtest_prev_day_values[pair].pop(0)

            if next_volume is not None:
                self.market.base_24hr_volumes[pair][0].append(next_volume)
                self.market.prev_day_values[pair].append(next_prev_day_value)

                truncate = len(self.market.base_24hr_volumes[pair][0]) - self.market.min_tick_length
                if truncate > 60:
                    del self.market.base_24hr_volumes[pair][0][:truncate]
                    del self.market.prev_day_values[pair][:truncate]

    async def _clean_finished_backtest_pair(self, pair: str):
        """
        Clean data for a completed backtest pair.
        """

        if pair in self.market.pairs:
            self.market.pairs.remove(pair)

        if pair in self.trader.trades:
            del self.trader.trades[pair]

    async def _refresh_backtest_services(self):
        """
        Refresh data for services during one backtest cycle.

        Updates the detector 'newly_added' triggers for any new pairs that were added since last cycle. Refreshes all
        derived market data, detector indicator states and triggers, and outputs reporter charts. Cleans any derived
        market data and trader data for pairs that have been dropped since last cycle.
        """

        new_pairs = [
            pair for pair in self.market.pairs
            if pair not in self.market.adjusted_close_values
        ]

        for pair in self.market.pairs:
            self.detector.pair_states[pair]['newly_added'] = pair in new_pairs

        trade_base_pairs, non_base_pairs = await self._split_trade_base_pairs(new_pairs)

        for pair in trade_base_pairs:
            await self.market.refresh_derived_data(pair)
            await self.detector.update_indicator_states(pair)
            await self.detector.update_detection_triggers(pair)
            await self._output_charts(pair)

        for pair in non_base_pairs:
            await self.market.refresh_derived_data(pair)
            await self.detector.update_indicator_states(pair)
            await self.detector.update_detection_triggers(pair)
            await self._output_charts(pair)

        active_pairs = self.market.pairs + self.market.extra_base_pairs
        await self._clean_derived_data(keep_pairs=active_pairs)
        await self._clean_trades(keep_pairs=self.market.pairs)

    async def _refresh_pairs_task(self):
        """
        Refresh the list of watched currency pairs on an interval.

        The pairs refresh will align itself with half the tick interval, so as to occur in-between tick updates.
        This coroutine is a task which runs continuously until explicitly cancelled or a user interrupt occurs.
        Iterates after the delay specified in: data: `config['pairs_refresh_secs']`.
        """

        while not interrupt.is_set():
            if self.first_refresh_completed.is_set():
                await self._wait_for_interval(config['tick_interval_secs'] / 2, 'Refresh pairs task')

            await self.market.acquire_data_lock('Refresh pairs task')
            await self.market.refresh_pairs()
            await self.trader.sync_pairs()
            await self.detector.sync_pairs()
            self.market.data_lock.release()

            self.pairs_refreshed.set()
            self.log.info('Refreshed list of currency pairs.')
            await asyncio.sleep(config['pairs_refresh_secs'])
            self.data_refreshed.clear()

    async def _wait_for_pairs_refresh(self, waiter: str):
        """
        Wait on the: attr: `pairs_refreshed` event and print a debug message if it's not already set.

        Arguments:
            waiter: The name of the waiting coroutine, used for disambiguation in logging.
        """

        if not self.pairs_refreshed.is_set():
            self.log.debug('{}: waiting for currency pair refresh.', waiter)
            await self.pairs_refreshed.wait()

    async def _wait_for_data_refresh(self, waiter: str):
        """
        Wait on the: attr: `data_refreshed` event and print a debug message if it's not already set.

        Arguments:
            waiter: The name of the waiting coroutine, used for disambiguation in logging.
        """

        if not self.data_refreshed.is_set():
            self.log.debug('{}: waiting for market data refresh.', waiter)
            await self.data_refreshed.wait()

    async def _refresh_data_task(self):
        """
        Refresh data for new currency pairs after each pairs refresh.

        Refreshes tick data, moving averages, detection triggers, and charts. This coroutine is a task which runs
        continuously until explicitly cancelled or a user interrupt occurs.
        """

        while not interrupt.is_set():
            await self._wait_for_pairs_refresh('Refresh data task')
            await self.market.acquire_data_lock('Refresh data task')
            await self._clean_untracked_data()

            new_pairs = await self._get_new_pairs()
            self.log.debug("Got new pairs: {}", new_pairs)

            for pair in self.market.pairs:
                is_new = pair in new_pairs
                if self.first_refresh_completed.is_set():
                    self.detector.pair_states[pair]['newly_added'] = is_new
                else:
                    self.detector.pair_states[pair]['startup_added'] = is_new

            trade_base_pairs, non_base_pairs = await self._split_trade_base_pairs(new_pairs)

            futures = await self._start_tick_data_refresh(trade_base_pairs)
            for result in asyncio.as_completed(futures):
                if interrupt.is_set(): break
                await self._init_market_data(await result)

            futures = await self._start_tick_data_refresh(non_base_pairs)
            for result in asyncio.as_completed(futures):
                if interrupt.is_set(): break
                await self._init_market_data(await result)

            self.market.data_lock.release()
            self.first_refresh_completed.set()
            self.pairs_refreshed.clear()
            self.data_refreshed.set()

    async def _split_trade_base_pairs(self, pairs: Sequence[str]) -> Tuple[Set[str], Set[str]]:
        """
        Split a list of pairs into trade-base and normal pairs.
        """

        trade_base_pairs = {pair for pair in pairs if common.get_pair_split(pair)[0] == config['trade_base']}
        non_base_pairs = set(pairs) - trade_base_pairs
        return (trade_base_pairs, non_base_pairs)

    async def _clean_untracked_data(self):
        """
        Clean any stale data from services that is no longer required after a refresh.

        As monitoring is intended to run indefinitely, this ensures unbounded growth does not occur.
        """

        current_pairs = self.market.pairs + self.market.extra_base_pairs
        await self._clean_tick_data(keep_pairs=current_pairs)
        await self._clean_derived_data(keep_pairs=current_pairs)
        await self._clean_trades(keep_pairs=self.market.pairs)

    async def _clean_tick_data(self, keep_pairs: Sequence[str]):
        """
        Clean any tick data for pairs not in the list of pairs.

        Arguments:
            keep_pairs: Pairs whose data should be retained.
        """

        remove_pairs = []

        for pair in self.market.close_times:
            if pair not in keep_pairs:
                remove_pairs.append(pair)

        for key in remove_pairs:
            del self.market.close_values[key]
            del self.market.close_values_backup[key]
            del self.market.close_times[key]
            del self.market.close_times_backup[key]
            del self.market.base_24hr_volumes[key]
            del self.market.base_24hr_volumes_backup[key]

    async def _clean_derived_data(self, keep_pairs: Sequence[str]):
        """
        Clean any derived market data for pairs not in the list of pairs.

        Arguments:
            keep_pairs: Pairs whose data should be retained.
        """

        for data_dict in [
                    self.market.adjusted_close_values,
                    self.market.source_close_value_mas,
                    self.market.close_value_mas,
                    self.market.source_close_value_emas,
                    self.market.close_value_emas,
                    self.market.volume_deriv_mas,
        ]:

            remove_pairs = []
            for pair in data_dict:
                if pair not in keep_pairs:
                    remove_pairs.append(pair)
            for key in remove_pairs:
                del data_dict[key]

    async def _clean_trades(self, keep_pairs: Sequence[str]):
        """
        Clean any closed trades for pairs not in the list of pairs.

        Trades for untracked pairs that are still open must still be retained until they close.

        Arguments:
            keep_pairs: Pairs whose data should be retained.
        """

        remove_pairs = []

        for pair in self.trader.trades:
            if pair not in keep_pairs:
                if not self.trader.trades[pair]['open']:
                    remove_pairs.append(pair)

        for pair in remove_pairs:
            del self.trader.trades[pair]
            if pair in config['base_pairs']:
                await self.trader.prepare_trades(pair)

    async def _get_new_pairs(self) -> List[str]:
        """
        Get any new pairs that do not yet have any tick and / or derived data.

        Returns:
            The list of new currency pairs.
        """

        return [
            pair for pair in self.market.pairs + self.market.extra_base_pairs
            if pair not in self.market.adjusted_close_values or pair not in self.market.close_values
        ]

    async def _start_tick_data_refresh(self, pairs: str) -> List[asyncio.Future]:
        """
        Start tick data refresh tasks for the list of currency pairs.

        Arguments:
            pairs: The list of currency pairs to refresh.

        Returns:
            A list of: attr: `asyncio.Future` objects for each refresh task.
        """

        futures = []

        for pair in pairs:
            self.log.info('{} loading initial tick data.', pair)
            futures.append(utils.async_task(self.market.refresh_tick_data(pair), loop=loop, error_cb=self._error_cb))

        return futures

    async def _init_market_data(self, pair: str):
        """
        Initialize market data for a pair, or drop the pair if it cannot be initialized.

        Filters the pair from the market pairs list if no tick data exists for it.

        Arguments:
            pair: The currency pair to initialize eg. 'BTC-ETH'.
        """

        if pair is not None:
            if not self.market.close_values[pair]:
                self.log.warning('{} has no tick values, cannot be monitored.', pair)
                if pair in self.market.pairs:
                    self.market.pairs.remove(pair)
            else:
                await self.market.refresh_derived_data(pair)
                await self._output_charts(pair)

    async def _output_charts(self, pair: str):
        """
        Output charts for the specified pair.

        Outputs the normal simple moving averages chart and optionally any EMA and indicator charts that are enabled.
        """

        if config['enable_charts'] and pair in self.market.close_values and pair in self.market.close_times:
            price_data = self.market.close_value_mas[pair]
            if config['chart_show_close']:
                price_data.update({'C': self.market.adjusted_close_values[pair]})

            volume_data = self.market.volume_deriv_mas[pair]

            if config['enable_bbands']:
                price_data.update(self.market.bollinger_bands[pair])

            await self.reporter.output_chart(pair, price_data, config['charts_path'] + pair)
            await self.reporter.output_chart(pair, volume_data, config['charts_path'] + pair + ' volume')

            if config['ema_windows']:
                await self.reporter.output_chart(pair, self.market.close_value_emas[pair],
                                                 config['charts_path'] + pair + ' EMA')
            if config['enable_rsi']:
                await self.reporter.output_chart(pair, {'RSI': self.market.relative_strength_indexes[pair]},
                                                 config['charts_path'] + pair + ' RSI')

    async def _output_market_charts(self):
        """
        Output charts for all market pairs.
        """

        for pair in self.market.pairs:
            await self._output_charts(pair)

    async def _update_data_task(self):
        """
        Update new data for all currently watched currency pairs on an interval.

        Updates tick data, moving averages, detection triggers, and charts. This coroutine is a task which runs
        continuously until explicitly cancelled or a user interrupt occurs.

        Iterates approximately every: data: `config['tick_interval_secs']` seconds, as any tick updates should align
        themselves on that time interval.
        """

        while not interrupt.is_set():
            await self._wait_for_data_refresh('Update data task')
            await self._wait_for_interval(config['tick_interval_secs'], 'Update data task')
            await self._wait_for_data_refresh('Update data task')
            await self.market.acquire_data_lock('Update data task')

            pairs = self.market.pairs + self.market.extra_base_pairs

            futures = [
                utils.async_task(self.market.update_tick_data(pair), loop=loop, error_cb=self._error_cb)
                for pair in pairs
            ]

            for result in asyncio.as_completed(futures):
                pair = await result
                if pair is not None and pair in config['base_pairs']:
                    await self.market.update_base_rate(pair)

            await self._clean_untracked_data()
            await self._process_market_data()
            await self._output_market_charts()
            await self._ensure_startup_init()
            await self._process_trading()

            for pair in await self.market.check_back_refreshes():
                await self.market.refresh_derived_data(pair)

            gc.collect()

            self.market.data_lock.release()

    async def _wait_for_interval(self, interval: float, waiter: str):
        """
        Sleep the calling coroutine until the start of the next given interval.

        Arguments:
            interval: The interval to wait for, in seconds.
        """

        last_time = self.market.close_times[config['base_pairs'][0]][-1]
        current_time = time.time()
        close_time = current_time - (current_time % interval)
        delta_seconds = int(close_time - last_time)

        if delta_seconds <= 0:
            wait_time = interval - (current_time % interval) - delta_seconds
            self.log.debug("{}: next interval in {} seconds.", waiter, wait_time)
            await asyncio.sleep(wait_time)

    async def _process_market_data(self):
        """
        Process market data for all market pairs.
        """

        pairs = self.market.pairs + self.market.extra_base_pairs
        trade_base_pairs, non_base_pairs = await self._split_trade_base_pairs(pairs)

        for pair in trade_base_pairs:
            if pair in self.market.close_times and self.market.close_times[pair]:
                await self.market.update_derived_data(pair)

        for pair in non_base_pairs:
            if pair in self.market.close_times and self.market.close_times[pair]:
                await self.market.update_derived_data(pair)

    async def _process_trading(self):
        """
        Process trading on all market pairs for the current tick.
        """

        await self.market.update_trade_minimums()
        await self.trader.update_trade_sizes()

        for pair in self.market.pairs:
            if pair in self.market.adjusted_close_values:
                await self.detector.update_detection_triggers(pair)
                await self.detector.update_indicator_states(pair)
                await self.detector.process_detections(pair)
                await self.trader.update_open_trades(pair)

        for base in config['min_base_volumes']:
            await self.trader.balancer.update_remit_orders(base)

        await self.trader.update_trade_stats()

    async def _ensure_startup_init(self):
        """
        Perform startup initialization after all market data has been refreshed and updated.

        Initializes and restores sim balances and detection triggers before any trades or detections are processed.
        """

        if not self.startup_init_completed.is_set():
            self.trader.balancer.restore_attr('sim_balances')
            await self.trader.balancer.init_sim_balances()
            await self.detector.restore_detection_triggers()
            self.startup_init_completed.set()

    async def _update_rollover_task(self):
        """
        Update rollover time and dependent data.

        Re - synchronizes the time prefix if the rollover time changes. This coroutine is a task which runs continuously
        until explicitly cancelled or a user interrupt occurs.
        """

        while not interrupt.is_set():
            await self.market.acquire_data_lock('Update rollover task')
            time_prefix = common.get_rollover_time_str(time.time())

            if self.time_prefix != time_prefix:
                await self._sync_time_prefix(time_prefix)

            self.market.data_lock.release()
            await asyncio.sleep(config['tick_interval_secs'])

    async def _sync_time_prefix(self, time_prefix: str):
        """
        Synchronize time prefix.

        Updates any paths in the global config and syncs any services which are dependent on time prefix.
        """

        self.log.info('Updating time prefix to {}.', time_prefix)
        self.time_prefix = time_prefix

        config['logs_path'] = config['mode_path'] + defaults.LOGS_DIR + time_prefix + '/'
        config['charts_path'] = config['mode_path'] + defaults.CHARTS_DIR + time_prefix + '/'
        config['snapshot_path'] = config['mode_path'] + defaults.SNAPSHOT_DIR + time_prefix + '/'
        config['alert_log'] = config['mode_path'] + defaults.LOGS_DIR + defaults.ALERT_LOG
        config['output_log'] = config['logs_path'] + defaults.OUTPUT_LOG
        config['debug_log'] = config['logs_path'] + defaults.DEBUG_LOG
        config['error_log'] = config['logs_path'] + defaults.ERROR_LOG

        common.create_user_dirs()

        self.log.config(filename=config['output_log'], debug_filename=config['debug_log'],
                        error_filename=config['error_log'])

        await self.trader.sync_time_prefix(time_prefix)
        await self.detector.sync_time_prefix(time_prefix)

    async def _follow_up_snapshots_task(self):
        """
        Check the list of follow - up snapshots on an interval.

        This coroutine is a task which runs continuously until explicitly cancelled, and iterates after a delay
        specified in: data: `config['follow_up_check_secs']`.
        """

        while not interrupt.is_set():
            await self._wait_for_data_refresh('Follow-up snapshots task')
            await self.market.acquire_data_lock('Follow-up snapshots task')
            await self.reporter.check_follow_up_snapshots()
            self.market.data_lock.release()
            await asyncio.sleep(config['follow_up_check_secs'])


def run(backtest=False, backtest_pairs: List[str]=None):
    """
    Run the application.

    Arguments:
        backtest: If true, runs the application in backtest mode.
        backtest_pairs: If backtest = True, the currency pairs to backtest over.
    """

    try:
        loop.run_until_complete(Application().execute(backtest=backtest, backtest_pairs=backtest_pairs))
    except Exception as e:
        print('{}: {}\n{}'.format(type(e).__name__, e, ''.join(traceback.format_tb(e.__traceback__))))
        interrupt.set()


def run_backtest():
    """
    Run the application in backtest mode.

    Handles initial setup for the backtest, including execution in a multiprocess pool if
    :data:`config['backtest_multicore']` is enabled. Certain features are disabled in multicore mode, specifically
    pair changes, global statistics gathering (though aggregates are still available) and balance simulation.
    """

    gc.set_threshold(35000, 500, 500)

    if config['backtest_limit_pairs']:
        pairs = config['backtest_limit_pairs']
    else:
        pairs = [] if not config['backtest_multicore'] else get_backtest_pairs()

    start_time = time.time()

    if config['backtest_multicore']:
        config['backtest_refresh_pairs'] = False
        config['sim_watch_trade_base_pairs'] = False
        config['sim_enable_balances'] = False

        backtest_pool = multiprocessing.Pool(processes=config['backtest_processes'])
        backtest_pool.daemon = True

        if config['backtest_split_map']:
            split_length = len(pairs) // config['backtest_processes'] + 1
            splits = [pairs[index:index + split_length] for index in range(0, len(pairs), split_length)]
            results = [backtest_pool.apply_async(run, [True, pairs]) for pairs in splits]
        else:
            results = [backtest_pool.apply_async(run, [True, [pair]]) for pair in pairs]

        for result in results:
            result.wait()

        backtest_pool.close()
        backtest_pool.join()

    else:
        run(backtest=True, backtest_pairs=pairs)

    print('Backtest of {} minutes completed in {} seconds.'
          .format(config['backtest_window'], time.time() - start_time))


def get_backtest_pairs():
    """
    Get a list of pairs available from the backtest data on disk.

    Returns a list of all pairs for backtesting based on the JSON filenames in the backtest data directory. Will search
    recursively if the data directory contains only subdirectories. Filters out any pairs whose base is not in
    data:`config['min_base_volumes']`
    """

    filenames = glob.glob(config['backtest_data_dir'] + '*.json')
    pairs = []

    if not filenames:
        dirnames = sorted(glob.glob(config['backtest_data_dir'] + '*' + os.sep))
        filenames = glob.glob(dirnames[0] + '*.json')

    for filename in filenames:
        pair = os.path.splitext(os.path.basename(filename))[0]
        base = pair.split('-')[0]
        if base in config['min_base_volumes']:
            pairs.append(pair)

    return pairs


def main():
    """
    Main entry point.
    """

    common.set_default_signal_handler()
    common.init_config_paths()
    common.create_user_dirs()

    if config['enable_backtest']:
        run_backtest()
    else:
        run()


if __name__ == '__main__':
    main()
