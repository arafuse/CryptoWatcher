# -*- coding: utf-8 -*-

"""
Binance API module.

Note: Ignoring retries for 429 responses and caching None values is done on purpose, as the Binance API is touchy
about throttling and will ban IPs.
"""

__author__ = 'Adam Rafuse <$(echo nqnz.enshfr#tznvy.pbz | tr a-z# n-za-m@)>'
__version__ = "0.1.0"
__all__ = ['Client']

import re
import hmac
import json
import time
import asyncio
import hashlib
import traceback

from typing import Any, Dict, List, Sequence, Tuple

import api
import utils
import common
import configuration

import aiohttp

config = configuration.config
"""
Global configuration.
"""


CACHE_INFO_SECS = 60 * 15
TIME_FORMAT = '%Y-%m-%dT%H:%M:%S'
API_URL = 'https://api.binance.com/api/{}{}'

API_METHODS = {
    'getExchangeInfo': {
        'path': 'v1/exchangeInfo',
        'params': '',
        'verb': 'GET',
        'auth': False
    },
    'getKlines': {
        'path': 'v1/klines',
        'params': 'symbol={}&interval={}&endTime={}',
        'verb': 'GET',
        'auth': False
    },
    'getOldKlines': {
        'path': 'v1/klines',
        'params': 'symbol={}&interval={}&startTime={}',
        'verb': 'GET',
        'auth': False
    },
    'getPrices': {
        'path': 'v3/ticker/price',
        'params': '',
        'verb': 'GET',
        'auth': False
    },
    'get24hrChange': {
        'path': 'v1/ticker/24hr',
        'params': '',
        'verb': 'GET',
        'auth': False
    },
    'newOrder': {
        'path': 'v3/order',
        'params': 'symbol={}&side={}&type={}&quantity={}&price={}&timeInForce={}',
        'verb': 'POST',
        'auth': True
    },
    'newOrderSimple': {
        'path': 'v3/order',
        'params': 'symbol={}&side={}&type={}&quantity={}',
        'verb': 'POST',
        'auth': True
    },
    'getOrder': {
        'path': 'v3/order',
        'params': 'symbol={}&origClientOrderId={}',
        'verb': 'GET',
        'auth': True
    },
    'cancelOrder': {
        'path': 'v3/order',
        'params': 'symbol={}&origClientOrderId={}',
        'verb': 'DELETE',
        'auth': True
    },
    'getAccount': {
        'path': 'v3/account',
        'params': '',
        'verb': 'GET',
        'auth': True
    },
}


class Client(api.Client):
    """
    Client for interacting with the Binance API.
    """

    def __init__(self, session: aiohttp.ClientSession, log=utils.logging.DummyLogger()):

        self.session = session
        """
        Object HTTP client session.
        """

        self.log = utils.logging.ChildLogger(parent=log, scope=self)
        """
        Object logger.
        """

        self.lock = asyncio.Lock()
        """
        Lock used for syncing access to API data.
        """

        self.cache = {}
        """
        Response cache.
        """

        if config['tick_interval_secs'] == 60:
            self.tick_interval_str = '1m'
        elif config['tick_interval_secs'] == 300:
            self.tick_interval_str = '5m'
        else:
            raise ValueError("Unsupported tick interval: {}".format(config['tick_interval_secs']))

    async def call(self, method: str, params: Sequence[Any]=None):
        """
        Call a Binance API method.

        Implements retry and exponentional backoff for HTTP level error conditions.

        Arguments:
            method:  Name of the API method to call.
            params:  Values of query parameters to pass to the method.

        Returns:
            (tuple):  A tuple containing:

            data (str):     The raw HTTP response body (may be None).
            status (int):   The HTTP response status code. A value of 0 indicates a connection or transport failure.
        """

        retry = False
        attempt = 0
        status = 0
        data = None

        url, verb, body, headers = await self._get_request_data(method, params)

        while attempt < config['http_max_retries']:
            try:
                async with self.session.request(verb, url, data=body, headers=headers) as response:
                    status = response.status

                    if status >= 200 and status <= 399:
                        data = await response.text()
                        break

                    if (status >= 500 and status <= 599 and status != 504) or (status in [0, 408]):
                        retry_reason = 'status {}'.format(status)
                        retry = True

                    else:
                        self.log.error('Got non-retryable status {}.', status)
                        data = await response.text()
                        break

            except (aiohttp.ClientConnectionError, aiohttp.ClientPayloadError, asyncio.TimeoutError) as e:
                retry_reason = '{}: {}'.format(type(e).__name__, e)
                retry = True

            if retry:
                attempt += 1
                await common.backoff(attempt, "Binance call {}".format(method), retry_reason)
                retry = False

        return (data, status)

    @staticmethod
    async def _get_request_data(method: str, params: Sequence[Any]=None):
        """
        Get the request URL and headers for a given API method and parameter list.

        Forms the full URL with query string and calculates any needed HMAC signature to be passed in headers.

        Arguments:
            method:  Name of the API method to call.
            params:  Values of query parameters to pass to the method.

        Returns:
            (tuple):  A tuple containing:
                (str):   Full URL for the request.
                (str):   HTTP verb of the request ('GET', 'POST' or 'DELETE')
                (str):   Request body, or None if a 'GET' request.
                (dict):  Dictionary of headers for the request, or None if no headers are required.
        """

        api_key = config['binance_api_key']
        api_secret = config['binance_api_secret']
        headers = {'Accept': 'application/json', 'X-MBX-APIKEY': api_key}

        query = API_METHODS[method]['params'].format(*params or [])
        verb = API_METHODS[method]['verb']

        if API_METHODS[method]['auth']:
            query += '&timestamp=' + str(int(time.time() * 1000))
            signature = hmac.new(api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
            query += '&signature=' + signature

        if verb == "POST":
            url = API_URL.format(API_METHODS[method]['path'], '')
            body = query

        else:
            url = API_URL.format(API_METHODS[method]['path'], '?' + query if query else '')
            body = None

        return (url, verb, body, headers)

    async def call_json(self, method: str, params: list=None):
        """
        Call a Binance API method and parse JSON response.

        Implements retry and exponential backoff for higher-level API error conditions on a 200 response, specifically
        empty response body or malformed response body (invalid JSON).

        Arguments:
            method:  Name of the API method to call.
            params:  Values of query parameters to pass to the method.

        Returns:
            (tuple):  A tuple containing:

            data (object):  On success, a dict containing the parsed JSON response.
                            On a non-200 response, the raw response body (may be None).
                            On a response with a missing response body, None.
            status (int):   The HTTP response status code. A value of 0 indicates a connection or transport failure.
        """

        retry = False
        attempt = 0
        status = 0
        data = None

        while attempt < config['http_max_retries']:
            raw_data, status = await self.call(method, params)

            if status != 200:
                return (raw_data, status)

            if raw_data is None:
                retry_reason = "'None' on successful response"
                retry = True

            if not retry:
                try:
                    data = json.loads(raw_data)
                    return (data, status)

                except json.JSONDecodeError:
                    retry_reason = 'invalid JSON response'
                    retry = True

            if retry:
                attempt += 1
                await common.backoff(attempt, "Binance call_json {}".format(method), retry_reason)
                retry = False

        return (data, status)

    async def call_extract(self, extract: Sequence[str], method: str, params: Sequence[Any]=None,
                           retry_data=False, retry_fail=False, log=False):
        """
        Call a Binance API method and extract data items from its JSON response.

        Implements retry and exponential backoff for invalid data items. Caution must be taken to ensure that the
        specified extract dict keys are correct to avoid repeating of non-idempotent operations (such as buying or
        selling) so should always be tested with retry=False (the default) first.

        Arguments:
            extract:     A list of strings representing the dictionary paths of the response data items to extract,
                         eg. ["['result'][0]['C']", "['result'][0]['T']"]
            method:      Name of the API method to call.
            params:      Values of query parameters to pass to the method.
            retry_data:  If True, will perform backoff and retry on empty or missing data items. Syntax errors in
                         extract paths will not be retried.
            retry_fail:  Not implemented for this API.
            log:         If True, will log the API JSON response. This is optional as some responses can be quite
                         large.

        Returns:
            (tuple):  A tuple containing:

            data (object):  On a normal 200 response, a tuple containing the values for each extracted item. Any items
                            that failed to be extracted after exhausting all retries, or had syntax errors in extract
                            paths will be set to None.
                            On a non-200 response, the raw response body (may be None).
                            On a 200 response with a missing response body, None.
            status (int):   The HTTP response status code. A value of 0 indicates a connection or transport failure.

        Raises:
            SyntaxError, NameError:  If one or more of the passed extract dict paths contains invalid syntax.
        """

        retry = False
        attempt = 0

        while attempt <= config['api_max_retries']:
            data, status = await self.call_json(method, params)

            if status != 200 or data is None:
                self.log.error("Failed on API method '{}({})': status {}, data {}", method, params, status, data)
                return (data, status)

            data = {'result': data}

            if log:
                self.log.debug("API method '{}({})' response:\n{}", method, params, json.dumps(data, indent=2))

            if not retry:
                results, ex = await self._extract_items(extract, data)
                retry, reason = await self._handle_extract_exception(ex, data, retry_data)

                if retry:
                    attempt += 1
                    await common.backoff(attempt, "Binance call_extract {}".format(method), reason)
                    retry = False

                else:
                    break

        if reason is not None:
            self.log.error("Giving up on: {}", reason)

        return (tuple(results), status)

    @staticmethod
    async def _extract_items(extract: Sequence[str], data: Dict[str, Any]):
        """
        Extract items from a dictionary of data.

        Arguments:
            extract:   List of strings representing the dictionary paths of the response data items to extract,
                       eg. ["['result'][0]['C']", "['result'][0]['T']"]
            data:      Dictionary of data to extract items from.

        Returns:
            (tuple):  A tuple containing:
                list:       Result of each extracted path, or None if a syntax or or extraction error occurred.
                Exception:  The last exception that occurred during extraction, or None if no exception occurred.
        """

        ex = None
        results = []

        for item in extract:
            try:
                expr = 'lambda d: d' + item
                expr_func = eval(expr)           # pylint: disable=W0123
                results.append(expr_func(data))

            except (TypeError, IndexError, KeyError, SyntaxError, NameError) as e:
                ex = e
                results.append(None)

        return (results, ex)

    @staticmethod
    async def _handle_extract_exception(ex: Exception, data: Dict[str, Any], retry_data: bool):
        """
        Handle any exception produced from an extract operation.

        Arguments:
            ex:          Exception returned from :meth:`_extract_items`.
            data:        Dictionary of data passed to :meth:`_extract_items`.
            retry_data:  True if missing data should be retried, false otherwise.

        Returns:
            (tuple):   A tuple containing:
              (bool):  True if the exception warrants a retry, False if no error or and unretryable error occurred.
              (str):   Sentence fragment or formatted traceback describing the reason for retry or error, or None
                       if no issue occurred.
        """

        if isinstance(ex, (TypeError, IndexError, KeyError)):
            reason = await Client._get_extract_failure_reason(ex, data)

            if retry_data and 'code' not in data:
                retry = True
            else:
                retry = False

        elif isinstance(ex, (SyntaxError, NameError)):
            reason = "{}: {}\n{}".format(type(ex).__name__, ex, ''.join(traceback.format_tb(ex.__traceback__)))
            retry = False

        elif ex is not None:
            reason = await Client._get_extract_failure_reason(ex, data)
            retry = False

        else:
            reason = None
            retry = False

        return (retry, reason)

    @staticmethod
    async def _get_extract_failure_reason(ex: Exception, data: Dict[str, Any]):
        """
        Get the failure reason from the given extraction exception and API response message (if present).

        Arguments:
            data:   Dict of the parsed API response.
            ex:     Exception thrown as a result of the extraction attempt.
        """

        if 'msg' in data and data['msg'] and data['msg'] != '':
            api_message = data['msg']
        else:
            api_message = 'empty or missing results'

        return "{} ({}: {})".format(api_message, type(ex).__name__, ex)

    async def get_market_summaries(self) -> List[Dict[str, Any]]:
        """
        Get the market summaries from the Binance API.

        Returns:
            The market summaries dict.
        """

        exchange_info = await self._get_exchange_info()
        if exchange_info is None:
            self.log.error('Could not get exchange info data.')
            return None

        changes_24hr = await self._get_24hr_changes()
        if changes_24hr is None:
            self.log.error('Could not get 24-hour change data.')
            return None

        prices = await self._get_prices()
        if prices is None:
            self.log.error('Could not get price data.')
            return None

        summaries = {}

        for symbol, info in exchange_info['symbols'].items():
            base = info['quoteAsset']  # Chinese exchanges use inverted base / quote
            quote = info['baseAsset']

            pair = '{}-{}'.format(base, quote)
            active = info['status'] == "TRADING"

            if active:
                try:
                    base_volume = float(changes_24hr[symbol]['quoteVolume'])
                    prev_day = float(changes_24hr[symbol]['prevClosePrice'])
                    last_value = float(prices[symbol]['price'])
                except KeyError:
                    active = False
                    base_volume = 0.0
                    prev_day = 0.0
                    last_value = 0.0

            else:
                base_volume = 0.0
                prev_day = 0.0
                last_value = 0.0

            try:
                min_trade_qty = float(info['filters']['LOT_SIZE']['minQty'])
            except KeyError:
                min_trade_qty = 0.0

            try:
                min_trade_size = float(info['filters']['MIN_NOTIONAL']['minNotional'])
            except KeyError:
                min_trade_size = 0.0

            try:
                min_trade_value = float(info['filters']['PRICE_FILTER']['minPrice'])
            except KeyError:
                min_trade_value = 0.0

            summaries[pair] = {
                'active': active,
                'baseCurrency': base,
                'minTradeQty': min_trade_qty,
                'minTradeSize': min_trade_size,
                'minTradeValue': min_trade_value,
                'baseVolume': base_volume,
                'prevDay': prev_day,
                'last': last_value,
            }

        return summaries

    async def get_ticks(self, pair: str, length: int=None) -> List[Dict[str, Any]]:
        """
        Get ticks (closing values and closing times) for a pair from the Binance API.

        Arguments:
            pair:  The currency pair eg. 'BTC-ETH'.
            length:   Maximum number of ticks to return. Is rounded up to the nearest 500. Defaults to the global
                      minimum needed to perform operations as returned by :meth:`common.get_min_tick_length`.

        Returns:
            A list of the raw tick data from the API, or None if an error occurred or no ticks are available.
        """

        base, quote = common.get_pair_split(pair)
        tick_length = length if length else common.get_min_tick_length()
        symbol = '{}{}'.format(quote, base)
        end_time = int(time.time() * 1000)
        ticks = []

        while len(ticks) < tick_length:
            tick_batch = []

            results, status = await self.call_extract([
                "['result']",
            ], 'getKlines', params=[symbol, self.tick_interval_str, end_time], retry_data=True)

            if status != 200 or results is None or results[0] is None:
                self.log.error("Failed getting klines: status {}, results {}.", status, results)
                break

            if not results[0]:
                break

            for result in results[0]:
                tick_batch.append({
                    'T': result[0] / 1000,
                    'O': float(result[1]),
                    'H': float(result[2]),
                    'L': float(result[3]),
                    'C': float(result[4]),
                    'V': float(result[5]),
                    'BV': float(result[7])
                })

            end_time = results[0][0][0] - (config['tick_interval_secs'] * 1000)
            ticks = tick_batch + ticks

        return ticks if ticks else None

    async def get_tick_range(self, pair: str, start_time: float, end_time: float) -> List[Dict[str, Any]]:
        """
        Get a range of ticks (closing values and closing times) for a pair from the Binance API.

        Arguments:
            pair:        The currency pair eg. 'BTC-ETH'.
            start_time:  Timestamp to start at.
            end_time:    Timestamp to start at.

        Returns:
            A list of the raw tick data from the API.
        """

        base, quote = common.get_pair_split(pair)
        symbol = '{}{}'.format(quote, base)
        start_param = int(start_time * 1000)
        completed = False
        ticks = []

        while not completed:
            tick_batch = []

            results, status = await self.call_extract([
                "['result']",
            ], 'getOldKlines', params=[symbol, self.tick_interval_str, start_param], retry_data=True)

            if status != 200 or results is None or results[0] is None or not results[0]:
                if not ticks: ticks = None
                break

            for result in results[0]:
                tick_batch.append({
                    'T': result[0] / 1000,
                    'O': float(result[1]),
                    'H': float(result[2]),
                    'L': float(result[3]),
                    'C': float(result[4]),
                    'V': float(result[5]),
                    'BV': float(result[7])
                })

            start_param = results[0][-1][0] + (config['tick_interval_secs'] * 1000)
            completed = tick_batch[-1]['T'] > end_time
            ticks.extend(tick_batch)

        return ticks

    async def get_last_values(self, pair: str) -> Tuple[float, float]:
        """
        Get the last price and 24-hour volume for a currency pair from the API.

        Arguments:
            pair:  Currency pair name eg. 'BTC-ETH'

        Returns:
            (tuple):  A tuple containing:
            float:    The current close price, or None if an error occurred.
            float:    The current 24 hour volume, or None if an error occurred.
        """

        base, quote = common.get_pair_split(pair)
        symbol = '{}{}'.format(quote, base)

        prices = await self._get_prices()
        if prices is None:
            self.log.error('Could not get price data.')
            price = None
        else:
            price = float(prices[symbol]['price'])

        changes_24hr = await self._get_24hr_changes()
        if changes_24hr is None:
            self.log.error('Could not get 24-hour change data.')
            volume = None
        else:
            volume = float(changes_24hr[symbol]['quoteVolume'])

        return (price, volume)

    async def buy_limit(self, pair: str, quantity: float, value: float):
        """
        """

        base, quote = common.get_pair_split(pair)
        symbol = '{}{}'.format(quote, base)

        step_size, tick_size = await self._get_step_tick_sizes(symbol)
        if step_size is None:
            self.log.error("Could not get step and tick sizes for {}.", symbol)
            return None

        quantity_str = self._to_precision(quantity, self._precision(step_size))
        value_str = self._to_precision(value, self._precision(tick_size))

        results, status = await self.call_extract([
            "['result']['clientOrderId']",
        ], 'newOrder', params=[symbol, 'BUY', 'LIMIT', quantity_str, value_str, 'GTC'], log=True)

        if status == 400:
            quantity -= float(step_size)
            quantity_str = self._to_precision(quantity, self._precision(step_size))
            self.log.warning("{} re-trying buy with next lowest step size.", pair)

            results, status = await self.call_extract([
                "['result']['clientOrderId']",
            ], 'newOrder', params=[symbol, 'BUY', 'LIMIT', quantity_str, value_str, 'GTC'], log=True)

        if status != 200 or results is None or results[0] is None:
            return None

        return results[0]

    async def sell_limit(self, pair: str, quantity: float, value: float):
        """
        FIXME: This actually submits a market sell and ignores the given value, as the intent is to
        submit a market sell anyway and the Binance API complains frequently with small values.
        """

        base, quote = common.get_pair_split(pair)
        symbol = '{}{}'.format(quote, base)

        step_size, _ = await self._get_step_tick_sizes(symbol)
        if step_size is None:
            self.log.error("Could not get step and tick sizes for {}.", symbol)
            return None

        quantity_str = self._to_precision(quantity, self._precision(step_size))
        results, status = await self.call_extract([
            "['result']['clientOrderId']",
        ], 'newOrderSimple', params=[symbol, 'SELL', 'MARKET', quantity_str], log=True)

        if status == 400:
            # Binance still has this dust issue even when using BNB for fees.
            quantity_str = self._to_precision(quantity - float(step_size), self._precision(step_size))
            results, status = await self.call_extract([
                "['result']['clientOrderId']",
            ], 'newOrderSimple', params=[symbol, 'SELL', 'MARKET', quantity_str], log=True)

        if status != 200 or results is None or results[0] is None:
            return None

        return results[0]

    def _precision(self, string):
        """
        """

        parts = re.sub(r'0+$', '', string).split('.')
        return len(parts[1]) if len(parts) > 1 else 0

    def _to_precision(self, value, precision):
        """
        """

        return ('{:.' + str(precision) + 'f}').format(value)

    async def _get_step_tick_sizes(self, symbol: str):
        """
        Gets the step and tick sizes for the given symbol.

        Forces a refresh of exchange data if these values are not cached.

        Arguments:
            symbol:  The currency symbol eg. "ETHUSDT"

        Returns:
            (tuple):    A tuple containing:
              (float):  The step size for this symbol.
              (float):  The tick size for this symbol.

            Returns (None, None) if there were no cached data and the the exchange data refresh failed.
        """

        try:
            step_size = self.cache['exchangeInfo']['data']['symbols'][symbol]['filters']['LOT_SIZE']['stepSize']
            tick_size = self.cache['exchangeInfo']['data']['symbols'][symbol]['filters']['PRICE_FILTER']['tickSize']

        except KeyError:
            exchange_info = await self._get_exchange_info()
            if exchange_info is None:
                self.log.error('Could not get exchange info data.')
                return None

            try:
                step_size = self.cache['exchangeInfo']['data']['symbols'][symbol]['filters']['LOT_SIZE']['stepSize']
                tick_size = self.cache['exchangeInfo']['data']['symbols'][symbol]['filters']['PRICE_FILTER']['tickSize']
            except KeyError:
                return (None, None)

        return (step_size, tick_size)

    async def get_order(self, pair: str, order_id: str):
        """
        TODO: Binance does not return anything useful for the price, may need to try GET /api/v3/myTrades.
        """

        base, quote = common.get_pair_split(pair)
        symbol = '{}{}'.format(quote, base)

        results, status = await self.call_extract([
            "['result']['status']",
            "['result']['origQty']",
            "['result']['executedQty']",
            "['result']['price']",
        ], 'getOrder', params=[symbol, order_id], log=True)

        if status != 200 or results is None or not results[0]:
            return None

        status = results[0]
        quantity = float(results[1])
        exec_quantity = float(results[2])
        price = float(results[3])

        return {
            'open': status in ["NEW", "PARTIALLY_FILLED"],
            'quantity': quantity,
            'remaining': quantity - exec_quantity,
            'value': price,
            'fees': price * exec_quantity * config['trade_fee_percent'],
        }

    async def cancel_order(self, pair: str, order_id: str):
        """
        """

        base, quote = common.get_pair_split(pair)
        symbol = '{}{}'.format(quote, base)

        results, status = await self.call_extract([
            "['result']['clientOrderId']",
        ], 'cancelOrder', params=[symbol, order_id], log=True)

        if status != 200 or results is None or results[0] is None:
            return None

        return True

    async def get_balance(self, base: str):
        """
        """

        balances = await self._get_balances()
        if balances is None:
            return None

        return float(balances[base]['free'])

    async def _get_exchange_info(self):
        """
        Get exchange info from the API, cached for the current tick interval.

        Converts the 'symbols', and filters' list field of each 'symbols' element in the response to a dict for faster
        lookups.
        """

        await self.lock.acquire()

        if 'exchangeInfo' in self.cache:
            if time.time() - self.cache['exchangeInfo']['time'] < CACHE_INFO_SECS:
                self.log.debug("Returning cached data for exchange info.", verbosity=1)
                self.lock.release()
                return self.cache['exchangeInfo']['data']

        results, status = await self.call_extract([
            "['result']",
            "['result']['symbols'][0]['symbol']",      # For retry of missing fields
            "['result']['symbols'][0]['baseAsset']",
            "['result']['symbols'][0]['quoteAsset']",
            "['result']['symbols'][0]['status']",
            "['result']['symbols'][0]['filters']"
        ], 'getExchangeInfo', retry_data=True)

        if status == 200 and results is not None and results[0] is not None:
            for symbol in results[0]['symbols']:
                filters_as_dict = {}
                for filt in symbol['filters']:
                    filters_as_dict[filt['filterType']] = filt
                symbol['filters'] = filters_as_dict

            symbols_as_dict = {}
            for symbol in results[0]['symbols']:
                symbols_as_dict[symbol['symbol']] = symbol
            results[0]['symbols'] = symbols_as_dict

            cache_time = time.time()
            exchange_info = results[0]

        else:
            self.log.error("Failed getting exchange info: status {}, results {}.", status, results)
            cache_time = time.time() - CACHE_INFO_SECS + config['tick_interval_secs']
            if 'exchangeInfo' in self.cache:
                exchange_info = self.cache['exchangeInfo']['data']
            else:
                exchange_info = None

        self.cache['exchangeInfo'] = {
            'time': cache_time,
            'data': exchange_info
        }

        self.lock.release()
        return exchange_info

    async def _get_24hr_changes(self):
        """
        Get 24 hour changes from the API, cached for the current tick interval.

        Converts the response list to a dict for faster lookups.
        """

        await self.lock.acquire()

        if '24hrChange' in self.cache:
            if time.time() - self.cache['24hrChange']['time'] < config['tick_interval_secs']:
                self.log.debug("Returning cached data for 24hrChange.", verbosity=1)
                self.lock.release()
                return self.cache['24hrChange']['data']

        results, status = await self.call_extract([
            "['result']",
            "['result'][0]['symbol']",          # For retry of missing fields
            "['result'][0]['prevClosePrice']",
            "['result'][0]['quoteVolume']",
        ], 'get24hrChange', retry_data=True)

        if status == 200 and results is not None and results[0] is not None:
            results_as_dict = {}
            for result in results[0]:
                results_as_dict[result['symbol']] = result
            changes_24hr = results_as_dict

        else:
            if '24hrChange' in self.cache:
                changes_24hr = self.cache['24hrChange']['data']
            else:
                changes_24hr = None

        self.cache['24hrChange'] = {
            'time': time.time(),
            'data': changes_24hr
        }

        self.lock.release()
        return changes_24hr

    async def _get_prices(self):
        """
        Get prices from the API, cached for the current tick interval.

        Converts the response list to a dict for faster lookups.
        """

        await self.lock.acquire()

        if 'prices' in self.cache:
            if time.time() - self.cache['prices']['time'] < config['tick_interval_secs']:
                self.log.debug("Returning cached data for prices.", verbosity=1)
                self.lock.release()
                return self.cache['prices']['data']

        results, status = await self.call_extract([
            "['result']",
            "['result'][0]['symbol']",  # For retry of missing fields
            "['result'][0]['price']"
        ], 'getPrices', retry_data=True)

        if status == 200 and results is not None and results[0] is not None:
            results_as_dict = {}
            for result in results[0]:
                results_as_dict[result['symbol']] = result
            prices = results_as_dict

        else:
            if 'prices' in self.cache:
                prices = self.cache['prices']['data']
            else:
                prices = None

        self.cache['prices'] = {
            'time': time.time(),
            'data': prices
        }

        self.lock.release()
        return prices

    async def _get_balances(self):
        """
        Get balances from the API, cached for the current tick interval.

        Converts the response list to a dict for faster lookups.
        """

        results, status = await self.call_extract([
            "['result']['balances']",
        ], 'getAccount', retry_data=True)

        if status == 200 and results is not None and results[0] is not None:
            balances_as_dict = {}
            for balance in results[0]:
                balances_as_dict[balance['asset']] = balance
            balances = balances_as_dict

        else:
            if 'balances' in self.cache:
                balances = self.cache['balances']['data']
            else:
                balances = None

        self.cache['balances'] = {
            'time': time.time(),
            'data': balances
        }

        return balances
