#!/usr/bin/python3
"""
description: creates a Logger object.

usage:
    from helpers.logger import LogFormatter
"""
import logging
from sys import stdout

class LogFormatter(logging.Formatter):
    """
    Sets a cutsom log formmat for INFO messages vs debug, warning, and error messages.
    """

    def format(self, record: logging.LogRecord):
        # Save the original format configured by the user
        # when the logger formatter was instantiated
        format_orig = self._style._fmt
        self.datefmt = "%Y-%m-%d %I:%M:%S %p"

        if (
            record.levelno == logging.INFO
            or record.levelno == logging.DEBUG
            or record.levelno == logging.WARNING
        ):
            self._style._fmt = "%(asctime)s - [%(levelname)s] - %(message)s"

        else:
            self._style._fmt = "%(asctime)s - [%(levelname)s] - %(name)s.%(funcName)s.line_%(lineno)d: %(message)s"

        # Call the original formatter class to do the grunt work
        result = super().format(record)

        # Restore the original format configured by the user
        self._style._fmt = format_orig

        return result

def get_file_handler(log_file: str) -> logging.FileHandler:
    """
    Writes any log messages from code warnings or
    errors to a log file
    """
    # only create the logging file if ERROR msgs are created
    file_handler = logging.FileHandler(log_file, delay=True)
    # file_handler.setLevel(logging.WARNING)
    file_handler.setLevel(logging.ERROR)
    file_handler.setFormatter(LogFormatter())
    return file_handler

def get_stream_handler() -> logging.StreamHandler:
    """
    Writes any log messages from general status updates, plus warnings and errors to the screen
    """
    stream_handler = logging.StreamHandler(stdout)
    stream_handler.setLevel(logging.DEBUG)
    stream_handler.setFormatter(LogFormatter())
    return stream_handler