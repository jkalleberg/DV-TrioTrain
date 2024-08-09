#!/bin/python3
"""
description: 

example:
"""

from argparse import Namespace
from collections import OrderedDict
from csv import DictReader
from dataclasses import dataclass, field
from pathlib import Path
from sys import exit, path
from typing import Dict, List, Union

from regex import compile

abs_path = Path(__file__).resolve()
module_path = str(abs_path.parent.parent)
path.append(module_path)
from helpers.files import Files
from model_training.slurm.suffix import remove_suffixes


@dataclass
class SummarizeResults:
    """
    Data to pickle for processing the summary stats from a VCF/BCF output.
    """

    args: Namespace
    sample_metadata: Union[List[Dict[str, str]], Dict[str, str]]
    output_file: Files

    # Imutable, internal parameters
    _contains_valid_trio: bool = field(default=False, init=False, repr=False)
    _digits_only: compile = field(default=compile(r"\d+"), init=False, repr=False)
    _file_path: Path = field(default=None, init=False, repr=False)
    _input_file: Files = field(default=None, init=False, repr=False)
    _index: int = field(default=0, init=False, repr=False)
    _merged_data: Union[List[str], Dict[str, str]] = field(
        default_factory=dict, init=False, repr=False
    )
    _sample_label: str = field(default=None, init=False, repr=False)
    _trio_num: int = field(default=None, init=False, repr=False)
    _total_samples: int = field(default=0, init=False, repr=False)
    # _output_lines_mie: List[str] = field(default_factory=list, init=False, repr=False)
    # _output_lines_stats: List[str] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:

        if isinstance(self.sample_metadata, dict):
            if "file_path" not in self.sample_metadata.keys():
                self.output_file.logger.error(
                    f"{self.output_file.logger_msg}: unrecognized file format, missing column with 'file_path'\nExiting..."
                )
                exit(1)
            self._file_path = Path(self.sample_metadata["file_path"])
            self._total_samples = 1
            self._sample_label = self.sample_metadata["label"]
        else:
            if "file_path" not in self.sample_metadata[0].keys():
                self.output_file.logger.error(
                    f"{self.output_file.logger_msg}: unrecognized file format, missing column with 'file_path'\nExiting..."
                )
                exit(1)
            self._file_path = Path(self.sample_metadata[0]["file_path"])
            self._total_samples = len(self.sample_metadata)
            self._sample_label = self.sample_metadata[0]["label"]

    def check_file_path(self) -> None:
        """
        Confirm that the VCF file in the metadata file exists.
        """
        self._input_file = Files(
            path_to_file=self._file_path,
            logger=self.output_file.logger,
            logger_msg=self.output_file.logger_msg,
            dryrun_mode=self.output_file.dryrun_mode,
            debug_mode=self.output_file.debug_mode,
        )

        self._input_file._test_file.check_existing(
            logger_msg=self.output_file.logger_msg,
            debug_mode=self.output_file.debug_mode,
        )
        self._input_file.file_exists = self._input_file._test_file.file_exists

    def find_trio_name(self, trio_input: str) -> Union[str, None]:
        """
        Identify the 'Trio##' pattern in an input string.
        """
        _trio_regex = compile(rf"Trio\d+")
        match = _trio_regex.search(trio_input)
        if match:
            if self.output_file.debug_mode:
                self.output_file.logger.debug(
                    f"{self.output_file.logger_msg}: INPUT CLEAN_FILENAME | '{match.group()}'"
                )
            return match.group()

    def find_trio_num(self, trio_input: str) -> None:
        """
        Identify the run order '##' pattern from an input string.
        """
        match = self._digits_only.search(trio_input)
        if match:
            _trio_num = int(match.group())
            if self._trio_num is not None:
                if _trio_num != self._trio_num:
                    self.output_file.logger.error(
                        f"{self.output_file.logger_msg}: discrepency in trio numbering: input file has 'Trio{self._trio_num}', but input label has 'Trio{_trio_num}'\nExiting..."
                    )
                    exit(1)
                else:
                    self._trio_num = _trio_num
            else:
                self._trio_num = _trio_num

        if self.output_file.debug_mode:
            self.output_file.logger.debug(
                f"{self.output_file.logger_msg}: INPUT NUMBER | '{self._trio_num}'"
            )

    def identify_trio(self) -> None:
        """
        Determine what metadata to retain internally with a valid Trio.
        """
        if self._total_samples == 3:
            # Determine if input file is labeled as a "TrioVCF"
            _result = self.find_trio_name(self._file_path.name)
            if _result is not None:
                self._ID = _result
                self._missing_merged_vcf = False
                self.find_trio_num(_result)
            else:
                self._missing_merged_vcf = True
            _metadata_dict = self.sample_metadata[0]
        elif self._total_samples == 1:
            if isinstance(self.sample_metadata, list):
                _metadata_dict = self.sample_metadata[0]
            else:
                _metadata_dict = self.sample_metadata
        elif self._total_samples == 0:
            self._missing_pedigree_data = True
            return
        else:
            self._missing_merged_vcf = True
            _metadata_dict = self.sample_metadata

        # Determine if any TrioNumber was found in the existing sample label
        self.find_trio_num(self._sample_label)

        # Create pedigree dictionary
        self._pedigree = {
            key: value
            for key, value in _metadata_dict.items()
            if key in ["sampleID", "paternalID", "maternalID", "sex"]
        }

        # Samples with any blank columns in pedigree will be ignored
        self._missing_pedigree_data = not any(self._pedigree.values())

    def validate_trio(self) -> None:
        """
        Determine which lines in metadata file contain trios with pedigrees.
        """
        # Collect pedigree
        if not self._missing_pedigree_data:
            self._childID = self._pedigree["sampleID"]
            self._child_sex = self._pedigree["sex"]
            self._motherID = self._pedigree["maternalID"]
            self._fatherID = self._pedigree["paternalID"]
        else:
            self._contains_valid_trio = False
            return

        if self._child_sex == "0":
            self.output_file.logger.info(
                f"{self.output_file.logger_msg}: missing sex info for 'child | {self._childID}'... SKIPPING AHEAD"
            )
            self._contains_valid_trio = False
        elif self._motherID == "0" and self._fatherID == "0":
            if self.output_file.debug_mode:
                self.output_file.logger.debug(
                    f"{self.output_file.logger_msg}: trio parent line... SKIPPING AHEAD"
                )
            self._contains_valid_trio = False
        elif (
            len(self._child_sex) == 0
            and len(self._motherID) == 0
            and len(self._fatherID) == 0
        ):
            if self.output_file.debug_mode:
                self.output_file.logger.debug(
                    f"{self.output_file.logger_msg}: not a Trio... SKIPPING AHEAD"
                )
            self._contains_valid_trio = False
        else:
            self._contains_valid_trio = True

    def get_sample_info(self) -> None:
        """
        Determine if working with a valid trio, or not.
        """
        self.check_file_path()
        self.identify_trio()
        self.validate_trio()

        if isinstance(self.sample_metadata, list):
            self._caller = self.sample_metadata[0]["variant_caller"]
            if self._contains_valid_trio:
                self._ID = f"Trio{self._trio_num}"
            else:
                self._ID = self.sample_metadata[0]["sampleID"]
        else:
            self._caller = self.sample_metadata["variant_caller"]
            if self._contains_valid_trio:
                self._ID = f"Trio{self._trio_num}"
            else:
                self._ID = self.sample_metadata["sampleID"]

    def add_metadata(
        self, messy_metrics: Union[List[Dict[str, str]], Dict[str, str]]
    ) -> None:
        """
        Merge the user-provided metadata with metrics Dict, or a list of Dicts
        """
        if isinstance(self.sample_metadata, dict):
            clean_metadata = {
                key: val
                for key, val in self.sample_metadata.items()
                if key != "file_path"
            }
            _clean_metrics = messy_metrics[0]
            self._merged_data = {**clean_metadata, **_clean_metrics}
        else:
            clean_metadata = [
                {key: val for key, val in d.items() if key != "file_path"}
                for d in self.sample_metadata
            ]

            rekeyed_metadata = OrderedDict({d["sampleID"]: d for d in clean_metadata})

            if (
                isinstance(messy_metrics, list)
                and "sampleID" in messy_metrics[0].keys()
            ):
                rekeyed_metrics = {d["sampleID"]: d for d in messy_metrics}
                combined = OrderedDict()

                for key in rekeyed_metrics:
                    temp = rekeyed_metadata[key]
                    temp.update(rekeyed_metrics[key])
                    combined[key] = temp

                self._merged_data = list(combined.values())

            else:
                _sample_path = remove_suffixes(self._input_file.file_path)
                _sample_name = Path(_sample_path).stem

                for d in clean_metadata:
                    if _sample_name in d["sampleID"]:
                        _metadata = d
                    else:
                        continue
                _clean_metrics = messy_metrics[0]
                self._merged_data = {**_metadata, **_clean_metrics}

    def write_output(
        self, unique_records_only: bool = False, data_type: str = "mie"
    ) -> None:
        """
        Save the combined metrics to a new CSV output, or display to screen.
        """

        if data_type != "mie":
            _new_output = self.output_file.file.replace("mie", data_type)
            self.output_file = Files(
                path_to_file=self.output_file.path / _new_output,
                logger=self._input_file.logger,
                logger_msg=self.output_file.logger_msg,
                debug_mode=self._input_file.debug_mode,
                dryrun_mode=self._input_file.dryrun_mode,
            )

        self.output_file._test_file.check_missing()

        if unique_records_only and self.output_file._test_file.file_exists:
            with open(self.output_file.path_str, "r") as file:
                dict_reader = DictReader(file)
                current_records = list(dict_reader)

            for r in current_records:
                if isinstance(self._merged_data, list):
                    if r in self._merged_data:
                        if self._input_file.debug_mode:
                            self._input_file.logger.debug(
                                f"{self.output_file.logger_msg}: skipping a previously processed file | '{self._input_file.file}'"
                            )
                        self._input_file.logger.info(
                            f"{self.output_file.logger_msg}: data has been written previously... SKIPPING AHEAD"
                        )
                        return
                    else:
                        continue

                else:
                    if self._merged_data == r:
                        if self._input_file.debug_mode:
                            self._input_file.logger.debug(
                                f"{self.output_file.logger_msg}: skipping a previously processed file | '{self._input_file.file}'"
                            )
                        self._input_file.logger.info(
                            f"{self.output_file.logger_msg}: data has been written previously... SKIPPING AHEAD"
                        )
                        return
                    else:
                        continue
        
        # _current_sample = self._merged_data[0]["sampleID"]
        self._input_file.logger.info(
            f"{self.output_file.logger_msg}: saving summary stats data | '{self.output_file.file_path}'"
        )

        # Ensure that output doesn't have duplicate sampleID column
        if isinstance(self._merged_data, dict):
            col_names = list(self._merged_data.keys())
            self.output_file.add_rows(col_names=col_names, data_dict=self._merged_data)
        else:
            for row in self._merged_data:
                col_names = list(row.keys())
                self.output_file.add_rows(col_names=col_names, data_dict=row)
