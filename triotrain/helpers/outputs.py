from logging import Logger
from os import listdir
from pathlib import Path
from typing import List, Tuple

import regex
from natsort import natsorted


def check_if_output_exists(
    match_pattern: regex.Pattern,
    file_type: str,
    search_path: Path,
    msg: str,
    logger: Logger,
    debug_mode: bool = False,
    dryrun_mode: bool = False,
) -> Tuple[bool, int, List[str]]:
    """Confirms if file(s) matching a regular expression already exist, and counts the number of matches found.

    Parameters
    ----------
    match_pattern : regex.Pattern
        a regular expression
    file_type : str
        general descriptor for the files to find
    search_path : Path
        where to look for the files
    msg : str
        prefix for the logging messages
    logger : Logger
        handler for print statements
    debug_mode : bool, optional
        if True, print out additional details; by default False
    dryrun_mode : bool, optional
        if True, clarify that no files should exist; by default False

    Returns
    -------
    tuple

        output_exists : bool
            if True, files matching the regular expression were found
        n_matches : int
            how many matching files were found
        unique_files_list: List[str]
            identifies non-specific regular expression errors
    """
    files: List[str] = list()
    n_matches = 0
    if search_path.exists():
        if Path(search_path).is_dir():
            for file in listdir(str(search_path)):
                match = regex.search(match_pattern, str(file))
                if match:
                    files.append(match.group())

            unique_files = set(files)
            num_unique_files = len(unique_files)
            unique_files_list = list(natsorted(unique_files))

            if debug_mode:
                logger.debug(f"{msg} - [outputs]: files found | {unique_files_list}")

            for file in files:
                filename: Path = search_path / file
                if filename.exists():
                    n_matches += 1
        else:
            num_unique_files = 0
            unique_files_list = []
    else:
        if not dryrun_mode:
            logger.warning(
                f"{msg} - [outputs]: unable to search a non-existant path | '{str(search_path)}'"
            )
        num_unique_files = 0
        unique_files_list = []

    if n_matches == 0:
        if debug_mode:
            logger.info(f"{msg}: missing {file_type}")
        output_exists = False
        num_unique_files = 0
        unique_files_list = []
    else:
        if debug_mode:
            logger.debug(f"{msg} - [outputs]: found [{int(n_matches):,}] {file_type}")
        output_exists = True

    if n_matches > num_unique_files:
        logger.warning(f"{msg} - [outputs]: pattern provided returns duplicate files")
        logger.warning(f"{msg} - [outputs]: please use a more specific regex")

    return output_exists, n_matches, unique_files_list


def check_expected_outputs(
    outputs_found: int,
    outputs_expected: int,
    msg: str,
    file_type: str,
    logger: Logger,
    verbose: bool = True,
) -> bool:
    """Confirms if expected outputs were made correctly.

    Parameters
    ----------
    outputs_found : int
        how many outputs were identified
    outputs_expected : int
        how many outputs should be identified
    msg : str
        prefix for the logging messages
    file_type : str
        general descriptor for the files to find
    logger : Logger
        handler for print statements
    verbose: bool
        if True, print additional logging msgs

    Returns
    -------
    bool
        if True, 1+ expected files are missing
    """
    if outputs_found == outputs_expected:
        if outputs_expected == 1:
            if verbose:
                logger.info(
                    f"{msg}: found the {int(outputs_found):,} expected {file_type}... SKIPPING AHEAD"
                )
        else:
            logger.info(
                f"{msg}: found all {int(outputs_found):,} expected {file_type}... SKIPPING AHEAD"
            )
        missing_outputs = False
    else:
        if int(outputs_expected) > int(outputs_found):
            logger.info(
                f"{msg}: missing {int(int(outputs_expected) - int(outputs_found)):,}-of-{int(outputs_expected):,} {file_type}"
            )
            missing_outputs = True
        else:
            logger.warning(
                f"{msg}: found {int(int(outputs_found)-int(outputs_expected)):,} more {file_type} than expected!"
            )
            missing_outputs = False

    return missing_outputs
