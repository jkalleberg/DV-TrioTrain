#!/bin/python3
"""
description: 

example:
    python3 triotrain/summarize/summary.py                                     \\
        --metadata ../TRIO_TRAINING_OUTPUTS/final_results/inputs/240329_summary_metrics.csv    \\
        --output ../TRIO_TRAINING_OUTPUTS/final_results/240402_sample_stats.csv        \\
        -r triotrain/model_training/tutorial/resources_used.json  \\
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
from typing import Dict, List, Union
from json import load

from regex import compile

abs_path = Path(__file__).resolve()
module_path = str(abs_path.parent.parent)
path.append(module_path)
from helpers.files import TestFile, WriteFiles
from helpers.iteration import Iteration
from helpers.utils import check_if_all_same, generate_job_id
from model_training.slurm.sbatch import SBATCH, SubmitSBATCH
from pantry import preserve


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
        "--overwrite",
        dest="overwrite",
        help="if True, enable re-writing files",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "-r",
        "--resources",
        dest="resource_config",
        help="[REQUIRED]\ninput file (.json)\ndefines HPC cluster resources for SLURM",
        type=str,
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


def check_args(args: argparse.Namespace, logger: Logger) -> None:
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
        logger.info("[DRY_RUN]: output will display to screen and not write to a file")

    assert (
        args.metadata
    ), "missing --metadata; Please provide a file with descriptive data for test samples."

    assert (
        args.resource_config
    ), "Missing --resources; Please designate a path to pipeline compute resources in JSON format"

    # if not args.dry_run:
    assert args.outpath, "missing --output; Please provide a file name to save results."


@dataclass
class SummarizeResults:
    """
    Data to pickle for processing the summary stats from a VCF/BCF output.
    """

    sample_metadata: Union[List[Dict[str, str]], Dict[str, str]]
    output_file: WriteFiles

    # imutable, internal parameters
    _contains_trio: bool = field(default=False, init=False, repr=False)
    _digits_only: compile = field(default=compile(r"\d+"), init=False, repr=False)
    _input_file: WriteFiles = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if isinstance(self.sample_metadata, dict):
            self.total_samples = 1
            self._file_path = Path(self.sample_metadata["file_path"])
            self._sample_label = self.sample_metadata["label"]
        else:
            self.total_samples = len(self.sample_metadata)
            self._file_path = Path(self.sample_metadata[0]["file_path"])
            self._sample_label = self.sample_metadata[0]["label"]

        if self.total_samples == 3:
            match = self._digits_only.search(self._sample_label)
            if match:
                self._trio_num = int(match.group())
            self._contains_trio = True
        else:
            self._contains_trio = False

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

    def get_sample_info(self) -> None:
        input_name = Path(self._input_file._test_file.clean_filename).name

        if self._contains_trio:
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
            self._job_name = f"stats.{self._ID}.{self._caller}"
        else:
            self._job_name = f"stats.{input_name}.{self._caller}"


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

    # imutable, internal parameters
    _digits_only: compile = field(default=compile(r"\d+"), init=False, repr=False)
    _get_sample_stats: bool = field(default=True, init=False, repr=False)
    _job_nums: List = field(default_factory=list, repr=False, init=False)
    _num_processed: int = field(default=0, init=False, repr=False)
    _num_skipped: int = field(default=0, init=False, repr=False)
    _num_submitted: int = field(default=0, init=False, repr=False)
    _trio_counter: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        with open(str(self.args.resource_config), mode="r") as file:
            self._slurm_resources = load(file)

    def load_variables(self) -> None:
        """
        Define python variables.
        """
        self._phase = "summary"
        self._logger_msg = f"[{self._phase}]"
        self._metadata_input = Path(self.args.metadata)
        output = Path(self.args.outpath)
        self._csv_output = WriteFiles(
            path_to_file=str(output.parent),
            file=output.name,
            logger=self.logger,
            logger_msg=self._logger_msg,
            dryrun_mode=self.args.dry_run,
            debug_mode=self.args.debug,
        )
        self._csv_output.check_missing()
        # initalize an empty Iteration() to store paths
        self._itr = Iteration(logger=self.logger, args=self.args)

    def load_metadata(self) -> None:
        """
        Read in and save the metadata file as a dictionary.
        """
        # Confirm data input is an existing file
        metadata = TestFile(str(self._metadata_input), self.logger)
        metadata.check_existing(logger_msg=self._logger_msg, debug_mode=self.args.debug)
        if metadata.file_exists:
            # read in the csv file
            with open(
                str(self._metadata_input), mode="r", encoding="utf-8-sig"
            ) as data:
                dict_reader = DictReader(data)

                # removes whitespace within the CSV input
                self._data_list = [
                    dict((k.strip(), v.strip()) for k, v in row.items() if v)
                    for row in dict_reader
                ]
                self._total_samples = len(self._data_list)
        else:
            self.logger.error(
                f"{self._logger_msg}: unable to load metadata file | '{self._metadata_input}'"
            )
            raise ValueError("Invalid Input File")

    def find_trios(self) -> bool:
        """
        Determine if a trio VCF was provided.

        If so, save 3 rows of metadata, rather than one.
        """
        _input_name = Path(self._data["file_path"]).name
        self._sample_label = self._data["label"]

        pedigree = {
            key: value
            for key, value in self._data.items()
            if key in ["sampleID", "paternalID", "maternalID", "sex"]
        }
        # Samples with any blank columns in pedigree will be ignored
        _missing_pedigree = not any(pedigree.values())

        if "trio" in _input_name.lower():
            match = self._digits_only.search(self._sample_label)
            if match:
                self._trio_num = int(match.group())
            else:
                self._trio_counter += 1
                self._trio_num = self._trio_counter

            _trio_vcf_exists = True
        else:
            # print("TRIO VCF & PEDIGREE WILL NEED TO BE CREATED FOR MIE STATS!")
            _trio_vcf_exists = False
            self._trio_num = 0

        if _missing_pedigree or _trio_vcf_exists is False:
            return _trio_vcf_exists
        else:
            self._data = self._data_list[self._index : (self._index + 3)]
            return _trio_vcf_exists

    def process_sample(self) -> None:
        """
        Generate the pickled data file, and the SLURM job for processing each sample.
        """
        self._pickled_data = SummarizeResults(
            sample_metadata=self._data, output_file=self._csv_output
        )

        self._pickled_data.check_file_path()
        self._pickled_data.get_sample_info()
        self._clean_file_path = self._pickled_data._input_file._test_file.clean_filename

        _pickle_file = TestFile(
            Path(f"{self._clean_file_path}.pkl"),
            logger=self.logger,
        )
        if self._get_sample_stats:
            slurm_cmd = [
                "python3",
                "./triotrain/summarize/smpl_stats.py",
                "--pickle-file",
                _pickle_file.file,
            ]
            cmd_string = " ".join(slurm_cmd)
            self._command_list = [cmd_string]
        else:
            print("PUT MIE COMMAND(S) HERE!")
            breakpoint()

        if self.args.dry_run:
            self.logger.info(
                f"[DRY_RUN] - {self._logger_msg}: pretending to create pickle file | '{_pickle_file.file}'"
            )
        else:
            preserve(item=self._pickled_data, pickled_path=_pickle_file, overwrite=self.args.overwrite)

        self._slurm_job = self.make_job()
        self.submit_job(index=self._index)
        self._command_list.clear()

    def process_multiple_samples(self) -> None:
        """
        Iterate through multiple VCF files
        """
        if self.args.debug:
            itr = self._data_list[0:3]
        else:
            itr = self._data_list

        _counter = 0
        for i, item in enumerate(itr):
            self._index = i
            self._data = item
            _contains_trio_vcf = self.find_trios()
            _counter += int(_contains_trio_vcf)

            if _contains_trio_vcf:
                if _counter == 1:
                    self.logger.info(
                        f"{self._logger_msg}: input file contains a family | Trio{self._trio_num}"
                    )
                    self.process_sample()
                else:
                    if self.args.dry_run:
                        self.logger.info(
                            f"[DRY_RUN] - {self._logger_msg}: multi-sample VCF detected... SKIPPING AHEAD"
                        )
                    self._num_skipped += 1
                    if _counter == 3:
                        _counter = 0
                    continue
            else:
                self.process_sample()

    def make_job(self) -> Union[SBATCH, None]:
        """
        Define the contents of the SLURM job for the rtg-mendelian phase for TrioTrain Pipeline.
        """
        self._itr.job_dir = Path(self._clean_file_path).parent
        self._itr.log_dir = Path(self._clean_file_path).parent

        # initialize a SBATCH Object
        slurm_job = SBATCH(
            itr=self._itr,
            job_name=self._pickled_data._job_name,
            error_file_label=self._pickled_data._caller,
            handler_status_label=None,
            logger_msg=self._logger_msg,
        )

        if slurm_job.check_sbatch_file():
            if self.args.overwrite:
                self._itr.logger.info(
                    f"{self._logger_msg}: --overwrite=True, re-writing the existing SLURM job now..."
                )
            else:
                self._itr.logger.info(
                    f"{self._logger_msg}: SLURM job file already exists... SKIPPING AHEAD"
                )
                self._num_skipped += 1
                return
        else:
            if self._itr.debug_mode:
                self._itr.logger.debug(f"{self._logger_msg}: creating file job now... ")

        slurm_cmd = slurm_job._start_conda + [
                "conda activate miniconda_envs/beam_v2.30"] + self._command_list

        slurm_job.create_slurm_job(
            None,
            command_list=slurm_cmd,
            overwrite=self.args.overwrite,
            **self._slurm_resources[self._phase],
        )
        return slurm_job

    def submit_job(self, index: int = 0) -> None:
        """
        Submit SLURM jobs to queue.
        """
        # only submit a job if a new SLURM job file was created
        if self._slurm_job is None:
            return

        if self._itr.dryrun_mode:
            self._slurm_job.display_job()
        else:
            self._slurm_job.write_job()

        # submit the training eval job to queue
        submit_slurm_job = SubmitSBATCH(
            sbatch_dir=self._itr.job_dir,
            job_file=f"{self._pickled_data._job_name}.sh",
            label="None",
            logger=self.logger,
            logger_msg=self._logger_msg,
        )

        submit_slurm_job.build_command()
        submit_slurm_job.display_command(
            current_job=(index + 1),
            total_jobs=self._total_samples,
            display_mode=self._itr.dryrun_mode,
            debug_mode=self._itr.debug_mode,
        )

        if self._itr.dryrun_mode:
            self._job_nums.append(generate_job_id())
            self._num_processed += 1
        else:
            submit_slurm_job.get_status(
                debug_mode=self._itr.debug_mode,
                current_job=(index + 1),
                total_jobs=self._total_samples,
            )

            if submit_slurm_job.status == 0:
                self._num_submitted += 1
                self._job_nums.append(submit_slurm_job.job_number)
            else:
                self.logger.error(
                    f"{self._logger_msg}: unable to submit SLURM job",
                )
                self._job_nums.append(None)

    def check_submission(self) -> None:
        """
        Check if SLURM job file(s) were submitted to the SLURM queue successfully.
        """
        # look at job number list to see if all items are 'None'
        _results = check_if_all_same(self._job_nums, None)
        if _results is False:
            if self.args.dry_run:
                print(
                    f"============ [DRY_RUN] - {self._logger_msg} Job Numbers - {self._job_nums} ============"
                )
            else:
                print(
                    f"============ {self._logger_msg} Job Numbers - {self._job_nums} ============"
                )
        elif self._num_skipped == self._total_lines:
            self.logger.info(
                f"{self._logger_msg}: no SLURM jobs were submitted... SKIPPING AHEAD"
                )
        else:
            self.logger.warning(
                f"{self._logger_msg}: expected SLURM jobs to be submitted, but they were not",
            )
            self.logger.warning(
                f"{self._logger_msg}: fatal error encountered, unable to proceed further with pipeline.\nExiting... ",
            )
            exit(1)

    def run(self) -> None:
        """
        Combine all the steps into a single command.
        """
        self.load_variables()
        self.load_metadata()

        # Process all samples
        self.process_multiple_samples()
        self.check_submission()
        if self._num_processed != 0:
            self.logger.info(
                f"{self._logger_msg}: processed {self._num_processed}-of-{self._total_samples} VCFs"
            )

        if self._num_skipped != 0:
            self.logger.info(
                f"{self._logger_msg}: skipped {self._num_skipped}-of-{self._total_samples} VCFs"
            )


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
