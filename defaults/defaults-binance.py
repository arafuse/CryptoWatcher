# -*- coding: utf-8 -*-

# Copyright (c) A 2017 Adam M. Rafuse - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential

import os
import multiprocessing

import utils
import detections


"""
Application defaults.
"""

__author__ = 'Adam Rafuse <$(echo nqnz.enshfr#tznvy.pbz | tr a-z# n-za-m@)>'

# App parameters
APP_DEBUG = True
APP_MULTICORE = False
APP_PROCESSES = 1
APP_MAX_INTERRUPTS = 5
APP_THREAD_SLEEP_SECS = 0.15
APP_LOG_LEVEL = utils.logging.DEBUG if APP_DEBUG else utils.logging.INFO
APP_NODE_INDEX = None
APP_NODE_MAX = 2

# Directories and files.
APP_PATH = os.path.dirname(os.path.realpath(__file__)) + '/'
USER_PATH = os.path.expanduser("~") + '/.cryptowatcher/'
NODE_DIR = 'default/'
LOGS_DIR = 'logs/'
DATA_DIR = 'data/'
CHARTS_DIR = 'charts/'
SNAPSHOT_DIR = 'snapshots/'
STATE_DIR = 'state/'
OUTPUT_LOG = 'output.log'
DEBUG_LOG = 'debug.log'
ERROR_LOG = 'error.log'
ALERT_LOG = 'alerts.log'
TOOL_OUTPUT_LOG = 'tool-output.log'
TOOL_DEBUG_LOG = 'tool-debug.log'
TOOL_ERROR_LOG = 'tool-error.log'

# Time parameters.
TIME_FORMAT = '%Y-%m-%dT%H:%M:%S'

# Network parameters.
HTTP_TIMEOUT_SECS = 30
HTTP_READ_TIMEOUT_SECS = 30
HTTP_MAX_RETRIES = 10
HTTP_MAX_BACKOFF_SECS = 30
HTTP_HOST_CONN_LIMIT = 3
API_INITIAL_RATE_LIMIT_SECS = 0.25
API_MAX_RETRIES = 10

# Sound parameters.
ENABLE_SOUND = False
ALERT_SOUND = 'alert.wav'
BUY_SOUND = 'buy-alert.wav'
SELL_HIGH_SOUND = 'sell-alert-high.wav'
SELL_LOW_SOUND = 'sell-alert-low.wav'
CRITICAL_SOUND = 'red-alert.wav'
PLAY_SOUND_CMD_LINUX = ['aplay', '-N', '-q']
PLAY_SOUND_CMD_WINDOWS = ['sounder.exe']
PLAY_SOUND_CMD_DARWIN = ['afplay']
PLAY_SOUND_CMD_DEFAULT = ['play']

# Color parameters.
ALERT_COLOR = '\033[1;93m'
BUY_COLOR = '\033[1;96m'
SELL_HIGH_COLOR = '\033[1;92m'
SELL_LOW_COLOR = '\033[1;91m'

# Chart parameters.
ENABLE_CHARTS = True
CHART_SHOW_CLOSE = False
CHART_FORMAT = 'pickle'
CHART_AGE = 1440
CHART_WIDTH = 1440
CHART_HEIGHT = 720

# Snapshot parameters.
ENABLE_SNAPSHOTS = True
SNAPSHOT_FORMAT = 'pickle'

# Forecast parameters (no longer implemented).
FORECAST_WINDOW = 34
FORECAST_NUM = 1
FORECAST_WEIGHT = 1.5

# Backtesting parameters.
ENABLE_BACKTEST = False
BACKTEST_LIMIT_PAIRS = []
BACKTEST_REFRESH_PAIRS = True
BACKTEST_WINDOW = 1440 * 100
BACKTEST_OFFSET = 1440 * 0
BACKTEST_MULTICORE = False
BACKTEST_SPLIT_MAP = True
BACKTEST_PROCESSES = multiprocessing.cpu_count()
BACKTEST_FOLLOW_UP_TICKS = 30
BACKTEST_DATA_DIR = 'testdata/bittrex/2018-01/'
BACKTEST_MAX_BEGIN_SKEW = 8 * 60 * 60

# Intervals.
TICK_INTERVAL_SECS = 60
TICK_GAP_MAX = 60
PAIRS_UPDATE_SECS = TICK_INTERVAL_SECS
PAIRS_GREYLIST_SECS = 60 * 15
FOLLOW_UP_SECS = 28800
FOLLOW_UP_CHECK_SECS = TICK_INTERVAL_SECS
OUTPUT_ROLLOVER_SECS = 86400
BACK_REFRESH_MIN_SECS = 60 * 60
BACK_REFRESH_MAX_PER_TICK = 3

# Base currency values.
TRADE_BASE = 'USDT'
BASE_PAIRS = ['USDT-BNB', 'USDT-BTC', 'USDT-ETH', 'BTC-BNB', 'BTC-ETH', 'ETH-BNB']
MIN_BASE_VOLUMES = {
    'USDT': 100000.0,
    'BNB': 10000.0,
    'BTC': 10.0,
    'ETH': 100.0
}

# Currency pair parameters
PAIR_PREFER_FILTER = False
PAIR_CHANGE_FILTER = False
PAIR_DIP_FILTER = False
MAX_PAIRS = None
PAIR_CHANGE_MIN = 0.0015
PAIR_CHANGE_MAX = 0.0
PAIR_CHANGE_DIP = 0.025
PAIR_CHANGE_CUTOFF = 0.0125

# Moving average parameters.
MA_WINDOWS = [5, 13, 34, 89, 233, 610, 1597]
VDMA_WINDOWS = [34]
EMA_WINDOWS = []
EMA_TRADE_BASE_ONLY = True
MA_FILTER = False
MA_FILTER_WINDOW = 35
MA_FILTER_ORDER = 13

# Bollinger band parameters.
ENABLE_BBANDS = False
BBAND_MA = 2
BBAND_MULT = 2.0

# Specific API parameters.
COIN_EXCHANGE = 'binance'

# Detection parameters.
DETECTION_MIN_FOLLOW_SECS = 180.0
DETECTION_MAX_FOLLOW_SECS = 28800.0
DETECTION_RESTORE_TIMEOUT_SECS = 60 * 60
DETECTION_FLASH_CRASH_SENS = 0.5

# Trade parameters.
TRADE_SIMULATE = False
TRADE_MIN_SIZE = 15.0
TRADE_MAX_SIZE = 15.0
TRADE_SIZE_MULT = None  # 0.5
TRADE_MIN_SIZE_BTC = 0.001
TRADE_MIN_SAFE_PERCENT = 0.25
TRADE_FEE_PERCENT = 0.00075
TRADE_BUY_LIMIT_MARGIN = 0.005
TRADE_BUY_RETRY_MARGIN = 0.0025
TRADE_BALANCE_MARGIN = 0.015
TRADE_BALANCE_BUFFER = 1
TRADE_BALANCE_SYNC = True
TRADE_REFILL_LIMIT_MARGIN = 0.005
TRADE_PUSH_SELL_PERCENT = 0.08
TRADE_SOFT_SELL_PERCENT = 0.05
TRADE_HARD_SELL_PERCENT = 0.02
TRADE_STOP_PERCENT = 0.15
TRADE_STOP_CUTOFF = 0.035
TRADE_STOP_CHECK = 0.01
TRADE_DYNAMIC_SELL_PERCENT = 0.000025
TRADE_DYNAMIC_STOP_PERCENT = 0.00005
TRADE_HARD_STOP_THRESHOLD = 1
TRADE_DEFERRED_PUSH_SELL = False
TRADE_DEFERRED_SOFT_SELL = False
TRADE_DEFERRED_HARD_SELL = False
TRADE_PUSH_MAX = 2
TRADE_SOFT_MAX = 1
TRADE_REBUY_MAX = 2
TRADE_REBUY_PUSH_PENALTY = 1
TRADE_GARBAGE_COLLECT = True
TRADE_USE_INDICATORS = False
TRADE_UPDATE_SECS = 5

# Remit and refill parameters.
REMIT_RESERVED = {'BNB': 5.0}
REMIT_PUSH_SELL_PERCENT = 0.06
REMIT_SOFT_SELL_PERCENT = 0.04
REMIT_HARD_SELL_PERCENT = 0.02
REMIT_PUSH_MAX = 2
REMIT_STOP_PERCENT = 0.15
REMIT_STOP_CUTOFF = 0.015
REMIT_STOP_CHECK = 0.01
REFILL_SYNC_TIMEOUT = 60.0
REFILL_SYNC_RETRY = 3.0

# Simulation parameters.
SIM_BALANCE = 10000.0
SIM_WATCH_TRADE_BASE_PAIRS = True
SIM_ENABLE_BALANCES = True
SIM_ENABLE_BALANCER = True

# Relative Strength Index parameters.
ENABLE_RSI = False
RSI_WINDOW = 14
RSI_SIZE = 34
RSI_OVERBOUGHT = 60
RSI_OVERSOLD = 40

# Detections
DETECTIONS = {}
DETECTIONS.update(detections.BUY_RETRACEMENT_0)
DETECTIONS.update(detections.BUY_RETRACEMENT_1)
DETECTIONS.update(detections.BUY_RETRACEMENT_2)
DETECTIONS.update(detections.BUY_REVERSAL_0)
DETECTIONS.update(detections.CONTINUATIONS)
DETECTIONS.update(detections.SELL_PUSHES)
DETECTIONS.update(detections.SOFT_STOPS)