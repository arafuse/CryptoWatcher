# -*- coding: utf-8 -*-

"""
Gate.io API module.
"""

__author__ = 'Adam Rafuse <$(echo nqnz.enshfr#tznvy.pbz | tr a-z# n-za-m@)>'
__version__ = "0.2.0"
__all__ = ['Client']

import hmac
import json
import asyncio
import hashlib
import traceback

from typing import Any, Dict, List, Sequence

import api
import utils
import common
import configuration

import aiohttp

config = configuration.config
"""
Global configuration.
"""


API_URL = 'https://data.gate.io/api2/1/{}/{}'

API_METHODS = {
    'marketinfo': {
        'path': 'marketinfo',
        'params': '',
        'auth': False
    },
    'tickers': {
        'path': 'tickers',
        'params': '',
        'auth': False
    },
    'ticker': {
        'path': 'ticker',
        'params': '{}',
        'auth': False
    },
    'buy': {
        'path': 'private/buy',
        'params': 'currencyPair={}&rate={}&amount={}',
        'auth': True
    },
    'sell': {
        'path': 'private/sell',
        'params': 'currencyPair={}&rate={}&amount={}',
        'auth': True
    },
    'cancelOrder': {
        'path': 'private/cancelOrder',
        'params': 'orderNumber={}&currencyPair={}',
        'auth': True
    },
    'getOrder': {
        'path': 'private/getOrder',
        'params': 'orderNumber={}&currencyPair={}',
        'auth': True
    },
    'balances': {
        'path': 'private/balances',
        'params': '',
        'auth': True
    }
}


class Client(api.AbstractClient):
    """
    Client for interacting with the Gate.io API.
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

    async def call(self, method: str, params: Sequence[Any]=None):
        """
        Call a Gate.io API method.

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

                    if (status >= 500 and status <= 599) or (status in [408, 429] or status == 0):
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
                await common.backoff(attempt, retry_reason)
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
                (str):   HTTP verb of the request ('GET' or 'POST')
                (str):   Request body, or None if a 'GET' request.
                (dict):  Dictionary of headers for the request, or None if no headers are required.
        """

        query = API_METHODS[method]['params'].format(*params or [])

        if API_METHODS[method]['auth']:
            verb = 'POST'
            body = query            
            api_key = config['gate_api_key']
            api_secret = config['gate_api_secret']
            url = API_URL.format(API_METHODS[method]['path'], '')
            signature = hmac.new(api_secret.encode(), body.encode(), hashlib.sha512).hexdigest()
            headers = {
                'Content-Type': "application/x-www-form-urlencoded",
                'KEY': api_key,
                'SIGN': signature
            }

        else:
            verb = 'GET'
            body = None
            url = API_URL.format(API_METHODS[method]['path'], query)
            headers = None

        return (url, verb, body, headers)

    async def call_json(self, method: str, params: list=None):
        """
        Call a Gate.io API method and parse JSON response.

        Implements retry and exponential backoff for higher-level API error conditions on a 200 response, specifically
        empty response body, and malformed response body (invalid JSON).

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
                await common.backoff(attempt, retry_reason)
                retry = False

        return (data, status)

    async def call_extract(self, extract: Sequence[str], method: str, params: Sequence[Any]=None,
                           retry_data=False, retry_fail=False, log=False):
        """
        Call a Gate.io API method and extract data items from its JSON response.

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
                self.log.error("Could not call Gate.io API method '{}({})'.", method, params)
                return (data, status)

            if log:
                self.log.debug("API method '{}({})' response:\n{}", method, params, json.dumps(data, indent=2))

            if retry_fail and ('result' not in data or not data['result']):
                retry = True

                if data['message'] and data['message'] != '':
                    reason = data['message']
                elif data['msg'] and data['msg'] != '':
                    reason = data['msg']
                else:
                    reason = "'result' == false (blank or missing message)"

            if not retry:
                results, ex = await Client._extract_items(extract, data)
                retry, reason = await Client._handle_extract_exception(ex, data, retry_data)

                if retry:
                    attempt += 1
                    await common.backoff(attempt, reason)
                    retry = False

                else:
                    break

        if reason is not None:
            self.log.debug("Giving up on: {}", reason)

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
            if retry_data:
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
        elif 'msg' in data and data['msg'] and data['msg'] != '':
            api_message = data['msg']
        else:
            api_message = 'empty or missing results'

        return "{} ({}: {})".format(api_message, type(ex).__name__, ex)

    async def get_market_summaries(self) -> List[Dict[str, Any]]:
        """
        Get the market summaries from the Bittrex API.

        Returns:
            The market summaries dict.
        """

        marketinfo, status, = await self.call_extract([
            "['result']",
            "['pairs']",
            "['pairs'][0]['min_amount']",
        ], 'marketinfo', retry_data=True, retry_fail=True)

        if status != 200 or marketinfo is None:
            self.log.error('Could not download market info data.')
            return None

        tickers, status, = await self.call_json('tickers', retry_data=True, retry_fail=True)

        if status != 200 or tickers is None:
            self.log.error('Could not download market summaries data.')
            return None

        # results, status, = await self.call_extract([
        #    "['result']",
        #    "['result'][0]['Market']['BaseCurrency']",  # To retry on any missing fields
        #    "['result'][0]['Market']['MinTradeSize']",
        #    "['result'][0]['Market']['IsActive']",
        #    "['result'][0]['Summary']['MarketName']",
        #    "['result'][0]['Summary']['BaseVolume']",
        #    "['result'][0]['Summary']['PrevDay']",
        #    "['result'][0]['Summary']['Last']",
        #], 'tickers', retry_data=True, retry_fail=True)
