#!/bin/python3
"""
description: 

example:
    python3 triotrain/summarize/summary.py                                     \\
        --metadata ../TRIO_TRAINING_OUTPUTS/final_results/inputs/240329_summary_metrics.csv    \\
        --output ../TRIO_TRAINING_OUTPUTS/final_results/240329_sample_stats.csv        \\
        # -r resource_configs/221205_resources_used.json  \\
        --dry-run
"""

import argparse
from csv import DictReader
from dataclasses import dataclass, field
from logging import Logger
from os import environ
from os import path as p
from pathlib import Path
from sys import path
from typing import Dict, List

abs_path = Path(__file__).resolve()
module_path = str(abs_path.parent.parent)
path.append(module_path)
from helpers.files import TestFile, WriteFiles
from pantry import prepare, preserve
from smpl_stats import Stats


def collect_args() -> argparse.Namespace:
    """
    Process command line argument to execute script.
    """
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-M",
        "--metadata",
        dest="metadata",
        type=str,
        help="[REQUIRED]\ninput file (.csv)\nprovides the list of VCFs to find or produce summary stats",
        metavar="</path/file>",
    )
    parser.add_argument(
        "-O",
        "--output",
        dest="outpath",
        type=str,
        help="[REQUIRED]\noutput file (.csv)\nwhere to save the resulting summary stats",
        metavar="</path/file>",
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
        help="if True, display +smpl-stats metrics to the screen",
        action="store_true",
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
        args.metadata
    ), "missing --metadata; Please provide a file with descriptive data for test samples."


    # if not args.dry_run:
    assert args.outpath, "missing --output; Please provide a file name to save results."


@dataclass
class SummarizeResults:
    """
    Data to pickle for processing the summary stats from a VCF/BCF output.
    """

    sample_metadata: Dict[str, str]
    output_file: WriteFiles

    # optional values
    contains_trio: bool = False

    # imutable, internal parameters
    _input_file: WriteFiles = field(default=None, init=False, repr=False)

    def check_file_path(self) -> None:
        """
        Confirm that the VCF file in the metadata file exists.
        """
        path = Path(self.sample_metadata["file_path"])
        self._input_file = WriteFiles(
            path_to_file=path.parent,
            file=path.name,
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
        print("INPUT FILE EXISTS:", self._input_file.file_exists)


@dataclass
class Summary:
    """
    Define what data to keep when generating VCF summary stats
    """

    # required parameters
    args: argparse.Namespace
    logger: Logger

    # optional values
    run_iteractively: bool = False
    overwrite: bool = False

    # imutable, internal parameters
    _command_list: List = field(default_factory=list, repr=False, init=False)

    _output_lines: dict = field(default_factory=dict, init=False, repr=False)

    def load_variables(self) -> None:
        """
        Define python variables.
        """
        self._phase = "[summary]"
        self._metadata_input = Path(self.args.metadata)
        output = Path(self.args.outpath)
        self._csv_output = WriteFiles(
            path_to_file=str(output.parent),
            file=output.name,
            logger=self.logger,
            logger_msg=self._phase,
            dryrun_mode=self.args.dry_run,
            debug_mode=self.args.debug,
        )
        self._csv_output.check_missing()

    def load_metadata(self) -> None:
        """
        Read in and save the metadata file as a dictionary.
        """
        # Confirm data input is an existing file
        metadata = TestFile(str(self._metadata_input), self.logger)
        metadata.check_existing(logger_msg=self._phase, debug_mode=self.args.debug)
        if metadata.file_exists:
            # read in the csv file
            with open(
                str(self._metadata_input), mode="r", encoding="utf-8-sig"
            ) as data:
                dict_reader = DictReader(data)
                self._data_list = list(dict_reader)
                self._total_lines = len(self._data_list)
        else:
            self.logger.error(
                f"{self._phase}: unable to load metadata file | '{self._metadata_input}'"
            )
            raise ValueError("Invalid Input File")

        print(f"TOTAL LINES:{self._total_lines}")
        print(f"LINE1: {self._data_list[1]}")
        # print(f"LINE53: {self._data_list[4]}")

    def get_sample_info(self) -> None:
        """ """
        self._sampleID = self._data["sampleID"]
        self._caller = self._data["variant_caller"]
        info = self._data["info"]
        if info:
            if "_" in info:
                self._species, self._description = info.split("_")
            else:
                self._species = info
                self._description = None
        self._logger_msg = (
            f"[{self._phase}] - [{self._caller}] - [{self._data['label']}]"
        )

    # def process_multiple_samples(self) -> None:
    #         """
    #         Iterate through multiple VCF files
    #         """
    #         if self.args.debug:
    #             itr = self._data_list[0:3]
    #         else:
    #             itr = self._data_list

    #         for i, item in enumerate(itr):
    #             self._data = item
    #             self.itr = Iteration(
    #                     current_trio_num="None",
    #                     next_trio_num="None",
    #                     current_genome_num=None,
    #                     total_num_genomes=None,
    #                     train_genome=None,
    #                     eval_genome=None,
    #                     env=None,
    #                     logger=self.logger,
    #                     args=self.args)

    #             self.save_metadata()
    #             self.find_vcf_input()

    #             # Raw genotypes ALL loci
    #             if self._vcf_file.file_exists:
    #                 self.stats(input=str(self._vcf_file.file), create_job=True)
    #             else:
    #                 self.logger.warning(f"{self._logger_msg}: missing the input VCF file | '{self._vcf_file.file}'... SKIPPING AHEAD")

    #             # Exclude based on GQ
    #             if self.args.filter_GQ:
    #                 GQ_scores = [10, 13, 20, 30]
    #                 for g in GQ_scores:
    #                     label = f"{self._clean_filename}.GQ{g}.vcf.gz"

    #                     _gq_vcf = TestFile(label, self.logger)
    #                     _gq_vcf.check_existing(
    #                         logger_msg=self._logger_msg, debug_mode=self.args.debug
    #                     )
    #                     if _gq_vcf.file_exists:
    #                         if self.args.debug:
    #                             self.logger.debug(
    #                             f"{self._logger_msg}: GQ.VCF file '{_gq_vcf.file}' already exists... SKIPPING AHEAD"
    #                             )
    #                         self.stats(label, create_job=False)
    #                         continue
    #                     else:
    #                         self.logger.info(
    #                             f"{self._logger_msg}: missing GQ.VCF file | '{_gq_vcf.file}'")
    #                         self.filter(f"--exclude 'GQ<{g}'", self._vcf_file.file, label)
    #                         self.index_vcf(label)
    #                         self.stats(label, create_job=True)

    #                 self._slurm_job = self.make_job()
    #                 self.submit_job(index=i)
    #                 self._command_list.clear()

    #                 if self._num_processed == 0:
    #                     completed = f"skipped {self._num_skipped}"
    #                 else:
    #                     completed = f"processed {self._num_processed}"

    #                 if (self._num_processed % 5) == 0:
    #                     self.logger.info(
    #                         f"{self._logger_msg}: {completed}-of-{self._total_lines} records"
    #                     )
    #             else:
    #                 # print("HERE!")
    #                 self._slurm_job = self.make_job()
    #                 self.submit_job(index=i)
    #                 self._command_list.clear()

    #                 if self._num_processed == 0:
    #                     completed = f"skipped {self._num_skipped}"
    #                 else:
    #                     completed = f"processed {self._num_processed}"

    #                 if (self._num_processed % 5) == 0:
    #                     self.logger.info(
    #                         f"{self._logger_msg}: {completed}-of-{self._total_lines} records"
    #                     )

    #         if self.args.dry_run:
    #             print("---------------------------------------------")

    def run(self) -> None:
        """
        Combine all the steps into a single command.
        """
        self.load_variables()
        self.load_metadata()
        
        # Process a single sample
        self._data = self._data_list[1]
        self.get_sample_info()

        pickled_data = SummarizeResults(
            sample_metadata=self._data, output_file=self._csv_output
        )

        pickled_data.check_file_path()

        _pickle_file = TestFile(
            Path(f"{pickled_data._input_file._test_file.clean_filename}.pkl"),
            logger=self.logger,
        )
        preserve(item=pickled_data, pickled_path=_pickle_file, overwrite=True)

        ## BELOW WILL GO IN A SEPARATE PYTHON SCRIPT!
        new_data = prepare(pickled_path=_pickle_file)
        run_stats = Stats(pickled_data=new_data, run_iteractively=True)
        run_stats.save_stats()
        breakpoint()
        # self.process_multiple_samples()
        # self.check_submission()
        # if self._num_processed != 0:
        #     completed = self._num_processed
        # else:
        #     completed = self._num_skipped
        # self.logger.info(
        #     f"[{self._phase}]: processed {completed}-of-{self._total_lines} VCFs from '{str(self._metadata_input)}'"
        # )


def __init__() -> None:
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

    try:
        # Check command line args
        check_args(args, logger)
        Summary(args, logger).run()
    except AssertionError as E:
        logger.error(E)

    Wrapper(__file__, "end").wrap_script(timestamp())


# Execute functions created
if __name__ == "__main__":
    __init__()
