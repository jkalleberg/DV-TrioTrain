from csv import QUOTE_NONE, DictReader, DictWriter, writer
from dataclasses import dataclass, field
from logging import Logger
from pathlib import Path
from typing import Dict, List, Union
from json import load, dump
import pandas as pd

from model_training.slurm.suffix import remove_suffixes


class TestFile:
    """Confirm if a file already exists or not."""

    def __init__(self, file: Union[str, Path], logger: Logger) -> None:
        self.file = str(file)
        self.path = Path(file)
        self.file_exists: bool
        self.logger = logger
        self.clean_filename = remove_suffixes(self.path)

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
class Files:
    """
    Check for exisiting files and to create multiple types of outputs.

    Attributes:
        path_to_file -- a Path object for the file
        logger -- a Logger object
    """

    # required parameters
    path_to_file: Union[Path, str]
    logger: Logger

    # optional parameters
    logger_msg: Union[str, None] = None
    debug_mode: bool = False
    dryrun_mode: bool = False

    # internal parameters
    file_exists: bool = field(default=False, init=False, repr=False)
    file_lines: List[str] = field(default_factory=list, init=False, repr=False)
    file_dict: Dict[str, str] = field(default_factory=dict, init=False, repr=False)
    _existing_data: List[Dict[str,str]] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        self.path = Path(self.path_to_file)
        self.file_name = self.path.name
        self.path_only = self.path.parent
        self._test_file = TestFile(self.path, self.logger)

    def check_status(
        self,
        should_file_exist: bool = False
    ) -> None:
        """
        Confirm that file is non-existant.
        """
        if should_file_exist is True:
            self._test_file.check_existing(logger_msg=self.logger_msg,debug_mode=self.debug_mode)
        else:
            self._test_file.check_missing(
                logger_msg=self.logger_msg, debug_mode=self.debug_mode
            )
        self.file_exists = self._test_file.file_exists

    def write_list(self, line_list: List[str]) -> None:
        """
        Take an iterable list of lines and write them to a text file.
        """
        if self.dryrun_mode:
            if self.logger_msg is None:
                self.logger.info(
                    f"[DRY_RUN]: pretending to write a list of lines | '{str(self.path)}'"
                )
            else:
                self.logger.info(
                    f"{self.logger_msg}: pretending to write a list of lines | '{str(self.path)}'"
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
                    f"[DRY_RUN]: pretending to write a list of dictionaries | '{str(self.path)}'"
                )
            else:
                self.logger.info(
                    f"{self.logger_msg}: pretending to write a list of dictionaries | '{str(self.path)}'"
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
            self.logger.info(
                    f"{self.logger_msg}: pretending to add header + row to a CSV | '{str(self.path)}'"
                )
            print("---------------------------------------------")
            print(",".join(data_dict.keys()))
            print(",".join(data_dict.values()))
            print("---------------------------------------------")
        else:
            if self.path.exists():
                if self.debug_mode:
                    debug_msg = f"appending [{self.file}] with a new row"
                    if self.logger_msg is None:
                        self.logger.debug(debug_msg)
                    else:
                        self.logger.debug(f"{self.logger_msg}: {debug_msg}")

                with open(str(self.path), mode="a") as file:
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

                with open(str(self.path), mode="w") as file:
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
                    f"[DRY_RUN]: pretending to write CSV file | '{str(self.path)}'"
                )
            else:
                self.logger.info(
                    f"{self.logger_msg}: pretending to write CSV file | '{str(self.path)}'"
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
            with open(str(self.path), mode="w") as file:
                write_file = writer(file)
                for key, value in write_dict.items():
                    if type(value) is list:
                        write_file.writerow([key] + value)
                    else:
                        write_file.writerow([key, value])

            if self.path.is_file():
                logging_msg = f"created intermediate CSV file | '{self.file}'"
                if self.logger_msg is None:
                    self.logger.info(logging_msg)
                else:
                    self.logger.info(f"{self.logger_msg}: {logging_msg}")
    
    def write_dataframe(self, df: pd.DataFrame, keep_index: bool = False) -> None:
        if self.dryrun_mode:
            self.logger.info(
                f"{self.logger_msg}: pretending to write CSV file | '{str(self.path)}'"
            )

            print("---------------------------------------------")
            print(df)
            print("---------------------------------------------")
        else:
            self.logger.info(
                f"{self.logger_msg}: writing a CSV file | '{str(self.path)}'"
            )
            df.to_csv(
                str(self.path),
                doublequote=False,
                quoting=QUOTE_NONE,
                index=keep_index,
            )
    
    def write_json_file(self) -> None:
        """
        Open the JSON config file, and confirm the user provided the 'ntasks' parameter as required by Cue
        """
        if self.dryrun_mode:
            self.logger.info(
                f"{self.logger_msg}: pretending to write JSON file | '{str(self.path)}'"
            )
            self.logger.info(
                f"{self.logger_msg}: JSON contents ---------------------"
            )
            for k, v in self.file_dict.items():
                self.logger.info(f"{self.logger_msg}:\t{k}: {v}")
            self.logger.info(
                f"{self.logger_msg}: -----------------------------------"
            )
        else:
            self.logger.info(
                f"{self.logger_msg}: writing a JSON file | '{str(self.path)}'"
            )
            with open(str(self.path), "w") as f:
                dump(self.file_dict, f)
    
    def load_csv(self) -> None:
        """
        Read in and save the CSV file as a dictionary.
        """
        if "gz" in self.path.suffix:
            import gzip
            logging_msg = f"handling a compressed file | '{self.path.stem}'"
            if self.logger_msg is None:
                self.logger.info(logging_msg)
            else:
                self.logger.info(f"{self.logger_msg}: {logging_msg}")
            with gzip.open(str(self.path), mode="rt") as data:
                reader = DictReader(data)
                self._existing_data = [dict(row) for row in reader]
        else:
            with open(str(self.path), mode="r", encoding="utf-8-sig") as data:
                reader = DictReader(data)
                self._existing_data = [dict(row) for row in reader]
    
    def load_tsv(self, header_list: List[str]) -> List[Dict[str, str]]:
        """
        Read in and save the TSV file as a list of lines.
        """
        if self._existing_data:
            reader = DictReader(
                self._existing_lines, fieldnames=header_list, delimiter="\t"
            )

            return [line for line in reader]
        else:
            list_of_line_dicts = []
            with open(str(self.path), mode="r", encoding="utf-8-sig") as data:
                reader = DictReader(data, fieldnames=header_list, delimiter="\t")
                for line in reader:
                    # If the file containes headers, skip them
                    contents = list(line.values())
                    if reader.fieldnames and any(
                        i in contents for i in reader.fieldnames
                    ):
                        if self.debug_mode:
                            self.logger.debug(
                                f"{self.logger_msg}: SKIPPING HEADERS"
                            )
                        continue
                    else:
                        list_of_line_dicts.append(line)
            return list_of_line_dicts

    def load_vcf(self) -> None:
        with open(str(self.path), mode="r", encoding="utf-8-sig") as data:
            Lines = data.readlines()
            for line in Lines:
                if line.startswith("##"):
                    self._vcf_header_lines.append(line.strip())
                elif line.startswith("#CHROM"):
                    self._vcf_header_lines.append(line.strip())
                    self._col_names = line.strip("#\n").split("\t")

        with open(str(self.path), mode="r", encoding="utf-8-sig") as data:
            reader = DictReader(data, fieldnames=self._col_names, delimiter="\t")
            for line in reader:
                # SKIP the VCF header lines saved previously
                if any(v.startswith("#") for v in line.values()):
                    continue
                self._list_of_line_dicts.append(line)
                
    def load_txt_file(self) -> None:
        """
        Read in and save a \n seperated file as list.
        """
        with open(str(self.path), mode="r", encoding="utf-8-sig") as data:
            for line in data.readlines():
                _clean_line = line.strip()
                self._existing_data.append(_clean_line)

    def load_json_file(self) -> None:
        """
        Open the JSON config file, and confirm the user provided the 'ntasks' parameter as required by Cue
        """
        with open(str(self.path), mode="r") as file:
            self.file_dict = load(file)
