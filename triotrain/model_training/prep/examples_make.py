#!/usr/bin/python3
"""
description: contains all of the functions specific to the make_examples phase of TrioTrain.

usage:
    from model_training.prep.examples_make import MakeExamples
"""
from dataclasses import dataclass, field
from sys import exit
from typing import Dict, List, Union

from helpers.files import Files
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
from model_training.prep.examples_re_shuffle import ReShuffleExamples
from model_training.prep.examples_shuffle import BeamShuffleExamples
from model_training.slurm.sbatch import SBATCH, SubmitSBATCH


@dataclass
class MakeExamples:
    """Build SLURM jobs to make labeled training examples.

    Returns
    -------
    List[Union[str, None]] or None
        if None, no SLURM jobs were submitted; or collect a list of submitted SLURM job numbers
    """

    # required values
    itr: Iteration
    slurm_resources: Dict[str, str]
    model_label: str

    # optional values
    benchmarking_file: Union[Files, None] = None
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
    _outputs_exist: bool = field(default=False, init=False, repr=False)
    _phase: str = field(default="make_examples", init=False, repr=False)
    _print_msg: Union[str, None] = field(default=None, init=False, repr=False)
    _skipped_counter: int = field(default=0, init=False, repr=False)
    _skip_phase: bool = field(default=False, init=False, repr=False)
    _total_regions: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.track_resources:
            assert (
                self.benchmarking_file is not None
            ), "unable to proceed, missing a Files object to save SLURM job numbers"

    def set_variables(self) -> None:
        """Add variables from SLURM config to ENV"""
        if self.itr.env is None:
            return
        self.n_parts = self.slurm_resources[self._phase]["ntasks"]
        self.total_shards = self.n_parts - 1
        if "N_Parts" not in self.itr.env.contents:
            self.itr.env.add_to(
                "N_Parts",
                str(self.n_parts),
                dryrun_mode=self.itr.dryrun_mode,
                msg=self.logger_msg,
            )
        if "TotalShards" not in self.itr.env.contents:
            self.itr.env.add_to(
                "TotalShards",
                str(self.total_shards),
                dryrun_mode=self.itr.dryrun_mode,
                msg=self.logger_msg,
            )

    def set_region(self, current_region: Union[int, str, None] = None) -> None:
        """
        Define the current region

        Parameters
        ----------
        current_region : Union[int, None], optional
            determines if constrained to a specific region number (i.e. region shuffling), by default None
        """
        if self.itr.demo_mode:
            self.current_region = self.itr.demo_chromosome

            if "chr" in self.itr.demo_chromosome.lower():
                self.region_logger_msg = f" - [{self.itr.demo_chromosome.upper()}]"
                self.prefix = f"{self.genome}-{self.itr.demo_chromosome}"
                self.job_label = f"{self.genome}{self.itr.current_trio_num}-{self.itr.demo_chromosome}"
            else:
                self.region_logger_msg = f" - [chr{self.itr.demo_chromosome}]"
                self.prefix = f"{self.genome}-chr{self.itr.demo_chromosome}"
                self.job_label = f"{self.genome}{self.itr.current_trio_num}-chr{self.itr.demo_chromosome}"

            self._print_msg = f"    echo SUCCESS: make_examples for demo-{self.genome}, part $t of {self.total_shards} &"

        elif current_region == 0 or current_region is None:
            self.current_region = None
            self.region_logger_msg = ""
            self.prefix = self.genome
            self.job_label = f"{self.genome}{self.itr.current_trio_num}"
            self._print_msg = f"    echo SUCCESS: make_examples for {self.genome}, part $t of {self.total_shards} &"
        else:
            self.current_region = current_region
            self.region_logger_msg = f" - [region{self.current_region}]"
            self.prefix = f"{self.genome}-region{self.current_region}"
            self.job_label = (
                f"{self.genome}{self.itr.current_trio_num}-region{self.current_region}"
            )

            self._print_msg = f"    echo SUCCESS: make_examples for {self.genome}-region{self.current_region}, part $t of {self.total_shards} &"

        if self.itr.demo_mode or self.current_region is None:
            self.logger_msg = (
                f"{self.itr._mode_string} - [{self._phase}] - [{self.genome}]"
            )
        else:
            self.logger_msg = f"{self.itr._mode_string} - [{self._phase}] - [{self.genome}]{self.region_logger_msg}"

    def set_genome(self) -> None:
        """Assign a genome label"""
        if self.itr.demo_mode:
            self.genome = self.itr.train_genome
            self._total_regions = 1
        elif self.itr.dryrun_mode:
            self.genome = self.itr.train_genome
            self._total_regions = 5

        if self.train_mode and self.itr.train_num_regions is not None:
            self.genome = self.itr.train_genome
            self.trio_dependency = self.itr.current_genome_dependencies[0]
            self._total_regions = self.itr.train_num_regions
        elif self.train_mode is False and self.itr.eval_num_regions is not None:
            self.genome = self.itr.eval_genome
            self.trio_dependency = self.itr.current_genome_dependencies[1]
            self._total_regions = self.itr.eval_num_regions

        self._beam_shuffle_dependencies = create_deps(self._total_regions)
        self.logger_msg = f"{self.itr._mode_string} - [{self._phase}] - [{self.genome}]"
        self.set_variables()
        self.set_region()

    def find_restart_jobs(self) -> None:
        """Collect any SLURM job ids for running tests to avoid submitting duplicate jobs simultaneously"""
        self._ignoring_restart_jobs = check_if_all_same(
            self.make_examples_job_nums, None
        )
        if not self._ignoring_restart_jobs:
            self._jobs_to_run = find_not_NaN(self.make_examples_job_nums)
            self._num_to_run = len(self._jobs_to_run)
            self._num_to_ignore = len(find_NaN(self.make_examples_job_nums))
        else:
            self._jobs_to_run = None
            self._num_to_run = 0
            self._num_to_ignore = self._total_regions
            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"{self.logger_msg}: running job ids were NOT provided"
                )

        if 0 < self._num_to_run <= self._total_regions:
            if self._jobs_to_run and not self._ignoring_restart_jobs:
                updated_jobs_list = []

                for index in self._jobs_to_run:
                    if is_jobid(
                        self.make_examples_job_nums[index], max_jobs=self._total_regions
                    ):
                        self._num_to_run -= 1
                        self._num_to_ignore += 1
                        self._skipped_counter += 1
                        self._beam_shuffle_dependencies[index] = str(
                            self.make_examples_job_nums[index]
                        )
                    elif is_job_index(
                        self.make_examples_job_nums[index], max_jobs=self._total_regions
                    ):
                        updated_jobs_list.append(index)

                if updated_jobs_list:
                    self._jobs_to_run = updated_jobs_list

        if self._num_to_ignore == 0:
            return
        elif 0 < self._num_to_ignore < self._total_regions:
            self.itr.logger.info(
                f"{self.logger_msg}: ignoring {self._num_to_ignore}-of-{self._total_regions} SLURM jobs"
            )
        elif self._num_to_ignore == self._total_regions:
            if self.make_examples_job_nums:
                self.itr.logger.info(
                    f"{self.logger_msg}: completed '{self._phase}:{self.genome}'... SKIPPING AHEAD"
                )
        else:
            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"{self.logger_msg}: --running-jobids triggered reprocessing {self._num_to_run} jobs"
                )
            self.itr.logger.error(
                f"{self.logger_msg}: incorrect format for 'make_examples_job_nums'"
            )
            self.itr.logger.error(
                f"{self.logger_msg}: expected a list of {self._total_regions} SLURM jobs (or 'None' as a place holder)"
            )

    def benchmark(self) -> None:
        """Save the SLURM job numbers to a file for future resource usage metrics"""
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
                        headers,
                        data_dict=data,
                    )
                else:
                    self.itr.logger.info(f"{self.logger_msg}: --keep-jobids=True")

    def make_job(self, index: int = 0) -> Union[SBATCH, None]:
        """Defines the SLURM job contents

        Parameters
        ----------
        index : int, optional
            defines where a SLURM job number is stored in a list; by default 0

        Returns
        -------
        Union[SBATCH, None]
            if None, no SLURM job is required; otherwise, produce the SLURM job file template
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
            f"{self.logger_msg}",
        )

        if slurm_job.check_sbatch_file():
            if self.overwrite:
                if (
                    self.make_examples_job_nums
                    and self.make_examples_job_nums[index] is not None
                    and is_jobid(
                        self.make_examples_job_nums[index], max_jobs=self._total_regions
                    )
                ):
                    self.itr.logger.info(
                        f"{self.logger_msg}: --overwrite=True, but skipping re-writing SLURM job due to a currently running job | '{self.make_examples_job_nums[index]}'"
                    )
                    return
                else:
                    self.itr.logger.info(
                        f"{self.logger_msg}: --overwrite=True, re-writing the existing SLURM job now..."
                    )
            else:
                self.itr.logger.info(
                    f"{self.logger_msg}: --overwrite=False; SLURM job file already exists."
                )
                return
        else:
            if self.itr.debug_mode:
                self.itr.logger.debug(f"{self.logger_msg}: creating job file now... ")

        if self.itr.demo_mode:
            command_args = (
                f"--genome {self.genome} --region-bed {self.itr.demo_chromosome}"
            )
        else:
            command_args = f"--genome {self.genome} --region-num {self.current_region}"

        command_list = slurm_job._start_conda + [
            f"for t in $(seq 0 {self.total_shards} ); do",
            self._print_msg,
            f"    conda run --no-capture-output -p miniconda_envs/beam_v2.30 python3 triotrain/model_training/slurm/make_examples.py --env-file {self.itr.env.env_file} {command_args} --task-id $t >& {self.itr.log_dir}/examples.{self.prefix}-part$t-of-{self.n_parts}.log",
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
            log_msg = f"{self.itr._mode_string} - [{self._phase}] - [{self.genome}]"
        else:
            log_msg = f"{self.itr._mode_string} - [{phase}] - [{self.genome}]"

        if not self.itr.demo_mode:
            log_msg = f"{log_msg}{self.region_logger_msg}"

        # Define the regrex pattern of expected output
        if self.itr.demo_mode:
            if "chr" in self.itr.demo_chromosome.lower():
                examples_pattern = rf"{self.genome}.{self.itr.demo_chromosome}.labeled.tfrecords-\d+-of-\d+.gz.example_info.json(*SKIP)(*FAIL)|{self.genome}.{self.itr.demo_chromosome}.labeled.tfrecords-\d+-of-\d+.gz"
            else:
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
            label = "the labeled.tfrecords"
        else:
            expected_outputs = int(self.n_parts)
            label = "labeled.tfrecords"

        # Confirm examples do not already exist
        (
            self._existing_tfrecords,
            self._num_tfrecords_found,
            self._tfrecord_files_list,
        ) = check_if_output_exists(
            examples_pattern,
            label,
            self.itr.examples_dir,
            log_msg,
            self.itr.logger,
            debug_mode=self.itr.debug_mode,
            dryrun_mode=self.itr.dryrun_mode,
        )

        if self._existing_tfrecords and self._num_tfrecords_found is not None:
            missing_files = check_expected_outputs(
                self._num_tfrecords_found,
                expected_outputs,
                log_msg,
                "labeled.tfrecords",
                self.itr.logger,
            )
            if missing_files:
                self._outputs_exist = False
            else:
                self._outputs_exist = True
        else:
            self._outputs_exist = False
            self._num_tfrecords_found = 0

    def submit_job(
        self,
        msg: str = "sub",
        dependency_index: int = 0,
        resubmission: bool = False,
        total_jobs: int = 1,
    ) -> None:
        """
        Submit SLURM jobs to queue.
        """
        if (self._outputs_exist and self.overwrite is False) or (
            self._outputs_exist
            and self._ignoring_restart_jobs
            and self.overwrite is False
        ):
            self._skipped_counter += 1
            if resubmission:
                self.itr.logger.info(
                    f"{self.logger_msg}: --overwrite=False; skipping job because found all labeled.tfrecords"
                )
            return

        slurm_job = self.make_job(index=dependency_index)

        if slurm_job is not None:
            if self.itr.dryrun_mode:
                slurm_job.display_job()
            else:
                slurm_job.write_job()

        if not self.overwrite and resubmission:
            self.itr.logger.info(
                f"{self.logger_msg}: --overwrite=False; {msg}mitting job because missing labeled.tfrecords"
            )

        elif self.overwrite and self._outputs_exist:
            self.itr.logger.info(
                f"{self.logger_msg}: --overwrite=True; {msg}mitting job because replacing existing labeled.tfrecords"
            )

        else:
            self.itr.logger.info(
                f"{self.logger_msg}: {msg}mitting job to create labeled.tfrecords"
            )

        slurm_job = SubmitSBATCH(
            self.itr.job_dir,
            f"{self.job_name}.sh",
            self.handler_label,
            self.itr.logger,
            f"{self.logger_msg}",
        )

        slurm_job.build_command(prior_job_number=None)

        if self.itr.demo_mode:
            slurm_job.display_command(
                display_mode=self.itr.dryrun_mode,
            )
        else:
            slurm_job.display_command(
                current_job=self.job_num,
                total_jobs=total_jobs,
                display_mode=self.itr.dryrun_mode,
                debug_mode=self.itr.debug_mode,
            )

        if self.itr.dryrun_mode:
            self._beam_shuffle_dependencies[dependency_index] = generate_job_id()
        else:
            if self.itr.demo_mode:
                slurm_job.get_status(
                    total_jobs=total_jobs, debug_mode=self.itr.debug_mode
                )
            else:
                slurm_job.get_status(
                    current_job=self.job_num,
                    total_jobs=total_jobs,
                    debug_mode=self.itr.debug_mode,
                )

            if slurm_job.status == 0:
                self._beam_shuffle_dependencies[dependency_index] = slurm_job.job_number
            else:
                self.itr.logger.error(
                    f"{self.logger_msg}: unable to {msg}mit SLURM job",
                )
                self._beam_shuffle_dependencies[dependency_index] = None

    def check_submissions(self) -> None:
        """
        Check if the SLURM job file was submitted to the SLURM queue successfully
        """
        self.logger_msg = f"{self.itr._mode_string} - [{self._phase}] - [{self.genome}]"

        if self.itr.debug_mode:
            self._total_regions = 5

        make_examples_results = check_if_all_same(self._beam_shuffle_dependencies, None)

        if make_examples_results is False:
            if len(self._beam_shuffle_dependencies) == 1:
                print(
                    f"============ {self.logger_msg} Job Number - {self._beam_shuffle_dependencies} ============"
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
            self.itr.logger.error(
                f"{self.logger_msg}: expected SLURM jobs to be submitted, but they were not",
            )
            self.itr.logger.warning(
                f"{self.logger_msg}: fatal error encountered, unable to proceed further with pipeline.\nExiting... ",
            )
            exit(1)

    def find_all_outputs(
        self, phase: str = "find_outputs", verbose: bool = False
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

        re_shuffle.set_genome()
        re_shuffle.find_outputs(phase=phase)

        if re_shuffle._outputs_exist and verbose:
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

        skip_re_runs = check_if_all_same(self.make_examples_job_nums, None)

        if skip_re_runs:
            msg = "sub"
        else:
            msg = "re-sub"

        self.find_restart_jobs()

        if self.itr.debug_mode:
            self._total_regions = 5

        # SKIP everything if a Trio Dependency was provided
        if self.trio_dependency is not None:
            self.itr.logger.info(
                f"{self.logger_msg}: current genome dependency provided [SLURM job # {self.trio_dependency}]... SKIPPING AHEAD",
            )
            return

        # Determine if we are re-submitting some of the regions for make_examples:
        if not self._ignoring_restart_jobs:
            if self._num_to_run == 0:
                self._skipped_counter = self._num_to_ignore
                if (
                    self._beam_shuffle_dependencies
                    and check_if_all_same(self._beam_shuffle_dependencies, None)
                    is False
                ):
                    self.itr.logger.info(
                        f"{self.logger_msg}: beam_shuffle dependencies updated | '{self._beam_shuffle_dependencies}'"
                    )
                else:
                    self._beam_shuffle_dependencies = None
            else:
                if self._num_to_run > self._total_regions:
                    self.itr.logger.error(
                        f"{self.logger_msg}: max number of {msg}mission SLURM jobs is {self._total_regions} but {self._num_to_run} were provided.\nExiting... ",
                    )
                    exit(1)

                for r in self._jobs_to_run:
                    region_index = self.make_examples_job_nums[r]
                    self.job_num = (
                        region_index + 1
                    )  # THIS HAS TO BE +1 to avoid starting with a region0

                    self.set_region(current_region=self.job_num)
                    if not self.itr.demo_mode:
                        self.find_outputs()

                    if skip_re_runs or not self._outputs_exist:
                        self.submit_job(
                            msg=msg,
                            dependency_index=region_index,
                            resubmission=False,
                            total_jobs=self._num_to_run,
                        )
                    else:
                        self.submit_job(
                            msg=msg,
                            dependency_index=region_index,
                            resubmission=True,
                            total_jobs=self._num_to_run,
                        )

        # run all regions for the first time
        else:
            if self._outputs_exist:
                return self._beam_shuffle_dependencies

            for r in range(0, int(self._total_regions)):
                self.job_num = (
                    r + 1
                )  # THIS HAS TO BE +1 to avoid starting with a region0
                self.set_region(current_region=self.job_num)
                if not self.itr.demo_mode:
                    self.find_outputs()

                if self.overwrite and self._outputs_exist:
                    self.submit_job(
                        msg=msg,
                        dependency_index=r,
                        total_jobs=int(self._total_regions),
                        resubmission=True,
                    )
                else:
                    self.submit_job(
                        msg=msg, dependency_index=r, total_jobs=int(self._total_regions)
                    )  # THIS HAS TO BE r because indexing of the list of job ids starts with 3

        self.check_submissions()

        if (
            len(self._beam_shuffle_dependencies) == 1
            and self._beam_shuffle_dependencies[0] is None
        ):
            return
        else:
            return self._beam_shuffle_dependencies
