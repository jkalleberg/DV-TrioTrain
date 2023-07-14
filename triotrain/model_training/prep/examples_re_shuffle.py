#!/usr/bin/python3
"""
description: contains all of the functions specific to the re_shuffle_examples phase of TrioTrain.

usage:
    from examples_re_shuffle import ReShuffleExamples
"""
from dataclasses import dataclass, field
from sys import exit
from typing import List, Union

from helpers.files import WriteFiles
from helpers.iteration import Iteration
from helpers.jobs import is_job_index, is_jobid
from helpers.outputs import check_expected_outputs, check_if_output_exists
from helpers.utils import (
    check_if_all_same,
    create_deps,
    find_NaN,
    find_not_NaN,
    generate_job_id,
)
from model_training.slurm.sbatch import SBATCH, SubmitSBATCH


@dataclass
class ReShuffleExamples:
    """
    Define what data to store for the re_shuffle phase of the TrioTrain Pipeline
    """

    # required values
    itr: Iteration
    slurm_resources: dict
    model_label: str

    # optional values
    beam_shuffling_jobs: Union[List[Union[str, None]], None] = field(
        default_factory=list
    )
    benchmarking_file: Union[WriteFiles, None] = None
    genome: Union[str, None] = None
    overwrite: bool = False
    re_shuffle_job_num: List = field(default_factory=list)
    track_resources: bool = False
    train_mode: bool = True

    # internal, imutable values
    _merged_config_exists: bool = field(default=False, init=False, repr=False)
    _num_to_ignore: int = field(default=0, init=False, repr=False)
    _outputs_exist: bool = field(default=False, init=False, repr=False)
    _phase: str = field(default="re_shuffle", init=False, repr=False)
    _skipped_counter: int = field(default=0, init=False, repr=False)
    _skip_phase: bool = field(default=False, init=False, repr=False)
    _train_dependency: Union[str, None] = field(default=None, init=False, repr=False)
    _variable_found: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.track_resources:
            assert (
                self.benchmarking_file is not None
            ), "unable to proceed, missing a WriteFiles object to save SLURM job IDs"

    def set_genome(self) -> None:
        """
        Define the current genome
        """
        if self.train_mode:
            self.genome = self.itr.train_genome
            self.index = 0
            self._total_regions = self.itr.train_num_regions
            self.trio_dependency = self.itr.current_genome_dependencies[0]
        else:
            self.genome = self.itr.eval_genome
            self.index = 1
            self._total_regions = self.itr.eval_num_regions
            self.trio_dependency = self.itr.current_genome_dependencies[1]

        self.logger_msg = (
            f"[{self.itr._mode_string}] - [{self._phase}] - [{self.genome}]"
        )

        if self.itr.demo_mode:
            if "chr" in self.itr.demo_chromosome:
                self.pattern = f"{self.genome}.{self.itr.demo_chromosome}"
            else:
                self.pattern = f"{self.genome}.chr{self.itr.demo_chromosome}"
            self.all_merged_tfrecords_pattern = f"{self.pattern}"
        else:
            self.pattern = f"{self.genome}"
            self.region_pattern = ".region\d+"
            self.all_merged_tfrecords_pattern = f"{self.genome}{self.region_pattern}"

        self.total_outputs_expected = 1
        self._re_shuffle_dependencies = create_deps(1)

    def find_restart_jobs(self) -> None:
        """
        Collect any SLURM job ids for running tests to avoid submitting a job while it's already running.
        """
        self._ignoring_beam_shuffle = check_if_all_same(self.beam_shuffling_jobs, None)

        if not self._ignoring_beam_shuffle:
            self._num_to_ignore = len(find_NaN(self.beam_shuffling_jobs))

            if len(find_not_NaN(self.beam_shuffling_jobs)) > 0:
                self._num_to_run = 1
            else:
                self._num_to_run = 0

        elif self.re_shuffle_job_num:
            num_job_ids = len(self.re_shuffle_job_num)

            if num_job_ids == 1:
                jobs_to_run = find_not_NaN(self.re_shuffle_job_num)
                self._num_to_run = len(jobs_to_run)
                self._num_to_ignore = len(find_NaN(self.re_shuffle_job_num))
                self._re_shuffle_dependencies = create_deps(1)

                if jobs_to_run:
                    updated_jobs_list = []

                    for index in jobs_to_run:
                        if index is not None:
                            if is_jobid(self.re_shuffle_job_num[index]):
                                self._num_to_run -= 1
                                self._num_to_ignore += 1
                                self._re_shuffle_dependencies[index] = str(
                                    self.re_shuffle_job_num[index]
                                )
                                if self.itr.debug_mode:
                                    self.itr.logger.debug(
                                        f"{self.logger_msg}: re_shuffling dependencies updated to '{self._re_shuffle_dependencies}'"
                                    )
                            elif is_job_index(self.make_examples_job_nums[index]):
                                updated_jobs_list.append(index)

                    if updated_jobs_list:
                        self.jobs_to_run = updated_jobs_list

                if self._num_to_ignore == 1:
                    self.itr.logger.info(
                        f"{self.logger_msg}: there are no jobs to re-submit for '{self._phase}:{self.genome}'... SKIPPING AHEAD"
                    )
                    self._skip_phase = True
            else:
                if self.itr.debug_mode:
                    self.itr.logger.debug(
                        f"{self.logger_msg}: --running-jobids triggered reprocessing {num_job_ids} job"
                    )
                self.itr.logger.error(
                    f"{self.logger_msg}: incorrect format for 're_shuffle' SLURM job ID"
                )
                self.itr.logger.error(
                    f"{self.logger_msg}: expected a list of 1 SLURM jobs (or 'None' as a place holder)"
                )
        else:
            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"{self.logger_msg}: running job ids were NOT provided"
                )

    def benchmark(self) -> None:
        """
        Save the SLURM job IDs to a file for future resource usage metrics
        """
        headers = ["AnalysisName", "RunName", "Parent", "Phase", "JobList"]

        if self.track_resources:
            if self._train_dependency is None:
                self.itr.logger.warning(
                    f": unable to perform benchmarking, as a SLURM job id is missing",
                )
            else:
                data = {
                    "AnalysisName": self.model_label,
                    "RunName": self.itr.run_name,
                    "Phase": self._phase,
                    "Parent": self.itr.train_genome,
                    "JobList": self._train_dependency,
                }

                if not self.itr.dryrun_mode and self.benchmarking_file is not None:
                    if self.itr.debug_mode:
                        self.itr.logger.debug(
                            f"{self.logger_msg}: writing SLURM job numbers to [{self.benchmarking_file.file}]",
                        )
                    self.benchmarking_file.add_rows(
                        headers,
                        data_dict=data,
                    )
                else:
                    self.itr.logger.info(
                        f"[DRY_RUN] - {self.logger_msg}: benchmarking is active"
                    )

    def make_job(self) -> Union[SBATCH, None]:
        """
        Define the contents of the SLURM job for the re_shuffle phase for TrioTrain Pipeline
        """
        if self.itr.env is None:
            return

        # initialize a SBATCH Object
        self.job_name = f"re-shuffle-{self.genome}{self.itr.current_trio_num}"
        self.handler_label = f"{self._phase}: {self.genome}"

        slurm_job = SBATCH(
            self.itr,
            self.job_name,
            self.model_label,
            self.handler_label,
            self.logger_msg,
        )

        if slurm_job.check_sbatch_file():
            if (
                self.re_shuffle_job_num[0] is not None
                or not self._ignoring_beam_shuffle
            ) and self.overwrite:
                self.itr.logger.info(
                    f"{self.logger_msg}: --overwrite=True, re-writing the existing SLURM job now..."
                )
            else:
                self.itr.logger.info(
                    f"{self.logger_msg}: --overwrite=False; SLURM job file already exists... SKIPPING AHEAD"
                )
                return
        else:
            if self.itr.debug_mode:
                self.itr.logger.debug(f"{self.logger_msg}: creating job file now... ")

        if self.itr.demo_mode:
            command_list = slurm_job._start_conda + [
                "conda activate ./miniconda_envs/beam_v2.30",
                f"python3 triotrain/model_training/slurm/re_shuffle.py -e {self.itr.env.env_file} -g {self.genome} --demo-mode --demo-chr {self.itr.demo_chromosome} --start-itr {self.itr.current_genome_num}",
            ]
        else:
            command_list = slurm_job._start_conda + [
                "conda activate ./miniconda_envs/beam_v2.30",
                f"python3 triotrain/model_training/slurm/re_shuffle.py -e {self.itr.env.env_file} -g {self.genome} --start-itr {self.itr.current_genome_num}",
            ]

        slurm_job.create_slurm_job(
            self.handler_label,
            command_list=command_list,
            **self.slurm_resources[self._phase],
            overwrite=self.overwrite,
        )

        return slurm_job

    def find_merged_outputs(self, msg: str) -> None:
        """
        Determine if merging is necessary
        """
        self.merged_config = WriteFiles(
            str(self.itr.examples_dir),
            f"{self.pattern}.labeled.shuffled.merged.dataset_config.pbtxt",
            self.itr.logger,
            logger_msg=msg,
        )
        self.merged_config.check_missing()

        self._merged_config_exists = self.merged_config.file_exists

        if self.merged_config.file_exists:
            self.itr.logger.info(
                f"{msg}: found the 1 labeled.shuffled.merged.dataset_config.pbtxt file... SKIPPING AHEAD"
            )
        else:
            self.itr.logger.info(
                f"{msg}: missing the labeled.shuffled.merged.dataset_config.pbtxt file | '{self.merged_config.file_path}'"
            )

    def find_variable(self, msg: str) -> None:
        """
        Determine if examples need to be counted
        """
        if self.itr.env is None:
            return
        self.new_variable_name = f"{self.genome}_Examples"
        self._variable_found = self.itr.env.test_contents(self.new_variable_name)

        if self._variable_found:
            self.itr.logger.info(
                f"{msg}: found the '{self.new_variable_name}' variable... SKIPPING AHEAD"
            )
        else:
            self.itr.logger.info(
                f"{msg}: missing the '{self.new_variable_name}' variable"
            )

    def find_merged_tfrecords(self, msg: str, expected_outputs: int = 1) -> None:
        """
        Check if tfrecord files exist already before attempting to create them
        """
        merged_shards_regex = (
            rf"{self.all_merged_tfrecords_pattern}.labeled.shuffled.merged.tfrecord.gz"
        )

        if self.itr.debug_mode:
            self.itr.logger.debug(f"merged pattern = {merged_shards_regex}")

        # Confirm genome's MERGED tfrecords do not already exist
        (
            self._merged_tfrecords_exist,
            num_merged_tfrecords,
            files_list,
        ) = check_if_output_exists(
            merged_shards_regex,
            "the labeled.shuffled.merged.tfrecords",
            self.itr.examples_dir,
            msg,
            logger=self.itr.logger,
            debug_mode=self.itr.debug_mode,
            dryrun_mode=self.itr.dryrun_mode,
        )

        if self._merged_config_exists:
            missing_files = check_expected_outputs(
                num_merged_tfrecords,
                expected_outputs,
                msg,
                "labeled.shuffled.merged.tfrecords",
                self.itr.logger,
            )

            if missing_files is True:
                self._merged_tfrecords_exist = False
            else:
                self._merged_tfrecords_exist = True

    def submit_job(self, resubmission: bool = False) -> Union[int, str, None]:
        """
        Submit SLURM job to queue
        """
        if not self.overwrite and self._outputs_exist:
            self._skipped_counter += 1
            if resubmission:
                self.itr.logger.info(
                    f"{self.logger_msg}: --overwrite=False; skipping job because found all labeled.shuffled.merged outputs"
                )
            return

        slurm_job = self.make_job()

        if slurm_job is not None:
            if self.itr.dryrun_mode:
                slurm_job.display_job()
            else:
                slurm_job.write_job()

        if not self.overwrite:
            if resubmission:
                if self._ignoring_beam_shuffle:
                    self.itr.logger.info(
                        f"{self.logger_msg}: --overwrite=False; re-submitting job because missing labeled.shuffled.merged outputs"
                    )
            else:
                self.itr.logger.info(
                    f"{self.logger_msg}: submitting job to create the labeled.shuffled.merged outputs"
                )
        else:
            if self._outputs_exist:
                self.itr.logger.info(
                    f"{self.logger_msg}: --overwrite=True; re-submitting job because replacing existing labeled.shuffled.merged outputs"
                )
            else:
                self.itr.logger.info(
                    f"{self.logger_msg}: submitting job to create labeled.shuffled.merged outputs"
                )

        slurm_job = SubmitSBATCH(
            self.itr.job_dir,
            f"{self.job_name}.sh",
            self.handler_label,
            self.itr.logger,
            f"{self.logger_msg}",
        )

        if self.beam_shuffling_jobs is not None:
            slurm_job.build_command(prior_job_number=self.beam_shuffling_jobs)
        else:
            slurm_job.build_command(prior_job_number=None)

        slurm_job.display_command(display_mode=self.itr.dryrun_mode, debug_mode=self.itr.debug_mode)

        if self.itr.dryrun_mode:
            self._train_dependency = generate_job_id()
            self.itr.current_genome_dependencies[self.index] = self._train_dependency
            if self.index > 0:
                self.itr.next_genome_dependencies[self.index] = generate_job_id()
        else:
            slurm_job.get_status(debug_mode=self.itr.debug_mode)

            if slurm_job.status == 0:
                self._train_dependency = slurm_job.job_number
                self.itr.current_genome_dependencies[
                    self.index
                ] = slurm_job.job_number
                if self.index > 0:
                    self.itr.next_genome_dependencies[
                        self.index
                    ] = slurm_job.job_number
            else:
                self.itr.logger.error(f"{self.logger_msg}: unable to submit SLURM job")

    def check_submission(self) -> None:
        """
        check if the SLURM job file was submitted to the SLURM queue successfully
        """
        if self._train_dependency is not None:
            if self.itr.dryrun_mode:
                print(
                    f"============================================================\n[DRY_RUN] - {self.logger_msg} Job Number: ['{self._train_dependency}']\n============================================================"
                )
            else:
                print(
                    f"============================================================\n{self.logger_msg} Job Number: ['{self._train_dependency}']\n============================================================"
                )

        elif self._skipped_counter == 1:
            self._train_dependency = None
        else:
            self.itr.logger.error(
                f"{self.logger_msg}: expected SLURM jobs to be submitted, but they were not",
            )
            self.itr.logger.warning(
                f"{self.logger_msg}: fatal error encountered, unable to proceed further with pipeline.\nExiting... ",
            )
            exit(1)

        if self.track_resources and self.benchmarking_file is not None:
            self.benchmark()

    def find_outputs(
        self, phase: Union[str, None] = None, find_all: bool = False
    ) -> None:
        """
        Determine if re-shuffling outputs already exist
        """
        if phase is None:
            merged_logger_msg = self.logger_msg
        else:
            merged_logger_msg = f"[{self.itr._mode_string}] - [{phase}]"

            if self.genome is not None:
                merged_logger_msg = f"{merged_logger_msg} - [{self.genome}]"

        if phase == "find_outputs":
            self.find_variable(msg=merged_logger_msg)

        self.find_merged_outputs(msg=merged_logger_msg)

        if self.itr.demo_mode:
            self.find_merged_tfrecords(msg=merged_logger_msg)
            if self._merged_tfrecords_exist and self._merged_config_exists:
                self._outputs_exist = True
        else:
            if self._total_regions is not None:
                if find_all and self._total_regions is not None:
                    self._expepected_outputs = self._total_regions
                else:
                    self._expepected_outputs = 1

                self.find_merged_tfrecords(
                    msg=merged_logger_msg, expected_outputs=self._expepected_outputs
                )

                if self.overwrite and (
                    self.re_shuffle_job_num or not self._ignoring_beam_shuffle
                ):
                    self._outputs_exist = False
                else:
                    if self._merged_tfrecords_exist and self._merged_config_exists:
                        self._outputs_exist = True

    def run(self) -> Union[Iteration, None]:
        """
        Combine all the steps required to submit a job to SLURM queue into one step
        """
        self.set_genome()
        self.find_restart_jobs()

        # SKIP everything if a Trio Dependency was provided
        if self.trio_dependency is not None:
            self.itr.logger.info(
                f"{self.logger_msg}: current genome dependency provided [SLURM job # {self.trio_dependency}]... SKIPPING AHEAD",
            )
            return

        # Determine if we are re-running the training
        if self.re_shuffle_job_num or not self._ignoring_beam_shuffle:
            if self._num_to_run == 0:
                self._skipped_counter = self._num_to_ignore
                if self._train_dependency and self._train_dependency[0] is not None:
                    self.itr.logger.info(
                        f"{self.logger_msg}: train dependency updated to '{self._train_dependency}'"
                    )
                else:
                    self._train_dependency = None
            else:
                if not self._ignoring_beam_shuffle:
                    self.itr.logger.info(
                        f"{self.logger_msg}: beam_shuffle jobs were submitted...",
                    )
                
                skip_re_runs = check_if_all_same(self.re_shuffle_job_num, None)

                if skip_re_runs:
                    msg = "sub"
                else:
                    msg = "re-sub"

                if self._num_to_run == 1:
                    self.itr.logger.info(
                        f"{self.logger_msg}: attempting to {msg}mit {self._num_to_run}-of-1 SLURM jobs to the queue",
                    )
                else:
                    self.itr.logger.error(
                        f"{self.logger_msg}: max number of SLURM jobs for {msg}mission is 1 but {self._num_to_run} were provided.\nExiting... ",
                    )
                    exit(1)
                
                self.submit_job(resubmission=True)

        # or running it for the first time
        else:
            if self._skip_phase:
                return
            self.find_outputs(find_all=True)
            self.submit_job()

        self.check_submission()

        if self._train_dependency is None:
            return None
        else:
            return self.itr
