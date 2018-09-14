# -*- coding: utf-8 -*-

# Copyright (c) A 2017 Adam M. Rafuse - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited.
# Proprietary and confidential.

"""
Common methods and classes.
"""

__author__ = 'Adam Rafuse <$(echo nqnz.enshfr#tznvy.pbz | tr a-z# n-za-m@)>'
__all__ = ['config']

import json
import defaults

timescale_mult = defaults.TICK_INTERVAL_SECS / 60

config = {
    'app_debug': defaults.APP_DEBUG,
    'app_multicore': defaults.APP_MULTICORE,
    'app_processes': defaults.APP_PROCESSES,
    'app_max_interrupts': defaults.APP_MAX_INTERRUPTS,
    'app_thread_sleep_secs': defaults.APP_THREAD_SLEEP_SECS,
    'app_log_level': defaults.APP_LOG_LEVEL,
    'app_node_index': defaults.APP_NODE_INDEX,
    'app_node_max': defaults.APP_NODE_MAX,
    'app_path': defaults.APP_PATH,
    'user_path': defaults.USER_PATH,
    'node_dir': defaults.NODE_DIR,
    'data_dir': defaults.DATA_DIR,
    'time_format': defaults.TIME_FORMAT,
    'http_timeout_secs': defaults.HTTP_TIMEOUT_SECS,
    'http_read_timeout_secs': defaults.HTTP_READ_TIMEOUT_SECS,
    'http_max_retries': defaults.HTTP_MAX_RETRIES,
    'http_max_backoff_secs': defaults.HTTP_MAX_BACKOFF_SECS,
    'http_host_conn_limit': defaults.HTTP_HOST_CONN_LIMIT,
    'api_initial_rate_limit_secs': defaults.API_INITIAL_RATE_LIMIT_SECS,
    'api_max_retries': defaults.API_MAX_RETRIES,
    'enable_sound': defaults.ENABLE_SOUND,
    'alert_sound': defaults.ALERT_SOUND,
    'buy_sound': defaults.BUY_SOUND,
    'sell_low_sound': defaults.SELL_LOW_SOUND,
    'sell_high_sound': defaults.SELL_HIGH_SOUND,
    'critical_sound': defaults.CRITICAL_SOUND,
    'play_sound_cmd_linux': defaults.PLAY_SOUND_CMD_LINUX,
    'play_sound_cmd_windows': defaults.PLAY_SOUND_CMD_WINDOWS,
    'play_sound_cmd_darwin': defaults.PLAY_SOUND_CMD_DARWIN,
    'play_sound_cmd_default': defaults.PLAY_SOUND_CMD_DEFAULT,
    'alert_color': defaults.ALERT_COLOR,
    'buy_color': defaults.BUY_COLOR,
    'sell_low_color': defaults.SELL_LOW_COLOR,
    'sell_high_color': defaults.SELL_HIGH_COLOR,
    'enable_charts': defaults.ENABLE_CHARTS,
    'chart_format': defaults.CHART_FORMAT,
    'chart_show_close': defaults.CHART_SHOW_CLOSE,
    'chart_age': defaults.CHART_AGE,
    'chart_width': defaults.CHART_WIDTH,
    'chart_height': defaults.CHART_HEIGHT,
    'enable_snapshots': defaults.ENABLE_SNAPSHOTS,
    'snapshot_format': defaults.SNAPSHOT_FORMAT,
    'tick_interval_secs': defaults.TICK_INTERVAL_SECS,
    'tick_gap_max': defaults.TICK_GAP_MAX,
    'pairs_refresh_secs': defaults.PAIRS_UPDATE_SECS,
    'pairs_greylist_secs': defaults.PAIRS_GREYLIST_SECS,
    'follow_up_secs': defaults.FOLLOW_UP_SECS,
    'follow_up_check_secs': defaults.FOLLOW_UP_CHECK_SECS,
    'trade_update_secs': defaults.TRADE_UPDATE_SECS,
    'output_rollover_secs': defaults.OUTPUT_ROLLOVER_SECS,
    'back_refresh_min_secs': defaults.BACK_REFRESH_MIN_SECS,
    'back_refresh_max_per_tick': defaults.BACK_REFRESH_MAX_PER_TICK,
    'trade_base': defaults.TRADE_BASE,
    'base_pairs': defaults.BASE_PAIRS,
    'min_base_volumes': defaults.MIN_BASE_VOLUMES,
    'pair_prefer_filter': defaults.PAIR_PREFER_FILTER,
    'pair_change_filter': defaults.PAIR_CHANGE_FILTER,
    'pair_dip_filter': defaults.PAIR_DIP_FILTER,
    'pair_change_min': defaults.PAIR_CHANGE_MIN,
    'pair_change_max': defaults.PAIR_CHANGE_MAX,
    'pair_change_dip': defaults.PAIR_CHANGE_DIP,
    'pair_change_cutoff': defaults.PAIR_CHANGE_CUTOFF,
    'max_pairs': defaults.MAX_PAIRS,
    'forecast_window': defaults.FORECAST_WINDOW,
    'forecast_num': defaults.FORECAST_NUM,
    'forecast_weight': defaults.FORECAST_WEIGHT,
    'enable_backtest': defaults.ENABLE_BACKTEST,
    'backtest_limit_pairs': defaults.BACKTEST_LIMIT_PAIRS,
    'backtest_refresh_pairs': defaults.BACKTEST_REFRESH_PAIRS,
    'backtest_window': defaults.BACKTEST_WINDOW,
    'backtest_offset': defaults.BACKTEST_OFFSET,
    'backtest_multicore': defaults.BACKTEST_MULTICORE,
    'backtest_split_map': defaults.BACKTEST_SPLIT_MAP,
    'backtest_processes': defaults.BACKTEST_PROCESSES,
    'backtest_follow_up_ticks': defaults.BACKTEST_FOLLOW_UP_TICKS,
    'backtest_data_dir': defaults.BACKTEST_DATA_DIR,
    'backtest_max_begin_skew': defaults.BACKTEST_MAX_BEGIN_SKEW,
    'ma_windows': defaults.MA_WINDOWS,
    'vdma_windows': defaults.VDMA_WINDOWS,
    'ema_windows': defaults.EMA_WINDOWS,
    'ema_trade_base_only': defaults.EMA_TRADE_BASE_ONLY,
    'ma_filter': defaults.MA_FILTER,
    'ma_filter_window': defaults.MA_FILTER_WINDOW,
    'ma_filter_order': defaults.MA_FILTER_ORDER,
    'enable_bbands': defaults.ENABLE_BBANDS,
    'bband_ma': defaults.BBAND_MA,
    'bband_mult': defaults.BBAND_MULT,
    'coin_exchange': defaults.COIN_EXCHANGE,
    'detection_min_follow_secs': defaults.DETECTION_MIN_FOLLOW_SECS,
    'detection_max_follow_secs': defaults.DETECTION_MAX_FOLLOW_SECS,
    'detection_restore_timeout_secs': defaults.DETECTION_RESTORE_TIMEOUT_SECS,
    'detection_flash_crash_sens': defaults.DETECTION_FLASH_CRASH_SENS,
    'trade_simulate': defaults.TRADE_SIMULATE,
    'trade_min_size': defaults.TRADE_MIN_SIZE,
    'trade_max_size': defaults.TRADE_MAX_SIZE,
    'trade_size_mult': defaults.TRADE_SIZE_MULT,
    'trade_min_size_btc': defaults.TRADE_MIN_SIZE_BTC,
    'trade_min_safe_percent': defaults.TRADE_MIN_SAFE_PERCENT,
    'trade_fee_percent': defaults.TRADE_FEE_PERCENT,
    'trade_buy_limit_margin': defaults.TRADE_BUY_LIMIT_MARGIN,
    'trade_buy_retry_margin': defaults.TRADE_BUY_RETRY_MARGIN,
    'trade_balance_margin': defaults.TRADE_BALANCE_MARGIN,
    'trade_balance_buffer': defaults.TRADE_BALANCE_BUFFER,
    'trade_balance_sync': defaults.TRADE_BALANCE_SYNC,
    'trade_refill_limit_margin': defaults.TRADE_REFILL_LIMIT_MARGIN,
    'trade_push_sell_percent': defaults.TRADE_PUSH_SELL_PERCENT,
    'trade_soft_sell_percent': defaults.TRADE_SOFT_SELL_PERCENT,
    'trade_hard_sell_percent': defaults.TRADE_HARD_SELL_PERCENT,
    'trade_dynamic_sell_percent': defaults.TRADE_DYNAMIC_SELL_PERCENT * timescale_mult,
    'trade_stop_percent': defaults.TRADE_STOP_PERCENT,
    'trade_stop_cutoff': defaults.TRADE_STOP_CUTOFF,
    'trade_stop_check': defaults.TRADE_STOP_CHECK,
    'trade_dynamic_stop_percent': defaults.TRADE_DYNAMIC_STOP_PERCENT * timescale_mult,
    'trade_hard_stop_threshold': defaults.TRADE_HARD_STOP_THRESHOLD,
    'trade_deferred_push_sell': defaults.TRADE_DEFERRED_PUSH_SELL,
    'trade_deferred_soft_sell': defaults.TRADE_DEFERRED_SOFT_SELL,
    'trade_deferred_hard_sell': defaults.TRADE_DEFERRED_HARD_SELL,
    'trade_push_max': defaults.TRADE_PUSH_MAX,
    'trade_soft_max': defaults.TRADE_SOFT_MAX,
    'trade_rebuy_max': defaults.TRADE_REBUY_MAX,
    'trade_rebuy_push_penalty': defaults.TRADE_REBUY_PUSH_PENALTY,
    'trade_use_indicators': defaults.TRADE_USE_INDICATORS,
    'trade_garbage_collect': defaults.TRADE_GARBAGE_COLLECT,
    'remit_reserved': defaults.REMIT_RESERVED,
    'remit_push_sell_percent': defaults.REMIT_PUSH_SELL_PERCENT,
    'remit_soft_sell_percent': defaults.REMIT_SOFT_SELL_PERCENT,
    'remit_hard_sell_percent': defaults.REMIT_HARD_SELL_PERCENT,
    'remit_push_max': defaults.REMIT_PUSH_MAX,
    'remit_stop_percent': defaults.REMIT_STOP_PERCENT,
    'remit_stop_cutoff': defaults.REMIT_STOP_CUTOFF,
    'remit_stop_check': defaults.REMIT_STOP_CHECK,
    'refill_sync_timeout': defaults.REFILL_SYNC_TIMEOUT,
    'refill_sync_retry': defaults.REFILL_SYNC_RETRY,
    'sim_balance': defaults.SIM_BALANCE,
    'sim_watch_trade_base_pairs': defaults.SIM_WATCH_TRADE_BASE_PAIRS,
    'sim_enable_balances': defaults.SIM_ENABLE_BALANCES,
    'sim_enable_balancer': defaults.SIM_ENABLE_BALANCER,
    'enable_rsi': defaults.ENABLE_RSI,
    'rsi_window': defaults.RSI_WINDOW,
    'rsi_size': defaults.RSI_SIZE,
    'rsi_overbought': defaults.RSI_OVERBOUGHT,
    'rsi_oversold': defaults.RSI_OVERSOLD,
    'detections': defaults.DETECTIONS
}
"""
Shared configuration.
"""

with open('secrets.json') as secrets_file:
    config.update(json.load(secrets_file))