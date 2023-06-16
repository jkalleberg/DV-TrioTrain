#!/usr/bin/python3
"""
description: contains general helper functions used throughout TrioTrain

usage:
    import helpers as h
"""
import datetime as dt
import os
import subprocess
import sys
from csv import DictWriter, writer
from dataclasses import dataclass, field
from logging import Logger
from pathlib import Path
from random import randint
from typing import Dict, List, Text, Union, Match
import dotenv
import regex
from natsort import natsorted


def timestamp():
    """
    Provide the current time in human readable format.
    """
    current_datetime = dt.datetime.now()
    formatted_time = current_datetime.strftime("%Y-%m-%d  %H:%M:%S")
    return str(formatted_time)


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


class Wrapper:
    """
    Print statement to indicate the boundaries of a script.

    Attributes:
        name -- script name
        message -- either start or end of the script
        time -- a string formatted timestamp
    """

    def __init__(self, name: str, message: str):
        self.name = name
        self.message = message

    def wrap_script(self, time: str):
        """
        display the script boundaries
        """
        print(f"===== {self.message} of {self.name} @ {time} =====")


class TestFile:
    """
    Performs checks on file(s).

        - check_missing(): confirms file does NOT exist already

        - check_existing(): confirms file does exist already
    """

    def __init__(self, file: Union[str, Path], logger: Logger):
        self.file = str(file)
        self.path = Path(file)
        self.file_exists: bool
        self.logger = logger

    def check_missing(self, logger_msg: Union[str, None] = None, debug_mode: bool = False):
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

    def check_existing(self, logger_msg: Union[str, None] = None, debug_mode: bool = False):
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


class Env:
    """
    Defines functions to check, add_to, and load
    environment variables to an env_file

    Attributes:
        env_file -- existing environment file
        key, value -- string pairs for variables
        contents -- a dictionary of existing variables
    """

    def __init__(self, env_file: str, logger: Logger, debug_mode: bool = False):
        self.env_file = env_file
        self.env_path = Path(self.env_file)
        self.logger = logger
        self.contents: Dict[str, Union[str, None]] = dotenv.dotenv_values(self.env_path)
        self.debug_mode = debug_mode
        self.updated_keys: Dict[str, Union[str, None]] = dict()

    def check_out(self) -> None:
        """
        Opens and returns the environment file contents object
        """
        if len(self.contents) != 0:
            if self.debug_mode:
                self.logger.debug(
                    f"[{self.env_path.name}] contains {len(self.contents)} variables"
                )
        else:
            raise ValueError(f"unable to load variables, {self.env_path} is empty")

    def test_contents(self, *variables: str) -> bool:
        """
        Search env for existing variables and print a msg depending on if they are found.

        Returns a boolean indicating if all variables were found in the env file.
        """
        self.check_out()
        self.var_count = 0
        for var in variables:
            if var in self.contents:
                if self.debug_mode:
                    self.logger.debug(f"[{self.env_path.name}] contains [{var}]")
                self.var_count += 1
            else:
                self.logger.warning(
                    f"[{self.env_path.name}] does not have a variable called [{var}]"
                )

        if self.var_count == len(variables):
            if self.debug_mode:
                self.logger.debug(
                    f"[{self.env_path.name}] contains [{self.var_count}-of-{len(variables)}] variables"
                )
            return True
        else:
            if self.debug_mode:
                self.logger.debug(
                    f"[{self.env_path.name}] contains [{self.var_count}-of-{len(variables)}] variables"
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
        """
        Adds a new variable to the environment file in 'export NEW_VARIABLE=value' format.
        """
        if msg is None:
            logger_msg = ""
        else:
            logger_msg = f"{msg}: "

        if update and key in self.contents:
            old_value = dotenv.get_key(self.env_file, key)
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
            self.logger.info(f"[DRY RUN] - {logger_msg}{description}")
            self.contents[key] = value
        else:
            self.logger.info(f"{logger_msg}{description}")
            dotenv.set_key(self.env_path, str(key), str(value), export=True)
            self.contents = dotenv.dotenv_values(self.env_path)

        # Test to confirm variable was added correctly
        if value is not None:
            if update or dryrun_mode:
                dotenv_output = self.contents[key]
            else:
                dotenv_output = dotenv.get_key(self.env_file, key)

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
        """
        Search env for existing variables.

        Returns a list of values for the set of *variables in the env.
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
    ):
        """
        Confirm that file is non-existant.
        """
        file = TestFile(self.file_path, self.logger)
        file.check_missing(logger_msg=self.logger_msg, debug_mode=self.debug_mode)
        self.file_exists = file.file_exists

    def write_list(self, line_list: List[str]):
        """
        Take an iterable list of lines and write them to a text file.
        """
        if self.dryrun_mode:
            if self.logger_msg is None:
                self.logger.info(
                    f"[DRY RUN]: pretending to write a list of lines | '{str(self.file_path)}'"
                )
            else:
                self.logger.info(
                    f"[DRY RUN] - {self.logger_msg}: pretending to write a list of lines | '{str(self.file_path)}'"
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

    def add_rows(self, col_names: List[str], data_dict: Dict[str, str]):
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
                    f"[DRY RUN]: pretending to write CSV file | '{str(self.file_path)}'"
                )
            else:
                self.logger.info(
                    f"[DRY RUN] - {self.logger_msg}: pretending to write CSV file | '{str(self.file_path)}'"
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


def collect_job_nums(dependency_list: List[str], allow_dep_failure: bool = False):
    """
    Function to format Slurm Job Numbers into SLURM dependency strings.
    """
    not_none_values = filter(None, dependency_list)
    complete_list = list(not_none_values)
    prep_jobs = ":".join(complete_list)
    if allow_dep_failure:
        list_dependency = [
            f"--dependency=afterany:{prep_jobs}",
            "--kill-on-invalid-dep=yes",
        ]
    else:
        list_dependency = [
            f"--dependency=afterok:{prep_jobs}",
            "--kill-on-invalid-dep=yes",
        ]
    return list_dependency


def check_if_all_same(list_of_elem: List[Union[str, int]], item: Union[str, int]):
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


def check_if_output_exists(
    match_pattern: regex.Pattern,
    file_type: str,
    search_path: Path,
    label: str,
    logger: Logger,
    debug_mode: bool = False,
):
    """
    Using a regex string/Pattern, confirms if file(s) exist and counts the number of files matching the regex.
    """
    files: List[str] = list()
    n_matches = 0
    if search_path.exists():
        if Path(search_path).is_dir():
            for file in os.listdir(str(search_path)):
                match: Match[str] = regex.search(match_pattern, str(file))
                if match:
                    files.append(match.group())

            unique_files = set(files)
            num_unique_files = len(unique_files)
            unique_files_list = list(natsorted(unique_files))

            if debug_mode:
                logger.debug(f"{label}: files found | {unique_files_list}")

            for file in files:
                filename: Path = search_path / file
                if filename.exists():
                    n_matches += 1
        else:
            num_unique_files = 0
            unique_files_list = []
    else:
        logger.warning(
            f"{label}: unable to search a non-existant path '{str(search_path)}'"
        )
        num_unique_files = 0
        unique_files_list = []

    if n_matches == 0:
        logger.info(f"{label}: missing {file_type}")
        output_exists = False
        num_unique_files = 0
        unique_files_list = []
    else:
        if debug_mode:
            logger.debug(f"{label}: found [{int(n_matches):,}] {file_type}")
        output_exists = True

    if n_matches > num_unique_files:
        logger.warning(f"{label}: pattern provided returns duplicate files")
        logger.warning(f"{label}: please use a more specific regex")

    return output_exists, n_matches, unique_files_list


def check_expected_outputs(
    outputs_found: int,
    outputs_expected: int,
    label: str,
    file_type: str,
    logger: Logger,
) -> bool:
    """
    Confirms if expected outputs were made correctly.
    """
    if outputs_found == outputs_expected:
        if outputs_expected == 1:
            logger.info(
                f"{label}: found the [{int(outputs_found):,}] expected {file_type}... SKIPPING AHEAD"
            )
        else:
            logger.info(
                f"{label}: found all [{int(outputs_found):,}] expected {file_type}... SKIPPING AHEAD"
            )
        missing_outputs = False
    else:
        if int(outputs_expected) > int(outputs_found):
            logger.info(
                f"{label}: missing [{int(int(outputs_expected) - int(outputs_found)):,}-of-{int(outputs_expected):,}] {file_type}"
            )
            missing_outputs = True
        else:
            logger.info(
                f"{label}: found [{int(int(outputs_found)-int(outputs_expected)):,}] more {file_type} than expected"
            )
            missing_outputs = False

    return missing_outputs


def process_phase(txt: str):
    """
    Handle any special characters and only use '_' as a separator.

    Input: 'A,Quick brown-fox jumped-over-the   lazy-dog'
    Output: 'A_Quick_brown_fox_jumped_over_the_lazy_dog'
    """
    special_chars = "!#$%^&*()"
    for special_char in special_chars:
        txt = txt.replace(special_char, "")
    standardize_seps = " -,"
    for sep in standardize_seps:
        txt = txt.replace(sep, "_")
    return txt


def process_resource(txt: str):
    """
    Handle any special characters and remove any separators.

    Input: 'A,Quick brown-fox jumped-over-the   lazy-dog'
    Output: 'AQuickbrownfoxjumpedoverthelazydog'
    """
    specialChars = "!#$%^&*()"
    for specialChar in specialChars:
        txt = txt.replace(specialChar, "")
    standardizeSeps = " -,_"
    for sep in standardizeSeps:
        txt = txt.replace(sep, "")
    return txt


def create_deps(num: int = 4) -> List[None]:
    """
    Create a list of None of a certain length.
    """
    return [None] * num


def remove_suffixes(filename: Path, remove_all: bool = True) -> Path:
    """
    Removing multiple file suffixes.
    """
    if not remove_all:
        suffixes = {".gz"}
    else:
        suffixes = {".bcf", ".vcf", ".gz"}
    while filename.suffix in suffixes:
        filename = filename.with_suffix("")

    return filename


def count_variants(
    truth_vcf: Path,
    logger_msg: str,
    logger: Logger,
    count_pass: bool = True,
    count_ref: bool = False,
    use_bcftools: bool = True,
    debug_mode: bool = False,
) -> Union[List[str], int, Dict[str, int], None]:
    """
    Use 'bcftools +smpl-stats' to count either REF/REF or PASS positions.
    """
    if count_pass and count_ref:
        filter = "BOTH"
        command = '$1=="FLT0"{hom_ref=$5}$1=="SITE0"{pass=$2}END{print hom_ref,pass}'
    elif count_pass and not count_ref:
        filter = "PASS"
        command = '$1=="SITE0" {print $2}'
    elif not count_pass and count_ref:
        filter = "REF/REF"
        command = '$1=="FLT0" {print $5}'
    else:
        filter = None
        command = None

    if use_bcftools:
        if debug_mode:
            logger.debug(
                f"{logger_msg}: using 'bcftools +smpl-stats' to count {filter} records | '{truth_vcf.name}'",
            )
        if command is None:
            bcftools_smpl_stats = subprocess.run(
                ["bcftools", "+smpl-stats", str(truth_vcf)],
                check=True,
                capture_output=True,
                text=True,
            )

            ## GETTING REALTIME OUTPUT WITH SUBPROCESS ##
            # ---- SOURCE: https://www.endpointdev.com/blog/2015/01/getting-realtime-output-using-python/
            # while True:
            #     output = bcftools_smpl_stats.stdout.readline()
            #     if output == '' and bcftools_smpl_stats.poll() is not None:
            #         break
            #     if output:
            #         print(output.strip())
            # return_code = bcftools_smpl_stats.poll()
            # return return_code

            if debug_mode:
                logger.debug(f"{logger_msg}: done with bcftools +smpl-stats")
            if bcftools_smpl_stats.returncode == 0:
                return str(bcftools_smpl_stats.stdout).split("\n")
            else:
                raise ChildProcessError("Unable to run bcftools +smpl-stats")

        else:
            bcftools_smpl_stats = subprocess.Popen(
                ["bcftools", "+smpl-stats", str(truth_vcf)],
                stdout=subprocess.PIPE,
            )
            bcftools_awk = subprocess.run(
                ["awk", str(command)],
                stdin=bcftools_smpl_stats.stdout,
                capture_output=True,
                text=True,
                check=True,
            )

            if bcftools_awk:
                if debug_mode:
                    logger.debug(f"{logger_msg}: done with bcftools +smpl-stats")
                if filter is not None and "both" in filter.lower():
                    multiple_results = bcftools_awk.stdout.split()
                    if len(multiple_results) != 2:
                        logger.error(
                            f"{logger_msg}: bcftools_awk() subproccess returned an unexpected number of results.\nExiting..."
                        )
                        sys.exit(1)
                    else:
                        num_RR_found = int(multiple_results[0])
                        num_pass_found = int(multiple_results[1])
                        num_variants_found = {
                            "ref/ref": num_RR_found,
                            "pass": num_pass_found,
                        }
                elif filter is not None and "pass" in filter.lower():
                    num_variants_found = int(bcftools_awk.stdout.strip())
                elif filter is not None and "ref" in filter.lower():
                    num_variants_found = int(bcftools_awk.stdout.strip())
                else:
                    num_variants_found = None
            else:
                num_variants_found = None
            return num_variants_found
    else:
        if debug_mode:
            logger.debug(
                f"{logger_msg}: counting {filter} records in [{truth_vcf.name}] using awk {command}",
            )
        count = 0
        with open(str(truth_vcf), "r") as count_file:
            for count, line in enumerate(count_file):
                pass
        if count != 0:
            num_variants_found = count + 1
        else:
            num_variants_found = None

        return num_variants_found


def add_to_dict(
    update_dict: Dict[str, Union[str, int, float]],
    new_key: str,
    new_val: Union[str, int, float],
    logger: Logger,
    logger_msg: str,
    valid_keys: Union[List[str], None] = None,
    replace_value: bool = False,
) -> None:
    """
    Confirms that a new key is valid. If the key is missing from the dictionarydd the 'key=value pair' to the results dictionary.
    """
    if valid_keys is not None:
        if new_key not in valid_keys:
            logger.error(f"{logger_msg}: invalid metadata key | '{new_key}'")
            valid_key_string: str = ", ".join(valid_keys)
            logger.error(
                f"{logger_msg}: use one of the following valid keys | '{valid_key_string}'\nExiting..."
            )
            sys.exit(1)

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
