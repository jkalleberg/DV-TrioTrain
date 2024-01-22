#!/bin/python3
"""
description: transform VCF into TSV file
"""
from csv import DictReader
from dataclasses import dataclass, field
from logging import Logger
from pathlib import Path
from subprocess import run as run_sub
from sys import path
from typing import Dict, List, Union

abs_path = Path(__file__).resolve()
module_path = str(abs_path.parent.parent)
path.append(module_path)

from helpers.files import TestFile
from model_training.slurm.suffix import remove_suffixes


@dataclass
class Convert_VCF:
    """
    Transform a Trio VCF into a TSV file.
    """

    # required parameters
    vcf_input: Union[str, Path]
    tsv_output: Union[str, Path]
    logger: Logger

    # optional values
    debug: bool = False
    dry_run: bool = False
    logger_msg: Union[str, None] = None
    query_format: str = field(
        default="%CHROM\t%POS\t%REF\t%ALT\t%INFO/MCU\t%INFO/MCV[\t%GT\t%GQ]\n"
    )
    tsv_column_names: List[str] = field(default_factory=list)

    # internal parameters
    _tsv_dict_array: List[Dict[str, str]] = field(
        default_factory=list, init=False, repr=False
    )

    def check_input(self) -> None:
        """
        Confirm the VCF input file exists.
        """
        self._input_file = TestFile(file=self.vcf_input, logger=self.logger)
        self._input_file.check_existing(
            logger_msg=self.logger_msg, debug_mode=self.debug
        )
        assert (
            self._input_file.file_exists
        ), f"non-existant file provided | '{self._input_file.file}'\nPlease provide a valid VCF file."

        self._prefix_path = remove_suffixes(self._input_file.path)
        self._prefix_name = self._prefix_path.name

    def check_output(self) -> None:
        """
        Determine if intermediate TSV file exists.
        """
        if self.tsv_output and self.tsv_output != self._input_file.path.parent:
            _output_path = self.tsv_output
            if self.dry_run:
                self.logger.info(f"{self.logger_msg}: using new output directory...'")
        else:
            _output_path = self._input_file.path.parent
            if self.dry_run:
                self.logger.info(
                    f"{self.logger_msg}: using existing output directory..."
                )
        if self.dry_run:
            self.logger.info(
                f"{self.logger_msg}: output file | '{_output_path / self._prefix_name}.tsv'"
            )
        self._output_file = TestFile(
            file=_output_path / f"{self._prefix_name}.tsv", logger=self.logger
        )
        self._output_file.check_missing(
            logger_msg=self.logger_msg, debug_mode=self.debug
        )

    def convert_to_tsv(self) -> None:
        """
        Run 'bcftools query' as a Python Subprocess, and write the output to an intermediate file.
        """
        self.logger.info(
            f"{self.logger_msg}: converting VCF -> TSV file | '{self._output_file.path.name}'"
        )
        bcftools_query = run_sub(
            [
                "bcftools",
                "query",
                "-f",
                self.query_format,
                str(self._input_file.path),
            ],  # type: ignore
            capture_output=True,
            text=True,
            check=True,
        )
        self.logger.info(
            f"{self.logger_msg}: done converting VCF -> TSV file | '{self._output_file.path.name}'"
        )

        # make entering a list of column names automatic if not provided by user
        _first_line = bcftools_query.stdout.splitlines()[0:1]
        _first_line_list = _first_line[0].split("\t")
        _total_cols = len(_first_line_list)

        if self.tsv_column_names:
            self._custom_header_list = self.tsv_column_names
        else:
            _query_fmt_cols = self.query_format.replace("%", "")
            _format_cols = _query_fmt_cols.split("[")
            _per_site_cols = _format_cols[0].split("\t")
            _per_sample_cols = _format_cols[1].strip().strip("]").split()
            _n_samples = int(
                (_total_cols - len(_per_site_cols)) / len(_per_sample_cols)
            )
            updated_sample_cols = []
            for itr in range(0, _n_samples):
                for col in _per_sample_cols:
                    updated_sample_cols.append(f"{col}_{itr}")

            self._custom_header_list = _per_site_cols + updated_sample_cols

        _custom_header_str = "\t".join(self._custom_header_list[0:]) + "\n"
        assert _total_cols == len(
            self._custom_header_list
        ), f"unexpected column headers | {_total_cols} != {len(self._custom_header_list)}"

        if not self.dry_run:
            if self.debug:
                self.logger.debug(
                    f"{self.logger_msg}: saving converted VCF file | '{self._output_file.path.name}'"
                )
            file = open(str(self._output_file.path), mode="w")
            # Add custom header to the new TSV
            file.write(_custom_header_str)
            file.close()
            contents = open(str(self._output_file.path), mode="a")
            contents.write(bcftools_query.stdout)
            contents.close()
            if self.debug:
                self.logger.debug(f"{self.logger_msg}: done saving converted VCF file")
        else:
            self.logger.info(
                f"{self.logger_msg}: pretending to write converted VCF file | '{self._output_file.path.name}'"
            )
            self.tsv_format = bcftools_query.stdout.splitlines()

    def load_raw_data(self) -> None:
        """
        Read lines of a TSV (tab-separated values) file as an array of dicts.

            NOTE: the input file should include a header line consisting of column names.

        Each dict represents a row in the input file, with column names as keys.
        """
        # Confirm input data is an existing file
        if self._output_file.path.exists():
            print("HERE!")
            breakpoint()
            with open(str(self._output_file.path), mode="r") as data:
                # Open the file as read only
                for itr, line in enumerate(DictReader(data, delimiter="\t")):
                    self._tsv_dict_array.insert(itr, line)
        else:
            if self.dry_run:
                # stream in the convert-tsv stdout to process without writing an intermediate file
                for itr, line in enumerate(
                    DictReader(
                        self.tsv_format,
                        fieldnames=self._custom_header_list,
                        delimiter="\t",
                    )
                ):
                    self._tsv_dict_array.insert(itr, line)
            else:
                self.logger.error(
                    f"{self._logger_msg}: unable to find existing TSV file | '{self._output_file.path}'\nExiting..."
                )
                exit(1)

    def run(self) -> None:
        self.check_input()
        self.check_output()
        if not self.dry_run and self._output_file.file_exists:
            self.logger.info(
                f"{self.logger_msg}: found exisiting converted VCF file | '{self._output_file.path.name}'"
            )
            return
        else:
            self.convert_to_tsv()
            self.load_raw_data()
