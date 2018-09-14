# -*- coding: utf-8 -*-

# Copyright (c) A 2017 Adam M. Rafuse - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited.
# Proprietary and confidential.

"""
Trader service.
"""

__author__ = 'Adam Rafuse <$(echo nqnz.enshfr#tznvy.pbz | tr a-z# n-za-m@)>'
__all__ = ['Trader']

import math
import uuid
import asyncio

from typing import Any, Dict, List

import api
import core
import utils
import common
import common.base
import configuration

config = configuration.config
"""
Global configuration.
"""


class Trader(common.base.Persistable):
    """
    Trader service object.

    Executes and manages trades.
    """

    def __init__(self, api_client: api.Client, market: core.Market, reporter: core.Reporter, time_prefix: str,
                 log=utils.logging.DummyLogger()):

        super().__init__(log=log)

        self.api = api_client
        """
        Bittrex API client.
        """

        self.market = market
        """
        Shared :class:`Market` service.
        """

        self.reporter = reporter
        """
        Shared :class:`Reporter` service.
        """

        self.time_prefix = time_prefix
        """
        Current time prefix, used for separating stat directories by time.
        """

        self.log = utils.logging.ChildLogger(parent=log, scope=self)
        """
        Object logger.
        """

        self.watch_only_pairs: List[str] = []
        """
        The currency pairs to only watch (not open new buy trades on).
        """

        self.pair_states: Dict[str, Any] = {}
        """
        Trader states for each currency pair.
        {
            (str):  Currency pair name eg. 'BTC-ETH'.
            {
                'enable_buy': (bool):    True if buys are enabled for this pair.
                'enable_rebuy': (bool):  True if rebuys are enabled for this pair .
            }
        }
        """

        self.trades = {}
        """
        Tracked open trades for each currency pair.

        ``
        {
            (str): Currency pair name eg. 'BTC-ETH'.
            {
                'last_open_time': (float):  UTC timestamp of the last open trade for this pair.
                'rebuy_count': (int):       Number of consecutive rebuys for this pair; reset on normal buy.
                'open':
                [
                    {
                        'pair': (str):                Currency pair for this trade (denormalized for easy reference).
                        'order_id': (str):            Unique identfier for this trade.
                        'open_value': (float):        Value this trade was opened at.
                        'base_value': (float):        Value of this trade's base currency at opening.
                        'open_time': (float):         UTC timestamp of when this trade was opened.
                        'close_value' (float):        Value this trade was closed at.
                        'close_time' (float):         UTC timestamp of when this trade was closed.
                        'quantity': (float):          Total quantity of this trade.
                        'remaining': (float):         Trade quantity still left to be bought.
                        'filled': (bool):             True if this trade was completely filled (remaining == 0.0)
                        'fees': (float):              Total trading fees incurred (for both buy and sell)
                        'sell_pushes': (int):         Number of sell pushes for this trade.
                        'push_locked': (bool):        True if sell pushes are currently locked for this trade.
                        'soft_sells': list(int):      Unique detection indexes that triggered soft sells for this trade.
                        'hard_sells': list(int):      Unique detection indexes that triggered hard sells for this trade.
                        'rebuy': (bool):              True if this trade is a re-buy on a previously closed trade.
                        'soft_stop': (bool):          True if a soft stop was triggered for this trade.
                        'detection_name': (int):      Index of the detection that triggered this trade.
                        'detection_time': (int):      Time of the detection that triggered this trade.
                        'stop_value': (float)':       Soft stop-loss value for this trade.
                        'soft_target': (float)':      Minimum target value for this trade.
                        'hard_target': (float)':      Minimum target value for this trade.
                    },
                    ... for trade in all open trades
                ]
                'closed':
                [
                    {
                        See 'open'
                    },
                    ... for trade in all closed trades
                ]
            },
            ... for pair in currently and previously tracked pairs
        }
        ``
        """

        self.trade_stats = {self.time_prefix: {}}
        """
        Statistics on trades intended for export.
        ``
        {
            (str): Current time prefix.
            {
                (str): Currency pair name eg. 'BTC-ETH'.
                {
                    'num_open': list(int)       Number of open trades open at once at each buy.
                    'most_open': (int):         Most number of trades open at once.
                    'avg_open': (int):          Average number of trades open at once.
                    'soft_stops': (int):        Total number of stop losses.
                    'total_profit': (float):    Total running profit.
                    'total_loss': (float):      Total running loss.
                    'total_fees': (float):      Total fees incurred.
                    'unfilled': (int):          Number of completely unfilled trades.
                    'unfilled_partial': (int):  Number of partially unfilled trades.
                    'unfilled_value': (float):  Total value of unfilled trades.
                }
                ... for pair in currently and previously tracked pairs

                (str): Base currency name eg. 'BTC'
                {
                    Aggregate of above values for all trades on this base currency.
                }
                ... for base currency in config['min_base_volumes']

                'global':
                {
                    Aggregate of above values for all trades.
                }
            }
        }
        ``
        """

        self.last_trades = {}
        """
        {
            (str): Currency pair name eg. 'BTC-ETH'.
            {
                'soft_stop_sell': {
                    'time': (float):    UTC timestamp in seconds of the last soft stop sell.
                    'value': (float):   Value at the last soft stop sell.
                }
            }
        }
        """

        self.trade_sizes = {}
        """
        Current trade sizes of each detection / trade group.

        {
            (str): Group name eg. 'default': (float):  Trade size
            ...
        }
        """

        self.trade_proceeds = {}
        """
        Running proceeds of open trades for each detection / trade group.

        {
            (str): Group name eg. 'reversal_0': (float):  Running proceeds.
            ...
        }
        """

        self.balancer = core.Balancer(self.api, self.market, self.reporter, self.time_prefix,
                                      self.trade_stats, self.trade_sizes, log=self.log)
        """
        Shared :class:`Balancer` service.
        """

        # Map of methods for trade actions.
        if config['enable_backtest'] or config['trade_simulate']:
            self._trade_methods = {
                'buy': self._buy_sim,
                'sell': self._sell_sim,
                'update': lambda _: asyncio.sleep(0),
            }

        else:
            self._trade_methods = {
                'buy': self._buy_live,
                'sell': self._sell_live,
                'update': self._update_live,
            }

        # Initialize dictionaries.
        self._init_group_dicts()

    def _init_group_dicts(self):
        """
        Add keys to groups dicts for all possible detection groups that can open trades.
        """

        all_groups = set()

        for detection in config['detections'].values():
            if 'action' in detection and detection['action'] == 'buy':
                if 'groups' in detection:
                    for group in detection['groups']:
                        all_groups.add(group)

        for group in all_groups:
            self.trade_sizes[group] = config['trade_min_size']
            self.trade_proceeds[group] = {}

        self.trade_sizes['default'] = config['trade_min_size']
        self.trade_proceeds['default'] = {}

    async def sync_pairs(self):
        """
        Synchronize currency pairs.

        Updates market pairs with those also tracked in open trades. Locally tracks pairs that are only being watched
        for trade management, so as not to open new trades on pairs outside of trading volume thresholds. Prepares any
        instance dictionaries that may require added keys with appropriate defaults.
        """

        self.watch_only_pairs = []

        await self._handle_trader_watch_pairs()
        await self._handle_balancer_watch_pairs()

        for pair in self.market.pairs + self.market.extra_base_pairs:
            await self.prepare_trades(pair)
            await self.prepare_states(pair)
            await self.prepare_last_trades(pair)

        await self.prepare_all_trade_stats()
        await self.balancer.sync_pairs()

    async def _handle_trader_watch_pairs(self):
        """
        Handle any watch pairs for the trader service.

        Sets any trade base pairs or pairs in open trades as watch pairs. Watching trade base pairs in simulation or
        backtest mode is optional as per :attr:`config['sim_watch_trade_base_pairs']`, at the cost of disabling
        certain detections that rely on them such as refill control.
        """

        for pair in self.trades:
            if self.trades[pair]['open']:
                await self._set_watch_pair(pair)

        is_backtest = config['enable_backtest']
        is_simulation = config['trade_simulate']

        if not (is_backtest or is_simulation) or config['sim_watch_trade_base_pairs']:
            for base in config['min_base_volumes']:
                if base != config['trade_base']:
                    pair = '{}-{}'.format(config['trade_base'], base)
                    await self._set_watch_pair(pair)

    async def _handle_balancer_watch_pairs(self):
        """
        Handle any watch pairs for the trader's balancer service.

        Sets any pairs in open remit orders as watch pairs.
        """

        for base in self.balancer.remit_orders:
            if self.balancer.remit_orders[base]:
                pair = '{}-{}'.format(config['trade_base'], base)
                await self._set_watch_pair(pair)

    async def _set_watch_pair(self, pair: str):
        """
        Set a pair as a watch pair.

        Moves or adds the pair to :attr:`market.pairs` if it is not already there, so that market data will be tracked
        for it and enable operations that depend on market data (ie detections). If a pair is not already in
        market pairs it is appended to :attr:`watch_only_pairs` to restrict the trader from opening new buys orders on
        it.

        The purpose of watch pairs is to ensure detections are still tracked for pairs in opened orders, or for pairs
        used for control purposes such as trade base pairs.
        """

        if pair not in self.market.pairs:
            if pair in self.market.extra_base_pairs:
                self.market.extra_base_pairs.remove(pair)

            self.market.pairs.append(pair)
            self.watch_only_pairs.append(pair)
            self.log.info('Setting watch-only pair {}.', pair, stack_depth=1)

    async def sync_time_prefix(self, time_prefix: str):
        """
        Synchronize time prefix.

        Creates new :attr:`trade_stats` on the new prefix and updates balancer prefix.
        """

        self.time_prefix = time_prefix
        self.trade_stats[time_prefix] = {}
        self.balancer.time_prefix = time_prefix
        await self.prepare_all_trade_stats()

    async def prepare_all_trade_stats(self):
        """
        Prepare global trade stats, and stats for all pairs and base currencies.
        """

        for pair in self.market.pairs:
            await self.prepare_trade_stats(pair)

        for base in config['min_base_volumes']:
            await self.prepare_trade_stats(base)

        await self.prepare_trade_stats('global')

    async def prepare_states(self, pair: str):
        """
        Prepare states for the specified pair.

        Ensures that the necessary keys exist in :attr:`states` before any operations are performed on them.

        Arguments:
            pair:  Name of the currency pair eg 'BTC-ETH'.
        """

        if pair not in self.pair_states:
            self.pair_states[pair] = {
                'enable_buy': True,
                'enable_rebuy': True
            }

    async def prepare_trades(self, pair: str):
        """
        Prepare trades for the specified pair.

        Ensures that the necessary keys exist in :attr:`trades` before any operations are performed on them.

        Arguments:
            pair:  Name of the currency pair eg 'BTC-ETH'.
        """

        if pair not in self.trades:
            self.trades[pair] = {
                'last_open_time': 0.0,
                'rebuy_count': 0,
                'open': [],
                'closed': []
            }

    async def prepare_trade_stats(self, key: str):
        """
        Prepare trade stats for the specified pair.

        Ensures that the necessary keys exist in :attr:`trade_stats` before any operations are performed on them.

        Arguments:
            key:  Trade stats key, either a pair or base currency name or 'global'.
        """

        if key not in self.trade_stats[self.time_prefix]:
            self.trade_stats[self.time_prefix][key] = {
                'num_open': [],
                'most_open': 0,
                'buys': 0,
                'rebuys': 0,
                'sells': 0,
                'collect_sells': 0,
                'soft_stop_sells': 0,
                'total_profit': 0.0,
                'total_loss': 0.0,
                'total_fees': 0.0,
                'unfilled': 0,
                'unfilled_partial': 0,
                'unfilled_quantity': 0.0,
                'unfilled_value': 0.0,
                'failed': 0,
                'balancer_refills': 0,
                'balancer_remits': 0,
                'balancer_stop_losses': 0,
                'balancer_profit': 0.0,
                'balancer_loss': 0.0,
                'balancer_fees': 0.0,
                'balancer_unfilled': 0,
                'balancer_failed': 0,
            }

    async def prepare_last_trades(self, pair: str):
        """
        """

        if pair not in self.last_trades:
            self.last_trades[pair] = {
                'most_recent': None,
                'buy': {
                    'value': None,
                    'time': None
                },
                'sell_low': {
                    'value': None,
                    'time': None
                },
                'sell_high': {
                    'value': None,
                    'time': None
                },
                'soft_stop_sell_low': {
                    'value': None,
                    'time': None
                },
                'soft_stop_sell_high': {
                    'value': None,
                    'time': None
                },
                'collect_sell_low': {
                    'value': None,
                    'time': None
                },
                'collect_sell_high': {
                    'value': None,
                    'time': None
                }
            }

    async def update_open_trades(self, pair: str):
        """
        Update open trades for a pair.

        Checks trades for stop loss and deferred sell triggers, and processes them as necessary.

        Arguments:
            pair:  The currency pair, eg. BTC-ETH.
        """

        remove_indexes = []

        for index, trade in enumerate(self.trades[pair]['open']):
            if await self._handle_deferred_push(trade):
                remove_indexes.append(index)
            elif await self._handle_deferred_sell(trade):
                remove_indexes.append(index)
            elif await self._handle_stop_loss(trade):
                remove_indexes.append(index)

            if not trade['filled']:
                await self._trade_methods['update'](trade)

        for index in reversed(remove_indexes):
            del self.trades[pair]['open'][index]

        self.save_attr('trade_stats', max_depth=2, filter_items=[pair], filter_keys=[self.time_prefix])
        self.save_attr('last_trades', max_depth=1, filter_items=[pair])
        self.save_attr('trades', max_depth=1, filter_items=[pair])

    async def _handle_deferred_push(self, trade: Dict[str, Any]) -> bool:
        """
        Handle any deferred push sell actions for an open trade.

        If a sell occurs the trade is copied to :attr:`trades[pair]['closed']`.

        Arguments:
            trade:  The trade to check for a deferred push sell.

        Returns:
            (bool):  True if a sell occurred, otherwise false.
        """

        pair = trade['pair']
        push_max = trade['push_max']

        adjusted_value = self.market.adjusted_close_values[pair][-1]
        target_value = 0.0 if trade['rebuy'] else trade['push_target']

        if trade['rebuy']:
            push_max -= config['trade_rebuy_push_penalty']

        if trade['deferred_push'] and trade['sell_pushes'] >= push_max and adjusted_value >= target_value:
            coro = self._trade_methods['sell'](trade, 'DEFERRED PUSH SELL')
            utils.async_task(coro, loop=common.loop)
            self.trades[pair]['closed'].append(trade)
            return True

        return False

    async def _handle_deferred_sell(self, trade: Dict[str, Any]) -> bool:
        """
        Handle any deferred sell actions for an open trade.

        If a sell occurs the list of closed trades for the pair is cleared to prevent re-buys.

        Arguments:
            trade:  The trade to check for a deferred sell.

        Returns:
            (bool):  True if a sell occurred, otherwise false.
        """

        pair = trade['pair']
        adjusted_value = self.market.adjusted_close_values[pair][-1]

        if trade['deferred_soft'] and trade['soft_sells'] and adjusted_value >= trade['soft_target']:
            coro = self._trade_methods['sell'](trade, 'DEFERRED SOFT SELL')
            utils.async_task(coro, loop=common.loop)
            self.trades[pair]['closed'] = []
            return True

        if trade['deferred_hard'] and trade['hard_sells'] and adjusted_value >= trade['hard_target']:
            coro = self._trade_methods['sell'](trade, 'DEFERRED HARD SELL')
            utils.async_task(coro, loop=common.loop)
            self.trades[pair]['closed'] = []
            return True

        return False

    async def _handle_stop_loss(self, trade: Dict[str, Any]) -> bool:
        """
        Handle any stop loss sell actions for an open trade.

        Arguments:
            trade:  The trade to check for a stop loss sell.

        Returns:
            (bool):  True if a sell occurred, otherwise false.
        """

        pair = trade['pair']
        current_value = self.market.adjusted_close_values[pair][-1]

        if current_value < trade['cutoff_value']:
            stop_percent = config['trade_dynamic_stop_percent'] * trade['soft_stops']
            trade['stop_value'] *= (1.0 + stop_percent)
            if trade['stop_value'] > trade['check_value']:
                trade['stop_value'] = trade['check_value']

        elif current_value < trade['check_value']:
            trade['stop_value'] *= (1.0 + config['trade_dynamic_stop_percent'])
            if trade['stop_value'] > trade['check_value']:
                trade['stop_value'] = trade['check_value']

        if current_value <= trade['stop_value']:
            coro = self._trade_methods['sell'](trade, 'SOFT STOP SELL', 'soft_stop')
            utils.async_task(coro, loop=common.loop)
            self.trades[pair]['closed'] = []
            return True

        return False

    async def buy(self, pair: str, detection_name: str, trigger_data: Dict[str, Any]):
        """
        Open a trade with a new buy order.

        Arguments:
            pair:            The currency pair, eg. BTC-ETH.
            detection_name:  Name of the detection that triggered this trade.
            trigger_data:    Aggregate trigger data from the detection.
        """

        params = core.Detector.get_detection_params(detection_name, {
            'rebuy': True
        })

        if pair in self.watch_only_pairs:
            self.log.info("{} Cannot open buy trade on watch-only pair.", pair)
            await self.reporter.send_alert(pair, trigger_data, detection_name, prefix='WATCH SKIP BUY')
            return

        if not self.pair_states[pair]['enable_buy']:
            self.log.info("{} Cannot open buy trade with buys disabled.", pair)
            await self.reporter.send_alert(pair, trigger_data, detection_name, prefix='DISABLED SKIP BUY')
            return

        if not self.balancer.states[pair.split('-')[0]]['enable_refill']:
            self.log.info("{} Cannot open buy trade with refills disabled.", pair)
            await self.reporter.send_alert(pair, trigger_data, detection_name, prefix='REFILL SKIP BUY')
            return

        new_trade = await self._trade_methods['buy'](pair, 'BUY', detection_name, trigger_data)
        if new_trade is not None:
            self.trades[pair]['open'].append(new_trade)
            await self._track_num_open_trades(pair)
            self.save_attr('trades', max_depth=1, filter_items=[pair])
            self.save_attr('trade_stats', max_depth=2, filter_items=[pair], filter_keys=[self.time_prefix])

        self.pair_states[pair]['enable_rebuy'] = params['rebuy']

    async def hold(self, pair: str, detection_name: str, trigger_data: dict):
        """
        Register a trade hold for a pair.

        A hold decrements the sell push count for a trade by one, keeping the trade open longer before a push sell
        occurs.

        Arguments:
            pair:            The currency pair, eg. BTC-ETH.
            detection_name:  Name of the detection that triggered this trade.
            trigger_data:    Aggregate trigger data from the detection.
        """

        current_value = self.market.adjusted_close_values[pair][-1]
        metadata = trigger_data.copy()

        for trade in self.trades[pair]['open']:
            trade['sell_pushes'] -= 1
            if trade['sell_pushes'] < 0: trade['sell_pushes'] = 0

            followed_time_str = common.utctime_str(trade['detection_time'], config['time_format'])
            followed_name = trade['detection_name']
            followed_prefix = 'RE-BUY ' if trade['rebuy'] else 'BUY '
            followed_norm_value = trade['open_value'] / current_value
            followed_delta = 1.0 - followed_norm_value

            metadata['followed'].append({
                'snapshot': '{} {} {}'.format(pair, followed_prefix + followed_name, followed_time_str),
                'name': followed_prefix + followed_name,
                'time': trade['detection_time'],
                'delta': followed_delta
            })

            alert_prefix = 'HOLD ' + trade['order_id']
            await self.reporter.send_alert(pair, metadata, detection_name, prefix=alert_prefix)

        base, quote, _ = common.get_pair_elements(pair)
        if base == config['trade_base'] and quote in config['min_base_volumes']:
            await self.balancer.remit_hold(quote)

        self.save_attr('trades', max_depth=1, filter_items=[pair])

    async def rebuy(self, pair: str, detection_name: str, trigger_data: dict):
        """
        Open a trade with a re-buy for a pair.

        A re-buy will only occur if a previously closed trade exists for a pair.

        Arguments:
            pair:            The currency pair, eg. BTC-ETH.
            detection_name:  Name of the detection that triggered this trade.
            trigger_data:    Aggregate trigger data from the detection.
        """

        params = core.Detector.get_detection_params(detection_name, {
            'rebuy_max': config['trade_rebuy_max'],
        })

        if not self.trades[pair]['closed']:
            self.log.info('{} no previous closed trades for re-buy.', pair)
            return

        if not self.pair_states[pair]['enable_rebuy']:
            self.log.info('{} last buy detection type disallows re-buys.', pair)
            return

        if not self.pair_states[pair]['enable_buy']:
            self.log.info("{} Cannot open buy trade with buys disabled.", pair)
            await self.reporter.send_alert(pair, trigger_data, detection_name, prefix='DISABLED SKIP BUY')
            return

        if pair in self.watch_only_pairs:
            self.log.info("{} Cannot open buy order on watch-only pair.", pair)
            await self.reporter.send_alert(pair, trigger_data, detection_name, prefix='WATCH SKIP RE-BUY')
            return

        if not self.balancer.states[pair.split('-')[0]]['enable_refill']:
            self.log.info("{} Cannot open re-buy trade with refills disabled.", pair)
            await self.reporter.send_alert(pair, trigger_data, detection_name, prefix='REFILL SKIP RE-BUY')
            return

        if self.trades[pair]['rebuy_count'] >= params['rebuy_max']:
            self.log.info("{} Cannot re-buy more than {} consecutive times.", pair, self.trades[pair]['rebuy_count'])
            await self.reporter.send_alert(pair, trigger_data, detection_name, prefix='CONSECUTIVE SKIP RE-BUY')
            return

        new_trade = await self._trade_methods['buy'](pair, 'RE-BUY', detection_name, trigger_data, rebuy=True)
        if new_trade is not None:
            self.trades[pair]['open'].append(new_trade)
            await self._track_num_open_trades(pair)
            self.save_attr('trades', max_depth=1, filter_items=[pair])
            self.save_attr('trade_stats', max_depth=2, filter_items=[pair], filter_keys=[self.time_prefix])

    async def sell_push(self, pair: str, detection_name: str, trigger_data: dict):
        """
        Register a sell push for a pair.

        Any open trades will close with a market sell if the sell push threshold exceeds
        :attr:`config['trade_push_max']` and the soft sell target value has been met (ie. a 'push sell'). If sell
        occurs the trade is appended to :attr:`trades[pair]['closed']`.

        Arguments:
            pair:            The currency pair, eg. BTC-ETH.
            detection_name:  Name of the detection that triggered this trade.
            trigger_data:    Aggregate trigger data from the detection.
        """

        params = core.Detector.get_detection_params(detection_name, {
            'apply': None,
            'ignore': None,
        })

        current_value = self.market.adjusted_close_values[pair][-1]
        remove_indexes = []

        for index, trade in enumerate(self.trades[pair]['open']):
            if not self._is_applied(trade, params) or self._is_ignored(trade, params):
                continue

            push_max = trade['push_max']
            target_value = 0.0 if trade['rebuy'] else trade['push_target']
            trade['last_push_value'] = current_value

            if trade['rebuy']:
                push_max -= config['trade_rebuy_push_penalty']

            if current_value >= target_value or trade['deferred_push']:
                trade['sell_pushes'] += 1
                if trade['sell_pushes'] >= push_max:  # and not trade['push_locked']:
                    coro = self._trade_methods['sell'](trade, 'PUSH SELL', None, detection_name, trigger_data)
                    utils.async_task(coro, loop=common.loop)
                    self.trades[pair]['closed'].append(trade)
                    remove_indexes.append(index)

            check_value = current_value * (1.0 - trade['stop_check'])
            cutoff_value = current_value * (1.0 - trade['stop_cutoff'])
            stop_value = current_value * (1.0 - trade['stop_percent'])

            if check_value > trade['check_value']:
                trade['check_value'] = check_value

            if cutoff_value > trade['cutoff_value']:
                trade['cutoff_value'] = cutoff_value

            if stop_value > trade['stop_value']:
                if stop_value > trade['check_value']:
                    trade['stop_value'] = trade['check_value']
                else:
                    trade['stop_value'] = stop_value

            soft_factor = trade['sell_pushes'] + len(trade['soft_sells'])
            hard_factor = trade['sell_pushes'] + len(trade['hard_sells'])
            trade['push_target'] *= (1.0 - config['trade_dynamic_sell_percent'] * trade['sell_pushes'])
            trade['soft_target'] *= (1.0 - config['trade_dynamic_sell_percent'] * soft_factor)
            trade['hard_target'] *= (1.0 - config['trade_dynamic_sell_percent'] * hard_factor)

        for index in reversed(remove_indexes):
            del self.trades[pair]['open'][index]

        if remove_indexes:
            await self._track_num_open_trades(pair)

        base, quote, _ = common.get_pair_elements(pair)
        if base == config['trade_base'] and quote in config['min_base_volumes']:
            await self.balancer.remit_sell_push(quote)

        self.save_attr('trades', max_depth=1, filter_items=[pair])
        self.save_attr('trade_stats', max_depth=2, filter_items=[pair], filter_keys=[self.time_prefix])

    async def push_release(self, pair: str, detection_name: str, _: dict):
        """
        Register a sell push release for a pair.

        A push release allows a push sell to occur once other conditions are met. New orders are by default 'locked'
        until a release event occurs (usually a downward move in volume). This allows for trend riding when volumes
        rise continually for extended periods of time.

        Arguments:
            pair:            The currency pair, eg. BTC-ETH.
            detection_name:  Name of the detection that triggered this trade.
            trigger_data:    Aggregate trigger data from the detection.
        """

        params = core.Detector.get_detection_params(detection_name, {
            'apply': None,
            'ignore': None
        })

        for trade in self.trades[pair]['open']:
            if not self._is_applied(trade, params) or self._is_ignored(trade, params):
                continue

            trade['push_locked'] = False

    async def soft_sell(self, pair: str, detection_name: str, trigger_data: dict):
        """
        Register a "soft" sell for a pair.

        Any open trades will close with a market sell if the soft sell target value has been met.

        Arguments:
            pair:            The currency pair, eg. BTC-ETH.
            detection_name:  Name of the detection that triggered this trade.
            trigger_data:    Aggregate trigger data from the detection.
        """

        params = core.Detector.get_detection_params(detection_name, {
            'apply': None,
            'ignore': None
        })

        remove_indexes = []

        for index, trade in enumerate(self.trades[pair]['open']):
            if not self._is_applied(trade, params) or self._is_ignored(trade, params):
                continue

            adjusted_value = self.market.adjusted_close_values[pair][-1]
            target_value = 0.0 if trade['rebuy'] else trade['soft_target']
            trade['soft_sells'].append(detection_name)

            if adjusted_value >= target_value:
                if trade['soft_sells'].count(detection_name) >= trade['soft_max']:
                    coro = self._trade_methods['sell'](trade, 'SOFT SELL', None, detection_name, trigger_data)
                    utils.async_task(coro, loop=common.loop)
                    self.trades[pair]['closed'] = []
                    remove_indexes.append(index)

            check_value = adjusted_value * (1.0 - trade['stop_check'])
            cutoff_value = adjusted_value * (1.0 - trade['stop_cutoff'])
            stop_value = adjusted_value * (1.0 - trade['stop_percent'])

            if check_value > trade['check_value']:
                trade['check_value'] = check_value

            if cutoff_value > trade['cutoff_value']:
                trade['cutoff_value'] = cutoff_value

            if stop_value > trade['stop_value']:
                if stop_value > trade['check_value']:
                    trade['stop_value'] = trade['check_value']
                else:
                    trade['stop_value'] = stop_value

            soft_factor = trade['sell_pushes'] + len(trade['soft_sells'])
            hard_factor = trade['sell_pushes'] + len(trade['hard_sells'])
            trade['soft_target'] *= (1.0 - config['trade_dynamic_sell_percent'] * soft_factor)
            trade['hard_target'] *= (1.0 - config['trade_dynamic_sell_percent'] * hard_factor)

        for index in reversed(remove_indexes):
            del self.trades[pair]['open'][index]
        if remove_indexes:
            await self._track_num_open_trades(pair)

        base, quote, _ = common.get_pair_elements(pair)
        if base == config['trade_base'] and quote in config['min_base_volumes']:
            await self.balancer.remit_soft_sell(quote, detection_name)

        self.save_attr('trades', max_depth=1, filter_items=[pair])
        self.save_attr('trade_stats', max_depth=2, filter_items=[pair], filter_keys=[self.time_prefix])

    async def hard_sell(self, pair: str, detection_name: str, trigger_data: dict):
        """
        Register a "hard" sell for a pair.

        Any open trades will close with a market sell if the hard sell target value has been met. If a sell occurs the
        list of closed trades for the pair is cleared.

        Arguments:
            pair:            The currency pair, eg. BTC-ETH.
            detection_name:  Name of the detection that triggered this trade.
            trigger_data:    Aggregate trigger data from the detection.
        """

        params = core.Detector.get_detection_params(detection_name, {
            'apply': None,
            'ignore': None
        })

        remove_indexes = []

        for index, trade in enumerate(self.trades[pair]['open']):
            if not self._is_applied(trade, params) or self._is_ignored(trade, params):
                continue

            adjusted_value = self.market.adjusted_close_values[pair][-1]
            target_value = 0.0 if trade['rebuy'] else trade['hard_target']
            trade['hard_sells'].append(detection_name)

            if adjusted_value >= target_value:
                coro = self._trade_methods['sell'](trade, 'HARD SELL', None, detection_name, trigger_data)
                utils.async_task(coro, loop=common.loop)
                self.trades[pair]['closed'] = []
                remove_indexes.append(index)

            check_value = adjusted_value * (1.0 - trade['stop_check'])
            cutoff_value = adjusted_value * (1.0 - trade['stop_cutoff'])
            stop_value = adjusted_value * (1.0 - trade['stop_percent'])

            if check_value > trade['check_value']:
                trade['check_value'] = check_value

            if cutoff_value > trade['cutoff_value']:
                trade['cutoff_value'] = cutoff_value

            if stop_value > trade['stop_value']:
                if stop_value > trade['check_value']:
                    trade['stop_value'] = trade['check_value']
                else:
                    trade['stop_value'] = stop_value

            hard_factor = trade['sell_pushes'] + len(trade['hard_sells'])
            trade['hard_target'] *= (1.0 - config['trade_dynamic_sell_percent'] * hard_factor)

        for index in reversed(remove_indexes):
            del self.trades[pair]['open'][index]

        if remove_indexes:
            await self._track_num_open_trades(pair)

        base, quote, _ = common.get_pair_elements(pair)
        if base == config['trade_base'] and quote in config['min_base_volumes']:
            await self.balancer.remit_hard_sell(quote, detection_name)

        self.save_attr('trades', max_depth=1, filter_items=[pair])
        self.save_attr('trade_stats', max_depth=2, filter_items=[pair], filter_keys=[self.time_prefix])

    async def hard_stop(self, pair: str, detection_name: str, trigger_data: dict):
        """
        Register a hard stop for a pair.

        Any open trades will close with a market sell if the number of occurring hard stops for a given detection
        index hits the defined threshold value.

        Arguments:
            pair:            The currency pair, eg. BTC-ETH.
            detection_name:  Name of the detection that triggered this trade.
            trigger_data:    Aggregate trigger data from the detection.
        """

        params = core.Detector.get_detection_params(detection_name, {
            'threshold': config['trade_hard_stop_threshold'],
            'apply': None,
            'ignore': None
        })

        remove_indexes = []

        for index, trade in enumerate(self.trades[pair]['open']):
            if not self._is_applied(trade, params) or self._is_ignored(trade, params):
                continue

            trade['hard_stops'].append(detection_name)
            if trade['hard_stops'].count(detection_name) >= params['threshold']:
                coro = self._trade_methods['sell'](trade, 'HARD STOP SELL', None, detection_name, trigger_data)
                utils.async_task(coro, loop=common.loop)
                self.trades[pair]['closed'] = []
                remove_indexes.append(index)

        for index in reversed(remove_indexes):
            del self.trades[pair]['open'][index]
        if remove_indexes:
            await self._track_num_open_trades(pair)

        self.save_attr('trades', max_depth=1, filter_items=[pair])
        self.save_attr('trade_stats', max_depth=2, filter_items=[pair], filter_keys=[self.time_prefix])

    async def dump_sell(self, pair: str, detection_name: str, trigger_data: dict):
        """
        Register a "dump" aka "oh shit" sell for a pair.

        Any open trades will close with a market sell immediately and the list of closed trades for the pair is
        cleared.

        Arguments:
            pair:            The currency pair, eg. BTC-ETH.
            detection_name:  Name of the detection that triggered this action.
            trigger_data:    Aggregate trigger data from the detection.
        """

        futures = await self._dump_trades(pair, detection_name, trigger_data)
        for result in asyncio.as_completed(futures):
            self.log.debug("Completed trade sell order {}.", await result)

        self.trades[pair]['closed'] = []

        base, quote, _ = common.get_pair_elements(pair)
        if base == config['trade_base'] and quote in config['min_base_volumes']:
            await self.balancer.remit_dump_sell(quote)

        self.save_attr('trades', max_depth=1, filter_items=[pair])
        self.save_attr('trade_stats', max_depth=2, filter_items=[pair], filter_keys=[self.time_prefix])

    async def _dump_trades(self, pair: str, detection_name: str, trigger_data: dict):
        """
        Dump all trades for a currency pair.

        Any open trades for the pair will close with a market sell immediately.
        TODO: Add retry for failed sells.

        Arguments:
            pair:            The currency pair, eg. BTC-ETH.
            detection_name:  Name of the detection that triggered this action.
            trigger_data:    Aggregate trigger data from the detection.
        """

        futures = []

        for trade in self.trades[pair]['open']:
            future = await self._trade_methods['sell'](trade, 'DUMP SELL', None, detection_name, trigger_data)
            futures.append(future)

        if futures:
            await self._track_num_open_trades(pair)

        self.trades[pair]['open'] = []
        return futures

    async def soft_stop(self, pair: str, detection_name: str, trigger_data: dict):
        """
        Register a "soft" stop for a pair.

        A soft stop enables a stop loss sell to occur for any open trades if the pair's value goes below the
        soft stop value.

        Arguments:
            pair:            The currency pair, eg. BTC-ETH.
            detection_name:  Name of the detection that triggered the soft stop.
            trigger_data:    Aggregate trigger data for the detection.
        """

        params = core.Detector.get_detection_params(detection_name, {
            'weight': 1.0,
            'apply': None,
            'ignore': None
        })

        current_value = self.market.adjusted_close_values[pair][-1]
        metadata = trigger_data.copy()

        for trade in self.trades[pair]['open']:
            if not self._is_applied(trade, params) or self._is_ignored(trade, params):
                continue

            trade['soft_stops'] += 1

            stop_percent = config['trade_dynamic_stop_percent'] * trade['soft_stops'] * params['weight']
            trade['stop_value'] *= (1.0 + stop_percent)
            if trade['stop_value'] > trade['check_value']:
                trade['stop_value'] = trade['check_value']

            followed_time_str = common.utctime_str(trade['detection_time'], config['time_format'])
            followed_name = trade['detection_name']
            followed_prefix = 'RE-BUY ' if trade['rebuy'] else 'BUY '
            followed_norm_value = trade['open_value'] / current_value
            followed_delta = 1.0 - followed_norm_value

            metadata['followed'].append({
                'snapshot': '{} {} {}'.format(pair, followed_prefix + followed_name, followed_time_str),
                'name': followed_prefix + followed_name,
                'time': trade['detection_time'],
                'delta': followed_delta
            })

            alert_prefix = 'SOFT STOP ' + trade['order_id']
            await self.reporter.send_alert(pair, metadata, detection_name, prefix=alert_prefix)

        base, quote, _ = common.get_pair_elements(pair)

        if common.is_trade_base(base, quote):
            await self.balancer.remit_soft_stop(quote, detection_name)

        self.save_attr('trades', max_depth=1, filter_items=[pair])

    async def stop_hold(self, pair: str, detection_name: str, trigger_data: dict):
        """
        Register a stop hold for a pair.

        Arguments:
            pair:            The currency pair, eg. BTC-ETH.
            detection_name:  Name of the detection that triggered this trade.
            trigger_data:    Aggregate trigger data for the detection.
        """

        params = core.Detector.get_detection_params(detection_name, {
            'weight': 1.0,
            'apply': None,
            'ignore': None
        })

        current_value = self.market.adjusted_close_values[pair][-1]
        metadata = trigger_data.copy()

        for trade in self.trades[pair]['open']:
            if not self._is_applied(trade, params) or self._is_ignored(trade, params):
                continue

            if trade['soft_stops'] > 0: trade['soft_stops'] -= 1

            stop_percent = config['trade_dynamic_stop_percent'] * trade['soft_stops'] * params['weight']
            trade['stop_value'] *= (1.0 - stop_percent)
            if trade['stop_value'] > trade['check_value']:
                trade['stop_value'] = trade['check_value']

            followed_time_str = common.utctime_str(trade['detection_time'], config['time_format'])
            followed_name = trade['detection_name']
            followed_prefix = 'RE-BUY ' if trade['rebuy'] else 'BUY '
            followed_norm_value = trade['open_value'] / current_value
            followed_delta = 1.0 - followed_norm_value

            metadata['followed'].append({
                'snapshot': '{} {} {}'.format(pair, followed_prefix + followed_name, followed_time_str),
                'name': followed_prefix + followed_name,
                'time': trade['detection_time'],
                'delta': followed_delta
            })

            alert_prefix = 'STOP HOLD ' + trade['order_id']
            await self.reporter.send_alert(pair, metadata, detection_name, prefix=alert_prefix)

        base, quote, _ = common.get_pair_elements(pair)

        if common.is_trade_base(base, quote):
            await self.balancer.remit_stop_hold(quote, detection_name)

        self.save_attr('trades', max_depth=1, filter_items=[pair])

    async def enable_refill(self, pair: str, detection_name: str, trigger_data: dict):
        """
        Enable trade balance refills for a pair's quote currency if this is a trade base pair.

        Submits a refill request to handle any refills that may have been deferred while refills were disabled.

        Arguments:
            pair:  The currency pair, eg. 'USDT-BTC'.
        """

        base, quote, trade_base_pair = common.get_pair_elements(pair)

        if base == config['trade_base'] and quote in config['min_base_volumes']:
            self.log.debug("{} got refill ENABLE trigger.", pair)

            if not self.balancer.states[quote]['enable_refill']:
                if not config['trade_balance_sync']:
                    reserved = await self._get_open_trades_value(trade_base_pair)
                    await self.balancer.handle_refill_request(base, config['trade_max_size'], reserved)
                await self.reporter.send_alert(pair, trigger_data, detection_name, prefix='ENABLE REFILL')
                self.balancer.states[quote]['enable_refill'] = True

    async def disable_refill(self, pair: str, detection_name: str, trigger_data: dict):
        """
        Disable trade balance refills for a pair's quote currency if this is a trade base pair.

        Arguments:
            pair:  The currency pair, eg. 'USDT-BTC'.
        """

        base, quote, _ = common.get_pair_elements(pair)

        if base == config['trade_base'] and quote in config['min_base_volumes']:
            self.log.debug("{} got refill DISABLE trigger.", pair)
            if self.balancer.states[quote]['enable_refill']:
                await self.reporter.send_alert(pair, trigger_data, detection_name, prefix='DISABLE REFILL')
                self.balancer.states[quote]['enable_refill'] = False

    async def enable_buy(self, pair: str, detection_name: str, trigger_data: dict):
        """
        Enable buys for a pair.

        Arguments:
            pair:  The currency pair, eg. 'USDT-BTC'.
        """

        if not self.pair_states[pair]['enable_buy']:
            await self.reporter.send_alert(pair, trigger_data, detection_name, prefix='ENABLE BUY')
            self.pair_states[pair]['enable_buy'] = True

    async def disable_buy(self, pair: str, detection_name: str, trigger_data: dict):
        """
        Disable buys for a pair.

        Arguments:
            pair:  The currency pair, eg. 'USDT-BTC'.
        """

        if self.pair_states[pair]['enable_buy']:
            await self.reporter.send_alert(pair, trigger_data, detection_name, prefix='DISABLE BUY')
            self.pair_states[pair]['enable_buy'] = False

    async def pullout(self, pair: str, detection_name: str, trigger_data: dict):
        """
        Execute a pullout of all trades under a pair's quote currency if this is a trade base pair.

        This is essentially a 'nuclear' option to completely divest from a base currency.

        Arguments:
            pair:            The currency pair, eg. 'USDT-BTC'.
            detection_name:  Name of the detection that triggered this action.
            trigger_data:    Aggregate trigger data from the detection.
        """

        base, quote, _ = common.get_pair_elements(pair)

        if base == config['trade_base'] and quote in config['min_base_volumes']:
            await self.reporter.send_alert(pair, trigger_data, detection_name, prefix='PULLOUT')

            futures = []
            for trade_pair in self.trades:
                if trade_pair.split('-')[0] == quote:
                    futures.extend(await self._dump_trades(trade_pair, detection_name, trigger_data))

            for result in asyncio.as_completed(futures):
                self.log.debug("Completed trade sell order {}.", await result)

            if not (config['enable_backtest'] or config['trade_simulate']):
                await self.balancer.handle_pullout_request(quote)

        self.save_attr('trades', max_depth=1, filter_items=[pair])
        self.save_attr('trade_stats', max_depth=2, filter_items=[pair], filter_keys=[self.time_prefix])

    @staticmethod
    def _is_applied(trade: Dict[str, Any], params: Dict[str, Any]) -> bool:
        """
        Check if a detection action should be applied to a trade based on the given parameters.

        Arguments:
            params:  Parameters from the detection in question.
            trade:   Trade to check against.

        Returns:
            True if action should be applied, otherwise False.
        """

        if params['apply'] is not None:
            for group in params['apply']['groups']:
                if group in trade['groups']:
                    return True
            return False
        return True

    @staticmethod
    def _is_ignored(trade: Dict[str, Any], params: Dict[str, Any]) -> bool:
        """
        Check if a detection action should be ignored for a trade based on the given parameters.

        Arguments:
            params:  Parameters from the detection in question.
            trade:   Trade to check against.

        Returns:
            True if action should be ignored, otherwise False.
        """

        if params['ignore'] is not None:
            for group in params['ignore']['groups']:
                if group in trade['groups']:
                    return True
            return False
        return False

    async def _buy_sim(self, pair: str, label: str, detection_name: str,
                       trigger_data: Dict[str, Any], rebuy=False) -> Dict[str, Any]:
        """
        Execute a simulated buy order.

        An alert and snapshot are triggered as a result of this action.

        Arguments:
            pair:            The currency pair for this trade eg. 'BTC-ETH'.
            label:           The text to prepend to the alert and snapshot string for this action.
            detection_name:  Name of the detection that triggered this action.
            trigger_data:    Aggregate trigger data from the detection that triggered this action.
            rebuy:           True if this is a re-buy of a previously closed trade, otherwise False (default).

        Returns:
            A new trade dict. See :attr:`trades`.
        """

        params = core.Detector.get_detection_params(detection_name, {
            'push_target': config['trade_push_sell_percent'],
            'soft_target': config['trade_soft_sell_percent'],
            'hard_target': config['trade_hard_sell_percent'],
            'push_max': config['trade_push_max'],
            'soft_max': config['trade_soft_max'],
            'stop_percent': config['trade_stop_percent'],
            'stop_cutoff': config['trade_stop_cutoff'],
            'stop_check': config['trade_stop_check'],
            'deferred_push': config['trade_deferred_push_sell'],
            'deferred_soft': config['trade_deferred_soft_sell'],
            'deferred_hard': config['trade_deferred_hard_sell'],
            'groups': ['default']
        })

        base_mult = await self.market.get_pair_base_mult(config['trade_base'], pair)
        trade_size = self.trade_sizes[params['groups'][0]]

        min_trade_size = self.market.min_safe_trade_size
        if trade_size < min_trade_size:
            self.log.warning("{} using trade size of {}, please update your config.", pair, min_trade_size)
            trade_size = min_trade_size

        adjusted_value = self.market.adjusted_close_values[pair][-1]
        quantity = trade_size / adjusted_value
        adjusted_cost = quantity * adjusted_value
        adjusted_fees = adjusted_cost * config['trade_fee_percent']
        current_time = self.market.close_times[pair][-1]
        success = await self._simulate_buy_balances(pair, base_mult, trade_size, adjusted_cost, adjusted_fees)

        if not success:
            return None

        await self._register_trade_buy(pair, label, detection_name, trigger_data, rebuy)

        return {
            'pair': pair,
            'order_id': uuid.uuid4().hex,
            'open_value': adjusted_value,
            'base_value': base_mult,
            'quantity': quantity,
            'remaining': 0.0,
            'filled': True,
            'fees': adjusted_fees,
            'sell_pushes': 0,
            'push_locked': True,
            'soft_stops': 0,
            'soft_sells': [],
            'hard_sells': [],
            'hard_stops': [],
            'base_soft_stops': [],
            'rebuy': rebuy,
            'open_time': current_time,
            'detection_name': detection_name,
            'detection_time': trigger_data['current_time'],
            'push_target': adjusted_value * (1.0 + params['push_target']),
            'soft_target': adjusted_value * (1.0 + params['soft_target']),
            'hard_target': adjusted_value * (1.0 + params['hard_target']),
            'stop_value': adjusted_value * (1.0 - params['stop_percent']),
            'cutoff_value': adjusted_value * (1.0 - params['stop_cutoff']),
            'check_value': adjusted_value * (1.0 - params['stop_check']),
            'push_max': params['push_max'],
            'soft_max': params['soft_max'],
            'stop_percent': params['stop_percent'],
            'stop_cutoff': params['stop_cutoff'],
            'stop_check': params['stop_check'],
            'deferred_push': params['deferred_push'],
            'deferred_soft': params['deferred_soft'],
            'deferred_hard': params['deferred_hard'],
            'groups': params['groups']
        }

    async def _simulate_buy_balances(self, pair: str, base_mult: float,
                                     trade_size: float, adjusted_cost: float, adjusted_fees: float):
        """
        """

        if not config['sim_enable_balances'] or not config['trade_simulate']:
            return True

        if not config['sim_enable_balancer']:
            if self.balancer.sim_balances[config['trade_base']] < adjusted_cost + adjusted_fees:
                self.log.warning('Could not simulate buy order for {}, insufficient funds.', pair)
                self.trade_stats[self.time_prefix][pair]['failed'] += 1
                success = False
            else:
                self.balancer.sim_balances[config['trade_base']] -= adjusted_cost + adjusted_fees
                self.balancer.save_attr('sim_balances', force=True)
                success = True

        else:
            base, _, trade_base_pair = common.get_pair_elements(pair)

            if config['trade_balance_sync']:
                reserved = await self._get_open_trades_value(trade_base_pair)
                await self.balancer.handle_refill_request(base, trade_size, reserved)
                await self._garbage_collect_sim(base, trade_size, reserved)

            cost = adjusted_cost / base_mult
            fees = adjusted_fees / base_mult

            if self.balancer.sim_balances[base] < cost + fees:
                self.log.warning('Could not simulate buy order for {}, insufficient funds.', pair)
                self.trade_stats[self.time_prefix][pair]['failed'] += 1
                success = False
            else:
                self.balancer.sim_balances[base] -= cost + fees
                self.balancer.save_attr('sim_balances', force=True)
                success = True

            if not config['trade_balance_sync']:
                reserved = await self._get_open_trades_value(trade_base_pair)
                await self.balancer.handle_refill_request(base, trade_size, reserved)
                await self._garbage_collect_sim(base, trade_size + config['trade_min_size'], reserved)

        return success

    async def _garbage_collect_sim(self, base: str, trade_size: float, reserved: float):
        """
        Garbage collect oldest trade to free balance if balance is low.

        Arguments:
            trade_size:  Trade size to consider for remaining balance.
        """

        if not config['trade_garbage_collect']:
            return

        base_mult = await self.market.get_base_mult(config['trade_base'], base)
        current_balance = self.balancer.sim_balances[base] * base_mult - reserved

        if current_balance >= trade_size:
            return

        open_trades_by_time = []
        for pair in self.trades:
            if pair.split('-')[0] == base:
                for trade in self.trades[pair]['open']:
                    open_trades_by_time.append((trade['open_time'], trade))

        open_trades_sorted = [trade_tuple[1] for trade_tuple in sorted(open_trades_by_time, key=lambda x: x[0])]

        if open_trades_sorted:
            collect_trade = open_trades_sorted[0]
            await self._sell_sim(collect_trade, 'GARBAGE COLLECT SELL', remit=False)
            self.trades[collect_trade['pair']]['open'].remove(collect_trade)

    async def _buy_live(self, pair: str, label: str, detection_name: str,
                        trigger_data: Dict[str, Any], rebuy=False):
        """
        Execute a live limit buy order.

        An alert and snapshot are triggered as a result of this action.

        Arguments:
            pair:            The currency pair for this trade eg. 'BTC-ETH'.
            label:           The text to prepend to the alert and snapshot string for this action.
            detection_name:  Name of the detection that triggered this action.
            trigger_data:    Aggregate trigger data from the detection that triggered this action.
            rebuy:           True if this is a re-buy of a previously closed trade, otherwise False (default).

        Returns:
            A new trade object. See :attr:`trades`.
        """

        params = core.Detector.get_detection_params(detection_name, {
            'push_target': config['trade_push_sell_percent'],
            'soft_target': config['trade_soft_sell_percent'],
            'hard_target': config['trade_hard_sell_percent'],
            'push_max': config['trade_push_max'],
            'soft_max': config['trade_soft_max'],
            'stop_percent': config['trade_stop_percent'],
            'stop_cutoff': config['trade_stop_cutoff'],
            'stop_check': config['trade_stop_check'],
            'deferred_push': config['trade_deferred_push_sell'],
            'deferred_soft': config['trade_deferred_soft_sell'],
            'deferred_hard': config['trade_deferred_hard_sell'],
            'groups': ['default']
        })

        base, _, trade_base_pair = common.get_pair_elements(pair)
        trade_size = self.trade_sizes[params['groups'][0]]

        if config['trade_balance_sync']:
            reserved = await self._get_open_trades_value(trade_base_pair)
            await self.balancer.handle_refill_request(base, trade_size, reserved)
            await self._garbage_collect_live(base, trade_size, reserved)

        order_id, quantity = await self._submit_limit_buy(pair, trade_size)

        if order_id is None:
            self.log.warning("Could not open buy order for {}.", pair)
            await self.reporter.send_alert(pair, trigger_data, detection_name, prefix='FAIL BUY')
            success = False
        else:
            success = True

        if not success:
            self.trade_stats[self.time_prefix][pair]['failed'] += 1
            return None

        await self._register_trade_buy(pair, label, detection_name, trigger_data, rebuy)

        if not config['trade_balance_sync']:
            reserved = await self._get_open_trades_value(trade_base_pair)
            await self.balancer.handle_refill_request(base, trade_size, reserved)
            await self._garbage_collect_live(base, trade_size + config['trade_min_size'], reserved)

        adjusted_value = self.market.adjusted_close_values[pair][-1]
        current_time = self.market.close_times[pair][-1]

        order = {
            'pair': pair,
            'order_id': order_id,
            'open_value': adjusted_value,
            'base_value': await self.market.get_pair_base_mult(config['trade_base'], pair),
            'quantity': quantity,
            'remaining': quantity,
            'filled': False,
            'fees': 0.0,
            'sell_pushes': 0,
            'push_locked': True,
            'soft_stops': 0,
            'soft_sells': [],
            'hard_sells': [],
            'hard_stops': [],
            'base_soft_stops': [],
            'rebuy': rebuy,
            'open_time': current_time,
            'detection_name': detection_name,
            'detection_time': trigger_data['current_time'],
            'push_target': adjusted_value * (1.0 + params['push_target']),
            'soft_target': adjusted_value * (1.0 + params['soft_target']),
            'hard_target': adjusted_value * (1.0 + params['hard_target']),
            'stop_value': adjusted_value * (1.0 - params['stop_percent']),
            'cutoff_value': adjusted_value * (1.0 - params['stop_cutoff']),
            'check_value': adjusted_value * (1.0 - params['stop_check']),
            'push_max': params['push_max'],
            'soft_max': params['soft_max'],
            'stop_percent': params['stop_percent'],
            'stop_cutoff': params['stop_cutoff'],
            'stop_check': params['stop_check'],
            'deferred_push': params['deferred_push'],
            'deferred_soft': params['deferred_soft'],
            'deferred_hard': params['deferred_hard'],
            'groups': params['groups']
        }

        return order

    async def _submit_limit_buy(self, pair: str, trade_size: float):
        """
        Submit a limit buy for the specified currency pair.

        Arguments:
            pair:        The pair to buy on eg. 'BTC-ETH'.
            trade_size:  Size of the trade, in trade base currency units.

        Returns:
            (tuple):  A tuple containing:
            (str):    The UUID of the buy order, or None if an API error occurred.
            (float):  The quantity of the order, or 0.0 if an API error occurred.
        """

        adjusted_value = self.market.adjusted_close_values[pair][-1]
        current_value = self.market.close_values[pair][-1]

        min_trade_size = self.market.min_trade_sizes[pair] * (1.0 + config['trade_min_safe_percent'])
        if min_trade_size < self.market.min_safe_trade_size:
            min_trade_size = self.market.min_safe_trade_size

        if trade_size < min_trade_size:
            self.log.warning("{} using trade size of {}, please update your config.", pair, min_trade_size)
            trade_size = min_trade_size

        quantity = trade_size / adjusted_value
        min_quantity = self.market.min_trade_qtys[pair]

        if quantity < min_quantity:
            self.log.warning("{} trade quantity {} too low, using minimum of {}.", pair, quantity, min_quantity)
            quantity = min_quantity

        limit_value = current_value * (1.0 + config['trade_buy_limit_margin'])
        order_id = await self.api.buy_limit(pair, quantity, limit_value)

        if order_id is None:
            base = pair.split('-')[0]
            base_mult = await self.market.get_base_mult(config['trade_base'], base)
            reserved = config['remit_reserved'][base] if base in config['remit_reserved'] else 0.0
            balance = await self.api.get_balance(base)

            if balance is None:
                self.log.error("Could not get available balance for {}!", base)
                return (None, 0.0)

            balance *= (1.0 - config['trade_buy_retry_margin']) - reserved

            min_size = self.market.min_trade_size / base_mult
            if min_size < self.market.min_trade_sizes[pair]:
                min_size = self.market.min_trade_sizes[pair]

            if balance >= min_size:
                quantity = balance / limit_value
                self.log.warning("{} re-trying buy with available balance {}.", pair, balance)
                order_id = await self.api.buy_limit(pair, quantity, limit_value)

        if order_id is None:
            return (None, 0.0)

        return (order_id, quantity)

    async def _garbage_collect_live(self, base: str, trade_size: float, reserved: float):
        """
        Garbage collect oldest trade to free balance if balance is low.

        Arguments:
            trade_size:  Trade size to consider for remaining balance.
        """

        if not config['trade_garbage_collect']:
            return

        balance = await self.api.get_balance(base)
        if balance is None:
            self.log.error("Could not get available balance for {}!", base)
            return

        base_mult = await self.market.get_base_mult(config['trade_base'], base)
        adjusted_balance = balance * base_mult - reserved

        if adjusted_balance >= trade_size:
            return

        open_trades_by_time = []
        for pair in self.trades:
            if pair.split('-')[0] == base:
                for trade in self.trades[pair]['open']:
                    open_trades_by_time.append((trade['open_time'], trade))

        open_trades_sorted = [trade_tuple[1] for trade_tuple in sorted(open_trades_by_time, key=lambda x: x[0])]
        if open_trades_sorted:
            collect_trade = open_trades_sorted[0]
            utils.async_task(self._sell_live(collect_trade, 'COLLECT SELL', 'collect', remit=False), loop=common.loop)
            self.trades[collect_trade['pair']]['open'].remove(collect_trade)

    async def _register_trade_buy(self, pair: str, label: str, detection_name: str,
                                  trigger_data: Dict[str, Any], rebuy=False):
        """
        Register a bought trade.

        Updates trade statistics, and outputs alerts and snapshots for the trade buy.

        Arguments:
            See :meth:`_buy_live`
        """

        current_time = self.market.close_times[pair][-1]
        current_value = self.market.adjusted_close_values[pair][-1]

        if rebuy:
            last_closed_trade = self.trades[pair]['closed'][-1]
            followed_time_str = common.utctime_str(last_closed_trade['detection_time'], config['time_format'])
            followed_name = last_closed_trade['detection_name']
            followed_prefix = 'RE-BUY ' if last_closed_trade['rebuy'] else 'BUY '
            followed_norm_value = last_closed_trade['open_value'] / current_value
            followed_delta = 1.0 - followed_norm_value

            metadata = trigger_data.copy()
            metadata['followed'].append({
                'snapshot': '{} {} {}'.format(pair, followed_prefix + followed_name, followed_time_str),
                'name': followed_prefix + followed_name,
                'time': last_closed_trade['detection_time'],
                'delta': followed_delta
            })

        else:
            metadata = trigger_data

        await self.reporter.send_alert(pair, metadata, detection_name, prefix=label,
                                       color=config['buy_color'], sound=config['buy_sound'])

        self.trades[pair]['last_open_time'] = current_time
        self.last_trades[pair]['buy'] = {'value': current_value, 'time': current_time}

        if rebuy:
            self.trades[pair]['rebuy_count'] += 1
            self.last_trades[pair]['most_recent'] = 'rebuy'
            self.last_trades[pair]['rebuy'] = {'value': current_value, 'time': current_time}
        else:
            self.trades[pair]['rebuy_count'] = 0
            self.last_trades[pair]['most_recent'] = 'buy'

        buy_stat = 'rebuys' if rebuy else 'buys'
        self.trade_stats[self.time_prefix][pair][buy_stat] += 1

    async def _sell_sim(self, trade: Dict[str, Any], label: str, sell_type: str=None,
                        detection_name: str=None, trigger_data: dict=None, remit: bool=True) -> asyncio.Future:
        """
        Execute a simulated sell of an open trade.

        An alert and snapshot are also triggered as a result of this action.

        Arguments:
            trade:            The open trade to sell.
            label:            The text to prepend to the alert and snapshot string for this action.
            detection_name:   If provided, the name of the detection that triggered this sell, which is added to
                              the alert and snapshot string.
            trigger_data:     If provided, the aggregate trigger data from the triggering detection, which is added
                              to the snapshot metadata.

        Returns:
            A completed :class:`asyncio.Future` with a dummy UUID. Used to maintain interface compatibility with
            :meth:`_live_sell()` which returns a future for a sell task.
        """

        pair = trade['pair']
        adjusted_value = self.market.adjusted_close_values[pair][-1]
        adjusted_proceeds = adjusted_value * trade['quantity']
        adjusted_fees = adjusted_proceeds * config['trade_fee_percent']
        current_time = self.market.close_times[pair][-1]

        trade['close_time'] = current_time
        trade['close_value'] = adjusted_value
        trade['fees'] += adjusted_fees

        await self._simulate_sell_balances(trade, remit, adjusted_proceeds, adjusted_fees)
        await self._register_trade_sell(trade, label, sell_type, detection_name, trigger_data)

        future = asyncio.Future()
        future.set_result(uuid.uuid4().hex)
        return future

    async def _simulate_sell_balances(self, trade: Dict[str, Any], remit: bool,
                                      adjusted_proceeds: float, adjusted_fees: float):
        """
        """

        if not config['sim_enable_balances'] or not config['trade_simulate']:
            return

        if not config['sim_enable_balancer']:
            self.balancer.sim_balances[config['trade_base']] += adjusted_proceeds - adjusted_fees
            self.balancer.save_attr('sim_balances', force=True)

        else:
            base_mult = await self.market.get_pair_base_mult(config['trade_base'], trade['pair'])
            proceeds = adjusted_proceeds / base_mult
            fees = adjusted_fees / base_mult
            base, _, trade_base_pair = common.get_pair_elements(trade['pair'])
            self.balancer.sim_balances[base] += proceeds - fees
            self.balancer.save_attr('sim_balances', force=True)

            if remit:
                reserved = await self._get_open_trades_value(trade_base_pair)
                await self.balancer.handle_remit_request(base, trade['base_value'], reserved, adjusted_proceeds)

    async def _sell_live(self, trade: Dict[str, Any], label: str, sell_type: str=None,
                         detection_name: str=None, trigger_data: dict=None, remit: bool=True) -> asyncio.Future:
        """
        Execute a live sell of an open trade.

        An alert and snapshot are also triggered as a result of this action. Kicks off an async task to handle the
        submission of the sell order. Any unfilled buy orders still open for the trade are cancelled.

        Arguments:
            trade:           The open trade to sell.
            label:           The text to prepend to the alert and snapshot string for this action.
            detection_name:  If provided, the name of a detection that triggered this sell, which is added to
                             the alert and snapshot string.
            trigger_data:    If provided, the aggregate trigger data from the triggering detection, which is added
                             to the snapshot metadata.
            remit:           If True (default), will process a remit for the sell once it completes.

        Returns:
            The :class:`asyncio.Future` for the sell task, which will contain the UUID for the sell order once it
            completes.
        """

        future = utils.async_task(self._sell_live_task(trade, label, sell_type, detection_name, trigger_data, remit),
                                  loop=common.loop)

        if not trade['filled']:
            pair = trade['pair']

            if not await self.api.cancel_order(pair, trade['order_id']):
                self.log.error("Could not cancel unfilled {} order {}.", pair, trade['order_id'])
            else:
                self.log.warning("Cancelled unfilled {} order {}.", pair, trade['order_id'])

            current_time = self.market.close_times[pair][-1]
            current_value = self.market.close_values[pair][-1]
            base_mult = await self.market.get_pair_base_mult(config['trade_base'], pair)
            self.trade_stats[self.time_prefix][pair]['unfilled_quantity'] += trade['remaining']
            self.trade_stats[self.time_prefix][pair]['unfilled_value'] += trade['remaining'] * current_value * base_mult

            if math.isclose(trade['quantity'], trade['remaining']):
                self.trade_stats[self.time_prefix][pair]['unfilled'] += 1
                await self.reporter.send_alert(pair, trigger_data, detection_name, prefix='UNFILLED CANCEL')
                self.log.error("{} buy order {} went unfilled at {}.", pair, trade['order_id'], current_time)
            else:
                self.trade_stats[self.time_prefix][pair]['unfilled_partial'] += 1
                await self.reporter.send_alert(pair, trigger_data, detection_name, prefix='PARTIAL FILL CANCEL')
                self.log.error("{} buy order {} only partially filled at {}.", pair, trade['order_id'], current_time)

        return future

    async def _sell_live_task(self, trade: Dict[str, Any], label: str, sell_type: str,
                              detection_name: str, trigger_data: Dict[str, Any], remit: bool):
        """
        Handle the sell order, tracking, update, registering, and balance remit of a live sell for a trade.

        Arguments:
            See :meth:`_sell_live`
        """

        order_id = await self._submit_trade_sell(trade)

        if order_id is not None:
            await self._update_trade_sell(trade, order_id)
            await self._register_trade_sell(trade, label, sell_type, detection_name, trigger_data)

            if remit:
                base, _, trade_base_pair = common.get_pair_elements(trade['pair'])
                reserved = await self._get_open_trades_value(trade_base_pair)
                filled_quantity = trade['quantity'] - trade['remaining']
                adjusted_proceeds = filled_quantity * (trade['close_value'] - trade['open_value'])
                await self.balancer.handle_remit_request(base, trade['base_value'], reserved, adjusted_proceeds)

        return order_id

    async def _submit_trade_sell(self, trade: Dict[str, Any]) -> str:
        """
        Submit a market sell for the specified trade.

        Explicit market orders are not supported by the API, but an effective market sell is achieved by using a limit
        sell with the sell value adjusted for the minimum trade size.

        TODO: Also use min trade values returned by the API if available.

        Arguments:
            trade:  The trade to sell on.

        Returns:
            The UUID of the sell order, or None if an API error occurred or the trade has no filled volume.
        """

        pair = trade['pair']
        filled_quantity = trade['quantity'] - trade['remaining']
        base_mult = await self.market.get_pair_base_mult(config['trade_base'], pair)

        if filled_quantity > 0.0:
            min_size = self.market.min_trade_size / base_mult
            if min_size < self.market.min_trade_sizes[pair]:
                min_size = self.market.min_trade_sizes[pair]

            min_value = min_size / filled_quantity
            order_id = await self.api.sell_limit(pair, filled_quantity, min_value)

            if order_id is None:
                quote = pair.split('-')[1]
                reserved = config['remit_reserved'][quote] if quote in config['remit_reserved'] else 0.0
                balance = await self.api.get_balance(quote)

                if balance is None:
                    self.log.error("Could not get available balance for {}!", quote)
                    return None

                balance -= reserved

                if balance >= min_size:
                    min_value = min_size / balance
                    self.log.warning("{} re-trying sell with available balance {}.", pair, balance)
                    order_id = await self.api.sell_limit(pair, balance, min_value)

                if order_id is None:
                    self.log.error("{} could not submit market sell for trade {}!", pair, trade['order_id'])

            else:
                self.log.info("{} submitted market sell for trade {}.", pair, trade['order_id'])

            return order_id

        self.log.warning("{} has no filled volume on trade {} for sell.", pair, trade['order_id'])
        return None

    async def _update_trade_sell(self, trade: Dict[str, Any], order_id: str):
        """
        Track a sell order for a trade until closing and update it with the closing values.

        Tracks the trade's open sell order until closing and updates the trade's close_time, close_value, and fees
        attributes. If tracking the sell order fails, the close_value and fees are estimated from current tick data.

        Arguments:
            trade:      The trade to update.
            order_id:   The order id of the sell order to track.
        """

        pair = trade['pair']
        success = False
        is_open = True

        filled_quantity = trade['quantity'] - trade['remaining']

        while is_open:
            await asyncio.sleep(config['trade_update_secs'])
            order = await self.api.get_order(pair, order_id)

            if order is None:
                self.log.error("{} could not track sell order {} for trade {}!", pair, order_id, trade['order_id'])
                success = False
                is_open = False

            else:
                success = True
                is_open = order['open']
                unit_value = order['value']
                fees = order['fees']

                base_mult = await self.market.get_pair_base_mult(config['trade_base'], pair)
                adjusted_value = unit_value * base_mult if unit_value is not None else None
                adjusted_fees = fees * base_mult if fees is not None else None

                self.log.info("{} updated trade {} sell order {}: open {}, close value {}.",
                              pair, trade['order_id'], order_id, is_open, unit_value)

        if not success:
            adjusted_value = self.market.adjusted_close_values[pair][-1]
            adjusted_fees = filled_quantity * adjusted_value * config['trade_fee_percent']

        trade['close_time'] = self.market.close_times[pair][-1]
        trade['close_value'] = adjusted_value
        trade['fees'] += adjusted_fees

    async def _register_trade_sell(self, trade: Dict[str, Any], label: str, sell_type: str,
                                   detection_name: str, trigger_data: Dict[str, Any]):
        """
        Register a closed trade sell.

        Updates trade statistics and outputs alerts and snapshots for the trade sell.

        Arguments:
            See :meth:`_sell_live`

        Returns:
            The proceeds of the trade.
        """

        pair = trade['pair']

        metadata = trade.copy()
        if trigger_data:
            metadata.update(trigger_data)
        else:
            metadata['followed'] = []

        current_value = self.market.adjusted_close_values[pair][-1]

        followed_time_str = common.utctime_str(trade['detection_time'], config['time_format'])
        followed_name = trade['detection_name']
        followed_prefix = 'RE-BUY ' if trade['rebuy'] else 'BUY '
        followed_norm_value = trade['open_value'] / current_value
        followed_delta = 1.0 - followed_norm_value

        metadata['followed'].append({
            'snapshot': '{} {} {}'.format(pair, followed_prefix + followed_name, followed_time_str),
            'name': followed_prefix + followed_name,
            'time': trade['detection_time'],
            'delta': followed_delta
        })

        filled_quantity = trade['quantity'] - trade['remaining']
        proceeds = filled_quantity * (trade['close_value'] - trade['open_value'])

        if proceeds > 0.0:
            color = config['sell_high_color']
            sound = config['sell_high_sound']
            text = label + ' HIGH ' + trade['order_id']
            await self._track_last_sell(pair, sell_type, 'high')

        else:
            color = config['sell_low_color']
            sound = config['sell_low_sound']
            text = label + ' LOW ' + trade['order_id']
            await self._track_last_sell(pair, sell_type, 'low')

        await self.reporter.send_alert(pair, metadata, detection_name, prefix=text, color=color, sound=sound)
        await self._track_sell_stats(trade, proceeds, sell_type)

    async def _track_last_sell(self, pair: str, sell_type: str, direction: str):
        """
        """

        current_value = self.market.adjusted_close_values[pair][-1]
        current_time = self.market.close_times[pair][-1]

        if sell_type:
            trade_key = sell_type + '_sell_' + direction
            self.last_trades[pair]['most_recent'] = trade_key
            self.last_trades[pair][trade_key] = {
                'value': current_value,
                'time': current_time
            }

        else:
            self.last_trades[pair]['most_recent'] = 'sell_' + direction

        self.last_trades[pair]['sell_' + direction] = {
            'value': current_value,
            'time': current_time
        }

    async def _track_sell_stats(self, trade: Dict[str, Any], proceeds: float, sell_type: str):
        """
        """

        pair = trade['pair']

        if proceeds > 0.0:
            self.trade_stats[self.time_prefix][pair]['total_profit'] += proceeds
        else:
            self.trade_stats[self.time_prefix][pair]['total_loss'] -= proceeds

        self.trade_stats[self.time_prefix][pair]['total_fees'] += trade['fees']

        if sell_type:
            self.trade_stats[self.time_prefix][pair][sell_type + '_sells'] += 1
        else:
            self.trade_stats[self.time_prefix][pair]['sells'] += 1

    async def _update_live(self, trade: Dict[str, Any]):
        """
        Update an open live trade.

        Checks the status of any open limit orders that have not yet been filled, and updates the filled state,
        quantity and other information accordingly. If an order fills, the open value and target values are updated
        to match the actual values of the trade.

        Arguments:
            trade:  The open trade to update.
        """

        order = await self.api.get_order(trade['pair'], trade['order_id'])
        if order is None:
            self.log.error("Could not update trade {}.", trade['order_id'])
            return

        is_open = order['open']
        quantity = order['quantity']
        remaining = order['remaining']
        unit_value = order['value']
        fees = order['fees']

        trade['filled'] = not is_open
        trade['quantity'] = quantity
        trade['remaining'] = remaining

        if trade['filled'] and unit_value is not None:
            base_mult = await self.market.get_pair_base_mult(config['trade_base'], trade['pair'])
            adjusted_value = unit_value * base_mult
            trade['open_value'] = adjusted_value
            trade['base_value'] = base_mult
            trade['fees'] = fees * base_mult

        self.log.info("Updated trade {}: filled {}, quantity {}, remaining {}.",
                      trade['order_id'], trade['filled'], quantity, remaining)

    async def _get_open_trades_value(self, pair: str) -> float:
        """
        Get the total value of all open trades for a pair.

        Arguments:
            pair:  The currency pair eg. 'BTC-ETH'.

        Returns:
            The total open trades value.
        """

        total = 0.0

        if pair in self.trades:
            for trade in self.trades[pair]['open']:
                total += trade['open_value'] * trade['quantity']

        return total

    async def _get_num_open_high_low_trades(self) -> float:
        """
        Get the total value of all open trades for all pairs.

        Returns:
            (tuple)  A tuple containing:
                (int):  The total number of low trades.
                (int):  The total number of high trades.
        """

        low = 0
        high = 0

        for pair in self.trades:
            current_value = self.market.adjusted_close_values[pair][-1]
            for trade in self.trades[pair]['open']:
                fees = config['trade_fee_percent'] * trade['open_value'] + config['trade_fee_percent'] * current_value
                if current_value - fees > trade['open_value']:
                    high += 1
                else:
                    low += 1

        return (low, high)

    async def _get_num_open_trades(self) -> int:
        """
        Get the total number of all open trades for all pairs.

        Returns:
            The total number of open trades.
        """

        num = 0

        for pair in self.trades:
            num += len(self.trades[pair]['open'])

        return num

    async def _get_num_open_group_trades(self) -> Dict[str, int]:
        """
        Get the total number of all open trades for all pairs by group.

        Returns:
            The total number of open trades by group.
        """

        num_trades = {}
        total = 0

        for pair in self.trades:
            for trade in self.trades[pair]['open']:
                total += 1
                for group in trade['groups']:
                    if group not in num_trades:
                        num_trades[group] = 0
                    else:
                        num_trades[group] += 1

        num_trades['default'] = total
        return num_trades

    async def _track_num_open_trades(self, pair: str):
        """
        Track the number of open trades for a pair and update trade stats accordingly.

        Updates the 'most_open' and 'num_open' trade stats field for the given pair and current time prefix.

        Arguments:
            pair:  The currency pair eg. 'BTC-ETH'.
        """

        open_count = len(self.trades[pair]['open'])
        if open_count > self.trade_stats[self.time_prefix][pair]['most_open']:
            self.trade_stats[self.time_prefix][pair]['most_open'] = open_count

        num_open_list = self.trade_stats[self.time_prefix][pair]['num_open']
        if not num_open_list or num_open_list[-1][1] != open_count:
            current_time = self.market.close_times[pair][-1]
            num_open = (current_time, open_count)
            self.trade_stats[self.time_prefix][pair]['num_open'].append(num_open)

    async def update_trade_sizes(self):
        """
        Update trade sizes based on the current trade base balance.
        """

        if config['trade_size_mult'] is None:
            return

        trade_sizes = await self._get_num_open_group_trades()
        for group, num in trade_sizes.items():
            trade_size = config['trade_min_size'] * config['trade_size_mult'] * (num + 1)
            if trade_size > config['trade_max_size']: trade_size = config['trade_max_size']
            if trade_size < config['trade_min_size']: trade_size = config['trade_min_size']

            old_trade_size = self.trade_sizes[group]
            self.trade_sizes[group] = trade_size
            if not math.isclose(old_trade_size, trade_size):
                self.log.info("Group '{}' trade size updated to {}.", group, trade_size)

    async def update_trade_stats(self):
        """
        Update trade stats for all pairs as well as base currencies and 'global'.
        """

        summary_keys = [base for base in config['min_base_volumes']] + ['global']
        summaries = {
            key: {
                'open_count': 0,
                'buys': 0,
                'rebuys': 0,
                'sells': 0,
                'collect_sells': 0,
                'soft_stop_sells': 0,
                'total_profit': 0.0,
                'total_loss': 0.0,
                'total_fees': 0.0,
                'balancer_refills': 0,
                'balancer_remits': 0,
                'balancer_stop_losses': 0,
                'balancer_profit': 0.0,
                'balancer_loss': 0.0,
                'balancer_fees': 0.0,
            } for key in summary_keys
        }

        for pair in self.trades:
            if pair not in self.trade_stats[self.time_prefix]:
                continue

            base = pair.split('-', 1)[0]
            open_count = len(self.trades[pair]['open'])

            summaries[base]['open_count'] += open_count
            summaries[base]['buys'] += self.trade_stats[self.time_prefix][pair]['buys']
            summaries[base]['rebuys'] += self.trade_stats[self.time_prefix][pair]['rebuys']
            summaries[base]['sells'] += self.trade_stats[self.time_prefix][pair]['sells']
            summaries[base]['collect_sells'] += self.trade_stats[self.time_prefix][pair]['collect_sells']
            summaries[base]['soft_stop_sells'] += self.trade_stats[self.time_prefix][pair]['soft_stop_sells']
            summaries[base]['total_profit'] += self.trade_stats[self.time_prefix][pair]['total_profit']
            summaries[base]['total_loss'] += self.trade_stats[self.time_prefix][pair]['total_loss']
            summaries[base]['total_fees'] += self.trade_stats[self.time_prefix][pair]['total_fees']
            summaries[base]['balancer_refills'] += self.trade_stats[self.time_prefix][pair]['balancer_refills']
            summaries[base]['balancer_remits'] += self.trade_stats[self.time_prefix][pair]['balancer_remits']
            summaries[base]['balancer_profit'] += self.trade_stats[self.time_prefix][pair]['balancer_profit']
            summaries[base]['balancer_loss'] += self.trade_stats[self.time_prefix][pair]['balancer_loss']
            summaries[base]['balancer_fees'] += self.trade_stats[self.time_prefix][pair]['balancer_fees']

            summaries['global']['open_count'] += open_count
            summaries['global']['buys'] += self.trade_stats[self.time_prefix][pair]['buys']
            summaries['global']['rebuys'] += self.trade_stats[self.time_prefix][pair]['rebuys']
            summaries['global']['sells'] += self.trade_stats[self.time_prefix][pair]['sells']
            summaries['global']['collect_sells'] += self.trade_stats[self.time_prefix][pair]['collect_sells']
            summaries['global']['soft_stop_sells'] += self.trade_stats[self.time_prefix][pair]['soft_stop_sells']
            summaries['global']['total_profit'] += self.trade_stats[self.time_prefix][pair]['total_profit']
            summaries['global']['total_loss'] += self.trade_stats[self.time_prefix][pair]['total_loss']
            summaries['global']['total_fees'] += self.trade_stats[self.time_prefix][pair]['total_fees']
            summaries['global']['balancer_refills'] += self.trade_stats[self.time_prefix][pair]['balancer_refills']
            summaries['global']['balancer_remits'] += self.trade_stats[self.time_prefix][pair]['balancer_remits']
            summaries['global']['balancer_profit'] += self.trade_stats[self.time_prefix][pair]['balancer_profit']
            summaries['global']['balancer_loss'] += self.trade_stats[self.time_prefix][pair]['balancer_loss']
            summaries['global']['balancer_fees'] += self.trade_stats[self.time_prefix][pair]['balancer_fees']

        for key in summaries:
            self.trade_stats[self.time_prefix][key]['buys'] = summaries[key]['buys']
            self.trade_stats[self.time_prefix][key]['rebuys'] = summaries[key]['rebuys']
            self.trade_stats[self.time_prefix][key]['sells'] = summaries[key]['sells']
            self.trade_stats[self.time_prefix][key]['collect_sells'] = summaries[key]['collect_sells']
            self.trade_stats[self.time_prefix][key]['soft_stop_sells'] = summaries[key]['soft_stop_sells']
            self.trade_stats[self.time_prefix][key]['total_profit'] = summaries[key]['total_profit']
            self.trade_stats[self.time_prefix][key]['total_loss'] = summaries[key]['total_loss']
            self.trade_stats[self.time_prefix][key]['total_fees'] = summaries[key]['total_fees']
            self.trade_stats[self.time_prefix][key]['balancer_refills'] = summaries[key]['balancer_refills']
            self.trade_stats[self.time_prefix][key]['balancer_remits'] = summaries[key]['balancer_remits']
            self.trade_stats[self.time_prefix][key]['balancer_profit'] = summaries[key]['balancer_profit']
            self.trade_stats[self.time_prefix][key]['balancer_loss'] = summaries[key]['balancer_loss']
            self.trade_stats[self.time_prefix][key]['balancer_fees'] = summaries[key]['balancer_fees']

            if summaries[key]['open_count'] > self.trade_stats[self.time_prefix][key]['most_open']:
                self.trade_stats[self.time_prefix][key]['most_open'] = summaries[key]['open_count']

        filter_items = [pair for pair in self.trades] + [base for base in config['min_base_volumes']] + ['global']
        self.save_attr('trade_stats', max_depth=2, filter_items=filter_items, filter_keys=[self.time_prefix])
