#!/usr/bin/python3
"""
description: contains all of the functions specific to the make_examples phase of TrioTrain.

usage:
    from examples_make import MakeExamples
"""
import sys
from dataclasses import dataclass, field
from typing import List, Union

import helpers as h
from examples_beam_shuffle import BeamShuffleExamples
from examples_re_shuffle import ReShuffleExamples
from iteration import Iteration
from sbatch import SBATCH, SubmitSBATCH


@dataclass
class MakeExamples:
    """
    Define what data to store for the make_examples phase of the TrioTrain Pipeline.
    """

    # required values
    itr: Iteration
    slurm_resources: dict
    model_label: str

    # optional values
    benchmarking_file: Union[h.WriteFiles, None] = None
    make_examples_job_nums: List = field(default_factory=list)
    overwrite: bool = False
    total_shards: int = 1
    track_resources: bool = False
    train_mode: bool = True

    # internal, imutable values
    _beam_shuffle_dependencies: List[Union[str, None]] = field(
        default_factory=list, init=False, repr=False
    )
    _num_tfrecords_found: Union[int, None] = field(default=None, init=False, repr=False)
    _num_to_ignore: int = field(default=0, init=False, repr=False)
    _phase: str = field(default="make_examples", init=False, repr=False)
    _print_msg: Union[str, None] = field(default=None, init=False, repr=False)
    _run_jobs: Union[bool, None] = field(default=None, init=False, repr=False)
    _skipped_counter: int = field(default=0, init=False, repr=False)
    _total_regions: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.itr.env is None:
            return
        self.n_parts = self.slurm_resources[self._phase]["ntasks"]
        self.total_shards = self.n_parts - 1
        if "N_Parts" not in self.itr.env.contents:
            self.itr.env.add_to("N_Parts", str(self.n_parts), dryrun_mode=self.itr.dryrun_mode)
        if "TotalShards" not in self.itr.env.contents:
            self.itr.env.add_to("TotalShards", str(self.total_shards), dryrun_mode=self.itr.dryrun_mode)
        if self.track_resources:
            assert (
                self.benchmarking_file is not None
            ), "unable to proceed, missing a h.WriteFiles object to save SLURM job IDs"

    def set_genome(self, current_region: Union[int, None] = None) -> None:
        """
        Assign a genome + region label
        """
        if self.itr.demo_mode:
            self._total_regions = 1
            self.genome = self.itr.train_genome
        elif self.itr.dryrun_mode:
            self._total_regions = 5
            self.genome = self.itr.train_genome

        if self.train_mode and self.itr.train_num_regions is not None:
            self._total_regions = self.itr.train_num_regions
            self.genome = self.itr.train_genome
            self.trio_dependency = self.itr.current_genome_dependencies[0]
        elif self.train_mode is False and self.itr.eval_num_regions is not None:
            self._total_regions = self.itr.eval_num_regions
            self.genome = self.itr.eval_genome
            self.trio_dependency = self.itr.current_genome_dependencies[1]

        # self.total_outputs_expected = int(self._total_regions * self.n_parts)

        self.logger_msg = (
            f"[{self.itr._mode_string}] - [{self._phase}] - [{self.genome}]"
        )
        if self.itr.demo_mode:
            self.current_region = self.itr.demo_chromosome
            self.prefix = f"{self.genome}-chr{self.itr.demo_chromosome}"
            self.job_label = f"{self.genome}{self.itr.current_trio_num}-chr{self.itr.demo_chromosome}"
            self.region_logger_msg = f" - [CHR{self.itr.demo_chromosome}]"
            self._print_msg = f"    echo SUCCESS: make_examples for demo-{self.genome}, part $t of {self.total_shards} &"

        if current_region is None:
            self.current_region = current_region
            self.prefix = f"{self.genome}"
            self.job_label = f"{self.genome}{self.itr.current_trio_num}"
            self.region_logger_msg = ""
            self._print_msg = f"    echo SUCCESS: make_examples for {self.genome}, part $t of {self.total_shards} &"
        else:
            self.current_region = current_region
            self.prefix = f"{self.genome}-region{self.current_region}"
            self.job_label = (
                f"{self.genome}{self.itr.current_trio_num}-region{self.current_region}"
            )
            self.region_logger_msg = f" - [region{self.current_region}]"
            self._print_msg = f"    echo SUCCESS: make_examples for {self.genome}-region{self.current_region}, part $t of {self.total_shards} &"

    def find_restart_jobs(self) -> None:
        """
        Collect any SLURM job ids for running tests to avoid submitting a job while it's already running.
        """
        if self.make_examples_job_nums:
            num_job_ids = len(self.make_examples_job_nums)
            if num_job_ids == self._total_regions:
                self.jobs_to_run = h.find_not_NaN(self.make_examples_job_nums)
                self.jobs_to_ignore = h.find_NaN(self.make_examples_job_nums)
                self._num_to_run = len(self.jobs_to_run)
                self._num_to_ignore = len(self.jobs_to_ignore)
                self._beam_shuffle_dependencies = h.create_deps(self._total_regions)

                if self.jobs_to_run:
                    updated_jobs_list = []
                    self._run_jobs = True
                    for index in self.jobs_to_run:
                        if index is not None:
                            if (
                                isinstance(self.make_examples_job_nums[index], str)
                                or self.make_examples_job_nums[index]
                                > self._total_regions
                                or self.make_examples_job_nums[index] is None
                            ):
                                if len(str(self.make_examples_job_nums[index])) != 8:
                                    self.itr.logger.error(
                                        f"{self.logger_msg}: invalid input for SLURM job ID | {self.make_examples_job_nums[index]}"
                                    )
                                    self.itr.logger.error(
                                        f"{self.logger_msg}: an 8-digit value must be provided for any number greater than {self._total_regions}.\nExiting..."
                                    )
                                    sys.exit(1)
                                self._num_to_run -= 1
                                self._num_to_ignore += 1
                                self._skipped_counter += 1
                                self._beam_shuffle_dependencies[index] = str(
                                    self.make_examples_job_nums[index]
                                )
                                if self.itr.debug_mode:
                                    self.itr.logger.debug(
                                        f"{self.logger_msg}: beam_shuffling dependencies updated to {self._beam_shuffle_dependencies}"
                                    )
                            else:
                                updated_jobs_list.append(index)

                    if updated_jobs_list:
                        self.jobs_to_run = updated_jobs_list

                if 0 < self._num_to_ignore < self._total_regions:
                    self.itr.logger.info(
                        f"{self.logger_msg}: ignoring {self._num_to_ignore}-of-{self._total_regions} SLURM jobs"
                    )
                else:
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
                    f"{self.logger_msg}: incorrect format for 'make_examples_job_nums'"
                )
                self.itr.logger.error(
                    f"{self.logger_msg}: expected a list of {self._total_regions} SLURM jobs (or 'None' as a place holder)"
                )
                self._run_jobs = None
        else:
            self._run_jobs = True
            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"{self.logger_msg}: running job ids were NOT provided"
                )

    def benchmark(self) -> None:
        """
        Save the SLURM job IDs to a file for future resource usage metrics.
        """
        headers = ["AnalysisName", "RunName", "Parent", "Phase", "JobList"]

        if self.track_resources:
            shuffle_deps_string = ",".join(
                filter(None, self._beam_shuffle_dependencies)
            )
            if shuffle_deps_string is None:
                self.itr.logger.warning(
                    f" - [{self.genome}]: unable to perform benchmarking, as SLURM job id(s) are missing",
                )
            else:
                data = {
                    "AnalysisName": self.model_label,
                    "RunName": self.itr.run_name,
                    "Phase": self._phase,
                    "Parent": self.itr.train_genome,
                    "JobList": shuffle_deps_string,
                }

                if not self.itr.dryrun_mode and self.benchmarking_file is not None:
                    if self.itr.debug_mode:
                        self.itr.logger.debug(
                            f"{self.logger_msg}: writing SLURM job numbers to [{self.benchmarking_file.file}]",
                        )
                    self.benchmarking_file.add_rows(
                        headers, data_dict=data,
                    )
                else:
                    self.itr.logger.info(
                        f"[DRY RUN] - {self.logger_msg}: benchmarking is active"
                    )

    def make_job(self, index: int = 0) -> Union[SBATCH, None]:
        """
        Define the contents of the SLURM job for the 'make_examples' phase for TrioTrain Pipeline.
        """
        if self.itr.env is None:
            return
            
        # initialize a SBATCH Object
        self.job_name = f"examples-parallel-{self.job_label}"
        self.handler_label = f"{self._phase}: {self.prefix}-shard$t"

        slurm_job = SBATCH(
            self.itr,
            self.job_name,
            self.model_label,
            self.handler_label,
            f"{self.logger_msg}{self.region_logger_msg}",
        )

        if slurm_job.check_sbatch_file():
            if self.make_examples_job_nums[index] is not None and self.overwrite:
                self.itr.logger.info(
                    f"{self.logger_msg}: --overwrite=True, re-writing the existing SLURM job now..."
                )
            else:
                self.itr.logger.info(
                    f"{self.logger_msg}{self.region_logger_msg}: SLURM job file already exists... SKIPPING AHEAD"
                    )
                return
        else:
            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"{self.logger_msg}{self.region_logger_msg}: creating job file now... "
                )

        if self.itr.demo_mode:
            command_args = f"--genome {self.genome} --region demo"
        else:
            command_args = f"--genome {self.genome} --region {self.current_region}"

        command_list = slurm_job._start_conda + [
            f"for t in $(seq 0 {self.total_shards} ); do",
            self._print_msg,
            f"    conda run --no-capture-output -p miniconda_envs/beam_v2.30 python3 scripts/model_training/slurm_make_examples.py --env-file {self.itr.env.env_file} {command_args} --task-id $t >& {self.itr.log_dir}/examples.{self.prefix}-part$t-of-{self.n_parts}.log",
            "done",
            "wait",
        ]

        slurm_job.create_slurm_job(
            self.handler_label,
            command_list=command_list,
            error_index=-3,
            **self.slurm_resources[self._phase],
            overwrite=self.overwrite,
        )

        return slurm_job

    def find_outputs(
        self, phase: Union[str, None] = None, find_all: bool = False
    ) -> None:
        """
        Determines if make_examples phase has completed successfully.
        """
        if phase is None:
            logger_msg = (
                f"[{self.itr._mode_string}] - [{self._phase}] - [{self.genome}]"
            )
        else:
            logger_msg = f"[{self.itr._mode_string}] - [{phase}] - [{self.genome}]"

        # Define the regrex pattern of expected output
        if self.itr.demo_mode:
            examples_pattern = rf"{self.genome}.chr{self.itr.demo_chromosome}.labeled.tfrecords-\d+-of-\d+.gz.example_info.json(*SKIP)(*FAIL)|{self.genome}.chr{self.itr.demo_chromosome}.labeled.tfrecords-\d+-of-\d+.gz"
        elif find_all:
            examples_pattern = rf"{self.genome}.region\d+.labeled.tfrecords-\d+-of-\d+.gz.example_info.json(*SKIP)(*FAIL)|{self.genome}.region\d+.labeled.tfrecords-\d+-of-\d+.gz"

        elif self.current_region is not None:
            examples_pattern = rf"{self.genome}.region{self.current_region}.labeled.tfrecords-\d+-of-\d+.gz.example_info.json(*SKIP)(*FAIL)|{self.genome}.region{self.current_region}.labeled.tfrecords-\d+-of-\d+.gz"
        else:
            examples_pattern = rf"{self.genome}.labeled.tfrecords-\d+-of-\d+.gz.example_info.json(*SKIP)(*FAIL)|{self.genome}.labeled.tfrecords-\d+-of-\d+.gz"

            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"{self.logger_msg}: tfrecord examples pattern | {examples_pattern}"
                )

        if find_all:
            expected_outputs = int(self.n_parts) * self._total_regions
            logger_msg = logger_msg
        else:
            expected_outputs = int(self.n_parts)
            logger_msg = f"{logger_msg}{self.region_logger_msg}"
        
        # Confirm examples do not already exist
        (
            self._existing_tfrecords,
            self._num_tfrecords_found,
            self._tfrecord_files_list,
        ) = h.check_if_output_exists(
            examples_pattern,
            "labeled tfrecord shards",
            self.itr.examples_dir,
            logger_msg,
            self.itr.logger,
            debug_mode=self.itr.debug_mode,
        )

        if self._existing_tfrecords and self._num_tfrecords_found is not None:
            if self.overwrite and self.make_examples_job_nums and h.check_if_all_same(self.make_examples_job_nums, None) is False:
                self._outputs_exist = False
                self._num_tfrecords_found = 0
            else:
                missing_files = h.check_expected_outputs(
                    self._num_tfrecords_found,
                    expected_outputs,
                    logger_msg,
                    "labeled tfrecord files",
                    self.itr.logger,
                )
                if missing_files:
                    self._outputs_exist = False
                else:
                    self._outputs_exist = True
        else:
            self._num_tfrecords_found = 0

    def submit_job(
        self, dependency_index: int = 0, resubmission: bool = False, total_jobs: int = 1
    ) -> None:
        """
        Submit SLURM jobs to queue.

        Note: Do NOT want to define default # of
              expected number of outputs, as
              the number created depends on
              the number of CPUs available from SLURM.
        """
        self.find_outputs()
        slurm_job = self.make_job(index=dependency_index)

        if slurm_job is not None:
            if self.itr.dryrun_mode:
                slurm_job.display_job()
            else:
                slurm_job.write_job()

        num_missing_files = int(self.n_parts) - int(self._num_tfrecords_found)  # type: ignore
        if not self.overwrite:
            if resubmission:
                self.itr.logger.info(
                    f"{self.logger_msg}{self.region_logger_msg}: re-submitting job because [{num_missing_files}] shards failed to create tfrecords files"
                )
            else:
                self.itr.logger.info(
                    f"{self.logger_msg}{self.region_logger_msg}: submitting job to create [{num_missing_files}] labeled tfrecords shards"
                )

        else:
            self.itr.logger.info(
                f"{self.logger_msg}{self.region_logger_msg}: re-submitting job to overwrite any existing tfrecords files"
            )
        submit_slurm_job = SubmitSBATCH(
            self.itr.job_dir,
            f"{self.job_name}.sh",
            self.handler_label,
            self.itr.logger,
            f"{self.logger_msg}{self.region_logger_msg}",
        )

        submit_slurm_job.build_command(prior_job_number=None)

        if self.itr.dryrun_mode:
            submit_slurm_job.display_command(
                current_job=self.job_num,
                total_jobs=total_jobs,
                display_mode=self.itr.dryrun_mode,
            )
            self._beam_shuffle_dependencies.insert(
                dependency_index, h.generate_job_id()
            )

        else:
            submit_slurm_job.display_command(debug_mode=self.itr.debug_mode)
            submit_slurm_job.get_status(
                current_job=self.job_num,
                total_jobs=total_jobs,
                debug_mode=self.itr.debug_mode,
            )

            if submit_slurm_job.status == 0:
                self._beam_shuffle_dependencies.insert(
                    dependency_index, submit_slurm_job.job_number
                )
            else:
                self.itr.logger.error(
                    f"{self.logger_msg}{self.region_logger_msg}: unable to submit SLURM job",
                )
                self._beam_shuffle_dependencies.insert(dependency_index, None)

    def check_submissions(self) -> None:
        """
        Check if the SLURM job file was submitted to the SLURM queue successfully
        """
        if self.itr.debug_mode:
            self._total_regions = 5
        make_examples_results = h.check_if_all_same(
            self._beam_shuffle_dependencies, None
        )
        if make_examples_results is False:
            if len(self._beam_shuffle_dependencies) == 1:
                if self.itr.dryrun_mode:
                    print(
                        f"============ [DRY RUN] - {self.logger_msg} Job Number - {self._beam_shuffle_dependencies} ============"
                    )
                else:
                    print(
                        f"============ {self.logger_msg} Job Number - {self._beam_shuffle_dependencies} ============"
                    )
            else:
                if self.itr.dryrun_mode:
                    print(
                        f"============ [DRY RUN] - {self.logger_msg} Job Numbers ============\n{self._beam_shuffle_dependencies}\n============================================================"
                    )
                else:
                    print(
                        f"============ {self.logger_msg} Job Numbers ============\n{self._beam_shuffle_dependencies}\n============================================================"
                    )

            if self.track_resources and self.benchmarking_file is not None:
                self.benchmark()

        elif self._skipped_counter != 0:
            if self._skipped_counter == self._total_regions:
                self._beam_shuffle_dependencies = [None]
            else:
                self.itr.logger.info(
                    f"{self.logger_msg}: skipping {self._skipped_counter} regions"
                )
        else:
            self.itr.logger.error(
                f"{self.logger_msg}: expected SLURM jobs to be submitted, but they were not",
            )
            self.itr.logger.warning(
                f"{self.logger_msg}: fatal error encountered, unable to proceed further with pipeline.\nExiting... ",
            )
            sys.exit(1)

    def find_all_outputs(
        self, phase: str = "find_outputs", find_beam_tfrecords: bool = False
    ) -> None:
        """
        Determine if final data_prep outputs already exist.
        """
        re_shuffle = ReShuffleExamples(
            itr=self.itr,
            slurm_resources=self.slurm_resources,
            model_label=self.model_label,
            train_mode=self.train_mode,
            track_resources=self.track_resources,
            benchmarking_file=self.benchmarking_file,
        )

        re_shuffle.find_outputs(phase=phase, find_all=True)

        if re_shuffle._outputs_exist and find_beam_tfrecords:

            beam = BeamShuffleExamples(
                itr=self.itr,
                slurm_resources=self.slurm_resources,
                model_label=self.model_label,
                train_mode=self.train_mode,
                track_resources=self.track_resources,
                benchmarking_file=self.benchmarking_file,
                overwrite=self.overwrite,
            )
            beam.set_genome()
            beam.find_outputs(phase=phase, find_all=True)

            if beam._outputs_exist:
                self._outputs_exist = beam._outputs_exist
            else:
                self._outputs_exist = False
        else:
            self._outputs_exist = re_shuffle._outputs_exist

    def run(self) -> Union[List[Union[str, None]], None]:
        """
        Combine all the steps for making examples for all regions into one step
        """
        self.set_genome()
        self.find_restart_jobs()

        if self.itr.debug_mode:
            self._total_regions = 5

        # SKIP everything if a Trio Dependency was provided
        if self.trio_dependency is not None:
            self.itr.logger.info(
                f"{self.logger_msg}: current genome dependency provided [SLURM job # {self.trio_dependency}]... SKIPPING AHEAD",
            )
            return

        # determine if we are demo region only
        if self.itr.demo_mode:
            self.set_genome(current_region=self._total_regions)
            self.submit_job()

        # determine if we are re-submitting some of the regions for make_examples:
        elif self.make_examples_job_nums and self._run_jobs is not None:
            if self._num_to_run == 0:
                self._beam_shuffle_dependencies = [None]
            elif self._num_to_run != self._total_regions:
                self.itr.logger.info(
                    f"{self.logger_msg}: re-submitting {self._num_to_run}-of-{self._total_regions} SLURM jobs to the queue",
                )
            elif self._num_to_run == self._total_regions:
                self.itr.logger.info(
                    f"{self.logger_msg}: attempting to re-submit all [{self._total_regions}] SLURM jobs now... ",
                )
            else:
                self.itr.logger.error(
                    f"{self.logger_msg}: max number of re-submission SLURM jobs is {self._total_regions} but {self._num_to_run} were provided.\nExiting... ",
                )
                sys.exit(1)

            if not self._beam_shuffle_dependencies:
                self._beam_shuffle_dependencies = h.create_deps(self._total_regions)

            for r in self.jobs_to_run:
                region_index = self.make_examples_job_nums[r]
                self.job_num = (
                    region_index + 1
                )  # THIS HAS TO BE +1 to avoid starting with a region0

                # remove the place holder job num
                del self._beam_shuffle_dependencies[region_index]

                self.set_genome(current_region=self.job_num)

                if not self.overwrite:
                    self.itr.logger.info(
                        f"{self.logger_msg}: --overwrite=False, any exiting results will not be re-written...",
                    )

                else:
                    self.itr.logger.info(
                        f"{self.logger_msg}: --overwrite=True, any exiting results files will be re-written...",
                    )
                self.submit_job(
                    dependency_index=region_index,
                    resubmission=True,
                    total_jobs=int(self._num_to_run),
                )  # THIS (^) HAS TO BE region_index to ensure the dependencies maintain appropriate order

        # run all regions for the first time
        else:
            if self._skip_phase:
                return         
            self.find_outputs(find_all=True)
            if self._outputs_exist:
                return
            
            for r in range(0, int(self._total_regions)):
                self.job_num = (
                    r + 1
                )  # THIS HAS TO BE +1 to avoid starting with a region0
                self.set_genome(current_region=self.job_num)

                self.submit_job(
                    dependency_index=r, total_jobs=int(self._total_regions)
                )  # THIS HAS TO BE r because indexing of the list of job ids starts with 3

        self.check_submissions()

        if (
            len(self._beam_shuffle_dependencies) == 1
            and self._beam_shuffle_dependencies[0] is None
        ):
            return
        else:
            return self._beam_shuffle_dependencies
