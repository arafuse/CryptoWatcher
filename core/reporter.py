# -*- coding: utf-8 -*-

# Copyright (c) A 2017 Adam M. Rafuse - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential

"""
Reporter service.
"""

__author__ = 'Adam Rafuse <$(echo nqnz.enshfr#tznvy.pbz | tr a-z# n-za-m@)>'
__all__ = ['Reporter']

import http
import json
import base64
import pickle
import socket
import urllib
import multiprocessing.pool

from typing import Any, Dict, List, Sequence

import core
import utils
import common
import common.base
import configuration

config = configuration.config
"""
Global configuration.
"""


class Reporter(common.base.Persistable):
    """
    Reporter service object.

    Manages output to the user such as alerting, charts, and snapshots.
    """

    def __init__(self, market: core.Market, log=utils.logging.DummyLogger()):

        super().__init__(log=log)

        self.market = market
        """
        Shared :class:`Market` object.
        """

        self.log = utils.logging.ChildLogger(parent=log, scope=self)
        """
        Object logger.
        """

        self.follow_up_snapshots: List[Dict[str, Any]] = []
        """
        Snapshots that need to be taken in the future as a follow-up. These are useful for inspecting the results of
        detections.

        ``
        [
            {
               'pair': (str):              Name of the currency pair for this snapshot.
               'name': (str):              Name of the original snapshot.
               'snapshot_time': (float):   UTC timestamp in seconds of when the original snapshot was taken.
               'follow_up_time': (float):  UTC timestamp in seconds of when to take the follow-up snapshot.
            },
            ... for snapshot in pending follow-up snapshots
        ]
        ``
        """

        self.render_pool: multiprocessing.pool.Pool = common.get_task_pool()
        """
        Rendering task pool.
        """

    async def output_chart(self, pair: str, data: Dict[Any, Sequence[float]], filename: str):
        """
        Output a chart in SVG format for the specified currency pair.

        Arguments:
            pair:      Name of the currency pair eg 'BTC-ETH'.
            data:      Dictionary of lists of chart data to output.
            filename:  The filename including path of the chart file to output, minus the extension.
        """

        if config['chart_format'] == 'json':
            chart_filename = filename + '.json'
            with open(chart_filename, 'w') as file:
                json.dump(data, file)

        elif config['chart_format'] == 'pickle':
            chart_filename = filename + '.pickle'
            with open(chart_filename, 'wb') as file:
                pickle.dump(data, file)

        elif config['chart_format'] == 'svg':
            chart_filename = filename + '.svg'
            self.render_pool.apply_async(common.render_svg_chart, [pair, data, chart_filename])

        else:
            self.log.error("Invalid chart format specified: {}", config['chart_format'])
            return

        self.log.debug('{} saved chart to {}.', pair, chart_filename, verbosity=1)

    async def output_metadata(self, data: Dict[Any, Any], filename: str):
        """
        Output metadata data to a JSON or pickle file.

        Arguments:
            data:      The data to dump.
            filename:  The filename including path of the ile to output, minus the extension.
        """

        if config['snapshot_format'] == 'json':
            meta_filename = filename + '.json'
            with open(meta_filename, 'w') as file:
                json.dump(data, file, indent=2, sort_keys=True)

        elif config['snapshot_format'] == 'pickle':
            meta_filename = filename + '.pickle'
            with open(meta_filename, 'wb') as file:
                pickle.dump(data, file)

        else:
            self.log.error("Invalid snapshot format specified: {}", config['snapshot_format'])
            return

        self.log.debug("Saved metadata file to {}", meta_filename, verbosity=1)

    async def output_snapshot(self, pair: str, name: str, trigger_data: Dict[str, Any]=None, follow_up=True):
        """
        Output a snapshot for a given pair.

        Outputs current value and active indicator SVG charts and JSON metadata for a given pair. Optionally
        queues the snapshot for a later chart follow-up.

        Arguments:
            pair:          Name of the currency pair this snapshot is for eg 'BTC-ETH'.
            name:          Name of the snapshot, usually a detection or alert name eg. 'Breakout 0 confirm 0'.
            trigger_data:  Optional trigger data from a causing detection to include in the JSON metadata for this
                           snapshot. If None, only basic metadata (name, value) is saved.
            follow_up:     If True, queues an automatic follow-up snapshot of the charts for this pair after
                           data:`config['follow_up_secs']`.
        """

        if not config['enable_snapshots']:
            return

        current_time = self.market.close_times[pair][-1]

        await self._output_snapshot_charts(pair, name, current_time)
        await self._output_snapshot_metadata(pair, name, current_time, trigger_data)

        if follow_up and config['follow_up_secs']:
            follow_up_time = current_time + config['follow_up_secs']
            self.follow_up_snapshots.append({
                'pair': pair,
                'name': name,
                'snapshot_time': current_time,
                'follow_up_time': follow_up_time
            })
            self.log.debug("{} queued for follow up snapshot at {} for '{}'", pair, follow_up_time, name)

        self.save_attr('follow_up_snapshots')

    async def check_follow_up_snapshots(self):
        """
        Check the queue of pending follow-up snapshots and execute any that are due.

        Intended to be called on an interval after a time delay eg. from a coroutine task.
        """

        remove_indexes = []

        for index, snapshot in enumerate(self.follow_up_snapshots):
            pair = snapshot['pair']

            last_close_time = self.market.close_times[config['base_pairs'][0]][-1]
            if last_close_time > snapshot['follow_up_time']:
                try:
                    if not config['enable_backtest']:
                        if pair not in self.market.pairs and pair not in self.market.extra_base_pairs:
                            await self.market.refresh_tick_data(pair)
                            await self.market.update_tick_data(pair)
                            await self.market.refresh_derived_data(pair)

                    else:
                        if pair not in self.market.adjusted_close_values:
                            await self.market.refresh_derived_data(pair)

                    name = snapshot['name']
                    await self._output_snapshot_charts(pair, name, snapshot['snapshot_time'], follow_up=True)
                    self.log.info("{} processed follow-up snapshot for '{}'.", pair, name)

                except KeyError:
                    # Has happened with exchanges suddenly de-listing coins.
                    self.log.warning("{} is now defunct, discarding follow-up snapshot for '{}'.", pair, name)

                remove_indexes.append(index)

        for index in reversed(remove_indexes):
            del self.follow_up_snapshots[index]

        if remove_indexes:
            self.save_attr('follow_up_snapshots')

    async def _output_snapshot_charts(self, pair: str, name: str, timestamp: float, follow_up=False):
        """
        Output value and active indicator charts for a snapshot.

        Arguments:
            pair:       Name of the currency pair this snapshot is for eg 'BTC-ETH'.
            name:       Name of the snapshot, usually a detection name eg. 'Breakout 0 confirm 0'.
            timestamp:  UTC timestamp of this snapshot, usually the time of the causing detection.
            follow_up:  If True, appends "follow-up" to the resulting filenames.
        """

        time_str = common.utctime_str(timestamp, config['time_format'])
        full_name = '{} {} {}'.format(pair, name, time_str)
        price_filename = config['snapshot_path'] + full_name + ' price'
        volume_filename = config['snapshot_path'] + full_name + ' volume'
        ema_filename = config['snapshot_path'] + full_name + ' ema'
        rsi_filename = config['snapshot_path'] + full_name + ' rsi'

        if follow_up:
            price_filename += ' follow-up'
            volume_filename += ' follow-up'
            ema_filename += ' follow-up'
            rsi_filename += ' follow-up'

        price_data = self.market.close_value_mas[pair]
        if config['chart_show_close']:
            price_data.update({'C': self.market.adjusted_close_values[pair]})

        volume_data = self.market.volume_deriv_mas[pair]
        # volume_data.update({'VD': self.market.base_24hr_volumes[pair][1]})

        if config['enable_bbands']:
            price_data.update(self.market.bollinger_bands[pair])

        await self.output_chart(pair, price_data, price_filename)
        await self.output_chart(pair, volume_data, volume_filename)

        if config['ema_windows']:
            await self.output_chart(pair, self.market.close_value_emas[pair], ema_filename)

        if config['enable_rsi']:
            await self.output_chart(pair, {'RSI': self.market.relative_strength_indexes[pair]}, rsi_filename)

        self.log.debug("{} saved snapshot charts for '{}'", pair, full_name)

    async def _output_snapshot_metadata(self, pair: str, name: str, timestamp: float,
                                        trigger_data: Dict[str, Any]=None):
        """
        Output metadata for a snapshot.

        Arguments:
            pair:          Name of the currency pair this snapshot is for eg 'BTC-ETH'.
            name:          Name of the snapshot, usually a detection name eg. 'Breakout 0 confirm 0'.
            timestamp:     UTC timestamp of this snapshot, usually the time of the causing detection.
            trigger_data:  Optional trigger data from a causing detection to include in the JSON metadata for this
                           snapshot. If None, only basic metadata (name, value) is saved.
        """

        time_str = common.utctime_str(timestamp, config['time_format'])
        full_name = '{} {} {}'.format(pair, name, time_str)

        metadata_filename = config['snapshot_path'] + full_name
        metadata = trigger_data.copy() if trigger_data else {'followed_name': None}
        metadata['name'] = full_name
        metadata['value'] = self.market.close_values[pair][-1]

        await self.output_metadata(metadata, metadata_filename)
        self.log.debug("Saved snapshot metadata for '{}'", full_name)

    async def send_alert(self, pair: str, trigger_data: dict, detection_name: str=None,
                         prefix: str=None, color: str=None, sound: str=None, follow_up: bool=True):
        """
        Send an alert for the specified currency pair and detection.

        Arguments:
            pair:            Name of the currency pair eg 'BTC-ETH'.
            detection_name:  Name of the detection.
            trigger_data:    Aggregate trigger data from the detection.
        """

        default_params = {
            'color': color if color else '\033[1;93m',
            'sound': sound if sound else config['alert_sound'],
            'snapshot': True
        }

        if detection_name is not None:
            params = core.Detector.get_detection_params(detection_name, default_params)
        else:
            params = default_params

        if detection_name is not None:
            name = prefix + ' ' + detection_name if prefix else detection_name
        else:
            name = prefix if prefix else ''

        alert_string = '{}{}\033[0m for {}'.format(params['color'], name, pair)
        await self.output_alert(pair, alert_string, params['sound'])
        if params['snapshot']:
            await self.output_snapshot(pair, name, trigger_data, follow_up=follow_up)

    async def output_alert(self, pair, text, sound_file=None):
        """
        Handle the actual audio, visual, and logging of an alert.

        Arguments:
            pair:        Name of the currency pair eg 'BTC-ETH'.
            text:        The text to display and log for this alert.
            sound_file:  Path to the sound file to play for this alert, defaults to None.
        """

        now_string = common.utctime_str(self.market.close_times[pair][-1], config['time_format'])
        alert_string = '{} at {}'.format(text, now_string)
        self.log.info(alert_string)

        if sound_file is not None:
            common.play_sound(config['data_dir'] + sound_file)

        with open(config['alert_log'], 'a') as alert_log_file:
            alert_log_file.write(alert_string + '\n')

    def email_report(self, buffer: Sequence[str]):
        """
        Email a report to the administrator using the Mailgun API.

        Arguments:
            buffer:  List of strings for each line of the report.
        """

        fqdn = socket.getfqdn()
        auth = base64.b64encode('api:{}'.format(config['mailgun_api_key']).encode()).decode()
        host = 'api.mailgun.net'
        path = "/v3/{}/messages".format(config['mailgun_domain'])
        text = '\n'.join(buffer)

        headers = {
            'Authorization': 'Basic {}'.format(auth),
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        body = {
            "from": '"CryptoWatcher" <do-not-reply@{}>'.format(config['mailgun_domain']),
            "to": config['admin_email'],
            "subject": "Log report from {}".format(fqdn),
            "text": text,
            "html": "<pre>{}</pre>".format(text)
        }

        conn = http.client.HTTPSConnection(host)
        conn.request('POST', path, body=urllib.parse.urlencode(body), headers=headers)
        response = conn.getresponse()

        self.log.debug("Report emailed: response {}, status {}.", response.read(), response.status)
