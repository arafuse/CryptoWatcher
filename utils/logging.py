#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Enhanced logging package.
"""

__author__ = 'Adam Rafuse <$(echo nqnz.enshfr#tznvy.pbz | tr a-z# n-za-m@)>'
__version__ = "0.6.0"
__license__ = "http://opensource.org/licenses/MIT"
__all__ = ['Logger', 'DummyLogger', 'ThreadedLogger', 'ChildLogger',
           'NOTSET', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

# TODO: Current time output is in UTC only.

import abc
import sys
import time
import queue
import logging
import inspect
import datetime
import threading

from typing import Dict, Callable, Sequence, TextIO

NOTSET = logging.NOTSET
DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL
DISABLED = logging.CRITICAL + 50


class Logger(abc.ABC):
    """Abstract logger."""

    @abc.abstractmethod
    def log(self, level: int, message: str, scope: object=None, stack_depth: int=0):
        """
        Log a message at a given level.

        Arguments:
            level:        Logging level (DEBUG .. CRITICAL).
            message:      The message to log.
            scope:        Optionally override default logger scope if not None. Can be an object or a string, eg. self
                          or __name__. Prepended to method names in log entries for loggers that support it.
            stack_depth:  Additional stack depth to trace back for the calling method name (default 0). Useful when
                          calling from inside a helper method but wanting to log the outer method name.
        """

    @abc.abstractmethod
    def debug(self, message: str, *args, stack_depth: int=0, verbosity: int=0):
        """
        Log a message at DEBUG level, with formatting.

        Arguments:
            message:        Message to log. Can include format string syntax as per str.format().
            *args:          Format string positional arguments for 'message'.
            stack_depth:    See 'stack_depth' in :meth:`log`,
            verbosity:      Display output is silenced if greater than configured verbosity for loggers that support
                            it.
        """

    @abc.abstractmethod
    def info(self, message: str, *args, stack_depth: int=0):
        """
        Log a message at INFO level, with formatting.

        Arguments:
            message:        Message to log. Can include format string syntax as per str.format().
            *args:          Format string positional arguments for 'message'.
            stack_depth:    See 'stack_depth' in :meth:`log`.
        """

    @abc.abstractmethod
    def warning(self, message: str, *args, stack_depth: int=0):
        """
        Log a message at WARNING level, with formatting.

        Arguments:
            message:        Message to log. Can include format string syntax as per str.format().
            *args:          Format string positional arguments for 'message'.
            stack_depth:    See 'stack_depth' in :meth:`log`.
        """

    @abc.abstractmethod
    def error(self, message: str, *args, stack_depth: int=0):
        """
        Log a message at ERROR level, with formatting.

        Arguments:
            message:        Message to log. Can include format string syntax as per str.format().
            *args:          Format string positional arguments for 'message'.
            stack_depth:    See 'stack_depth' in :meth:`log`.
        """

    @abc.abstractmethod
    def critical(self, message: str, *args, stack_depth: int=0):
        """
        Log a message at CRITICAL level, with formatting.

        Arguments:
            message:        Message to log. Can include format string syntax as per str.format().
            *args:          Format string positional arguments for 'message'.
            stack_depth:    See 'stack_depth' in :meth:`log`.
        """

    @abc.abstractproperty
    def level(self):
        """"int: The configured minimum level of this logger."""

    @abc.abstractproperty
    def debug_verbosity(self):
        """"int: The configured debug verbosity of this logger."""


class DummyLogger (Logger):
    """
    Logger that does nothing.

    Used as a default logger for methods and classes that require one, to make logging optional.
    """

    def log(self, level: int, message: str, scope: object=None, stack_depth: int=0):
        pass

    def debug(self, message: str, *args, stack_depth: int=0, verbosity: int=0):
        pass

    def info(self, message: str, *args, stack_depth: int=0):
        pass

    def warning(self, message: str, *args, stack_depth: int=0):
        pass

    def error(self, message: str, *args, stack_depth: int=0):
        pass

    def critical(self, message: str, *args, stack_depth: int=0):
        pass

    @property
    def level(self):
        return NOTSET

    @property
    def debug_verbosity(self):
        return 0


class ThreadedLogger (Logger, threading.Thread):
    """
    Multithreaded logger with other goodies.

    Arguments:
        scope:            Calling object or module name. Can be an object or a string, eg. self or __name__. Prepended
                          to method names in log entries if set (default None).
        level:            Minimum overall logging level (default NOTSET).
        display_level:    Minimum logging level for display stream output (default NOTSET).
        logger_level:     Minimum logging level for logger output (default DISABLED).
        html:             Formats output as HTML if True, otherwise uses plaintext with ANSI escapes (default False).

        filename:         If set, the default info logger handler is a FileHandler with this filename.
        debug_filename:   If set, the default debug logger handler is a FileHandler with this filename.
        error_filename:   If set, the default warning, error and critical logger handler is a FileHandler with this
                          filename.

        module_name:      Name of this logging module (default: None for the root logger). This is used in the names
                          of internal loggers. Eg. None will use loggers None (root), 'debug' and 'error'; a module
                          name of 'default' will use 'default', 'default_debug' and 'default_error' etc.
        time_format:      Format of displayed time as passed to strftime() for log messages (default
                          '%Y-%m-%dT%H:%M:%S:%f').
        inspect_stack:    If false, does not perform stack inspection to get the calling method name. Useful if
                          stack inspection does not work on a particular Python implementation (like Cython) (default
                          True).
        debug_verbosity:  Controls the level of debug display output with the 'verbosity' argument to :meth:`debug`
                          (default 0). Debug messages with verbosity higher than this will not be displayed. Setting
                          this to -1 or lower can effectively silence debug display output only while still sending to
                          the logger.

        output_stream:    File object used for info and debug display stream output (default stdout).
        error_stream:     File object used for warning, error, and critical display stream output (default stderr).

    Attributes:
        Visible attributes can be modified post-construction:

        scope (object):             See 'scope' above.
        debug_verbosity (int):      See 'debug_verbosity' above.
        inspect_stack (bool):       See 'inspect_stack' above.
        time_format (str):          See 'time_format' above.

        These attributes control how the text of logging level labels appear in the display streams, and by default
        include ANSI color escapes / HTML color attributes:

        debug_text (str):           Text of the log label for 'debug' messages.
        info_text (str):            Text of the log label for 'info' messages.
        warning_text (str):         Text of the log label for 'warning' messages.
        error_text (str):           Text of the log label for 'error' messages.
        critical_text (str):        Text of the log label for 'critical' messages.
        debug_html (str):           HTML of the log label for 'debug' messages.
        info_html (str):            HTML of the log label for 'info' messages.
        warning_html (str):         HTML of the log label for 'warning' messages.
        error_html (str):           HTML of the log label for 'error' messages.
        critical_html (str):        HTML of the log label for 'critical' messages.

        These streams default to sys.stdout and sys.stderr respectively. These can be replaced eg. with io.StringIO
        streams or the output stream of a web framework like a webapp2 response:

        output_stream (object):     The file object used for info and warning display stream output.
        error_stream (object):      The file object used for debug, error, and critical display stream output.
    """

    def __init__(self, *args, scope: object=None, html: bool=False, module_name: str=None,
                 level: int=NOTSET, display_level: int=NOTSET, logger_level: int=DISABLED,
                 filename: str=None, debug_filename: str=None, error_filename: str=None,
                 inspect_stack: bool=True, time_format: str='%Y-%m-%dT%H:%M:%S:%f',
                 output_stream: TextIO=None, error_stream: TextIO=None,
                 callback: Callable[[Sequence[str]], None]=None, callback_interval: float=900.0,
                 callback_level: int=WARNING, debug_verbosity: int=0, **kwargs):

        threading.Thread.__init__(self, *args, **kwargs)

        self.scope = scope

        self.inspect_stack = inspect_stack
        self.time_format = time_format

        self.debug_text = '\033[1;95mDEBUG\033[0m'
        self.info_text = '\033[1;94mINFO\033[0m'
        self.warning_text = '\033[1;93mWARNING\033[0m'
        self.error_text = '\033[1;91mERROR\033[0m'
        self.critical_text = '\033[1;41mCRITICAL\033[0m'
        self.time_text = '\033[97m{}\033[0m'

        self.debug_html = '<span style="color:#ff007f">DEBUG</span>'
        self.info_html = '<span style="color:#007fff">INFO</span>'
        self.warning_html = '<span style="color:#ffdf00">WARNING</span>'
        self.error_html = '<span style="color:#ff3f3f>ERROR</span>'
        self.critical_html = '<span style="color:#ff3f3f><b>CRITICAL</b></span>'

        self._logger: logging.Logger = None
        self._debug_logger: logging.Logger = None
        self._error_logger: logging.Logger = None

        self.output_stream: TextIO = None
        self.error_stream: TextIO = None

        self._module_name = module_name

        self._level = level
        self._display_level = display_level
        self._logger_level = logger_level
        self._debug_verbosity = debug_verbosity

        self._logger_methods: Dict[str, Callable[..., None]] = None
        self._display_methods: Dict[str, Callable[..., None]] = None

        self._html = html
        self._logger_string = '[{}][{}] {}:{} {}'
        self._log_level_labels: Dict[int, str] = None
        self._display_string: str = None
        self._display_debug_string: str = None

        self.callback = callback
        self.callback_interval = callback_interval
        self.callback_level = callback_level

        self._callback_buffer = []
        self._callback_time = time.time()
        self._callback_triggered = False

        self._set_output_streams(output_stream, error_stream)
        self._set_loggers(module_name)
        self._set_logger_methods()
        self._set_display_mode()
        self._set_file_handlers(filename, debug_filename, error_filename)

        self._running = threading.Event()
        self._running.set()

        self._log_entries = queue.Queue()
        """
        Queue of log entries processed by the logger main thread.

        [
            {
                scope (object):       Object or string to log as the scope caller.
                level(int):            Log level (DEBUG .. CRITICAL).
                message(str):          Message to log.
                timestamp(float):      Epoch seconds of this log record.
                stack_depth(int):      Depth of stack to trace back for caller name.
                stack_frame(object):  Stack frame of the method which invoked the logging call.
            },
            ...
        ]
        """

    @property
    def level(self):
        return self._level

    @property
    def debug_verbosity(self):
        return self._debug_verbosity

    @debug_verbosity.setter
    def debug_verbosity(self, value: int):
        self._debug_verbosity = value

    @property
    def logger(self):
        """logging.Logger: The underlying logger used for info output."""
        return self._logger

    @property
    def debug_logger(self):
        """logging.Logger: The underlying logger used for debug output."""
        return self._debug_logger

    @property
    def error_logger(self):
        """logging.Logger: The underlying logger used for warning, error, and critical output."""
        return self._error_logger

    def config(self, scope: object=None, level: int=None, display_level: int=None, logger_level: int=None,
               html: bool=None, filename: str=None, debug_filename: str=None, error_filename: str=None,
               module_name: str=None, inspect_stack: bool=None, time_format: str=None,
               output_stream: TextIO=None, error_stream: TextIO=None,
               callback: Callable[[Sequence[str]], None]=None, callback_interval: float=None, callback_level: int=None,
               debug_verbosity: int=None):
        """
        Configure the logger with new parameters.

        This method can be called after the logger has been created to reconfigure it on the fly.

        Arguments:
            scope:            Change 'scope' if set, see :meth:`__init__`.
            level:            Change 'level' if set, see :meth:`__init__`.
            display_level:    Change 'display_level' if set, see :meth:`__init__`.
            logger_level:     Change 'logger_level' if set, see :meth:`__init__`.
            html:             Change 'html' if set, see :meth:`__init__`.
            filename:         Change 'filename' if set, see :meth:`__init__`.
            debug_filename:   Change 'debug_filename' if set, see :meth:`__init__`.
            error_filename:   Change 'error_filename' if set, see :meth:`__init__`.
            module_name:      Change 'module_name' if set, see :meth:`__init__`.
            time_format:      Change 'time_format' if set, see :meth:`__init__`.
            inspect_stack:    Change 'inspect_stack' if set, see :meth:`__init__`.
            debug_verbosity:  Change 'debug_verbosity' if set, see :meth:`__init__`.
            output_stream     Change 'output_stream' if set, see :meth:`__init__`.
            error_stream      Change 'error_stream' if set, see :meth:`__init__`.
        """

        if scope is not None: self.scope = scope
        if level is not None: self._level = level
        if display_level is not None: self._display_level = display_level
        if logger_level is not None: self._logger_level = logger_level
        if debug_verbosity is not None: self._debug_verbosity = debug_verbosity
        if inspect_stack is not None: self.inspect_stack = inspect_stack
        if time_format is not None: self.time_format = time_format
        if html is not None: self._html = html
        if output_stream is not None: self.output_stream = output_stream
        if error_stream is not None: self.error_stream = error_stream
        if callback is not None: self.callback = callback
        if callback_interval is not None: self.callback_interval = callback_interval
        if callback_level is not None: self.callback_level = callback_level

        self._set_loggers(module_name)
        self._set_logger_methods()
        self._set_display_mode()
        self._set_file_handlers(filename, debug_filename, error_filename)

    def _set_output_streams(self, output_stream: TextIO, error_stream: TextIO):
        """
        Set the output streams for logging display.
        """

        if output_stream is not None:
            self.output_stream = output_stream
        else:
            self.output_stream = sys.stdout

        if error_stream is not None:
            self.error_stream = error_stream
        else:
            self.error_stream = sys.stderr

    def _set_loggers(self, module_name: str):
        """
        Set each logger.

        Three separate loggers are used to be able to split file output for different log levels.
        """

        self._logger = logging.getLogger(module_name)
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False

        debug_prefix = module_name + "_" if module_name is not None else ''
        self._debug_logger = logging.getLogger(debug_prefix + 'debug')
        self._debug_logger.setLevel(logging.DEBUG)
        self._debug_logger.propagate = False

        error_prefix = module_name + "_" if module_name is not None else ''
        self._error_logger = logging.getLogger(error_prefix + 'error')
        self._error_logger.setLevel(logging.WARNING)
        self._error_logger.propagate = False

    def _set_logger_methods(self):
        """
        Set each logger method selectively based on the configured log levels.
        """

        self._logger_methods = {
            DEBUG: self._debug_logger.log if self._logger_level <= DEBUG else lambda *_, **__: None,
            INFO: self._logger.log if self._logger_level <= INFO else lambda *_, **__: None,
            WARNING: self._error_logger.log if self._logger_level <= WARNING else lambda *_, **__: None,
            ERROR: self._error_logger.log if self._logger_level <= ERROR else lambda *_, **__: None,
            CRITICAL: self._error_logger.log if self._logger_level <= CRITICAL else lambda *_, **__: None,
        }

        self._display_methods = {
            DEBUG: self.output_stream.write if self._display_level <= DEBUG else lambda *_, **__: None,
            INFO: self.output_stream.write if self._display_level <= INFO else lambda *_, **__: None,
            WARNING: self.error_stream.write if self._display_level <= WARNING else lambda *_, **__: None,
            ERROR: self.error_stream.write if self._display_level <= ERROR else lambda *_, **__: None,
            CRITICAL: self.error_stream.write if self._display_level <= CRITICAL else lambda *_, **__: None,
        }

        self.debug = self._debug if self._level <= DEBUG else lambda *_, **__: None
        self.info = self._info if self._level <= INFO else lambda *_, **__: None
        self.warning = self._warning if self._level <= WARNING else lambda *_, **__: None
        self.error = self._error if self._level <= ERROR else lambda *_, **__: None
        self.critical = self._critical if self._level <= CRITICAL else lambda *_, **__: None

    def _set_display_mode(self):
        """
        Set display mode for either ANSI text or HTML depending on the configured switch.
        """

        if self._html:
            self._log_level_labels = {
                DEBUG: self.debug_html,
                INFO: self.info_html,
                WARNING: self.warning_html,
                ERROR: self.error_html,
                CRITICAL: self.critical_html,
            }
            self._display_string = '<b>[{{}}][{}] {{}}:{{}}</b> {{}}</br>'.format(self.time_text)
            self._display_debug_string = ('<code><b>[{{}}][{}] {{}}:{{}}</b> {{}}</br></code>'
                                          .format(self.time_text))

        else:
            self._log_level_labels = {
                DEBUG: self.debug_text,
                INFO: self.info_text,
                WARNING: self.warning_text,
                ERROR: self.error_text,
                CRITICAL: self.critical_text,
            }
            self._display_string = '[{{}}][{}] {{}}:{{}} {{}}'.format(self.time_text)
            self._display_debug_string = '[{{}}][{}] {{}}:{{}} {{}}'.format(self.time_text)

    def _set_file_handlers(self, filename: str, debug_filename: str, error_filename: str):
        """
        Set each logger file handler selectively depending on the given filenames.
        """

        if filename is not None:
            self._logger.handlers = []
            self._logger.addHandler(logging.FileHandler(filename))

        if debug_filename is not None:
            self._debug_logger.handlers = []
            self._debug_logger.addHandler(logging.FileHandler(debug_filename))

        if error_filename is not None:
            self._error_logger.handlers = []
            self._error_logger.addHandler(logging.FileHandler(error_filename))

    def start(self):
        """
        Start the logger.

        Starts the logger main thread. It's possible to call logging methods before starting the logger, however any
        output will remain queued.
        """

        threading.Thread.start(self)

    def run(self):
        """
        Run the logger main thread.

        Grabs log records from the queue and sends them off to their respective loggers and streams. This method is
        invoked automaticlly by the :mod:`threading` module and should not be invoked directly.
        """

        while self._running.is_set():
            log_entry = self._log_entries.get()
            if log_entry is None:
                if self._callback_buffer:
                    self.callback(self._callback_buffer)

                self._running.clear()
                continue

            scope = log_entry['scope']
            level = log_entry['level']
            message = log_entry['message']
            stack_frame = log_entry['stack_frame']

            if level == DEBUG:
                display_string = self._display_string
            else:
                display_string = self._display_debug_string

            if stack_frame is not None:
                try:
                    for _ in range(0, log_entry['stack_depth']):
                        stack_frame = stack_frame.f_back
                        caller_name = stack_frame.f_back.f_code.co_name
                        caller_lineno = stack_frame.f_back.f_lineno

                except AttributeError:
                    pass  # Keep the last valid name and lineno

            else:
                caller_name = '(unknown)'
                caller_lineno = 0

            if scope is not None:
                if isinstance(scope, str):
                    scope_name = scope
                else:
                    scope_name = scope.__class__.__name__

                caller_name = '{}.{}'.format(scope_name, caller_name)

            time_string = datetime.datetime.utcfromtimestamp(log_entry['timestamp']).strftime(self.time_format)

            display_string = display_string.format(self._log_level_labels[level], time_string,
                                                   caller_name, caller_lineno, message) + '\n'

            logger_string = self._logger_string.format(logging.getLevelName(level), time_string,
                                                       caller_name, caller_lineno, message)

            self._logger_methods[level](level, logger_string)
            self._display_methods[level](display_string)
            self._handle_callback(level, logger_string)

    def _do_callback(self):
        """
        Execute a callback with the current buffer contents, and reset callback state.
        """

        self.callback(self._callback_buffer)
        self._callback_triggered = False
        self._callback_time = time.time()
        self._callback_buffer = []

    def _handle_callback(self, level: int, string: str):
        """
        Handle any callbacks based on the current time and the given level and string.
        """

        if self.callback and level >= self.callback_level:
            self._callback_buffer.append(string)
            if level == CRITICAL:
                self._do_callback()

        if self._callback_triggered and time.time() - self._callback_time > 60.0:
            self._do_callback()

        elif self._callback_buffer and time.time() - self._callback_time > self.callback_interval:
            self._callback_triggered = True
            self._callback_time = time.time()

    def stop(self):
        """
        Stop the logger.

        This will terminate the logger main thread. As per Python's :mod:`threading` module, the thread cannot be
        restarted again.
        """

        self._log_entries.put(None)

    def log(self, level: int, message: str, scope: object=None, stack_depth: int=0):
        current_frame = inspect.currentframe() if self.inspect_stack else None

        self._log_entries.put({
            'scope': scope if scope else self.scope,
            'level': level,
            'message': message,
            'timestamp': time.time(),
            'stack_depth': stack_depth,
            'stack_frame': current_frame
        })

    def debug(self, message: str, *args, stack_depth: int=0, verbosity: int=0):  # pylint: disable=E0202
        pass

    def _debug(self, message: str, *args, stack_depth: int=0, verbosity: int=0):
        if verbosity <= self._debug_verbosity:
            self.log(logging.DEBUG, message.format(*args), stack_depth=stack_depth + 1)

    def info(self, message: str, *args, stack_depth: int=0):  # pylint: disable=E0202
        pass

    def _info(self, message: str, *args, stack_depth: int=0):
        self.log(logging.INFO, message.format(*args), stack_depth=stack_depth + 1)

    def warning(self, message: str, *args, stack_depth: int=0):  # pylint: disable=E0202
        pass

    def _warning(self, message: str, *args, stack_depth: int=0):
        self.log(logging.WARNING, message.format(*args), stack_depth=stack_depth + 1)

    def error(self, message: str, *args, stack_depth: int=0):  # pylint: disable=E0202
        pass

    def _error(self, message: str, *args, stack_depth: int=0):
        self.log(logging.ERROR, message.format(*args), stack_depth=stack_depth + 1)

    def critical(self, message: str, *args, stack_depth: int=0):  # pylint: disable=E0202
        pass

    def _critical(self, message: str, *args, stack_depth: int=0):
        self.log(logging.CRITICAL, message.format(*args), stack_depth=stack_depth + 1)


class ChildLogger (Logger):
    """
    Logger that encapsulates another parent :class:`Logger` with a different default scope and parameters.

    This is useful with :class:`ThreadedLogger` as it allows output from multiple child loggers to be directed to
    the same output files and streams without causing contention.

    Arguments:
        parent:          The parent logger instance.
        scope:           The new scope of this logger, see 'scope' in :class:`ThreadedLogger`.
        level:           If set, the new level of this logger, see 'level' in :class:`ThreadedLogger` (default None for
                         same as parent).
        debug_verbosty:  If set, the new debug verbosity of this logger, see 'debug_verbosity' in
                         :class:`ThreadedLogger` (default None for same as parent).
    """

    def __init__(self, parent: Logger, scope: object, level: int=None, debug_verbosity: int=None):
        self.parent = parent
        self.scope = scope

        self._level = level if level else parent.level
        self._debug_verbosity = debug_verbosity if debug_verbosity else parent.debug_verbosity

        self.debug = self._debug if self._level <= DEBUG else lambda *_, **__: None
        self.info = self._info if self._level <= INFO else lambda *_, **__: None
        self.warning = self._warning if self._level <= WARNING else lambda *_, **__: None
        self.error = self._error if self._level <= ERROR else lambda *_, **__: None
        self.critical = self._critical if self._level <= CRITICAL else lambda *_, **__: None

    @property
    def level(self):
        return self._level

    @property
    def debug_verbosity(self):
        return self._debug_verbosity

    @debug_verbosity.setter
    def debug_verbosity(self, value: int):
        self._debug_verbosity = value

    def log(self, level: int, message: str, scope: object=None, stack_depth: int=0):
        self.parent.log(level, message, scope if scope else self.scope, stack_depth + 1)

    def debug(self, message: str, *args, stack_depth: int=0, verbosity: int=0):  # pylint: disable=E0202
        pass

    def _debug(self, message: str, *args, stack_depth: int=0, verbosity: int=0):
        if verbosity <= self._debug_verbosity:
            self.parent.log(logging.DEBUG, message.format(*args), scope=self.scope, stack_depth=stack_depth + 1)

    def info(self, message: str, *args, stack_depth: int=0):  # pylint: disable=E0202
        pass

    def _info(self, message: str, *args, stack_depth: int=0):
        self.parent.log(logging.INFO, message.format(*args), scope=self.scope, stack_depth=stack_depth + 1)

    def warning(self, message: str, *args, stack_depth: int=0):  # pylint: disable=E0202
        pass

    def _warning(self, message: str, *args, stack_depth: int=0):
        self.parent.log(logging.WARNING, message.format(*args), scope=self.scope, stack_depth=stack_depth + 1)

    def error(self, message: str, *args, stack_depth: int=0):  # pylint: disable=E0202
        pass

    def _error(self, message: str, *args, stack_depth: int=0):
        self.parent.log(logging.ERROR, message.format(*args), scope=self.scope, stack_depth=stack_depth + 1)

    def critical(self, message: str, *args, stack_depth: int=0):  # pylint: disable=E0202
        pass

    def _critical(self, message: str, *args, stack_depth: int=0):
        self.parent.log(logging.CRITICAL, message.format(*args), scope=self.scope, stack_depth=stack_depth + 1)
