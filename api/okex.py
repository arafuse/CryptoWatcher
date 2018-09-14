# -*- coding: utf-8 -*-

"""
OKEx API module.
"""

__author__ = 'Adam Rafuse <$(echo nqnz.enshfr#tznvy.pbz | tr a-z# n-za-m@)>'
__version__ = "0.1.0"
__all__ = ['Client']

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

CACHE_PRODUCTS_SECS = 60 * 15
MAX_TICKS = 2000

TIME_FORMAT = '%Y-%m-%dT%H:%M:%S'
API_URL = 'https://www.okex.com/{}{}'


API_METHODS = {
    'getProducts': {
        'path': 'v2/markets/products',
        'params': '',
        'verb': 'GET',
        'auth': False
    },
    'getKlines': {
        'path': 'v2/markets/{}/kline',
        'params': 'since={}&type={}',
        'verb': 'GET',
        'auth': False
    },
    'getTickers': {
        'path': 'v2/markets/tickers',
        'params': '',
        'verb': 'GET',
        'auth': False
    },
}


class Client(api.Client):
    """
    Client for interacting with the OKEx API.
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
            self.tick_interval_str = '1min'
        elif config['tick_interval_secs'] == 300:
            self.tick_interval_str = '5min'
        else:
            raise ValueError("Unsupported tick interval: {}".format(config['tick_interval_secs']))

    async def call(self, method: str, params: Sequence[Any]=None, path_params: Sequence[Any]=None):
        """
        Call an OKEx API method.

        Implements retry and exponentional backoff for HTTP level error conditions.

        Arguments:
            method:       Name of the API method to call.
            params:       Values of query parameters to pass to the method.
            path_params:  Values of path parameters to pass to the method.

        Returns:
            (tuple):  A tuple containing:

            data (str):     The raw HTTP response body (may be None).
            status (int):   The HTTP response status code. A value of 0 indicates a connection or transport failure.
        """

        retry = False
        attempt = 0
        status = 0
        data = None

        url, verb, body, headers = await self._get_request_data(method, params, path_params)

        while attempt < config['http_max_retries']:
            try:
                async with self.session.request(verb, url, data=body, headers=headers) as response:
                    status = response.status

                    if status >= 200 and status <= 399:
                        data = await response.text()
                        break

                    if (status >= 500 and status <= 599 and status != 504) or (status in [0, 408, 429]):
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
                await common.backoff(attempt, "OKEx call {}".format(method), retry_reason)
                retry = False

        return (data, status)

    @staticmethod
    async def _get_request_data(method: str, params: Sequence[Any]=None, path_params: Sequence[Any]=None):
        """
        Get the request URL and headers for a given API method and parameter list.

        Forms the full URL with query string and calculates any needed HMAC signature to be passed in headers.

        Arguments:
            method:       Name of the API method to call.
            params:       Values of query parameters to pass to the method.
            path_params:  Values of path parameters to pass to the method.

        Returns:
            (tuple):  A tuple containing:
                (str):   Full URL for the request.
                (str):   HTTP verb of the request ('GET', 'POST' or 'DELETE')
                (str):   Request body, or None if a 'GET' request.
                (dict):  Dictionary of headers for the request, or None if no headers are required.
        """

        api_key = config['okex_api_key']
        api_secret = config['okex_api_secret']
        headers = None

        query = API_METHODS[method]['params'].format(*params or [])
        path = API_METHODS[method]['path'].format(*path_params or [])
        verb = API_METHODS[method]['verb']

        if API_METHODS[method]['auth']:
            query += '&api_key=' + api_key + '&secret_key=' + api_secret
            signature = hashlib.md5(query.encode()).hexdigest()
            query += '&sign=' + signature

        if verb == "POST":
            url = API_URL.format(path, '')
            body = query

        else:
            url = API_URL.format(path, '?' + query if query else '')
            body = None

        return (url, verb, body, headers)

    async def call_json(self, method: str, params: Sequence[Any]=None, path_params: Sequence[Any]=None):
        """
        Call a Binance API method and parse JSON response.

        Implements retry and exponential backoff for higher-level API error conditions on a 200 response, specifically
        empty response body or malformed response body (invalid JSON).

        Arguments:
            method:       Name of the API method to call.
            params:       Values of query parameters to pass to the method.
            path_params:  Values of path parameters to pass to the method.

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
            raw_data, status = await self.call(method, params, path_params)

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
                await common.backoff(attempt, "OKEx call_json {}".format(method), retry_reason)
                retry = False

        return (data, status)

    async def call_extract(self, extract: Sequence[str], method: str, params: Sequence[Any]=None,
                           path_params: Sequence[Any]=None, retry_data=False, retry_fail=False, log=False):
        """
        Call a Binance API method and extract data items from its JSON response.

        Implements retry and exponential backoff for invalid data items. Caution must be taken to ensure that the
        specified extract dict keys are correct to avoid repeating of non-idempotent operations (such as buying or
        selling) so should always be tested with retry=False (the default) first.

        Arguments:
            extract:      A list of strings representing the dictionary paths of the response data items to extract,
                          eg. ["['result'][0]['C']", "['result'][0]['T']"]
            method:       Name of the API method to call.
            params:       Values of query parameters to pass to the method.
            path_params:  Values of path parameters to pass to the method.
            retry_data:   If True, will perform backoff and retry on empty or missing data items. Syntax errors in
                          extract paths will not be retried.
            retry_fail:   Not implemented for this API.
            log:          If True, will log the API JSON response. This is optional as some responses can be quite
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
            data, status = await self.call_json(method, params, path_params)

            if status != 200 or data is None:
                self.log.error("Failed on API method '{}({})': status {}, data {}", method, params, status, data)
                return (data, status)

            if log:
                self.log.debug("API method '{}({})' response:\n{}", method, params, json.dumps(data, indent=2))

            if not retry:
                results, ex = await self._extract_items(extract, data)
                retry, reason = await self._handle_extract_exception(ex, data, retry_data)

                if retry:
                    attempt += 1
                    await common.backoff(attempt, "OKEx call_extract {}".format(method), reason)
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

            if retry_data and 'code' not in data and 'error_code' not in data:
                retry = True
            elif retry_data and 'code' in data and data['code'] == 0:
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

        api_message = ''

        if 'code' in data and data['code'] != 0:
            api_message += 'Error code {}: '.format(data['code'])
        elif 'error_code' in data:
            api_message += 'Error code {}: '.format(data['error_code'])

        if 'msg' in data and data['msg'] and data['msg'] != '':
            api_message += data['msg']
            if 'detailMsg' in data and data['detailMsg'] and data['detailMsg'] != '':
                api_message += '; ' + data['detailMsg']
        else:
            api_message += 'empty or missing results'

        return "{} ({}: {})".format(api_message, type(ex).__name__, ex)

    async def get_market_summaries(self) -> List[Dict[str, Any]]:
        """
        Get the market summaries from the OKEx API.

        Returns:
            The market summaries dict.
        """

        products = await self._get_products()
        if products is None:
            self.log.error('Could not get products data.')
            return None

        tickers = await self._get_tickers()
        if tickers is None:
            self.log.error('Could not get tickers data.')
            return None

        summaries = {}

        for symbol, product in products.items():
            symbol_split = symbol.upper().split('_')
            base = symbol_split[1]                    # Chinese exchanges use inverted base / quote
            quote = symbol_split[0]

            try:
                pair = '{}-{}'.format(base, quote)
                active = bool(product['online'])
                min_trade_qty = product['minTradeSize']

                if active:
                    last_value = float(tickers[symbol]['last'])
                    base_volume = float(tickers[symbol]['volume']) * last_value
                    prev_day = last_value - float(tickers[symbol]['change'])
                else:
                    last_value = 0.0
                    base_volume = 0.0
                    prev_day = 0.0

                summaries[pair] = {
                    'active': active,
                    'baseCurrency': base,
                    'minTradeQty': min_trade_qty,
                    'minTradeSize': 0.0,
                    'minTradeValue': 0.0,
                    'baseVolume': base_volume,
                    'prevDay': prev_day,
                    'last': last_value,
                }

            except KeyError:
                continue  # Pairs can appear in products for which there are no tickers

        return summaries

    async def get_ticks(self, pair: str, length=None) -> List[Dict[str, Any]]:
        """
        Get ticks (closing values and closing times) for a pair from the OKex API.

        Arguments:
            pair:     The currency pair eg. 'BTC-ETH'.
            length:   Maximum number of ticks to return. Is rounded up to the nearest 500. Defaults to the global
                      minimum needed to perform operations as returned by :meth:`common.get_min_tick_length`.

        Returns:
            A list of the raw tick data from the API, or None if an error occurred or no ticks are available.
        """

        base, quote = common.get_pair_split(pair)
        symbol = '{}_{}'.format(quote, base).lower()
        tick_length = length if length else common.get_min_tick_length()
        start_time = time.time() - (tick_length * config['tick_interval_secs'])

        results, status = await self.call_extract([
            "['data']",
        ], 'getKlines', params=[0, self.tick_interval_str], path_params=[symbol], retry_data=True)

        if status != 200 or results is None or results[0] is None or not results[0]:
            return None

        ticks = []
        for result in results[0]:
            close = float(result['close'])
            volume = float(result['volume'])

            ticks.append({
                'T': result['createdDate'] / 1000,
                'H': float(result['high']),
                'L': float(result['low']),
                'O': float(result['open']),
                'C': close,
                'V': volume,
                'BV': volume * close
            })

        if tick_length - len(ticks) > 0:
            ticks = await self._get_upscaled_ticks(symbol, start_time, ticks[0]['T']) + ticks

        return ticks if ticks else None

    async def get_tick_range(self, pair: str, start_time: float, end_time: float) -> List[Dict[str, Any]]:
        """
        Get a range of ticks (closing values and closing times) for a pair from the OKEx API.
        """

        raise NotImplementedError("Tick range not supported by the OKEx API.")

    async def _get_upscaled_ticks(self, symbol, start_time, end_time) -> List[Dict[str, float]]:
        """
        Get ticks from a lower resolution upscaled to the current resolution.

        Uses linear interpolation to get ticks scaled to the current resolution. Allows us to get more ticks at
        the current resolution than the API can provide otherwise, albiet with less accurate information.

        Arguments:
            symbol:     Currency symbol in native API format eg 'eth_usdt'.
            start_time  Starting timestamp of the ticks to return (inclusive).
            end_time    Ending timestamp of the ticks to return (exclusive).

        Returns:
            List of upscaled ticks.
        """

        start_time_millis = int(start_time - config['tick_interval_secs'] * 5) * 1000

        if self.tick_interval_str == '1min':
            next_interval_str = '5min'
        else:
            next_interval_str = '15min'

        results, status = await self.call_extract([
            "['data']",
        ], 'getKlines', params=[start_time_millis, next_interval_str], path_params=[symbol], retry_data=True)

        if status != 200 or results is None or results[0] is None or not results[0]:
            return []

        sparse_ticks = results[0]
        ticks = []

        for tick_index in range(1, len(sparse_ticks)):
            tick = sparse_ticks[tick_index]
            last_tick = sparse_ticks[tick_index - 1]

            timestamp = tick['createdDate'] / 1000
            open_value = float(tick['open'])
            high_value = float(tick['high'])
            low_value = float(tick['low'])
            close_value = float(tick['close'])
            volume = float(tick['volume'])
            base_volume = volume * close_value

            last_timestamp = last_tick['createdDate'] / 1000
            last_open_value = float(last_tick['open'])
            last_high_value = float(last_tick['high'])
            last_low_value = float(last_tick['low'])
            last_close_value = float(last_tick['close'])
            last_volume = float(last_tick['volume'])
            last_base_volume = last_volume * close_value
            gap = int((timestamp - last_timestamp) // config['tick_interval_secs'])

            if gap > 0.0:
                open_value_step = (open_value - last_open_value) / gap
                high_value_step = (high_value - last_high_value) / gap
                low_value_step = (low_value - last_low_value) / gap
                close_value_step = (close_value - last_close_value) / gap
                volume_step = (volume - last_volume) / gap
                base_volume_step = (base_volume - last_base_volume) / gap

            else:
                open_value_step = 0.0
                high_value_step = 0.0
                low_value_step = 0.0
                close_value_step = 0.0
                volume_step = 0.0
                base_volume_step = 0.0

            for _ in range(gap):
                if last_timestamp >= end_time:
                    return ticks

                ticks.append({
                    'T': last_timestamp,
                    'O': last_open_value,
                    'H': last_high_value,
                    'L': last_low_value,
                    'C': last_close_value,
                    'V': last_volume,
                    'BV': last_base_volume,
                })

                last_open_value += open_value_step
                last_high_value += high_value_step
                last_low_value += low_value_step
                last_close_value += close_value_step
                last_volume += volume_step
                last_base_volume += base_volume_step
                last_timestamp += config['tick_interval_secs']

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

        tickers = await self._get_tickers()
        if tickers is None:
            return None

        base, quote = common.get_pair_split(pair)
        symbol = '{}_{}'.format(quote, base).lower()
        last_value = float(tickers[symbol]['last'])
        base_volume = float(tickers[symbol]['volume']) * last_value

        return (last_value, base_volume)

    async def buy_limit(self, pair: str, quantity: float, value: float):
        """
        """

        return None

    async def sell_limit(self, pair: str, quantity: float, value: float):
        """
        """

        return None

    async def get_order(self, pair: str, order_id: str):
        """
        """

        return None

    async def cancel_order(self, pair: str, order_id: str):
        """
        """

        return None

    async def get_balance(self, base: str):
        """
        """

        return None

    async def _get_products(self):
        """
        Get exchange info from the API, cached for the current tick interval.

        Converts the 'filters' list field of each 'symbols' element in the response to a dict for faster lookups.
        """

        if 'products' in self.cache:
            if time.time() - self.cache['products']['time'] < CACHE_PRODUCTS_SECS:
                self.log.debug("Returning cached data for products.", verbosity=1)
                return self.cache['products']['data']

        results, status = await self.call_extract([
            "['data']",
            "['data'][0]['minTradeSize']",   # For retry of missing fields
            "['data'][0]['online']",
            "['data'][0]['symbol']",
        ], 'getProducts', retry_data=True)

        if status == 200 and results is not None and results[0] is not None:
            products = {}
            for product in results[0]:
                products[product['symbol']] = product

        else:
            if 'products' in self.cache:
                self.cache['products']['time'] = time.time() - CACHE_PRODUCTS_SECS + config['tick_interval_secs']
                return self.cache['products']['data']
            else:
                return None

        self.cache['products'] = {
            'time': time.time(),
            'data': products
        }

        return products

    async def _get_tickers(self):
        """
        Get tickers from the API, cached for the current tick interval.

        Converts the response list to a dict for faster lookups.
        """

        await self.lock.acquire()

        if 'tickers' in self.cache:
            if time.time() - self.cache['tickers']['time'] < config['tick_interval_secs']:
                self.log.debug("Returning cached data for prices.", verbosity=1)
                self.lock.release()
                return self.cache['tickers']['data']

        results, status = await self.call_extract([
            "['data']",
            "['data'][0]['change']",  # For retry of missing fields
            "['data'][0]['last']",
            "['data'][0]['symbol']",
            "['data'][0]['volume']"
        ], 'getTickers', retry_data=True)

        if status == 200 and results is not None and results[0] is not None:
            tickers = {}
            for ticker in results[0]:
                tickers[ticker['symbol']] = ticker

        else:
            if 'tickers' in self.cache:
                self.cache['tickers']['time'] = time.time()
                tickers = self.cache['tickers']['data']
            else:
                tickers = None

            self.lock.release()
            return tickers

        self.cache['tickers'] = {
            'time': time.time(),
            'data': tickers
        }

        self.lock.release()
        return tickers
