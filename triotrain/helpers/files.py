from csv import DictWriter, writer
from dataclasses import dataclass, field
from logging import Logger
from pathlib import Path
from typing import Dict, List, Union


class TestFile:
    """Confirm if a file already exists or not."""

    def __init__(self, file: Union[str, Path], logger: Logger):
        self.file = str(file)
        self.path = Path(file)
        self.file_exists: bool
        self.logger = logger

    def check_missing(
        self, logger_msg: Union[str, None] = None, debug_mode: bool = False
    ) -> None:
        """
        Confirms if a file is non-existant.
        """
        if logger_msg is None:
            msg = ""
        else:
            msg = f"{logger_msg}: "
        if self.path.is_file():
            if debug_mode:
                self.logger.debug(
                    f"{msg}'{str(self.path)}' already exists... SKIPPING AHEAD"
                )
            self.file_exists = True
        else:
            if debug_mode:
                self.logger.debug(f"{msg}file is missing, as expected | '{self.file}'")
            self.file_exists = False

    def check_existing(
        self, logger_msg: Union[str, None] = None, debug_mode: bool = False
    ) -> None:
        """
        Confirms if a file exists already.
        """
        if logger_msg is None:
            msg = ""
        else:
            msg = f"{logger_msg}: "

        if self.path.is_file() and self.path.stat().st_size != 0:
            if debug_mode:
                self.logger.debug(
                    f"{msg}'{str(self.path)}' already exists... SKIPPING AHEAD"
                )
            self.file_exists = True
        else:
            self.file_exists = False
            if debug_mode:
                self.logger.debug(f"{msg}unexpectedly missing a file | '{self.path}'")


@dataclass
class WriteFiles:
    """
    Check for exisiting files and to create multiple types of outputs.

    Attributes:
        path -- a Path object for the file
        file -- a string pairs naming pattern
        logger -- a Logger object
    """

    # required parameters
    path_to_file: str
    file: str
    logger: Logger

    # optional parameters
    logger_msg: Union[str, None] = None
    debug_mode: bool = False
    dryrun_mode: bool = False

    # internal parameters
    file_exists: bool = field(default=False, init=False, repr=False)
    file_lines: List[str] = field(default_factory=list, init=False, repr=False)
    file_dict: Dict[str, str] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self):
        self.path = Path(self.path_to_file)
        self.file_path = self.path / self.file

    def check_missing(
        self,
    ) -> None:
        """
        Confirm that file is non-existant.
        """
        file = TestFile(self.file_path, self.logger)
        file.check_missing(logger_msg=self.logger_msg, debug_mode=self.debug_mode)
        self.file_exists = file.file_exists

    def write_list(self, line_list: List[str]) -> None:
        """
        Take an iterable list of lines and write them to a text file.
        """
        if self.dryrun_mode:
            if self.logger_msg is None:
                self.logger.info(
                    f"[DRY_RUN]: pretending to write a list of lines | '{str(self.file_path)}'"
                )
            else:
                self.logger.info(
                    f"{self.logger_msg}: pretending to write a list of lines | '{str(self.file_path)}'"
                )

            print("---------------------------------------------")
            for line in line_list:
                print(line)
            print("---------------------------------------------")
        else:
            with open(f"{self.path}/{self.file}", mode="a", encoding="UTF-8") as file:
                file.writelines(f"{line}\n" for line in line_list)

            # confirm the expected number of lines were written
            with open(
                f"{self.path}/{self.file}", mode="r", encoding="UTF-8"
            ) as filehandle:
                self.file_lines = filehandle.readlines()

            assert len(line_list) == len(
                self.file_lines
            ), f"expected {len(line_list)} lines in {self.file}, but there were {len(self.file_lines)} found"

    def write_list_of_dicts(
        self, line_list: List[Dict[str, str]], delim: Union[str, None] = None
    ) -> None:
        """
        Take an iterable list of dictionaries and write them to a text file.
        """
        keys = line_list[0].keys()
        if delim is None:
            _delim = ","
        else:
            _delim = delim

        if self.dryrun_mode:
            if self.logger_msg is None:
                self.logger.info(
                    f"[DRY_RUN]: pretending to write a list of dictionaries | '{str(self.file_path)}'"
                )
            else:
                self.logger.info(
                    f"{self.logger_msg}: pretending to write a list of dictionaries | '{str(self.file_path)}'"
                )

            print("---------------------------------------------")
            header = f"{_delim}".join(keys)
            print(header)
            for dict in line_list[0:10]:
                line = f"{_delim}".join([str(value) for value in dict.values()])
                print(line)
            print("---------------------------------------------")
        else:
            with open(f"{self.path}/{self.file}", mode="a", encoding="UTF-8") as file:
                dict_writer = DictWriter(file, fieldnames=keys, delimiter=_delim)
                dict_writer.writeheader()
                dict_writer.writerows()

    def add_rows(self, col_names: List[str], data_dict: Dict[str, str]) -> None:
        """
        Append rows to a csv.
        """
        if self.dryrun_mode:
            print(",".join(data_dict.values()))
        else:
            if self.file_path.exists():
                if self.debug_mode:
                    debug_msg = f"appending [{self.file}] with a new row"
                    if self.logger_msg is None:
                        self.logger.debug(debug_msg)
                    else:
                        self.logger.debug(f"{self.logger_msg}: {debug_msg}")

                with open(str(self.file_path), mode="a") as file:
                    dictwriter = DictWriter(file, fieldnames=col_names)
                    dictwriter.writerow(data_dict)
                    self.file_dict.update(data_dict)
            else:
                if self.debug_mode:
                    debug_msg = f"initializing | '{self.file}'"
                    if self.logger_msg is None:
                        self.logger.debug(debug_msg)
                    else:
                        self.logger.debug(f"{self.logger_msg}: {debug_msg}")

                with open(str(self.file_path), mode="w") as file:
                    dictwriter = DictWriter(file, fieldnames=col_names)
                    dictwriter.writeheader()
                    dictwriter.writerow(data_dict)

                self.file_dict = data_dict

    def write_csv(self, write_dict: Dict[str, str]) -> None:
        """
        Save or display counts from [run_name]-[iteration]-[test_number] only.
        """
        # If only testing, display to screen
        if self.dryrun_mode:
            if self.logger_msg is None:
                self.logger.info(
                    f"[DRY_RUN]: pretending to write CSV file | '{str(self.file_path)}'"
                )
            else:
                self.logger.info(
                    f"{self.logger_msg}: pretending to write CSV file | '{str(self.file_path)}'"
                )

            print("---------------------------------------------")
            for key, value in write_dict.items():
                if type(value) is list:
                    v = ",".join(value)
                else:
                    v = value
                print(f"{key},{v}")
            print("---------------------------------------------")

        # Otherwise, write an intermediate CSV output file
        else:
            with open(str(self.file_path), mode="w") as file:
                write_file = writer(file)
                for key, value in write_dict.items():
                    if type(value) is list:
                        write_file.writerow([key] + value)
                    else:
                        write_file.writerow([key, value])

            if self.file_path.is_file():
                logging_msg = f"created intermediate CSV file | '{self.file}'"
                if self.logger_msg is None:
                    self.logger.info(logging_msg)
                else:
                    self.logger.info(f"{self.logger_msg}: {logging_msg}")
