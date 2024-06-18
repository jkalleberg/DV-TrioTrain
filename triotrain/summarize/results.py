#!/bin/python3
"""
description: 

example:
"""

from dataclasses import dataclass, field
from pathlib import Path
from sys import path, exit
from typing import Dict, List, Union

from regex import compile

abs_path = Path(__file__).resolve()
module_path = str(abs_path.parent.parent)
path.append(module_path)
from helpers.files import WriteFiles


@dataclass
class SummarizeResults:
    """
    Data to pickle for processing the summary stats from a VCF/BCF output.
    """

    sample_metadata: Union[List[Dict[str, str]], Dict[str, str]]
    output_file: WriteFiles

    # imutable, internal parameters
    _contains_valid_trio: bool = field(default=False, init=False, repr=False)
    _digits_only: compile = field(default=compile(r"\d+"), init=False, repr=False)
    _file_path: Path = field(default=None, init=False, repr=False)
    _input_file: WriteFiles = field(default=None, init=False, repr=False)
    _trio_num: int = field(default=None, init=False, repr=False)
    _total_samples: int = field(default=0, init=False, repr=False)
    _sample_label: str = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:

        if isinstance(self.sample_metadata, dict):
            if "file_path" not in self.sample_metadata.keys():
                self.output_file.logger.error(f"{self.output_file.logger_msg}: unrecognized file format, missing column with 'file_path'\nExiting...")
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
        self._input_file = WriteFiles(
            path_to_file=self._file_path.parent,
            file=self._file_path.name,
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

        if self.output_file.debug_mode:
            self.output_file.logger.debug(
                f"{self.output_file.logger_msg}: INPUT NUMBER | '{self._trio_num}'"
            )

    def identify_trio(self) -> None:
        if self._total_samples == 3:
            # Determine if input file is labeled as a "TrioVCF"
            _result = self.find_trio_name(self._file_path.name)
            if _result is not None:
                self._ID = _result
                self._missing_merged_vcf = False
                self.find_trio_num(_result)
            else:
                self._missing_merged_vcf = True

            # Determine if any TrioNumber was found in the existing sample label
            self.find_trio_num(self._sample_label)

            self._pedigree = {
                key: value
                for key, value in self.sample_metadata[0].items()
                if key in ["sampleID", "paternalID", "maternalID", "sex"]
            }
            # Samples with any blank columns in pedigree will be ignored
            self._missing_pedigree_data = not any(self._pedigree.values())

        else:
            self._missing_pedigree_data = True
            self._missing_merged_vcf = True

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

    def get_sample_info(self, use_mie: bool = False) -> None:
        self.check_file_path()
        self.identify_trio()
        self.validate_trio()
        input_name = Path(self._input_file._test_file.clean_filename).name

        if not self._missing_pedigree_data:
            self._ID = f"Trio{self._trio_num}"
            self._caller = self.sample_metadata[0]["variant_caller"]
        else:
            self._ID = self.sample_metadata["sampleID"]
            self._caller = self.sample_metadata["variant_caller"]

        if self._ID not in input_name:
            self.output_file.logger.warning(
                f"{self.output_file.logger_msg}: discrepancy between ID '{self._ID}' and file name '{input_name}'"
            )
            self.output_file.logger.info(
                f"{self.output_file.logger_msg}: therefore, job name will use ID | '{self._ID}'"
            )
            _job_name = f"{self._ID}.{self._caller}"
        else:
            _job_name = f"{input_name}.{self._caller}"

        if use_mie:
            self._job_name = f"mie.{_job_name}"
        else:
            self._job_name = f"stats.{_job_name}"

        print("TRIO NUMBER:", self._trio_num)
        print("ID:", self._ID)
        print("CONTAINS TRIO:", self._contains_valid_trio)
        print("MISSING PEDIGREE:", self._missing_pedigree_data)
        print("MISSING MERGED VCF:", self._missing_merged_vcf)
        breakpoint()
