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

abs_path = Path(__file__).resolve()
module_path = str(abs_path.parent.parent)
path.append(module_path)
# from _args import check_args, collect_args
from helpers.files import TestFile, WriteFiles
from helpers.iteration import Iteration
from helpers.utils import check_if_all_same, generate_job_id
from model_training.slurm.sbatch import SBATCH, SubmitSBATCH
from pantry import preserve
from results import SummarizeResults


@dataclass
class Summary:
    """
    Define what data to keep when processing a VCF generated by DeepVariant.
    """

    # required parameters
    args: argparse.Namespace
    logger: Logger

    # imutable, internal parameters
    _command_list: List[str] = field(default_factory=list, init=False, repr=False)
    _job_nums: List = field(default_factory=list, init=False, repr=False)
    _num_processed: int = field(default=0, init=False, repr=False)
    _num_skipped: int = field(default=0, init=False, repr=False)
    _num_submitted: int = field(default=0, init=False, repr=False)
    _phase: str = field(default="summary", init=False, repr=False)
    _trio_counter: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        if "pickle_file" not in self.args:
            with open(str(self.args.resource_config), mode="r") as file:
                self._slurm_resources = load(file)

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

    def load_variables(self) -> None:
        """
        Define python variables.
        """
        if self.args.dry_run:
            self._logger_msg = f"[DRY_RUN] - [{self._phase}]"
        else:
            self._logger_msg = f"[{self._phase}]"

        if "metadata" in self.args:
            self._metadata_input = Path(self.args.metadata)
            self.load_metadata()

        output = Path(self.args.outpath).resolve()

        if "." in output.name:
            _path = str(output.parent)
            _file_name = f"{output.name}.mie.csv"
        else:
            _path = str(output)
            _file_name = f"mie.csv"

        if not self.args.dry_run:
            output.mkdir(parents=True, exist_ok=True)

        self._csv_output = WriteFiles(
            path_to_file=_path,
            file=_file_name,
            logger=self.logger,
            logger_msg=self._logger_msg,
            dryrun_mode=self.args.dry_run,
            debug_mode=self.args.debug,
        )
        self._csv_output.check_missing()

        # initalize an empty Iteration() to store paths
        self._itr = Iteration(logger=self.logger, args=self.args)

    def process_sample(self, contains_trio: bool = False, pkl_suffix: Union[str, None] = None, store_data: bool = False) -> None:
        """
        Generate the pickled data file, and the SLURM job for processing each sample.
        """
        self._pickled_data = SummarizeResults(
            sample_metadata=self._data,
            output_file=self._csv_output,
            args=self.args,
        )
        self._pickled_data._index = self._index
        self._pickled_data.get_sample_info()
        self._clean_file_path = self._pickled_data._input_file._test_file.clean_filename

        if contains_trio and not self._pickled_data._contains_valid_trio:
            if self.args.debug:
                self.logger.debug(
                    f"{self._logger_msg}: not a valid trio... SKIPPING AHEAD"
                )
            return
        else:
            if pkl_suffix is None:
                _pickle_file = TestFile(
                    Path(f"{self._clean_file_path}.pkl"),
                    logger=self.logger,
                )
            else:
                _pickle_file = TestFile(
                    Path(f"{self._clean_file_path}.{pkl_suffix}.pkl"),
                    logger=self.logger,
                )
            slurm_cmd = [
                "python3",
                "./triotrain/summarize/post_process.py",
                "--pickle-file",
                _pickle_file.file,
            ]
            cmd_string = " ".join(slurm_cmd)

        if self._command_list:
            self._command_list.append(cmd_string)
        else:
            self._command_list = [cmd_string]

        if self.args.dry_run:
            self.logger.info(
                f"{self._logger_msg}: pretending to create pickle file | '{_pickle_file.file}'"
            )
        else:
            if store_data:
                preserve(
                    item=self._pickled_data,
                    pickled_path=_pickle_file,
                    overwrite=self.args.overwrite,
                )

    def make_job(self, job_name: str) -> Union[SBATCH, None]:
        """
        Define the contents of the SLURM job for the rtg-mendelian phase for TrioTrain Pipeline.
        """
        self._itr.job_dir = Path(self._clean_file_path).parent
        self._itr.log_dir = Path(self._clean_file_path).parent
        self._job_name = job_name

        # initialize a SBATCH Object
        slurm_job = SBATCH(
            itr=self._itr,
            job_name=self._job_name,
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
                    f"{self._logger_msg}: --overwrite=False, SLURM job file already exists."
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
            **self._slurm_resources["summary"],
        )
        return slurm_job

    def submit_job(self, index: int = 0, total: int = 1) -> None:
        """
        Submit SLURM jobs to queue.
        """
        self._total_samples = total
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
            job_file=f"{self._job_name}.sh",
            label="None",
            logger=self.logger,
            logger_msg=self._logger_msg,
        )

        submit_slurm_job.build_command()
        submit_slurm_job.display_command(
            current_job=(index + 1),
            total_jobs=total,
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
                total_jobs=total,
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
        Check if the SLURM job file was submitted to the SLURM queue successfully
        """
        if self._num_processed != 0 and self._num_skipped != 0:
            completed = self._num_processed + self._num_skipped
        elif self._num_processed != 0:
            completed = self._num_processed
        else:
            completed = self._num_skipped

        # look at job number list to see if all items are 'None'
        _results = check_if_all_same(self._job_nums, None)

        if _results is False:
            print(
                f"============ {self._logger_msg} Job Numbers - {self._job_nums} ============"
            )
        elif completed == self._total_samples:
            self.logger.info(
                f"{self._logger_msg}: no SLURM jobs were submitted... SKIPPING AHEAD"
            )
        elif self._itr.debug_mode and completed == self._total_samples:
            self.logger.debug(
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

    # def run(self) -> None:
    #     """
    #     Combine all the steps into a single command.
    #     """
    #     self.load_variables()

    #     # Process all samples
    #     self.process_multiple_samples()
    #     self.check_submission()
    #     if self._num_processed != 0:
    #         self.logger.info(
    #             f"{self._logger_msg}: processed {self._num_processed}-of-{self._total_samples} VCFs"
    #         )

    #     if self._num_skipped != 0:
    #         self.logger.info(
    #             f"{self._logger_msg}: skipped {self._num_skipped}-of-{self._total_samples} VCFs"
    #         )


# def __init__() -> None:
#     from helpers.utils import get_logger
#     from helpers.wrapper import Wrapper, timestamp

#     # Collect command line arguments
#     args = collect_args()

#     # Collect start time
#     Wrapper(__file__, "start").wrap_script(timestamp())

#     # Create error log
#     current_file = p.basename(__file__)
#     module_name = p.splitext(current_file)[0]
#     logger = get_logger(module_name)

#     try:
#         # Check command line args
#         check_args(args, logger)
#         Summary(args, logger).run()
#     except AssertionError as E:
#         logger.error(E)

#     Wrapper(__file__, "end").wrap_script(timestamp())


# # Execute functions created
# if __name__ == "__main__":
#     __init__()
