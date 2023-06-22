from logging import Logger
from sys import exit
from typing import Dict, List, Union


def add_to_dict(
    update_dict: Dict[str, Union[str, int, float]],
    new_key: str,
    new_val: Union[str, int, float],
    logger: Logger,
    logger_msg: str,
    valid_keys: Union[List[str], None] = None,
    replace_value: bool = False,
) -> None:
    """Write a key=value pair to a dictionary object.

    f the key is missing from the dictionarydd the 'key=value pair' to the results dictionary.

    Parameters
    ----------
    update_dict : Dict[str, Union[str, int, float]]
        the dictionary object to be altered
    new_key : str
        unique hash key
    new_val : Union[str, int, float]
        the value returned by the new key
    logger : Logger
        where to pass logging messages
    logger_msg : str
        label for any logging messages
    valid_keys : Union[List[str], None], optional
        if provided, compare the new against this list to catch typos or invalid entries, by default None
    replace_value : bool, optional
        if True, overwrite the value of an existing key, by default False
    """
    if valid_keys is not None:
        if new_key not in valid_keys:
            logger.error(f"{logger_msg}: invalid metadata key | '{new_key}'")
            valid_key_string: str = ", ".join(valid_keys)
            logger.error(
                f"{logger_msg}: use one of the following valid keys | '{valid_key_string}'\nExiting..."
            )
            exit(1)

    if new_key not in update_dict.keys():
        update_dict[new_key] = new_val
        logger.info(f"{logger_msg}: dictionary updated with | '{new_key}={new_val}'")
    elif new_key in update_dict.keys() and replace_value:
        old_value = update_dict[new_key]
        update_dict[new_key] = new_val
        logger.info(
            f"{logger_msg}: previous value '{new_key}={old_value}' | new value '{new_key}={new_val}'"
        )
    else:
        logger.warning(
            f"{logger_msg}: unable to overwrite value for an existing key | '{new_key}'"
        )
