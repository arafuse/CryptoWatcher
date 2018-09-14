#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API module.
"""

__author__ = 'Adam Rafuse <$(echo nqnz.enshfr#tznvy.pbz | tr a-z# n-za-m@)>'
__version__ = "0.2.0"
__all__ = ['Client']

import abc
from typing import Any, Dict, Sequence, List, Tuple


class Client(abc.ABC):
    """
    """

    @abc.abstractmethod
    async def call(self, method: str, params: Sequence[Any]=None):
        """
        Call an API method and return the raw response.

        Implements retry and exponentional backoff for HTTP level error conditions.

        Arguments:
            method:  Name of the API method to call.
            params:  Values of query parameters to pass to the method.

        Returns:
            (tuple):  A tuple containing:

            data (str):     The raw HTTP response body (may be None).
            status (int):   The HTTP response status code. A value of 0 indicates a connection or transport failure.
        """

    @abc.abstractmethod
    async def call_json(self, method: str, params: list=None):
        """
        Call an API method and parse JSON response.

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

    @abc.abstractmethod
    async def call_extract(self, extract: Sequence[str], method: str, params: Sequence[Any]=None,
                           retry_data=False, retry_fail=False, log=False):
        """
        Call an API method and extract data items from its JSON response.

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

    @abc.abstractmethod
    async def get_market_summaries(self) -> List[Dict[str, Any]]:
        """
        Get the market summaries from the API.

        Returns:
            The market summaries dict.
        """

    @abc.abstractmethod
    async def get_ticks(self, pair: str, length: int=None) -> List[Dict[str, Any]]:
        """
        Get ticks (closing values and closing times) for a pair from the API.

        Arguments:
            pair:    The currency pair eg. 'BTC-ETH'.
            length:  Maximum number of ticks to return if supported.

        Returns:
            A list of the raw tick data from the API.
        """

    @abc.abstractmethod
    async def get_tick_range(self, pair: str, start_time: float, end_time: float) -> List[Dict[str, Any]]:
        """
        Get a range of ticks (closing values and closing times) for a pair from the API.

        Arguments:
            pair:        The currency pair eg. 'BTC-ETH'.
            start_time:  Timestamp to start at.
            end_time:    Timestamp to start at.

        Returns:
            A list of the raw tick data from the API.
        """

    @abc.abstractmethod
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

    @abc.abstractmethod
    async def buy_limit(self, pair: str, quantity: float, value: float):
        """
        """

    @abc.abstractmethod
    async def sell_limit(self, pair: str, quantity: float, value: float):
        """
        """

    @abc.abstractmethod
    async def get_order(self, pair: str, order_id: str):
        """
        """

    @abc.abstractmethod
    async def cancel_order(self, pair: str, order_id: str):
        """
        """

    @abc.abstractmethod
    async def get_balance(self, base: str):
        """
        """
