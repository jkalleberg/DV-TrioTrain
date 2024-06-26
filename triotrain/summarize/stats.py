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
from json import load
from logging import Logger

from os import path as p
from pathlib import Path
from sys import path
from typing import List, Union

from regex import compile

abs_path = Path(__file__).resolve()
module_path = str(abs_path.parent.parent)
path.append(module_path)
from helpers.files import TestFile, WriteFiles
from helpers.iteration import Iteration
from helpers.utils import check_if_all_same, generate_job_id
from model_training.slurm.sbatch import SBATCH, SubmitSBATCH
from pantry import preserve
from _args import collect_args, check_args
from results import SummarizeResults

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
    _command_list: List[str] = field(default_factory=list, init=False, repr=False)
    
    _get_sample_stats: bool = field(default=True, init=False, repr=False)
    _job_nums: List = field(default_factory=list, init=False, repr=False)
    _num_processed: int = field(default=0, init=False, repr=False)
    _num_skipped: int = field(default=0, init=False, repr=False)
    _num_submitted: int = field(default=0, init=False, repr=False)
    _trio_counter: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        if "post_process" not in self.args:
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

    def process_sample(self) -> None:
        """
        Generate the pickled data file, and the SLURM job for processing each sample.
        """
        self._pickled_data = SummarizeResults(
            sample_metadata=self._data, output_file=self._csv_output
        )

        # self._pickled_data.check_file_path()
        # self._pickled_data.find_trios()
        
        self._pickled_data.get_sample_info()

        self._clean_file_path = self._pickled_data._input_file._test_file.clean_filename

        _pickle_file = TestFile(
            Path(f"{self._clean_file_path}.pkl"),
            logger=self.logger,
        )
        # if self._get_sample_stats:
        #     slurm_cmd = [
        #         "python3",
        #         "./triotrain/summarize/smpl_stats.py",
        #         "--pickle-file",
        #         _pickle_file.file,
        #     ]
        #     cmd_string = " ".join(slurm_cmd)
        #     self._command_list = [cmd_string]
        # else:
        #     print("PUT MIE COMMAND(S) HERE!")
        #     breakpoint()

        if self.args.dry_run:
            self.logger.info(
                f"[DRY_RUN] - {self._logger_msg}: pretending to create pickle file | '{_pickle_file.file}'"
            )
        else:
            preserve(
                item=self._pickled_data,
                pickled_path=_pickle_file,
                overwrite=self.args.overwrite,
            )

        # self._slurm_job = self.make_job()
        # self.submit_job(index=self._index)
        # self._command_list.clear()

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
            _contains_trio_vcf = self.find_trio_vcf()
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

        slurm_cmd = (
            slurm_job._start_conda
            + ["conda activate miniconda_envs/beam_v2.30"]
            + self._command_list
        )

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
