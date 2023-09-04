#!/bin/python3
"""
description: combine the CSV outputs from multiple TrioTrain iterations

example:
    python3 triotrain/summarize/merge_results.py                    \\
        --env-file TUTORIAL/GIAB_Trio/envs/run0.env                 \\
        --dry-run
"""
import argparse
from csv import DictReader, reader
from sys import exit, path
from collections import defaultdict
from dataclasses import dataclass, field
from logging import Logger
from os import environ, getcwd, path as p
from pathlib import Path
from typing import Union
import pandas as pd
from regex import compile

abs_path = Path(__file__).resolve()
module_path = str(abs_path.parent.parent)
path.append(module_path)

from helpers.environment import Env
from helpers.files import WriteFiles, TestFile
from helpers.outputs import check_if_output_exists

def collect_args():
    """
    Process command line argument to execute script.
    """
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-e",
        "--env-file",
        dest="env_file",
        help="[REQUIRED]\ninput file (.env)\nprovides environment variables",
        type=str,
        metavar="</path/file>",
    )
    parser.add_argument(
        "-g",
        "--first-genome",
        dest="first_genome",
        choices=["Mother", "Father", "None"],
        help="[REQUIRED] if RunOrder in --env-file >= 1\nsets the merging order\n(default: %(default)s)",
        default="None",
        type=str,
    )
    parser.add_argument(
        "-o",
        "--output-prefix",
        dest="output_prefix",
        type=str,
        help="output path and file prefix for where to store resulting merged CSV",
        metavar="</path/file_prefix>",
    )
    parser.add_argument(
        "-d",
        "--debug",
        dest="debug",
        help="if True, enables printing detailed messages",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        help="if True, display commands to the screen",
        action="store_true",
    )
    # parser.add_argument(
    #     "-s",
    #     "--merge-all",
    #     dest="merge_all",
    #     help="if True, after merging tests, merge the AllTests files in the summary/",
    #     action="store_true",
    # )
    parser.add_argument(
        "-m",
        "--metadata",
        dest="metadata",
        type=str,
        help="input file (.csv)\nprovide unique descriptions for the test genome(s)",
        metavar="</path/file>",
    )
    return parser.parse_args()

def check_args(args: argparse.Namespace, logger: Logger):
    """
    With "--debug", display command line args provided.
    With "--dry-run", display a msg.
    Then, check to make sure all required flags are provided.
    """
    if args.debug:
        str_args = "COMMAND LINE ARGS USED: "
        for key, val in vars(args).items():
            str_args += f"{key}={val} | "

        logger.debug(str_args)
        _version = environ.get("BIN_VERSION_DV")
        logger.debug(f"using DeepVariant version | {_version}")

    if args.dry_run:
        logger.info("[DRY RUN]: output will display to screen and not write to a file")

    assert (
        args.env_file
    ), "Missing --env-file\nPlease provide a file with environment variables for the current analysis"

    if args.first_genome == "None":
        args.first_genome = None


@dataclass
class MergedTests:
    """
    Define what data to keep when merging results from multiple test genomes within a single analysis.
    """

    # required values
    args: argparse.Namespace
    logger: Logger

    # internal, imutable values
    _digits_only = compile(r"\d+")
    _input_files: list = field(default_factory=list, init=False, repr=False)
    _logger_msg: Union[str, None] = None
    _metadata_dict: dict = field(default_factory=dict, init=False, repr=False)
    _output_samples: list = field(default_factory=list, init=False, repr=False)
    _phase = "merge_tests"
    _results_dict: dict = field(default_factory=dict, init=False, repr=False)
    _samples: list = field(default_factory=list, init=False, repr=False)
    _version: str = field(
        default=str(environ.get("BIN_VERSION_DV")), init=False, repr=False
    )

    def __post_init__(self) -> None:

        self._output_dict = defaultdict(list)
        if "run0" in str(self.args.env_file.lower()):
            self._custom_model = False
        else:
            self._custom_model = True
        self._num_found = 0
        self._num_loaded = 0
        self._num_merged = 0
        if self.args.first_genome == "Mother":
            self._next_genome = "Father"
        else:
            self._next_genome = "Mother"

    def load_variables(self) -> None:
        """
        Load in variables from the env file, and define python variables.
        """
        self.env = Env(self.args.env_file, self.logger)

        match = self._digits_only.search(self.env.env_path.name)
        if match:
            self._run_num = int(float(match.group()))
        else:
            self.logger.error(f"unable to identify a valid run number\nExiting...")
            exit(1)

        var_list = [
            "CodePath",
            "TotalTests",
            "BaselineModelResultsDir",
            "ResultsDir"]
        
        if self.args.first_genome is None:
            extra_vars = ["RunDir", "RunDir"]
        else:
            extra_vars = [f"{self.args.first_genome}CompareDir",
            f"{self._next_genome}CompareDir"]
        
        vars = var_list + extra_vars

        (
            code_path,
            _total_num_tests,
            self._baseline_results,
            _output_dir,
            self._compare_dir1,
            self._compare_dir2,
        ) = self.env.load(*vars)

        if self._custom_model:
            self._output_path = Path(_output_dir)
        else:
            self._output_path = Path(self._baseline_results)
        
        assert (
            getcwd() == code_path
        ), f"run the workflow in the {code_path} directory only!" 

        if self._run_num >= 1:
            assert (
                self.args.first_genome
            ), "missing --first-genome\nPlease set which training from the current trio was used first."

        self._total_num_tests = int(_total_num_tests)
        version_nums = (self._version.split("."))
        version_clean = ".".join(version_nums[0:2])
        self._model_version = f"DV{version_clean}"

        if self._custom_model:
            training_species = "bovine"
            model_type = "custom"
    
            if self.args.first_genome is None:
                self._expected_num_tests = self._total_num_tests
                self._mode = f"GIAB{self._run_num}"
            else:
                self._expected_num_tests = self._total_num_tests * 2
                self._mode = f"Trio{self._run_num}"
            
            if self.args.first_genome is None:
                self._search_paths = [self._compare_dir1]
                self._ckpts_list = ["TestCkptName"]
            else:
                self._search_paths = [self._compare_dir1, self._compare_dir2]
                self._ckpts_list = [
                    self.env.contents[f"{self.args.first_genome}TestCkptName"],
                    self.env.contents[f"{self._next_genome}TestCkptName"],
                ]
        else:
            training_species = "human"
            model_type = "default"

            self._expected_num_tests = self._total_num_tests
            self._mode = f"Baseline-{self._model_version}"
            self._search_paths = [self._baseline_results]
            self._ckpts_list = [self.env.contents["BaselineTestCkptName"]]

        self._model_used = {
            "training_species": training_species,
            "type": model_type,
            "version": self._model_version,
        }

        # if self.args.merge_all:
        #     self._logger_msg = "[merge_all]"
        # else:    
        self._logger_msg = f"[{self._mode}] - [{self._phase}]"

    def load_metadata(self) -> None:
        """
        Read in and save the metadata file as a dictionary.
        """
        # Confirm data input is an existing file
        self.metadata = TestFile(self.args.metadata, self.logger)
        self.metadata.check_existing()
        if self.metadata.file_exists:
            self.logger.info(f"{self._logger_msg}: adding test-specific metadata to CSV file")

            # if self.args.merge_all:
            #     return
            # else:
            # read in the csv file
            with open(self.metadata.file, mode="r", encoding="utf-8-sig") as data:
                dict_reader = DictReader(data)
                data_list = list(dict_reader)

            # identify the column with test name(s)
            for k, v in data_list[0].items():
                if "test".lower() in v:
                    self._key = k
                else:
                    pass

            # use the unique test names as keys,
            # and save all other columns as a dictionary
            for line in data_list:
                new_key = line[self._key]
                new_values = {key: val for key, val in line.items() if key != self._key}
                self._metadata_dict[new_key] = new_values

            num_missing = self._total_num_tests - len(self._metadata_dict)
            assert (
                num_missing == 0
            ), f"missing {num_missing} lines in metadata | '{str(self.metadata.path.name)}'"
        else:
            self.logger.error(
                f"{self._logger_msg}: unable to load metadata file | '{str(self.metadata.path)}'"
                )
            raise ValueError("Invalid Input File")

    def find_test(self, test_num: int = 1) -> None:
        """
        find the 'total' results file for a single test genome
        """
        input_file_csv = self._search_path / f"Test{test_num}.total.metrics.csv" 
        if input_file_csv.is_file():
            self._num_found += 1
            self._input_files.append(str(input_file_csv))
        else:
            if self._genome is not None:
                self.logger.warning(
                    f"{self._logger_msg} - [{self._genome}]: missing a file | '{str(input_file_csv)}'"
                )
            else:
                self.logger.warning(
                    f"{self._logger_msg}: missing a file | '{str(input_file_csv)}'"
                )

    def find_tests(
        self,
        search_path: Union[str, Path],
    ) -> None:
        """
        find the 'total' results files for every test genome
        """
        self._search_path = Path(search_path)
        current_model = self._search_path.name.split("_")
        
        if len(current_model) > 1:
            self._genome = current_model[1]
        else:
            self._genome = None

        for t in range(1, (self._total_num_tests + 1)):
            self.find_test(test_num=t)

        if self.args.debug:
            self.logger.debug(f"{self._logger_msg}:\n{self._input_files}")
        
        if len(self._input_files) == 0:
            self.logger.warning(
                f"{self._logger_msg}: no results files detected.\nExiting..."
            )
            exit(1)
    
    def find_AllTests(self) -> None:
        """
        identify how many 'AllTests' files exist.
        """
        self._total_found = 0
        self._file_names = list()
        search_paths = [Path(self._baseline_results), self._output_path]
        search_patterns = [r"\w+\.\w+\.\w+\.AllTests\.total\.metrics\.csv", r"\w+\d+\.AllTests\.total\.metrics\.csv"]
        
        for i,sp in enumerate(search_paths):
            self.logger.info(f"{self._logger_msg}: searching path | '{sp}'")
            files_exist, total_found, file_names = check_if_output_exists(
                match_pattern=search_patterns[i], 
                file_type="AllTests files",
                search_path=sp,
                msg=self._logger_msg,
                logger=self.logger,
                debug_mode=self.args.debug
            )
            self._files_exist = files_exist
            if files_exist:
                self._total_found += total_found
                self._file_names = self._file_names + [sp / f for f in file_names]
        
        if self._files_exist:        
            self.logger.info(f"{self._logger_msg}: found {self._total_found} matching files")

    def load_csv(self, index: int = 0) -> None:
        """
        load and process a single results csv file
        """
        K = None

        with open(
            self._input_files[index], mode="r", encoding="utf-8-sig"
        ) as results_csv:
            
            input_name = Path(self._input_files[index]).parent.name

            test_dict = {}
            csv_reader = reader(results_csv)

            keep_these = [
                "checkpoint",
                "SNPs_%",
                "INDELs_%",
                "precision",
                "recall",
                "F1-Score",
            ]

            self._model_name = None
            for row in csv_reader:
                key, value = row
                if "testname" in key.lower():
                    K = value.lower()
                    test_dict["test_name"] = K
                elif "modelused" in key.lower():
                    if "default" in value:
                        if self._custom_model:
                            self._model_name = self.env.contents["RunName"]
                        else:
                            if "noPop" in input_name:
                                self._model_name = f"{self._model_version}_default_human"
                            else:
                                self._model_name = f"{self._model_version}_WGS.AF_human"
                    else:
                        genome = value.split("-")[1]
                        self._model_name = f"Trio{self._run_num}-{genome}"
                    
                    test_dict["model_name"] = self._model_name
                    
                else:
                    if self.args.metadata:
                        for k in self._metadata_dict.keys():
                            if k in test_dict.values():
                                test_dict.update(self._metadata_dict[k])

                    for k in keep_these:
                        if k in key.lower() or k in key:
                            test_dict[key] = value
            
            if K is not None and len(test_dict) > 0:
                if K in self._results_dict.keys():
                    self._results_dict[index].update(test_dict)
                else:
                    self._results_dict[index] = test_dict

    def load_csv_results(self, starting_index: int = 0) -> None:
        """
        load and process the results file for every test genome
        """
        for i in range(starting_index, len(self._input_files)):
            self._num_loaded += 1
            if self._genome is None:
                self.logger.info(
                    f"{self._logger_msg}: loading file {self._num_loaded}-of-{self._expected_num_tests}"
                )
            else:
                self.logger.info(
                    f"{self._logger_msg} - [{self._genome}]: loading file {self._num_loaded}-of-{self._expected_num_tests}"
                )
            self.load_csv(i)

    def merge(self) -> None:
        """
        combine the two dictionaries and create a list of dicts to write as a file.
        """
        for key in self._results_dict.keys():
            self._num_merged += 1
            if self._genome is None:
                self.logger.info(
                    f"{self._logger_msg}: merging file {self._num_merged}-of-{self._expected_num_tests}"
                )
            else:
                self.logger.info(
                    f"{self._logger_msg} - [{self._genome}]: merging file {self._num_merged}-of-{self._expected_num_tests}"
                )

            # combine metrics from multiple tests
            merged_values = {**self._results_dict[key]}

            # use defaultdict so that any missing keys will be set to 'None' automatically
            _final_results = defaultdict(None)
            _final_results.update(merged_values)

            # create a list of defaultdicts
            index = self._num_merged - 1
            if self.args.debug:
                self.logger.debug(
                    f"{self._logger_msg}: SAMPLE#{index}\n{_final_results}"
                    )
            self._samples.insert(index, _final_results)

    def save_results(self) -> None:
        """
        either display output to the screen, or write to a new intermediate CSV file
        """
        # if self.args.merge_all:
        #     input_label = str(self._file_names[0]).split(".")
        #     name = ".".join(["AllRuns"] + input_label[2:])
        # else:
        input_label = Path(self._input_files[0]).name.split(".")
        if self._custom_model:
                name = ".".join([self._mode, "AllTests"] + input_label[1:])
        else:
            name = ".".join([str(self._model_name), "AllTests"] + input_label[1:])

        output = WriteFiles(
            str(self._output_path),
            name,
            self.logger,
            logger_msg=self._logger_msg,
            dryrun_mode=self.args.dry_run,
        )
        output.check_missing()

        # if self.args.merge_all:
            # if self.args.dry_run:
            #     self.logger.info(
            #         f"[DRY RUN] - {self._logger_msg}: pretending to write the final CSV file | '{str(output.file_path)}'"
            #     )
            #     print("---------------------------------------------")
            #     print(self._final_csv)
            #     print("---------------------------------------------")
            # else:
            #     self.logger.info(f"{self._logger_msg}: writing the final CSV file |  '{str(output.path)}'")
            #     self._final_csv.to_csv(output.file_path, index=False)
        # else:
        output.write_csv(write_dict=self._output_dict)
    
    def merge_tests(self) -> None:
        """
        merge the processed hap.py results from each test into a single file called 'AllTests'
        """
        for i, c in enumerate(self._search_paths):
            self.find_tests(search_path=c)

        self.load_csv_results(starting_index=0)
        self.merge()

        # Identify the final row names across all samples
        final_row_names = list()
        for d in self._samples:
            for key in d.keys():
                if key not in final_row_names:
                    final_row_names.append(key)

        # Pad any samples missing rows with an empty string ('')
        # And save to another defaultdict containing lists of values
        for i, dd in enumerate(self._samples):
            # Pad each dd with empty string for any missing keys
            for row_name in final_row_names:
                dd.setdefault(row_name, "")
            if self.args.debug:
                self.logger.debug(f"{self._logger_msg}: SAMPLE#{i}\n{dd}")
            # Combine all samples values into a dict where row names are keys
            for key, value in dd.items():
                self._output_dict[key].append(value)

        # confirm we didn't skip any samples
        num_missing = self._expected_num_tests - len(self._input_files)
        if num_missing != 0:
            self.logger.warning(f"{self._logger_msg}: missing {num_missing} input files... unable to include them in merge")
    
    def add_metadata(self) -> None:
        """combine metadata with columns
        """
        metadata_csv = pd.read_csv(self.metadata.file)

        # transpose columns and rows, remove a duplicate row
        transposed_csv = metadata_csv.T
        clean_metadata = transposed_csv.rename(columns=transposed_csv.iloc[0]).drop('label') # type: ignore
        self._metadata_dict = clean_metadata.to_dict()
            
        # clean_metadata.index.name = "test_name"
        # clean_metadata.reset_index(inplace=True)
        # self._final_csv = pd.concat([clean_metadata, combined_csv])
    
    # def merge_all(self) -> None:
    #     """
    #     merge the 'AllTests' files in the summary/ into a single file, and add optional metadata about each test.
    #     """
    #     self.find_AllTests()
        
    #     total_records = [x for x in range(0, (self._total_found * self._total_num_tests))]
    #     col_indexes = [total_records[i * self._total_num_tests:(i + 1) * self._total_num_tests] for i in range((len(total_records) + self._total_num_tests - 1) // self._total_num_tests )]
        
    #     # combine all files in the list
    #     csv1 = pd.read_csv(self._file_names[0], sep=",")
    #     print(csv1)
    #     csv2 = pd.read_csv(self._file_names[1], sep=",")
    #     print(csv2)
    #     breakpoint()
    #     # combined_csv = pd.concat([pd.read_csv(f, sep=",", names=col_indexes[i]) for i,f in enumerate(self._file_names)], axis=0)
    #     # print(combined_csv)
    #     # breakpoint()        
    #     self.save_results()

    def run(self) -> None:
        """
        Combine all steps into a single module
        """
        self.load_variables()
        if self.args.metadata:
            self.load_metadata()
            self.add_metadata()

        # if self.args.merge_all:
        #     self.merge_all()
        # else:
        self.merge_tests()
        self.save_results()

def __init__():
    from helpers.utils import get_logger
    from helpers.wrapper import Wrapper, timestamp

    # Collect command line arguments
    args = collect_args()

    # Collect start time
    Wrapper(__file__, "start").wrap_script(timestamp())

    # Create error log
    current_file = p.basename(__file__)
    module_name = p.splitext(current_file)[0]
    logger = get_logger(module_name)

    # Check command line args
    check_args(args, logger)

    merging = MergedTests(args, logger)

    try:
        merging.run()
    except AssertionError as e:
        if merging._logger_msg is not None:
            logger.error(f"{merging._logger_msg}: {e}\nExiting...")
        else:
            logger.error(f"{e}\nExiting...")
        exit(1)

    Wrapper(__file__, "end").wrap_script(timestamp())


# Execute functions created
if __name__ == "__main__":
    __init__()
