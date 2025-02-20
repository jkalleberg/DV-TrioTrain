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
    output_format: str = field(
        # default="%CHROM\t%POS\t%REF\t%ALT\t%INFO/MCU\t%INFO/MCV[\t%GT\t%GQ]\n"
        default="%CHROM\t%POS\t%REF\t%ALT\t%INFO/MCU\t%INFO/MCV\t%QUAL[\t%GT\t%GQ\t%DP\t%AD\t%PL]\n"
    )
    tsv_column_names: List[str] = field(default_factory=list)

    # internal parameters
    _bcftools_query: run_sub = field(default=None, init=False, repr=False)
    _custom_header_list: List[str] = field(default_factory=list, init=False, repr=False)
    _input_col_names: List[str] = field(default_factory=list, init=False, repr=False)
    _intermediate_header: List[str] = field(
        default_factory=list, init=False, repr=False
    )
    _tsv_dict_array: List[Dict[str, str]] = field(
        default_factory=list, init=False, repr=False
    )

    def __post_init__(self) -> None:
        if self.logger_msg is None:
            self.logger_msg = ""
            self._internal_msg = ""
        else:
            self._internal_msg = f"{self.logger_msg}: "

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

        _model_used = self._input_file.path.parent.name
        self._prefix_path = remove_suffixes(self._input_file.path)
        
        if "dv" in _model_used.lower() or "dt" in _model_used.lower():
            self._prefix_name = f"{_model_used}.{self._prefix_path.name}"
        else:
            self._prefix_name = self._prefix_path.name

    def check_outputs(self, filter_label: Union[str, None] = None) -> None:
        """
        Determine if intermediate filtered VCF & output TSV file exist.
        """
        if filter_label is None:
            self._intermediate_vcf_file = self._input_file
        else:
            self._intermediate_vcf_file = TestFile(
                file=f"{self._prefix_path}.{filter_label}.vcf.gz", logger=self.logger
            )
            if self.dry_run:
                self.logger.info(
                    f"{self._internal_msg}intermediate VCF file | '{self._intermediate_vcf_file.file}'"
                )
            self._intermediate_vcf_file.check_missing(
                logger_msg=self.logger_msg, debug_mode=self.debug
            ) 
        
        if self.tsv_output and self.tsv_output != self._input_file.path.parent:
            _output_path = Path(self.tsv_output)
            if self.dry_run:
                self.logger.info(f"{self._internal_msg}using user-provide output directory...")
        else:
            _output_path = Path(self._input_file.path.parent)
            if self.dry_run:
                self.logger.info(
                    f"{self._internal_msg}using existing output directory..."
                )
        
        if filter_label is None:
            self._output_file = TestFile(
                file=_output_path / f"{self._prefix_name}.tsv", logger=self.logger
            )
        else:
            self._output_file = TestFile(
                file=_output_path / f"{self._prefix_name}.{filter_label}.tsv", logger=self.logger
            )
        if self.dry_run:
            self.logger.info(
                f"{self._internal_msg}output file | '{self._output_file.path.name}'"
            )
        self._output_file.check_missing(
            logger_msg=self.logger_msg, debug_mode=self.debug
        )

    def get_vcf_headers(self) -> None:
        """
        Run 'bcftools view' as a Python Subprocess to identify the header row only. Transform into a list, and identify sample names.
        """
        self.logger.info(
            f"{self._internal_msg}identifying VCF headers\t\t\t| '{self._input_file.path.name}'"
        )
        
        bcftools_view = run_sub(
            [
                "bcftools",
                "view",
                "-h",
                self._input_file.file,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.logger.info(
            f"{self._internal_msg}done identifying VCF headers\t\t| '{self._input_file.path.name}'"
        )
        self._input_col_names = bcftools_view.stdout.splitlines()[-1].strip("#").split()
        self._samples = self._input_col_names[9:]

    def get_tsv_headers(self) -> None:
        """
        Identify output headers based on user input (i.e. 'bcftools query' format entered).
        """
        _output_format = self.output_format.replace("%", "").replace("]\n", "")
        _format_cols = _output_format.split("[")

        self._per_site_cols = _format_cols[0].split("\t")
        self._per_sample_cols = _format_cols[1].strip().split()

        _updated_sample_cols = []
        for s in self._samples:
            for col in self._per_sample_cols:
                _updated_sample_cols.append(f"{col}_{s}")
        self._custom_header_list = self._per_site_cols + _updated_sample_cols
    
    # def filter_vcf(self, filter: Union[str, None] = None) -> None:
    #     """
    #     Run 'bcftools filter' as a Python Subprocess, and write the output to an intermediate VCF file.
    #     """        
    #     if self._intermediate_vcf_file is not None and self._intermediate_vcf_file.file_exists:
    #         self.logger.info(
    #             f"{self._internal_msg}existing file found | '{self._intermediate_vcf_file.file}'"
    #         )
    #         return
        
    #     self.logger.info(
    #         f"{self._internal_msg}extracting 'PASS' SNPs only | '{self._intermediate_vcf_file.path.name}'"
    #     )
        
    #     self._bcftools_filter = run_sub(
    #         [
    #             "bcftools",
    #             "filter",
    #             "-i",
    #             "TYPE=\"snp\" & FILTER=\"PASS\"",
    #             "-o",
    #             self._intermediate_vcf_file.file,
    #             "-O",
    #             "z",
    #             self._input_file.file,
    #         ],  # type: ignore
    #         text=True,
    #         check=True,
    #     )
    #     self.logger.info(
    #         f"{self._internal_msg}done extracting 'PASS' SNPs only | '{self._intermediate_vcf_file.path.name}'"
    #     )

    def convert_to_tsv(self) -> None:
        """
        Run 'bcftools query' as a Python Subprocess, and write the output to an intermediate file.
        """
        if self._output_file.file_exists:
            self.logger.info(
                f"{self._internal_msg}existing file found\t| '{self._output_file.file}'"
            )
            return
        
        self.logger.info(
            f"{self._internal_msg}converting VCF -> TSV file\t\t| '{self._output_file.path.name}'"
        )
        self._bcftools_query = run_sub(
            [
                "bcftools",
                "query",
                "-f",
                self.output_format,
                self._intermediate_vcf_file.file,
                # self._input_file.file,
            ],  # type: ignore
            capture_output=True,
            text=True,
            check=True,
        )
        self.logger.info(
            f"{self._internal_msg}done converting VCF -> TSV file\t| '{self._output_file.path.name}'"
        )

        _header_line = self._bcftools_query.stdout.splitlines()[0:1]
        self._intermediate_header = _header_line[0].split("\t")

    def test_output_headers(self) -> None:
        """
        Confirm number of columns matches expectations.
        """
        _n_cols_found = len(self._intermediate_header)
        assert _n_cols_found == len(
            self._custom_header_list
        ), f"unexpected column headers | {_n_cols_found} != {len(self._custom_header_list)}"

    def save_output(self) -> None:
        """
        Either write output to disk, or store within the dataclass for use by another python class.
        """
        _custom_header_str = "\t".join(self._custom_header_list[0:]) + "\n"

        if not self.dry_run:
            if self.debug:
                self.logger.debug(
                    f"{self._internal_msg}saving converted VCF file | '{self._output_file.path.name}'"
                )
            file = open(str(self._output_file.path), mode="w")

            # Add custom header to the new TSV
            file.write(_custom_header_str)
            file.close()
            contents = open(str(self._output_file.path), mode="a")
            contents.write(self._bcftools_query.stdout)
            contents.close()
            if self.debug:
                self.logger.debug(f"{self._internal_msg}done saving converted VCF file")
        else:
            self.logger.info(
                f"{self._internal_msg}pretending to write converted VCF file | '{self._output_file.path.name}'"
            )
            self.tsv_format = self._bcftools_query.stdout.splitlines()

    def load_raw_data(self) -> None:
        """
        Read lines of a TSV (tab-separated values) file as an array of dicts.

            NOTE: the input file should include a header line consisting of column names.

        Each dict represents a row in the input file, with column names as keys.
        """
        # Stream in the convert-tsv stdout to process without writing an intermediate file
        if self.dry_run and not self._output_file.path.exists():
            self.logger.info(
                f"{self._internal_msg}loading contents from converting VCF -> TSV\t| '{self._output_file.path.name}'"
            )
            for itr, line in enumerate(
                DictReader(
                    self.tsv_format,
                    fieldnames=self._custom_header_list,
                    delimiter="\t",
                )
            ):
                self._tsv_dict_array.insert(itr, line)
            self.logger.info(
                f"{self._internal_msg}done loading contents from converting VCF -> TSV\t| '{self._output_file.path.name}'"
            )
        else:
            # Confirm converted TSV is an existing file
            if self._output_file.path.exists():
                self.logger.info(
                    f"{self._internal_msg}loading TSV file contents\t\t| '{self._output_file.path.name}'"
                )
                with open(str(self._output_file.path), mode="r") as data:
                    # Open the file as read only
                    for itr, line in enumerate(DictReader(data, delimiter="\t")):
                        if self.debug and itr % 30000 == 0:
                            self.logger.info(
                                f"{self._internal_msg}completed {itr:,} records..."
                            )
                        self._tsv_dict_array.insert(itr, line)
                self.logger.info(
                    f"{self._internal_msg}done loading TSV file contents\t| '{self._output_file.path.name}'"
                )
            else:
                self.logger.error(
                    f"{self._internal_msg}unable to find existing TSV file\t\t| '{self._output_file.path}'\nExiting..."
                )
                exit(1)

    def check_files(self) -> None:
        self.check_input()
        # self.check_outputs(filter_label="PASS")
        self.check_outputs()

    def run(self) -> None:
        self.get_vcf_headers()
        if self._output_file.file_exists:
            self.load_raw_data()
            return
        else:
            # Make entering a list of column names automatic if not provided by user
            if self.tsv_column_names:
                self._custom_header_list = self.tsv_column_names
            else:
                self.get_tsv_headers()
            
            # self.filter_vcf()
            self.convert_to_tsv()
            self.test_output_headers()
            self.save_output()
            self.load_raw_data()
