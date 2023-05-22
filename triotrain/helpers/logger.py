#!/usr/bin/python3
"""
description: creates a Logger for the TrioTrain pipeline.

usage:
    import helpers_logger
"""
import datetime as dt
import logging
import sys
from pathlib import Path

class LogFormatter(logging.Formatter):
    """
    Sets a cutsom log formmat for INFO messages vs debug, warning, and error messages.
    """

    def format(self, record):
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


def file_timestamp() -> str:
    """
    Create a timestamp for naming files.
    """
    current_datetime = dt.datetime.now()
    formatted_time = current_datetime.strftime("%Y-%m-%d")
    return str(formatted_time)


def get_file_handler(log_file) -> logging.FileHandler:
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
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.DEBUG)
    stream_handler.setFormatter(LogFormatter())
    return stream_handler


def get_logger(name):
    """
    Inializes a logging object to handle any print messages
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    error_dir = Path(f"errors/tmp_{file_timestamp()}/")
    error_log = f"{name}.err"
    if not error_dir.is_dir():
        logger.error("Creating a new directory to store error logs...")
        error_dir.mkdir(parents=True)
    logging_file = f"{str(error_dir)}/{error_log}"
    logger.addHandler(get_file_handler(logging_file))
    logger.addHandler(get_stream_handler())
    return logger
