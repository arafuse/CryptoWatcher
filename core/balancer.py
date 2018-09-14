# -*- coding: utf-8 -*-

# Copyright (c) A 2017 Adam M. Rafuse - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited.
# Proprietary and confidential.

"""
Balancer service.
"""

__author__ = 'Adam Rafuse <$(echo nqnz.enshfr#tznvy.pbz | tr a-z# n-za-m@)>'
__all__ = ['Balancer']

import uuid
import asyncio

from typing import Any, Dict

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


class Balancer(common.base.Persistable):
    """
    Balancer service object.

    Manages base currency balances and balance simulation.
    """

    def __init__(self, api_client: api.Client, market: core.Market, reporter: core.Reporter, time_prefix: str,
                 trade_stats: Dict[str, Dict[str, Any]], trade_sizes: Dict[str, float],
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

        self.trade_stats = trade_stats
        """
        Shared trade statistics dict. See :attr:`Trader.trade_stats`.
        """

        self.trade_sizes = trade_sizes
        """
        Shared trade sizes dict. See :attr:`Trader.trade_sizes`.
        """

        self.log = utils.logging.ChildLogger(parent=log, scope=self)
        """
        Object logger.
        """

        self.refill_orders = {}
        """
        Refill buy orders.
        """

        self.remit_orders = {}
        """
        Remit sell orders.

        ``
        {
            (str): Base currency name eg. 'BTC'
            [
                {
                    'open_value' (float):         Value the remit order was opened with.
                    'open_time': (float):         UTC timestamp of when this order was opened.
                    'quantity' (float):           Total quantity of this order.
                    'sell_pushes': (int):          Number of sell pushes for this order.
                    'soft_stops': list(int):      Indexes of detections triggering soft stops for this order.
                    'stop_value': (float)':       Stop-loss value for this order.
                    'soft_target': (float)':      Minimum target value for this order.
                    'hard_target': (float)':      Minimum target value for this order.
                }
            ]
        }
        ``
        """

        self.states = {}
        """
        Balancer states.
        {
            (str): Base currency name eg. 'BTC'
            {
                'enable_refill' (bool):  True if refills are enabled for the base currency.
            }
        }
        """

        self.sim_balances = {
            base: None for base in config['min_base_volumes']
        }
        """
        Balances used in simulation.
        {
            (str): Base currency name eg. 'BTC'
                (float):  Base currency balance.
        }
        """

        self.data_lock = asyncio.Lock()
        """
        Lock used for modify access to balancer data.
        """

        # Map of methods for rebalance actions.
        if not config['enable_backtest'] and not config['trade_simulate']:
            self._balance_methods = {
                'cleanup': self._cleanup_refill_orders,
                'refill_submit': self._submit_refill_buy,
                'remit_open': self._open_remit_order,
                'remit_submit': self._submit_remit_sell,
                'remit_update': self._update_remit_sell
            }

        else:
            self._balance_methods = {
                'cleanup': lambda _: asyncio.sleep(0),
                'refill_submit': self._sim_submit_refill_buy,
                'remit_open': self._sim_open_remit_order,
                'remit_submit': self._sim_submit_remit_sell,
                'remit_update': self._sim_update_remit_sell
            }

    async def acquire_data_lock(self, waiter: str):
        """
        Acquire the :attr:`Market.data_lock` lock and print a debug message if waiting for the lock.

        Arguments:
            waiter:  The name of the waiting coroutine, used for disambiguation in logging.
        """

        if self.data_lock.locked():
            self.log.debug('{}: waiting for balancer data update in progress.', waiter)

        await self.data_lock.acquire()

    async def sync_pairs(self):
        """
        Synchronize currency pairs.

        For now this just prepares attributes tied to base volumes.
        """

        for base in config['min_base_volumes']:
            await self._prepare_refill_orders(base)
            await self._prepare_remit_orders(base)
            await self._prepare_states(base)

    async def _prepare_refill_orders(self, base: str):
        """
        Prepare refill orders for the specified base currency.

        Ensures that the necessary keys exist in :attr:`refill_orders` before any operations are performed on them.

        Arguments:
            base:  Name of the base currency eg 'BTC'.
        """

        if base not in self.refill_orders:
            self.refill_orders[base] = []

    async def _prepare_remit_orders(self, base: str):
        """
        Prepare remit orders for the specified base currency.

        Ensures that the necessary keys exist in :attr:`remit_orders` before any operations are performed on them.

        Arguments:
            base:  Name of the base currency eg 'BTC'.
        """

        if base not in self.remit_orders:
            self.remit_orders[base] = []

    async def _prepare_states(self, base: str):
        """
        Prepare balancer states for the specified base currency.

        Ensures that the necessary keys exist in :attr:`states` before any operations are performed on them.

        Arguments:
            base:  Name of the base currency eg 'BTC'.
        """

        if base not in self.states:
            self.states[base] = {
                'enable_refill': True
            }

    async def init_sim_balances(self):
        """
        Set :attr:`sim_balances` to initial values.

        Adds the initial trade balance buffer amount to non-trade base currencies and the remainder of the total
        starting balance to the trade base currency. This can only be called after market tick data has been
        initialized.
        """

        if self.sim_balances[config['trade_base']] is not None:
            return

        if not config['sim_enable_balancer']:
            self.sim_balances[config['trade_base']] = config['sim_balance']
            self.save_attr('sim_balances', force=True)
            self.log.debug("Initialized sim_balances: {}", self.sim_balances)
            return

        buffer_size = config['trade_max_size'] * config['trade_balance_buffer']
        init_balance = buffer_size * (1.0 + config['trade_balance_margin'])

        num_base_volumes = 0
        for volume in config['min_base_volumes'].values():
            if volume is not None:
                num_base_volumes += 1

        for base, volume in config['min_base_volumes'].items():
            if base == config['trade_base']:
                self.sim_balances[base] = config['sim_balance'] - init_balance * (num_base_volumes - 1)
            elif volume is not None:
                base_mult = await self.market.get_base_mult(config['trade_base'], base)
                self.sim_balances[base] = init_balance / base_mult

        self.save_attr('sim_balances', force=True)
        self.log.debug("Initialized sim_balances: {}", self.sim_balances)

    async def handle_refill_request(self, base: str, trade_size: float, reserved: float):
        """
        Handle a request to refill the trade balance for a base currency.

        Arguments:
            base:        The base currency eg. 'BTC'.
            reserved:    Amount of the balance to consider reserved eg. from open trades against the base currency.
            trade_size:
        """

        if config['trade_balance_sync']:
            await self._refill_balance_task(base, trade_size, reserved)
        else:
            utils.async_task(self._refill_balance_task(base, trade_size, reserved), loop=common.loop)

    async def _refill_balance_task(self, base: str, size: float, reserved: float):
        """
        Handle any needed cleanup and execution of buy orders to refill the trade balance for a base currency.

        Arguments:
            base:        The base currency eg. 'BTC'.
            size:        Size of the refill in base currency units.
            reserved:    Amount of the balance to consider reserved eg. from open trades against the base currency.
        """

        if not config['trade_balance_sync']:
            await self._balance_methods['cleanup'](base)

        pair = '{}-{}'.format(config['trade_base'], base)
        order_id = await self._balance_methods['refill_submit'](base, size, reserved)

        if order_id is not None:
            self.log.info("{} submitted refill order {}.", base, order_id)

            if config['trade_balance_sync'] and not (config['enable_backtest'] or config['trade_simulate']):
                is_open = True
                timeout = config['refill_sync_timeout']

                while is_open and timeout > 0:
                    timeout -= config['refill_sync_retry']
                    await asyncio.sleep(config['refill_sync_retry'])

                    order = await self.api.get_order(pair, order_id)
                    if order is None:
                        self.log.error("Could not get refill order {}.", order_id)
                    else:
                        is_open = order['open']

                if is_open:
                    self.log.error("Sync refill order {} timed out.", order_id)
                    await self._balance_methods['cleanup'](base)
                else:
                    self.log.info("Completed sync refill order {}.", order_id)

            else:
                self.refill_orders[base].append(order_id)
                self.save_attr('refill_orders', max_depth=1, filter_items=[base])

    async def _cleanup_refill_orders(self, base: str):
        """
        Clean up any past refill orders that have filled or are still pending for the given base currency.

        Any trading fees incurred are added to the trade stats for the currency pair formed by
        ":attr:`config[trade_base]`-:param:`base`".

        Arguments:
            base:  The base currency eg. 'BTC'.
        """

        pair = '{}-{}'.format(config['trade_base'], base)
        base_mult = await self.market.get_pair_base_mult(config['trade_base'], pair)
        remove_indexes = []

        for index, order_id in enumerate(self.refill_orders[base]):
            order = await self.api.get_order(pair, order_id)
            if order is None:
                self.log.error("Could not get refill order {}.", order_id)
                continue

            if order['open']:
                if not await self.api.cancel_order(pair, order_id):
                    self.log.error("Could not cancel unfilled refill order {}.", order_id)
                else:
                    self.log.error("Cancelled unfilled refill order {}.", order_id)
                self.trade_stats[self.time_prefix][pair]['balancer_unfilled'] += 1

            self.trade_stats[self.time_prefix][pair]['balancer_fees'] += order['fees'] * base_mult
            remove_indexes.append(index)

        for index in reversed(remove_indexes):
            del self.refill_orders[base][index]

        self.save_attr('trade_stats', max_depth=2, filter_items=[pair], filter_keys=[self.time_prefix])
        self.save_attr('refill_orders', max_depth=1, filter_items=[base])

    async def _submit_refill_buy(self, base: str, size: float, reserved: float) -> str:
        """
        Submit a new refill order for the given base currency if one is required.

        A limit order is opened to top-up the trade balance for a base currency if it is less than
        size * (1.0 + :attr:`config['trade_balance_margin']`). All values are normalized to
        :attr:`config['trade_base']`.

        Arguments:
            base:      The base currency eg. 'BTC'.
            size:      Size of the refill in trade base currency units.
            reserved:  Amount of the balance to consider reserved eg. from open trades against the base currency.

        Returns:
            The order id if an order was submitted, or None if the trade balance is sufficient, or an error occurred.
        """

        if base == config['trade_base']:
            return None

        if not self.states[base]['enable_refill']:
            self.log.warning("Refills for {} are currently disabled.", base)
            return None

        pair = '{}-{}'.format(config['trade_base'], base)
        min_reserved = config['remit_reserved'][base] if base in config['remit_reserved'] else 0.0
        adjusted_balance, adjusted_req_balance = \
            await self._get_adjusted_trade_balances(base, size, reserved + min_reserved)

        if adjusted_balance is None:
            self.log.error("Could not get available balance for {}", base)
            return None

        if adjusted_balance >= adjusted_req_balance / config['trade_balance_buffer']:
            self.log.info("{} adjusted trade balance of {} is sufficient.", base, adjusted_balance)
            return None

        current_value = self.market.close_values[pair][-1]
        adjusted_size = adjusted_req_balance - adjusted_balance

        min_trade_size = self.market.min_trade_sizes[pair] * (1.0 + config['trade_min_safe_percent'])
        if min_trade_size < self.market.min_safe_trade_size:
            min_trade_size = self.market.min_safe_trade_size

        if adjusted_size < min_trade_size:
            self.log.warning("{} trade size {} too low, using minimum of {}.", pair, adjusted_size, min_trade_size)
            adjusted_size = min_trade_size

        quantity = adjusted_size / current_value
        min_quantity = self.market.min_trade_qtys[pair]

        if quantity < min_quantity:
            self.log.warning("{} trade quantity {} too low, using minimum of {}.", pair, quantity, min_quantity)
            quantity = min_quantity

        limit_value = current_value * (1.0 + config['trade_refill_limit_margin'])
        self.log.info("{} adjusted balance {}, needed {}.", base, adjusted_balance, adjusted_req_balance)

        order_id = await self.api.buy_limit(pair, quantity, limit_value)
        if order_id is None:
            self.log.error("Could not submit refill buy order for {}", base)
            self.trade_stats[self.time_prefix][pair]['balancer_failed'] += 1
            return None

        self.trade_stats[self.time_prefix][pair]['balancer_refills'] += 1
        return order_id

    async def _get_adjusted_trade_balances(self, base: str, trade_size: float, reserved: float=0.0):
        """
        Get the current and required trade balances for a base currency adjusted to the trade base currency.

        Arguments:
            base:      The base currency eg. 'BTC'.
            reserved:  Amount of the balance to consider reserved eg. from open trades against the base currency.

        Returns:
            (tuple):  A tuple containing:
                (float):  The current adjusted balance.
                (float):  The required adjusted balance.
        """

        balance = await self.api.get_balance(base)
        if balance is None:
            return (None, None)

        base_mult = await self.market.get_base_mult(config['trade_base'], base)
        pair = '{}-{}'.format(config['trade_base'], base)

        min_trade_size = self.market.min_trade_sizes[pair] * (1.0 + config['trade_min_safe_percent'])
        if min_trade_size < self.market.min_safe_trade_size:
            min_trade_size = self.market.min_safe_trade_size

        if trade_size < min_trade_size:
            self.log.warning("{} trade size {} too low, using minimum of {}.", pair, trade_size, min_trade_size)
            trade_size = min_trade_size

        adjusted_balance = balance * base_mult - reserved
        buffer_size = trade_size * config['trade_balance_buffer']
        adjusted_req_balance = buffer_size * (1.0 + config['trade_balance_margin'])

        return (adjusted_balance, adjusted_req_balance)

    async def _sim_submit_refill_buy(self, base: str, size: float, reserved: float):
        """
        Simulate a refill of the trade balance for a base currency.

        Arguments:
            base:      The base currency eg. 'BTC'.
            size:      Size of the refill in base currency units.
            reserved:  Amount of the balance to consider reserved eg. from open trades against the base currency.
        """

        if base == config['trade_base']:
            return None

        if not config['sim_enable_balancer']:
            return None

        if not self.states[base]['enable_refill']:
            self.log.warning("Refills for {} are currently disabled.", base)
            return None

        pair = '{}-{}'.format(config['trade_base'], base)
        adjusted_balance, adjusted_req_balance = await self._get_sim_adjusted_trade_balances(base, size, reserved)

        if adjusted_balance >= adjusted_req_balance / config['trade_balance_buffer']:
            self.log.info("{} adjusted trade balance of {} is sufficient.", base, adjusted_balance)
            return None

        current_value = self.market.close_values[pair][-1]
        adjusted_size = adjusted_req_balance - adjusted_balance

        min_trade_size = self.market.min_safe_trade_size
        if adjusted_size < min_trade_size:
            self.log.warning("{} trade size {} too low, using minimum of {}.", pair, adjusted_size, min_trade_size)
            adjusted_size = min_trade_size

        if self.sim_balances[config['trade_base']] < adjusted_size:
            self.log.warning('Cannot simulate refill, insufficient funds.')
            return None

        self.log.info("{} adjusted balance {}, needed {}.", base, adjusted_balance, adjusted_req_balance)

        quantity = adjusted_size / current_value
        fees = quantity * config['trade_fee_percent']

        self.sim_balances[base] += quantity - fees
        self.sim_balances[config['trade_base']] -= adjusted_size
        self.save_attr('sim_balances', force=True)

        adjusted_fees = adjusted_size * config['trade_fee_percent']
        self.trade_stats[self.time_prefix][pair]['balancer_fees'] += adjusted_fees
        self.trade_stats[self.time_prefix][pair]['balancer_refills'] += 1

        return uuid.uuid4().hex

    async def _get_sim_adjusted_trade_balances(self, base: str, trade_size: float, reserved: float=0.0):
        """
        Get the current and required simulated trade balances for a base currency adjusted to the trade base currency.

        Arguments:
            base:        The base currency eg. 'BTC'.
            trade_size:  Needed trade size in base currency units.
            reserved:    Amount of the balance to consider reserved eg. from open trades against the base currency.

        Returns:
            (tuple):  A tuple containing:
                (float):  The current adjusted balance.
                (float):  The required adjusted balance.
        """

        base_mult = await self.market.get_base_mult(config['trade_base'], base)

        min_trade_size = self.market.min_safe_trade_size
        if trade_size < min_trade_size:
            self.log.warning("Trade size {} too low, using minimum of {}.", trade_size, min_trade_size)
            trade_size = trade_size

        adjusted_balance = self.sim_balances[base] * base_mult - reserved
        buffer_size = trade_size * config['trade_balance_buffer']
        adjusted_req_balance = buffer_size * (1.0 + config['trade_balance_margin'])

        return (adjusted_balance, adjusted_req_balance)

    async def update_remit_orders(self, base: str):
        """
        Update remit orders for a base currency.

        Checks orders for stop loss triggers, and processes them as necessary.

        Arguments:
            base:  The base currency eg. 'BTC'.
        """

        remove_indexes = []

        for index, order in enumerate(self.remit_orders[base]):
            if await self._handle_stop_loss(order):
                remove_indexes.append(index)

        for index in reversed(remove_indexes):
            del self.remit_orders[base][index]

        if remove_indexes:
            pair = '{}-{}'.format(config['trade_base'], base)
            self.save_attr('trade_stats', max_depth=2, filter_items=[pair], filter_keys=[self.time_prefix])
            self.save_attr('remit_orders', max_depth=1, filter_items=[base])

    async def _handle_stop_loss(self, order: Dict[str, Any]) -> bool:
        """
        Handle any stop loss sell actions for a remit order.

        Arguments:
            order:  The remit order to check for a deferred push sell.

        Returns:
            (bool):  True if a sell occurred, otherwise false.
        """

        pair = order['pair']
        current_value = self.market.close_values[pair][-1]

        if current_value < order['cutoff_value']:
            stop_percent = config['trade_dynamic_stop_percent'] * order['soft_stops']
            order['stop_value'] *= (1.0 + stop_percent)
            if order['stop_value'] > order['check_value']:
                order['stop_value'] = order['check_value']

        elif current_value < order['check_value']:
            order['stop_value'] *= (1.0 + config['trade_dynamic_stop_percent'])
            if order['stop_value'] > order['check_value']:
                order['stop_value'] = order['check_value']

        if current_value < order['stop_value']:
            utils.async_task(self._remit_sell_task(order, 'REMIT STOP SELL'), loop=common.loop)
            self.trade_stats[self.time_prefix][pair]['balancer_stop_losses'] += 1
            return True

        return False

    async def remit_sell_push(self, base: str):
        """
        Register a remit sell push for a base currency.

        Arguments:
            base:  The base currency eg. 'BTC'.
        """

        remove_indexes = []

        for index, order in enumerate(self.remit_orders[base]):
            current_value = self.market.close_values[order['pair']][-1]

            if current_value >= order['push_target']:
                order['sell_pushes'] += 1
                if order['sell_pushes'] >= config['remit_push_max']:
                    utils.async_task(self._remit_sell_task(order, 'REMIT PUSH SELL'), loop=common.loop)
                    remove_indexes.append(index)

            check_value = current_value * (1.0 - config['remit_stop_check'])
            cutoff_value = current_value * (1.0 - config['remit_stop_cutoff'])
            stop_value = current_value * (1.0 - config['remit_stop_percent'])

            if check_value > order['check_value']:
                order['check_value'] = check_value

            if cutoff_value > order['cutoff_value']:
                order['cutoff_value'] = cutoff_value

            if stop_value > order['stop_value']:
                if stop_value > order['check_value']:
                    order['stop_value'] = order['check_value']
                else:
                    order['stop_value'] = stop_value

            soft_factor = order['sell_pushes'] + len(order['soft_sells'])
            hard_factor = order['sell_pushes'] + len(order['hard_sells'])
            order['push_target'] *= (1.0 - config['trade_dynamic_sell_percent'] * order['sell_pushes'])
            order['soft_target'] *= (1.0 - config['trade_dynamic_sell_percent'] * soft_factor)
            order['hard_target'] *= (1.0 - config['trade_dynamic_sell_percent'] * hard_factor)

        for index in reversed(remove_indexes):
            del self.remit_orders[base][index]

        self.save_attr('remit_orders', max_depth=1, filter_items=[base])

    async def remit_soft_sell(self, base: str, detection_name: str):
        """
        Register a remit soft sell for a base currency.

        Any open remit orders will close with a market sell if their soft sell target value has been met.

        Arguments:
            base:            The base currency eg. 'BTC'.
            detection_name:  Name of the detection that triggered this trade.
        """

        remove_indexes = []

        for index, order in enumerate(self.remit_orders[base]):
            current_value = self.market.close_values[order['pair']][-1]
            order['soft_sells'].append(detection_name)

            if current_value >= order['soft_target']:
                utils.async_task(self._remit_sell_task(order, 'REMIT SOFT SELL'), loop=common.loop)
                remove_indexes.append(index)

            check_value = current_value * (1.0 - config['remit_stop_check'])
            cutoff_value = current_value * (1.0 - config['remit_stop_cutoff'])
            stop_value = current_value * (1.0 - config['remit_stop_percent'])

            if check_value > order['check_value']:
                order['check_value'] = check_value

            if cutoff_value > order['cutoff_value']:
                order['cutoff_value'] = cutoff_value

            if stop_value > order['stop_value']:
                if stop_value > order['check_value']:
                    order['stop_value'] = order['check_value']
                else:
                    order['stop_value'] = stop_value

            soft_factor = order['sell_pushes'] + len(order['soft_sells'])
            hard_factor = order['sell_pushes'] + len(order['hard_sells'])
            order['soft_target'] *= (1.0 - config['trade_dynamic_sell_percent'] * soft_factor)
            order['hard_target'] *= (1.0 - config['trade_dynamic_sell_percent'] * hard_factor)

        for index in reversed(remove_indexes):
            del self.remit_orders[base][index]

        self.save_attr('remit_orders', max_depth=1, filter_items=[base])

    async def remit_hard_sell(self, base: str, detection_name: str):
        """
        Register a remit hard sell for a base currency.

        Any open remit orders will close with a market sell if their hard sell target value has been met.

        Arguments:
            base:            The base currency eg. 'BTC'.
            detection_name:  Name of the detection that triggered this trade.
        """

        remove_indexes = []

        for index, order in enumerate(self.remit_orders[base]):
            current_value = self.market.close_values[order['pair']][-1]
            order['hard_sells'].append(detection_name)

            if current_value >= order['hard_target']:
                utils.async_task(self._remit_sell_task(order, 'REMIT HARD SELL'), loop=common.loop)
                remove_indexes.append(index)

            check_value = current_value * (1.0 - config['remit_stop_check'])
            cutoff_value = current_value * (1.0 - config['remit_stop_cutoff'])
            stop_value = current_value * (1.0 - config['remit_stop_percent'])

            if check_value > order['check_value']:
                order['check_value'] = check_value

            if cutoff_value > order['cutoff_value']:
                order['cutoff_value'] = cutoff_value

            if stop_value > order['stop_value']:
                if stop_value > order['check_value']:
                    order['stop_value'] = order['check_value']
                else:
                    order['stop_value'] = stop_value

            hard_factor = order['sell_pushes'] + len(order['hard_sells'])
            order['hard_target'] *= (1.0 - config['trade_dynamic_sell_percent'] * hard_factor)

        for index in reversed(remove_indexes):
            del self.remit_orders[base][index]

        self.save_attr('remit_orders', max_depth=1, filter_items=[base])

    async def remit_dump_sell(self, base: str):
        """
        Submit a remit sell for a base currency.

        Any open remit orders will close with a market sell.

        Arguments:
            base:             The base currency eg. 'BTC'.
        """

        for order in self.remit_orders[base]:
            utils.async_task(self._remit_sell_task(order, 'REMIT DUMP SELL'), loop=common.loop)

        self.remit_orders[base] = []
        self.save_attr('remit_orders', max_depth=1, filter_items=[base])

    async def remit_hold(self, base: str):
        """
        Register a remit order hold for a base currency.

        A hold decrements the sell push count for a remit order by one, keeping the order open longer before a push sell
        occurs.

        Arguments:
            base:  The base currency eg. 'BTC'.
        """

        for order in self.remit_orders[base]:
            order['sell_pushes'] -= 1
            if order['sell_pushes'] < 0: order['sell_pushes'] = 0

        self.save_attr('remit_orders', max_depth=1, filter_items=[base])

    async def remit_soft_stop(self, base: str, detection_name: str):
        """
        Register a soft stop for a base currency.

        A soft stop enables a stop loss sell to occur for any open remit orders if the base currency's value goes below
        the soft stop value.

        Arguments:
            base:  The base currency eg. 'BTC'.
        """

        params = core.Detector.get_detection_params(detection_name, {
            'weight': 1.0
        })

        for order in self.remit_orders[base]:
            order['soft_stops'] += 1

            stop_percent = config['trade_dynamic_stop_percent'] * order['soft_stops'] * params['weight']
            order['stop_value'] *= (1.0 + stop_percent)
            if order['stop_value'] > order['check_value']:
                order['stop_value'] = order['check_value']

        self.save_attr('remit_orders', max_depth=1, filter_items=[base])

    async def remit_stop_hold(self, base: str, _: int):
        """
        Register a stop hold for a base currency.

        Arguments:
            base:  The base currency eg. 'BTC'.
        """

        for order in self.remit_orders[base]:
            if order['soft_stops'] > 0: order['soft_stops'] -= 1

            stop_percent = config['trade_dynamic_stop_percent'] * order['soft_stops']
            order['stop_value'] *= (1.0 - stop_percent)
            if order['stop_value'] > order['check_value']:
                order['stop_value'] = order['check_value']

        self.save_attr('remit_orders', max_depth=1, filter_items=[base])

    async def handle_remit_request(self, base: str, orig_value: float, reserved: float, proceeds: float):
        """
        Handle a request to remit excess trade balance for a base currency.

        Remit orders are treated like open trades, and become sell orders if triggered by a sell condition.

        If :data:`config['trade_balance_sync']` is True, remit orders are always sold immediately.

        Arguments:
            base:        The base currency eg. 'BTC'.
            orig_value:
            reserved:    Amount of the balance to consider reserved eg. from open trades against the base currency.
            proceeds:    Proceeds of the previous sell, used to calculate stop targets.
        """

        reserved += await self._get_remit_orders_value(base)
        order = await self._balance_methods['remit_open'](base, orig_value, reserved)

        if order is not None:
            self.remit_orders[base].append(order)
            self.log.info("{} tracked remit order for {} units.", base, order['quantity'])
            self.save_attr('remit_orders', max_depth=1, filter_items=[base])

            if proceeds < 0.0:
                utils.async_task(self._remit_sell_task(order, 'REMIT STOP SELL'), loop=common.loop)
                self.trade_stats[self.time_prefix][order['pair']]['balancer_stop_losses'] += 1

    async def _open_remit_order(self, base: str, orig_value: float, reserved: float) -> str:
        """
        Open a new remit order for the given base currency if one is required.

        Arguments:
            base:  The base currency eg. 'BTC'.
            orig_value:
            reserved:  Amount of the balance to consider reserved eg. from open trades against the base currency.
            proceeds:  Proceeds of the previous sell, used to calculate stop targets.

        Returns:
            The remit order dict, or None if the trade balance or order size is to low for remit, or an API
            error occurred.
        """

        if base == config['trade_base']:
            return None

        pair = '{}-{}'.format(config['trade_base'], base)
        min_reserved = config['remit_reserved'][base] if base in config['remit_reserved'] else 0.0
        adjusted_balance, adjusted_req_balance = await self._get_adjusted_trade_balances(base, reserved + min_reserved)

        if adjusted_balance is None:
            self.log.error("Could not get available balance for {}", base)
            return None

        adjusted_size = adjusted_balance if config['trade_balance_sync'] else adjusted_balance - adjusted_req_balance

        if adjusted_size <= 0:
            self.log.info("{} adjusted balance of {} is too low for remit.", base, adjusted_balance)
            return None

        min_trade_size = self.market.min_trade_sizes[pair] * (1.0 + config['trade_min_safe_percent'])
        if min_trade_size < self.market.min_safe_trade_size:
            min_trade_size = self.market.min_safe_trade_size

        if adjusted_size < min_trade_size:
            self.log.info("{} remit order size of {} is too small.", base, adjusted_size)
            return None

        current_value = self.market.close_values[pair][-1]
        quantity = adjusted_size / current_value
        min_quantity = self.market.min_trade_qtys[pair]

        if quantity < min_quantity:
            self.log.info("{} trade quantity {} too low for remit, need {} minimum.", pair, quantity, min_quantity)
            return None

        stop_base = current_value if orig_value < current_value else orig_value
        stop_value = stop_base * (1.0 - config['remit_stop_percent'])
        cutoff_value = stop_base * (1.0 - config['remit_stop_cutoff'])
        check_value = stop_base * (1.0 - config['remit_stop_check'])

        order = {
            'pair': pair,
            'open_value': current_value,
            'close_value': current_value,
            'open_time': self.market.close_times[pair][-1],
            'quantity': quantity,
            'fees': 0.0,
            'sell_pushes': 0,
            'soft_stops': 0,
            'soft_sells': [],
            'hard_sells': [],
            'push_target': orig_value * (1.0 + config['remit_push_sell_percent']),
            'soft_target': orig_value * (1.0 + config['remit_soft_sell_percent']),
            'hard_target': orig_value * (1.0 + config['remit_hard_sell_percent']),
            'stop_value': stop_value,
            'cutoff_value': cutoff_value,
            'check_value': check_value
        }

        text = 'REMIT OPEN'
        await self.reporter.send_alert(pair, order, prefix=text, color=config['buy_color'], sound=config['buy_sound'])

        return order

    async def _sim_open_remit_order(self, base: str, orig_value: float, reserved: float) -> str:
        """
        Open a new simulated remit order for the given base currency if one is required.

        Arguments:
            base:        The base currency eg. 'BTC'.
            orig_value:
            reserved:    Amount of the balance to consider reserved eg. from open trades against the base currency.
            proceeds:    Proceeds of the previous sell, used to calculate targets.

        Returns:
            The remit order dict, or None if the trade balance or order size is to low for remit, or an API
            error occurred.
        """

        if base == config['trade_base']:
            return None

        if not config['sim_enable_balancer']:
            return None

        pair = '{}-{}'.format(config['trade_base'], base)
        adjusted_balance, adjusted_req_balance = \
            await self._get_sim_adjusted_trade_balances(base, config['trade_max_size'], reserved)

        if adjusted_balance is None:
            self.log.error("Could not get available balance for {}", base)
            return None

        adjusted_size = adjusted_balance if config['trade_balance_sync'] else adjusted_balance - adjusted_req_balance

        if adjusted_size <= 0:
            self.log.info("{} adjusted balance of {} is too low for remit.", base, adjusted_balance)
            return None

        if adjusted_size < self.market.min_safe_trade_size:
            self.log.info("{} remit order size of {} is too small.", base, adjusted_size)
            return None

        current_value = self.market.close_values[pair][-1]
        quantity = adjusted_size / current_value

        stop_base = current_value if orig_value < current_value else orig_value
        stop_value = stop_base * (1.0 - config['remit_stop_percent'])
        cutoff_value = stop_base * (1.0 - config['remit_stop_cutoff'])
        check_value = stop_base * (1.0 - config['remit_stop_check'])

        order = {
            'pair': pair,
            'open_value': current_value,
            'close_value': current_value,
            'open_time': self.market.close_times[pair][-1],
            'quantity': quantity,
            'fees': 0.0,
            'sell_pushes': 0,
            'soft_stops': 0,
            'soft_sells': [],
            'hard_sells': [],
            'push_target': orig_value * (1.0 + config['remit_push_sell_percent']),
            'soft_target': orig_value * (1.0 + config['remit_soft_sell_percent']),
            'hard_target': orig_value * (1.0 + config['remit_hard_sell_percent']),
            'stop_value': stop_value,
            'cutoff_value': cutoff_value,
            'check_value': check_value
        }

        text = 'REMIT OPEN'
        await self.reporter.send_alert(pair, order, prefix=text, color=config['buy_color'], sound=config['buy_sound'])

        return order

    async def _remit_sell_task(self, order: Dict[str, Any], label: str):
        """
        Handle the sell order, tracking, update, and registering of an open remit order.

        Arguments:
            order:  The remit order to sell on.
        """

        order_id = await self._balance_methods['remit_submit'](order)

        if order_id is not None:
            await self._balance_methods['remit_update'](order, order_id)
            await self._register_remit_sell(order, label)

    async def _submit_remit_sell(self, order: Dict[str, Any]) -> str:
        """
        Submit a market sell order for the given remit order.

        TODO: Also use min trade values returned by the API if available.

        Arguments:
            order:  The remit order to sell on.

        Returns
            The UUID of the sell order, or None if not enough trade balance exists for the order or an API error
            occurred.
        """

        pair = order['pair']
        quote = pair.split('-')[1]

        current_value = self.market.close_values[pair][-1]
        quantity = order['quantity']
        size = current_value * quantity

        adjusted_balance, adjusted_req_balance = await self._get_adjusted_trade_balances(quote, size)

        if adjusted_balance is None:
            self.log.error("Could not get available balance for {}", quote)
            return None

        if config['trade_balance_sync']:
            adjusted_req_balance = 0.0

        if adjusted_balance - size < adjusted_req_balance:
            size = adjusted_balance - adjusted_req_balance
            quantity = size / current_value

        min_trade_size = self.market.min_trade_sizes[pair] * (1.0 + config['trade_min_safe_percent'])
        if min_trade_size < self.market.min_safe_trade_size:
            min_trade_size = self.market.min_safe_trade_size

        if size < min_trade_size:
            self.log.info("{} adjusted balance of {} is now too low for remit.", quote, adjusted_balance)
            return None

        min_size = self.market.min_trade_sizes[pair]
        if min_size < self.market.min_trade_size:
            min_size = self.market.min_trade_size

        min_value = min_size / quantity

        order_id = await self.api.sell_limit(pair, quantity, min_value)
        if order_id is None:
            self.log.error("{} could not submit market sell for remit order.", quote)

        return order_id

    async def _sim_submit_remit_sell(self, order: Dict[str, Any]) -> str:
        """
        Submit a simulated market sell order for the given remit order.

        Arguments:
            order:  The remit order to sell on.

        Returns
            The UUID of the sell order, or None if not enough trade balance exists for the order or an API error
            occurred.
        """

        if not config['sim_enable_balancer']:
            return None

        pair = order['pair']
        quote = pair.split('-')[1]

        current_value = self.market.close_values[pair][-1]
        quantity = order['quantity']
        size = current_value * quantity

        adjusted_balance, adjusted_req_balance = await self._get_sim_adjusted_trade_balances(quote, size)

        if config['trade_balance_sync']:
            adjusted_req_balance = 0.0

        if adjusted_balance - size < adjusted_req_balance:
            size = adjusted_balance - adjusted_req_balance

        if size < self.market.min_safe_trade_size:
            self.log.info("{} adjusted balance of {} is now too low for remit.", quote, adjusted_balance)
            return None

        if self.sim_balances[quote] < quantity:
            self.log.warning('Cannot simulate remit, insufficient funds.')
            return None

        fees = size * config['trade_fee_percent']
        order['fees'] = fees

        self.sim_balances[quote] -= quantity
        self.sim_balances[config['trade_base']] += size - fees
        self.save_attr('sim_balances', force=True)

        return uuid.uuid4().hex

    async def _update_remit_sell(self, order: Dict[str, Any], order_id: str):
        """
        Track a remit sell order until closing and update it with the closing values.

        Arguments:
            order:     The remit order to update.
            order_id:  The order id of the sell order to track.
        """

        pair = order['pair']
        success = False
        is_open = True

        while is_open:
            await asyncio.sleep(config['trade_update_secs'])

            order = await self.api.get_order(pair, order_id)
            if order is None:
                self.log.error("{} could not track remit order {}!", pair, order_id)
                success = False
                is_open = False

            else:
                success = True
                is_open = order['open']
                unit_value = order['value']
                fees = order['fees']

                self.log.info("{} remit order {}: open {}, close value {}.", pair, order_id, is_open, unit_value)

        if not success:
            unit_value = self.market.close_values[pair][-1]
            fees = order['quantity'] * unit_value * config['trade_fee_percent']

        order['close_time'] = self.market.close_times[pair][-1]
        order['close_value'] = unit_value
        order['fees'] += fees

        base = pair.split('-')[0]
        self.save_attr('remit_orders', max_depth=1, filter_items=[base])

    async def _sim_update_remit_sell(self, order: Dict[str, Any], order_id: str):
        """
        Update a simulated remit order with closing values.

        Arguments:
            order:     The remit order to update.
            order_id:  The order id of the sell order to track.
        """

        pair = order['pair']
        unit_value = self.market.close_values[pair][-1]
        commission = order['quantity'] * unit_value * config['trade_fee_percent']

        order['close_time'] = self.market.close_times[pair][-1]
        order['close_value'] = unit_value
        order['fees'] += commission

        base = pair.split('-')[0]
        self.save_attr('remit_orders', max_depth=1, filter_items=[base])

    async def _register_remit_sell(self, order: Dict[str, Any], label: str):
        """
        Register a closed remit sell.

        Updates trade statistics and outputs alerts and snapshots for the remit sell.

        FIXME: Sometimes 'close_value' does not get updated before this method is called.

        Arguments:
            order:  The remit order to register.
        """

        pair = order['pair']
        base_mult = await self.market.get_pair_base_mult(config['trade_base'], pair)
        proceeds = order['quantity'] * (order['close_value'] - order['open_value'])
        net_proceeds = proceeds * base_mult - order['fees'] * base_mult
        current_value = self.market.close_values[pair][-1]

        metadata = order.copy()
        metadata['followed'] = [{
            'name': 'REMIT OPEN',
            'time': order['open_time'],
            'delta': current_value - order['open_value'],
        }]

        if net_proceeds > 0.0:
            self.trade_stats[self.time_prefix][pair]['balancer_profit'] += net_proceeds
            color = config['sell_high_color']
            sound = config['sell_high_sound']
            text = label + ' HIGH'
        else:
            self.trade_stats[self.time_prefix][pair]['balancer_loss'] -= net_proceeds
            color = config['sell_low_color']
            sound = config['sell_low_sound']
            text = label + ' LOW'

        await self.reporter.send_alert(pair, metadata, prefix=text, color=color, sound=sound)

        self.trade_stats[self.time_prefix][order['pair']]['balancer_remits'] += 1
        self.trade_stats[self.time_prefix][pair]['balancer_fees'] += order['fees'] * base_mult
        self.save_attr('trade_stats', max_depth=2, filter_items=[pair], filter_keys=[self.time_prefix])

    async def _get_remit_orders_value(self, base: str) -> float:
        """
        Get the total value of all open remit orders for a base currency.

        Arguments:
            base:  The base currency eg. 'BTC'.

        Returns:
            The total open remit orders value.
        """

        total = 0.0

        if base in self.remit_orders:
            for order in self.remit_orders[base]:
                total += order['open_value'] * order['quantity']

        base_mult = await self.market.get_base_mult(config['trade_base'], base)
        return total / base_mult

    async def handle_pullout_request(self, base: str):
        """
        Handle a request to pull out all trade balance for a base currency.

        Arguments:
            base:  The base currency eg. 'BTC'.
        """

        if base == config['trade_base']:
            return None

        self.remit_orders[base] = []
        pair = '{}-{}'.format(config['trade_base'], base)
        adjusted_balance, _ = await self._get_adjusted_trade_balances(base, 0.0)

        if adjusted_balance is None:
            self.log.error("Could not get available balance for {}", base)
            return

        min_trade_size = self.market.min_trade_sizes[pair] * (1.0 + config['trade_min_safe_percent'])
        if min_trade_size < self.market.min_safe_trade_size:
            min_trade_size = self.market.min_safe_trade_size

        if adjusted_balance < min_trade_size:
            self.log.info("{} adjusted trade size of {} is too small.", base, adjusted_balance)
            return

        current_value = self.market.close_values[pair][-1]
        quantity = adjusted_balance / current_value
        min_quantity = self.market.min_trade_qtys[pair]

        if quantity < min_quantity:
            self.log.info("{} trade quantity {} too low, need {} minimum.", pair, quantity, min_quantity)
            return

        min_size = self.market.min_trade_sizes[pair]
        if min_size < self.market.min_trade_size:
            min_size = self.market.min_trade_size

        min_value = min_size / quantity
        order_id = await self.api.sell_limit(pair, quantity, min_value)
        if order_id is None:
            self.log.error("{} could not submit market sell for pullout.", base)
