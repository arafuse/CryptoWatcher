#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (c) 2017 Adam M. Rafuse - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential

"""
Analyze stats dumps.
"""

import sys
import json
import argparse

sys.path.insert(0, 'lib/')

import utils
import defaults

from configuration import config

NODE_DIR = 'default/'

config.update({
    'output_log': defaults.USER_PATH + NODE_DIR + defaults.TOOL_OUTPUT_LOG,
    'debug_log': defaults.USER_PATH + NODE_DIR + defaults.TOOL_DEBUG_LOG,
    'error_log': defaults.USER_PATH + NODE_DIR + defaults.TOOL_ERROR_LOG,
    'monitor_path': defaults.USER_PATH + NODE_DIR + 'monitor/' + defaults.STATE_DIR,
    'backtest_path': defaults.USER_PATH + NODE_DIR + 'backtest/' + defaults.STATE_DIR,
})

log = utils.logging.ThreadedLogger(level=config['app_log_level'], logger_level=utils.logging.INFO, debug_verbosity=2,
                                   filename=config['output_log'], debug_filename=config['debug_log'],
                                   error_filename=config['error_log'], module_name=__name__)
"""
Module logger.
"""

SIMPLE_STATS = {
    'buys': 0,
    'rebuys': 0,
    'sells': 0,
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
    'unfilled': 0,
    'unfilled_partial': 0,
    'unfilled_quantity': 0.0,
    'unfilled_value': 0.0,
    'failed': 0,
}

BASE_CURRENCIES = [base for base in config['min_base_volumes']]


def load_stats():
    """
    Load stats.
    """

    single_exclude = BASE_CURRENCIES + ['global']
    trade_stats = {'monitor': {}, 'backtest': {}}

    trade_stats['monitor']['single'] = \
        utils.io.load_split('trade_stats', config['monitor_path'], max_depth=2, exclude_items=single_exclude)
    trade_stats['backtest']['single'] = \
        utils.io.load_split('trade_stats', config['backtest_path'], max_depth=2, exclude_items=single_exclude)
    trade_stats['monitor']['base'] = \
        utils.io.load_split('trade_stats', config['monitor_path'], max_depth=2, filter_items=BASE_CURRENCIES)
    trade_stats['backtest']['base'] =\
        utils.io.load_split('trade_stats', config['backtest_path'], max_depth=2, filter_items=BASE_CURRENCIES)
    trade_stats['monitor']['global'] = \
        utils.io.load_split('trade_stats', config['monitor_path'], max_depth=2, filter_items=['global'])
    trade_stats['backtest']['global'] = \
        utils.io.load_split('trade_stats', config['backtest_path'], max_depth=2, filter_items=['global'])

    for mode in trade_stats:
        for key in ['single', 'base', 'global']:
            if trade_stats[mode][key] is None: trade_stats[mode][key] = {}
            for prefix in trade_stats[mode][key]:
                if trade_stats[mode][key][prefix] is None: trade_stats[mode][key][prefix] = {}

    return trade_stats


def get_singles(trade_stats):
    """
    Get singles.
    """

    singles = {'monitor': {}, 'backtest': {}}

    for mode in trade_stats:
        singles[mode] = trade_stats[mode]['single']

    return singles


def get_summary(trade_stats):
    """
    Get summary.
    """

    summary = {'monitor': {}, 'backtest': {}}
    num_open = {}

    for mode in summary:
        summary[mode]['base'] = {}
        for base in BASE_CURRENCIES:
            summary[mode]['base'][base] = {
                'most_open': [],
                'net_profit': 0.0,
                'profit_loss_ratio': 0.0,
                'profit_per_sell': 0.0
            }
            summary[mode]['base'][base].update(SIMPLE_STATS)

        for key in ['global', 'aggregate']:
            summary[mode][key] = {
                'most_open': [],
                'net_profit': 0.0,
                'profit_loss_ratio': 0.0,
                'profit_per_sell': 0.0
            }
            summary[mode][key].update(SIMPLE_STATS)

    for mode in trade_stats:
        for time_prefix in trade_stats[mode]['single']:
            agg_most_open = 0

            for pair, stats in trade_stats[mode]['single'][time_prefix].items():
                base = pair.split('-')[0]
                for stat in SIMPLE_STATS:
                    summary[mode]['aggregate'][stat] += stats[stat]
                    summary[mode]['base'][base][stat] += stats[stat]

                agg_most_open += stats['most_open']

                if pair in num_open:
                    num_open[pair].extend(stats['num_open'])
                else:
                    num_open[pair] = []

            summary[mode]['aggregate']['most_open'].append(agg_most_open)

            for stats in trade_stats[mode]['global'][time_prefix].values():
                for stat in SIMPLE_STATS:
                    summary[mode]['global'][stat] += stats[stat]
                summary[mode]['global']['most_open'].append(stats['most_open'])

        for key in ['aggregate', 'global']:
            summary[mode][key]['net_profit'] = (
                summary[mode][key]['total_profit'] + summary[mode][key]['balancer_profit'] -
                summary[mode][key]['total_loss'] - summary[mode][key]['balancer_loss'] -
                summary[mode][key]['total_fees'] - summary[mode][key]['balancer_fees']
            )

            total_sells = summary[mode][key]['sells'] +summary[mode][key]['soft_stop_sells']
            if total_sells > 0:
                summary[mode][key]['profit_per_sell'] = (
                    summary[mode][key]['net_profit'] / total_sells
                )

            if summary[mode][key]['total_loss'] != 0.0:
                summary[mode][key]['profit_loss_ratio'] = (
                    (summary[mode][key]['total_profit'] + summary[mode][key]['balancer_profit'] -
                     summary[mode][key]['total_fees'] - summary[mode][key]['balancer_fees']) /
                    (summary[mode][key]['total_loss'] + summary[mode][key]['balancer_loss'])
                )                

        for base in BASE_CURRENCIES:
            summary[mode]['base'][base]['net_profit'] = (
                summary[mode]['base'][base]['total_profit'] + summary[mode]['base'][base]['balancer_profit'] -
                summary[mode]['base'][base]['total_loss'] - summary[mode]['base'][base]['balancer_loss'] -
                summary[mode]['base'][base]['total_fees'] - summary[mode]['base'][base]['balancer_fees']
            )

            if summary[mode]['base'][base]['total_loss'] != 0.0:
                summary[mode]['base'][base]['profit_loss_ratio'] = (
                    (summary[mode]['base'][base]['total_profit'] + summary[mode]['base'][base]['balancer_profit'] -
                     summary[mode]['base'][base]['total_fees'] - summary[mode]['base'][base]['balancer_fees']) /
                    (summary[mode]['base'][base]['total_loss'] + summary[mode]['base'][base]['balancer_loss'])
                )

            total_sells = summary[mode][key]['sells'] + summary[mode][key]['soft_stop_sells']
            if total_sells > 0:
                summary[mode][key]['profit_per_sell'] = (
                    summary[mode][key]['net_profit'] / total_sells
                )                

    return summary


def main():
    """
    Main entry point.
    """

    trade_stats = load_stats()
    summary = get_summary(trade_stats)

    sim_balances = utils.io.load_split('sim_balances', config['backtest_path'])
    base_rates = utils.io.load_split('base_rates', config['backtest_path'])
    trades = utils.io.load_split('trades', config['backtest_path'], max_depth=1)

    print(json.dumps(summary, indent=4) + '\n')
    
    remaining_balance = 0.0

    if sim_balances is not None and base_rates is not None:
        print(json.dumps(sim_balances, indent=4))

        for base in sim_balances:
            if base == config['trade_base']:
                remaining_balance += sim_balances[base]
            else:
                base_pair = '{}-{}'.format(config['trade_base'], base)
                remaining_balance += sim_balances[base] * base_rates[base_pair]

    open_trade_balance = 0.0

    for pair in trades:
        for trade in trades[pair]['open']:
            if 'last_push_value' in trade:
                last_value = trade['last_push_value']
            else:
                last_value = trade['open_value']
            open_trade_balance += trade['quantity'] * last_value

    open_trade_balance *= 1.0 - config['trade_fee_percent']
    total_balance = remaining_balance + open_trade_balance
    real_profit = total_balance - config['sim_balance']

    print("\nRemaining sim balance: {}".format(remaining_balance))
    print("Open trade sim balance: {}".format(open_trade_balance))
    print("Total sim balance: {}".format(total_balance))
    print("Actual profit: {}".format(real_profit))

    for mode in summary:
        if summary[mode]['global']['most_open']:
            max_open = max(summary[mode]['global']['most_open'])
            if max_open > 0:
                real_profit = total_balance - config['sim_balance']
                profit_per_max_open = real_profit / max_open
                print("Profit per max open ({}): {}".format(mode, profit_per_max_open))


if __name__ == '__main__':
    log.start()
    main()
    log.stop()
