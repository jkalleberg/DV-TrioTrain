from logging import Logger
from pathlib import Path
from typing import Dict, List, Text, Union

from dotenv import dotenv_values, get_key, set_key


class Env:
    """
    Store environment variables as key=value pairs accessible for all TrioTrain

    Serves as a written record of experimental parameters.
    """

    def __init__(
        self,
        env_file: str,
        logger: Logger,
        debug_mode: bool = False,
        dryrun_mode: bool = False,
    ) -> None:
        self.env_file = env_file
        self.env_path = Path(self.env_file)
        self.logger = logger
        self.contents: Dict[str, Union[str, None]] = dotenv_values(self.env_path)
        self.debug_mode = debug_mode
        self.dryrun_mode = dryrun_mode
        self.updated_keys: Dict[str, Union[str, None]] = dict()

    def check_out(self) -> None:
        """Confirms if the environment file contains at least one variable.

        Raises
        ------
        ValueError
            attempting to load an empty file
        """
        if len(self.contents) != 0:
            if self.debug_mode:
                self.logger.debug(
                    f"{self.env_path.name} contains {len(self.contents)} variables"
                )
        else:
            self.logger.error(
                f"unable to load variables, '{self.env_path}' is empty\nExiting..."
            )
            exit(1)

    def test_contents(self, *variables: str) -> bool:
        """Give a list of variable names, search within an environment file, and print a msg depending on if they are found.

        Parameters

        Returns
        -------
        bool
            True: all input variables were found
            False: missing at least one input variable
        """
        self.check_out()
        self.var_count = 0
        for var in variables:
            if var in self.contents:
                if self.debug_mode:
                    self.logger.debug(f"{self.env_path.name} contains '{var}'")
                self.var_count += 1
            else:
                if self.dryrun_mode:
                    self.logger.info(
                        f"[DRY_RUN] - {self.env_path.name} does not have a variable, as expected | '{var}' "
                    )
                else:
                    self.logger.warning(
                        f"{self.env_path.name} does not have a variable  | '{var}'"
                    )

        if self.var_count == len(variables):
            if self.debug_mode:
                self.logger.debug(
                    f"{self.env_path.name} contains [{self.var_count}-of-{len(variables)}] variables"
                )
            return True
        else:
            if self.debug_mode:
                self.logger.debug(
                    f"{self.env_path.name} contains [{self.var_count}-of-{len(variables)}] variables"
                )
            return False

    def add_to(
        self,
        key: str,
        value: Union[str, None],
        update: bool = False,
        dryrun_mode: bool = False,
        msg: Union[str, None] = None,
    ) -> None:
        """Write a variable to the environment file in 'export NEW_VARIABLE=value' format.

        Parameters
        ----------
        key : str
            variable name, must be unique
        value : Union[str, None]
            returned when variable is called
        update : bool, optional
            if True, overwrite the existing value of a variable, by default False
        dryrun_mode : bool, optional
            if True, variables are stored in a dictionary rather than written to a file, by default False
        msg : Union[str, None], optional
            label for logging, by default None
        """
        if msg is None:
            logger_msg = ""
        else:
            logger_msg = f"{msg}: "

        if update and key in self.contents:
            old_value = get_key(self.env_file, key)
            if old_value == value:
                if self.debug_mode:
                    self.logger.debug(f"{logger_msg}SKIPPING {key}='{value}'")
                return
            else:
                self.updated_keys[key] = value
                description = f"updating {key}='{old_value}' to '{value}'"
        elif key not in self.contents:
            if value is None:
                description = f"adding a comment: '{key}'"
            else:
                description = f"adding {key}='{value}'"
                if self.debug_mode:
                    self.logger.debug(
                        f"{logger_msg}variable '{key}' missing in '{Path(self.env_file).name}'"
                    )
            pass
        else:
            if self.debug_mode:
                self.logger.debug(
                    f"{logger_msg}variable '{key}' found in '{Path(self.env_file).name}'"
                )
            return

        # Either save the variable within the Env object,
        # Or write it to the .env file
        if dryrun_mode:
            self.logger.info(f"[DRY_RUN] - {logger_msg}{description}")
            self.contents[key] = value
        else:
            self.logger.info(f"{logger_msg}{description}")
            set_key(self.env_path, str(key), str(value), export=True)
            self.contents = dotenv_values(self.env_path)

        # Test to confirm variable was added correctly
        if value is not None:
            if update or dryrun_mode:
                dotenv_output = self.contents[key]
            else:
                dotenv_output = get_key(self.env_file, key)

            if dotenv_output is not None:
                if self.debug_mode:
                    self.logger.debug(
                        f"{logger_msg}'{Path(self.env_file).name}' contains '{key}={dotenv_output}'"
                    )
            else:
                self.logger.error(
                    f"{logger_msg}{key}='{value}' was not added to '{Path(self.env_file).name}'"
                )

    def load(
        self,
        *variables: str,
    ) -> List[Union[str, Text]]:
        """Search env for existing variables

        Returns
        -------
        List[Union[str, Text]]
            a set of values from each input variable; to use the values within TrioTrain, define an equal number of Python variable names to the output

        Raises
        ------
        KeyError
            a variable name is missing from the environment
        """
        self.test_contents(*variables)
        if self.debug_mode:
            self.logger.debug(
                f"[{Path(self.env_file).name}] configured {self.var_count} variables"
            )
        return_list: List[Text] = []
        for var in variables:
            if var in self.contents and self.contents[f"{var}"] is not None:
                return_list.append(str(self.contents[f"{var}"]))
            else:
                raise KeyError(
                    f"Unable to load '{var}', because missing from '{self.env_file}'"
                )

        return return_list
