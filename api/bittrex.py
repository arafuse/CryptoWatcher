# -*- coding: utf-8 -*-

"""
Bittrex API module.
"""

__author__ = 'Adam Rafuse <$(echo nqnz.enshfr#tznvy.pbz | tr a-z# n-za-m@)>'
__version__ = "0.2.0"
__all__ = ['Client']

import hmac
import json
import time
import asyncio
import hashlib
import traceback

from datetime import datetime, timezone
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


TIME_FORMAT = '%Y-%m-%dT%H:%M:%S'
API_URL = 'https://bittrex.com/api/{}?{}'

API_METHODS = {
    'getMarketSummaries': {
        'path': 'v2.0/pub/markets/getMarketSummaries',
        'params': '',
        'auth': False
    },
    'getMarketSummariesV1': {
        'path': 'v1.1/public/getMarketSummaries',
        'params': '',
        'auth': False
    },
    'getTicks': {
        'path': 'v2.0/pub/market/getTicks',
        'params': 'marketName={}&tickInterval={}',
        'auth': False
    },
    'getLatestTick': {
        'path': 'v2.0/pub/market/getLatestTick',
        'params': 'marketName={}&tickInterval={}',
        'auth': False
    },
    'getTicker': {
        'path': 'v1.1/public/getticker',
        'params': 'market={}',
        'auth': False
    },
    'buyLimit': {
        'path': 'v1.1/market/buylimit',
        'params': 'market={}&quantity={}&rate={}',
        'auth': True
    },
    'sellLimit': {
        'path': 'v1.1/market/selllimit',
        'params': 'market={}&quantity={}&rate={}',
        'auth': True
    },
    'cancelOrder': {
        'path': 'v1.1/market/cancel',
        'params': 'uuid={}',
        'auth': True
    },
    'getOrder': {
        'path': 'v1.1/account/getorder',
        'params': 'uuid={}',
        'auth': True
    },
    'getBalance': {
        'path': 'v1.1/account/getbalance',
        'params': 'currency={}',
        'auth': True
    },
}


class Client(api.Client):
    """
    Client for interacting with the Bittrex API.
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

        self.cache = {
            'balance': {}
        }
        """
        Response cache.
        """

        self.tick_interval_str: str
        """
        String representation of the configured tick interval.
        """

        if config['tick_interval_secs'] == 60:
            self.tick_interval_str = 'oneMin'
        elif config['tick_interval_secs'] == 300:
            self.tick_interval_str = 'fiveMin'
        else:
            raise ValueError("Unsupported tick interval: {}".format(config['tick_interval_secs']))

    async def call(self, method: str, params: Sequence[Any]=None):
        """
        Call a Bittrex API method.

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

        url, headers = await self._get_request_data(method, params)

        while attempt < config['http_max_retries']:
            try:
                async with self.session.get(url, headers=headers) as response:
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
                await common.backoff(attempt, "Bittrex call {}".format(method), retry_reason)
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
                (dict):  Dictionary of headers for the request, or None if no headers are required.
        """

        query = API_METHODS[method]['params'].format(*params or [])

        if API_METHODS[method]['auth']:
            nonce = int(time.time() * 1000)
            api_key = config['bittrex_api_key']
            api_secret = config['bittrex_api_secret']

            query = 'apikey={}&nonce={}&'.format(api_key, nonce) + query
            url = API_URL.format(API_METHODS[method]['path'], query)
            signature = hmac.new(api_secret.encode(), url.encode(), hashlib.sha512).hexdigest()
            headers = {'apisign': signature}

        else:
            url = API_URL.format(API_METHODS[method]['path'], query)
            headers = None

        return (url, headers)

    async def call_json(self, method: str, params: list=None):
        """
        Call a Bittrex API method and parse JSON response.

        Implements retry and exponential backoff for higher-level API error conditions on a 200 response, specifically
        empty response body, malformed response body (invalid JSON), or missing 'success' value.

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
                    _ = data['success']
                    return (data, status)

                except json.JSONDecodeError:
                    retry_reason = 'invalid JSON response'

                except KeyError:
                    retry_reason = "missing 'success' value"

                retry = True

            if retry:
                attempt += 1
                await common.backoff(attempt, "Bittrex call_json {}".format(method), retry_reason)
                retry = False

        return (data, status)

    async def call_extract(self, extract: Sequence[str], method: str, params: Sequence[Any]=None,
                           retry_data=False, retry_fail=False, log=False):
        """
        Call a Bittrex API method and extract data items from its JSON response.

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
            retry_fail:  If True, will perform backoff and retry on explicit failure response from the API.
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

            if log:
                self.log.debug("API method '{}({})' response:\n{}", method, params, json.dumps(data, indent=2))

            if not data['success'] and retry_fail:
                retry = True

                try:
                    reason = data['message'] if data['message'] != '' else "success == false (blank message)"
                except KeyError:
                    reason = "success == false (missing message)"

            if not retry:
                results, ex = await self._extract_items(extract, data)
                retry, reason = await self._handle_extract_exception(ex, data, retry_data)

                if retry:
                    attempt += 1
                    await common.backoff(attempt, "Bittrex call_extract {}".format(method), reason)
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
            (tuple):  A tuple containing:
              (bool):  True if the exception warrants a retry, False if no error or and unretryable error occurred.
              (str):   Sentence fragment or formatted traceback describing the reason for retry or error, or None
                       if no issue occurred.
        """

        if isinstance(ex, (TypeError, IndexError, KeyError)):
            reason = await Client._get_extract_failure_reason(ex, data)

            if retry_data and data['success']:
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

        if 'message' in data and data['message'] and data['message'] != '':
            api_message = data['message']
        else:
            api_message = 'empty or missing results'

        return "{} ({}: {})".format(api_message, type(ex).__name__, ex)

    async def get_market_summaries(self) -> List[Dict[str, Any]]:
        """
        Get the market summaries from the Bittrex API.

        Returns:
            The market summaries dict.
        """

        results, status, = await self.call_extract([
            "['result']",
            "['result'][0]['Market']['BaseCurrency']",  # To retry on any missing fields
            "['result'][0]['Market']['MinTradeSize']",
            "['result'][0]['Market']['IsActive']",
            "['result'][0]['Market']['Notice']",
            "['result'][0]['Summary']['MarketName']",
            "['result'][0]['Summary']['BaseVolume']",
            "['result'][0]['Summary']['PrevDay']",
            "['result'][0]['Summary']['Last']",
        ], 'getMarketSummaries', retry_data=True, retry_fail=True)

        if status != 200 or results is None or results[0] is None:
            self.log.error("Failed getting market summaries: status {}, results {}.", status, results)
            return None

        summaries = {}

        for summary in results[0]:
            pair = summary['Summary']['MarketName']
            active = summary['Market']['IsActive']
            notice = summary['Market']['Notice']
            last = summary['Summary']['Last']
            prev_day = summary['Summary']['PrevDay']
            if not prev_day: prev_day = last

            if notice:
                self.log.info("{} NOTICE: {}", pair, notice)
                if 'will be removed' in notice or 'will be delisted' in notice or 'scheduled for delisting' in notice:
                    self.log.info("{} marked as inactive due to pending removal.", pair)
                    active = False

            summaries[pair] = {
                'active': active,
                'baseCurrency': summary['Market']['BaseCurrency'],
                'minTradeQty': summary['Market']['MinTradeSize'],
                'minTradeSize': 0.0,
                'minTradeValue': 0.0,
                'baseVolume': summary['Summary']['BaseVolume'],
                'prevDay': prev_day,
                'last': last,
            }

        return summaries

    async def get_ticks(self, pair: str, length: int=None) -> List[Dict[str, Any]]:
        """
        Get ticks (closing values and closing times) for a pair from the Bittrex API.

        Arguments:
            pair:     The currency pair eg. 'BTC-ETH'.
            length:   Not supported by the API, will always return all ticks.

        Returns:
            A list of the raw tick data from the API, or None if an error occurred or no ticks are available.
        """

        params = [pair, self.tick_interval_str]

        results, status, = await self.call_extract([
            "['result']",
            "['result'][0]['C']",  # To retry if not at least one element exists
            "['result'][0]['T']"
        ], 'getTicks', params=params, retry_data=True, retry_fail=True)

        if status != 200 or results is None or results[0] is None:
            self.log.error("Failed getting ticks: params {}, status {}, results {}.", params, status, results)
            return None

        for tick in results[0]:
            close_datetime = datetime.strptime(tick['T'], TIME_FORMAT)
            tick['T'] = close_datetime.replace(tzinfo=timezone.utc).timestamp()

        return results[0]

    async def get_tick_range(self, pair: str, start_time: float, end_time: float) -> List[Dict[str, Any]]:
        """
        Get a range of ticks (closing values and closing times) for a pair from the Bittrex API.
        """

        raise NotImplementedError("Tick range not supported by the Bittrex API.")

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

        market_summaries = await self._get_market_summaries_v1()
        if market_summaries is None:
            return None

        return (market_summaries[pair]['Last'], market_summaries[pair]['BaseVolume'])

    async def buy_limit(self, pair: str, quantity: float, value: float):
        """
        """

        params = [pair, quantity, value]

        results, status = await self.call_extract([
            "['result']['uuid']",
        ], 'buyLimit', params=params, log=True)

        if status != 200 or results is None or results[0] is None:
            self.log.error("Failed executing buy order request: params {}, status {}, results {}.",
                           params, status, results)
            return None

        return results[0]

    async def sell_limit(self, pair: str, quantity: float, value: float):
        """
        """

        params = [pair, quantity, value]

        results, status = await self.call_extract([
            "['result']['uuid']",
        ], 'sellLimit', params=params, log=True, retry_data=True)

        if status != 200 or results is None or results[0] is None:
            self.log.error("Failed executing sell order request: params {}, status {}, results {}.",
                           params, status, results)
            return None

        return results[0]

    async def get_order(self, pair: str, order_id: str):
        """
        """

        params = [order_id]

        results, status = await self.call_extract([
            "['success']",
            "['result']['IsOpen']",
            "['result']['Quantity']",
            "['result']['QuantityRemaining']",
            "['result']['PricePerUnit']",
            "['result']['CommissionPaid']",
        ], 'getOrder', params=params, log=True, retry_data=True)

        if status != 200 or results is None or not results[0]:
            self.log.error("Failed getting order: params{}, status {}, results {}.", params, status, results)
            return None

        return {
            'open': results[1],
            'quantity': results[2],
            'remaining': results[3],
            'value': results[4],
            'fees': results[5],
        }

    async def cancel_order(self, pair: str, order_id: str):
        """
        """

        params = [order_id]
        results, status = await self.call_extract([
            "['success']"
        ], 'cancelOrder', params=params, log=True, retry_data=True)

        if status != 200 or results is None or results[0] is None:
            self.log.error("Failed executing cancel order request: params {} status {}, results {}.",
                           params, status, results)
            return None

        return results[0]

    async def get_balance(self, base: str):
        """
        """

        params = [base]
        results, status = await self.call_extract([
            "['result']['Available']",
        ], 'getBalance', params=params, log=True, retry_data=True)

        if status != 200 or results is None or results[0] is None:
            self.log.error("Failed getting balance: params {}, status {}, results {}.",
                           params, status, results)
            return None

        balance = results[0]

        self.cache['balance'][base] = {
            'time': time.time(),
            'data': balance
        }

        return balance

    async def _get_market_summaries_v1(self):
        """
        Get v1 market summaries from the API, cached for the current tick interval.

        Converts the response list to a dict for faster lookups. This data is used for batching tick updates, since
        the v1 API is kept current (unlike v2).
        """

        await self.lock.acquire()

        if 'marketSummariesV1' in self.cache:
            if time.time() - self.cache['marketSummariesV1']['time'] < config['tick_interval_secs']:
                self.log.debug("Returning cached data for marketSummariesV1.", verbosity=1)
                self.lock.release()
                return self.cache['marketSummariesV1']['data']

        results, status = await self.call_extract([
            "['result']",
            "['result'][0]['Last']",       # For retry of missing fields
            "['result'][0]['BaseVolume']",
            "['result'][0]['PrevDay']",
        ], 'getMarketSummariesV1', retry_data=True)

        if status == 200 and results is not None and results[0] is not None:
            market_summaries = {}
            for result in results[0]:
                market_summaries[result['MarketName']] = result

        else:
            self.log.error("Failed getting v1 market summaries: status {}, results {}.", status, results)
            if 'marketSummariesV1' in self.cache:
                self.cache['marketSummariesV1']['time'] = time.time()
                self.lock.release()
                return self.cache['marketSummariesV1']['data']
            else:
                self.lock.release()
                return None

        self.cache['marketSummariesV1'] = {
            'time': time.time(),
            'data': market_summaries
        }

        self.lock.release()
        return market_summaries
