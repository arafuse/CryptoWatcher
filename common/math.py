#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Common math functions.
"""

__author__ = 'Adam Rafuse <$(echo nqnz.enshfr#tznvy.pbz | tr a-z# n-za-m@)>'
__all__ = ['moving_average', 'weighted_avg_forecast', 'norm_slope_simple', 'norm_slope_avg', 'norm_slope_linreg',
           'curvature_simple', 'curvature_avg', 'curvature_linreg']

from typing import Sequence
from array import array

import numpy as np


def diff(source: list):
    """
    Compute the first-order discrete differences for a 1-dimensional list.

    TODO: Support higher orders and dimensions as required.
    """

    result = []

    for index in range(1, len(source)):
        result.append(source[index] - source[index - 1])

    return result


def moving_average(source: Sequence[float], window_size: int):
    """
    Compute a simple moving average from a source list.

    Arguments:
        source:       The source list of data from which to compute the moving average.
        window_size:  The size of the moving average to compute.

    Returns:
        list(float):  The computed moving average. The returned list will contain 0.0 for the first 'window_size'
                      elements.
    """

    result = [0.0] * len(source)    

    for source_index in range(window_size, len(source)):
        window_sum = sum(source[source_index - window_size:source_index])
        result[source_index] = window_sum / window_size

    return result

def ar_moving_average(source: Sequence[float], window_size: int):
    """
    Compute a simple moving average from a source list.

    Arguments:
        source:       The source list of data from which to compute the moving average.
        window_size:  The size of the moving average to compute.

    Returns:
        array:  The computed moving average. The returned array will contain 0.0 for the first 'window_size' elements.
    """

    result = array('d', (0.0 for _ in range(len(source))))

    for source_index in range(window_size, len(source)):
        window_sum = sum(source[source_index - window_size:source_index])
        result[source_index] = window_sum / window_size

    return result

def np_moving_average(source: np.ndarray, window_size: int):
    """
    Compute a simple moving average from a source list.

    Arguments:
        source:       The source list of data from which to compute the moving average.
        window_size:  The size of the moving average to compute.

    Returns:
        list(float):  The computed moving average. The returned list will contain 0.0 for the first 'window_size'
                      elements.
    """

    result = np.zeros(source.size)

    for source_index in range(window_size, source.size):
        window_sum = source[source_index - window_size:source_index].sum()
        result[source_index] = window_sum / window_size

    return result


def exponential_moving_average(source: Sequence[float], window_size: int):
    """
    Compute an exponential moving average from a source list.

    Arguments:
        source:       The source list of data from which to compute the moving average.
        window_size:  The size of the moving average to compute.

    Returns:
        list(float):  The computed moving average. The returned list will contain 0.0 for the first 'window_size'
                      elements.
    """

    result = [0.0] * len(source)

    for source_index in range(window_size * 2, len(source)):
        c = 2.0 / (window_size + 1)
        current_ema = sum(source[source_index - window_size * 2:source_index - window_size]) / window_size

        for value in source[source_index - window_size:source_index]:
            current_ema = (c * value) + ((1 - c) * current_ema)

        result[source_index] = current_ema

    return result

def ar_exponential_moving_average(source: Sequence[float], window_size: int):
    """
    Compute an exponential moving average from a source list.

    Arguments:
        source:       The source list of data from which to compute the moving average.
        window_size:  The size of the moving average to compute.

    Returns:
        array:  The computed moving average. The returned array will contain 0.0 for the first 'window_size' elements.
    """

    result = array('d', (0.0 for _ in range(len(source))))

    for source_index in range(window_size * 2, len(source)):
        c = 2.0 / (window_size + 1)
        current_ema = sum(source[source_index - window_size * 2:source_index - window_size]) / window_size

        for value in source[source_index - window_size:source_index]:
            current_ema = (c * value) + ((1 - c) * current_ema)

        result[source_index] = current_ema

    return result

def np_exponential_moving_average(source: np.ndarray, window_size: int):
    """
    Compute an exponential moving average from a source list.

    Arguments:
        source:       The source list of data from which to compute the moving average.
        window_size:  The size of the moving average to compute.

    Returns:
        list(float):  The computed moving average. The returned list will contain 0.0 for the first 'window_size'
                      elements.
    """

    result = np.zeros(source.size)

    for source_index in range(window_size * 2, source.size):
        c = 2.0 / (window_size + 1)
        current_ema = source[source_index - window_size * 2:source_index - window_size].sum() / window_size

        for value in source[source_index - window_size:source_index]:
            current_ema = (c * value) + ((1 - c) * current_ema)

        result[source_index] = current_ema

    return result

def weighted_avg_forecast(source: list, window_size: int, num: int, weight: float=1.0):
    """
    Forecast new values from a list of existing values using a weighted average delta formula.

    Noticeably faster than linear regression while producing similar results.

    Arguments:
        source:       List of data to forecast from (integer or floating point).
        window_size:  The number of elements to use from the end of 'source' for prediction.
        num:          The number of elements to forecast.
        weight:       Amount of weight to give to the elements closest to the predicted data. Values less than 1.0 will
                      give the most weight to the farthest elements. Values exceeding 2.0 or -2.0 will increasingly
                      give no weight to the farthest and nearest elements, respectively.

    Returns:
        list(float):  A list of the additional predicted data.
    """

    assert num <= window_size, "Cannot forecast more elements than window size."
    assert len(source) >= window_size, ("Source data length {} is less than window size {}."
                                        .format(len(source), window_size))

    result = []
    weight_step = (weight - (1.0 + (1.0 - weight))) / window_size

    for index in range(num):
        delta_avg = 0.0

        # Include any previously forecasted data.
        for window_index in range(index):
            if window_index == 0:
                sample_2 = source[-1]
                sample_1 = result[0]
            else:
                sample_2 = result[-(window_index + 1)]
                sample_1 = result[-(window_index)]

            sample_delta = sample_1 - sample_2
            weight_amount = (weight - (weight_step * window_index))
            if (weight_amount) < 0: weight_amount = 0
            delta_avg += sample_delta * weight_amount

        # Include remaining source data.
        for window_index in range(window_size - index):
            sample_delta = (source[-(window_index + 1)] - source[-(window_index + 2)])
            weight_amount = (weight - (weight_step * (window_index + index)))
            if (weight_amount) < 0: weight_amount = 0
            delta_avg += sample_delta * weight_amount

        last_sample = source[-1] if index == 0 else result[-1]
        delta_avg /= window_size
        result.append(last_sample + delta_avg)

    return result


def norm_slope_simple(source: list, norm: float=None):
    """
    Calculate the normalized slope of a source list of values based on the slope of the extrema.

    Arguments:
        source:  List of values to analyze (integer or floating point).
        norm:    Value to normalize to, or None to normalize to first value in source.

    Returns:
        (float):  Normalized slope of the list.
    """

    if norm is None: norm = source[0]
    return (source[-1] - source[0]) / norm / len(source)


def norm_slope_avg(source: list, norm: float=None):
    """
    Calculate the normalized average slope of all elements of a source list of values.

    Arguments:
        source:  List of values to analyze (integer or floating point).
        norm:    Value ot normalize to, or None to normalize to first value in source.

    Returns:
        (float):  Normalized slope of the list.
    """

    delta = 0
    if norm is None: norm = source[0]
    length = len(source)

    for x in range(1, length):
        delta += (source[x] - source[x - 1]) / norm

    return delta / (length - 1) if length > 1 else delta


def norm_slope_linreg(source: list, norm: float=None):
    """
    Calculate the normalized slope of the linear regression of a source list of values.

    Arguments:
        source:  List of values to analyze (integer or floating point).
        norm:    Value to normalize to, or None to normalize to first value in source.

    Returns:
        (float):  Normalized slope of the list.
    """

    length = len(source)
    if norm is None: norm = source[0]

    y = [value / norm for value in source]
    x = [value for value in range(length)]

    x_sum = sum(x)
    y_sum = sum(y)

    squared_sum = sum(map(lambda a: a * a, x))
    products_sum = sum([x[i] * y[i] for i in range(length)])

    return (products_sum - (x_sum * y_sum) / length) / (squared_sum - ((x_sum ** 2) / length))


def curvature_simple(source: list, norm: float=None):
    """
    Calculate the curvature of a given list of values, using a simple slope.

    TODO: Allow for variable numbers of splits.

    Arguments:
        source:  List of data to values (integer or floating point).
        norm:    Value to normalize to, or None to normalize to first value in source.

    Returns:
        (float):  <0 if data is convex, >0 if data is concave. Greater magnitude corresponds to greater curvature.
    """

    split = len(source) // 2
    if norm is None: norm = source[0]

    norm_slope_1 = (source[split] - source[0]) / norm / split
    norm_slope_2 = (source[-1] - source[split]) / source[split] / len(source[split:])

    return norm_slope_2 - norm_slope_1


def curvature_avg(source: list, norm: float=None):
    """
    Calculate the curvature of a given list of values with reasonable accuracy, using the average slope.

    TODO: Allow for variable numbers of splits.

    Arguments:
        source:  List of data to values (integer or floating point).
        norm:    Value to normalize to, or None to normalize to first value in source.

    Returns:
        (float):  < 0 if data is convex, >0 if data is concave. Greater magnitude corresponds to greater curvature.
    """

    split = len(source) // 2
    if norm is None: norm = source[0]

    norm_slope_1 = norm_slope_avg(source[:split], norm)
    norm_slope_2 = norm_slope_avg(source[split:], norm)

    return norm_slope_2 - norm_slope_1


def curvature_linreg(source: list, norm: float=None):
    """
    Calculate the curvature of a given list of values with reasonable accuracy, using a linear regression based slope.

    TODO: Allow for variable numbers of splits.

    Arguments:
        source:  List of data to values (integer or floating point).

    Returns:
        (float):  < 0 if data is convex, >0 if data is concave. Greater magnitude corresponds to greater curvature.
    """

    split = len(source) // 2
    if norm is None: norm = source[0]

    norm_slope_1 = norm_slope_linreg(source[:split], norm)
    norm_slope_2 = norm_slope_linreg(source[split:], norm)

    return norm_slope_2 - norm_slope_1
