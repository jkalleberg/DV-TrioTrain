#!/usr/bin/python3
"""
description: contains basic functions used throughout TrioTrain

usage:
    from helpers.utils import check_if_all_same, create_deps, get_logger
"""
import logging
from random import randint
from typing import List, Union

from helpers.logger import get_stream_handler

def get_logger(name: str) -> logging.Logger:
    """
    Inializes a logging object to handle any print messages
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    # error_dir = Path(f"errors/tmp_{timestamp()}/")
    # error_log = f"{name}.err"
    # if not error_dir.is_dir():
    #     logger.error("Creating a new directory to store error logs...")
    #     error_dir.mkdir(parents=True)
    # logging_file = f"{str(error_dir)}/{error_log}"
    # logger.addHandler(get_file_handler(logging_file))
    logger.addHandler(get_stream_handler())
    return logger


def random_with_N_digits(n: int) -> int:
    """
    Create a number of an arbitrary length (n)
    """
    range_start = 10 ** (n - 1)
    range_end = (10**n) - 1
    return randint(range_start, range_end)


def generate_job_id() -> str:
    """
    Create a dummy slurm job id
    """
    return f"{random_with_N_digits(8)}"


def check_if_all_same(list_of_elem: List[Union[str, int]], item: Union[str, int]) -> bool:
    """
    Using List comprehension, check if all elements in list are same and matches the given item.
    """
    return all([elem == item for elem in list_of_elem])


def find_NaN(list_of_elem: List[Union[str, int, None]]) -> List[int]:
    """
    Returns a list of indexs within a list which are 'None'
    """
    list = [i for i, v in enumerate(list_of_elem) if v == None]
    return list


def find_not_NaN(list_of_elem: List[Union[str, int, None]]) -> List[int]:
    """
    Returns a list of indexs within a list which are not 'None'
    """
    list = [i for i, v in enumerate(list_of_elem) if v != None]
    return list


def create_deps(num: int = 4) -> List[None]:
    """
    Create a list of None of a certain length.
    """
    return [None] * num
