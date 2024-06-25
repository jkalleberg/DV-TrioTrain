#!/usr/bin/python3
"""
Description: module for preserving objects as 'pickles'
"""
import pickle
from pathlib import Path
from sys import path


abs_path = Path(__file__).resolve()
module_path = str(abs_path.parent.parent)
path.append(module_path)
from helpers.files import TestFile


def preserve(item: object, pickled_path: TestFile, overwrite: bool = False) -> None:
    """
    Preserve a pickled item.

    Parameters
    ----------
    item : object
        something needed by a command-line Python script
    pickled_path : TestFile
        a temporary file of where to store the pickled object
    overwrite : bool, optional
        if True, allows writing over an existing pickled object
        default=False
    """
    pickled_path.check_existing()
    if pickled_path.file_exists and overwrite is False:
        pickled_path.logger.info(
            f"unable to overwrite an existing pickle file | '{pickled_path.file}'"
        )
    else:
        try:
            if pickled_path.file_exists and overwrite is True:
                pickled_path.logger.warning(
                    f"overwriting an existing pickle file | '{pickled_path.file}'"
                )
            else:
                pickled_path.logger.info(
                    f"creating a new pickle file | '{pickled_path.file}'"
                )
            pickle.dump(item, open(pickled_path.file, "wb"))
        except pickle.PicklingError:
            pickled_path.logger.error(f"unable to pickle an item | '{item}'")


def prepare(pickled_path: Path) -> object:
    """
    Unpack a pickled item.

    Parameters
    ----------
    pickled_path : TestFile
        a temporary file of containing a pickled object

    Returns
    -------
    object
        something needed by a command-line Python script
    """
    if pickled_path.is_file():
        try:
            return pickle.load(open(str(pickled_path), "rb"))

        except pickle.UnpicklingError:
            print(f"unable to unpickle an item | '{pickled_path.file}'")
    else:
        print(f"missing the pickled item | '{pickled_path.file}'")
