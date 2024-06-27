#!/usr/bin/python3
"""
description: contains all of the functions specific to the Beam shuffle_examples phase of TrioTrain.

usage:
    from model_training.prep.examples_make import BeamShuffleExamples
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
class BeamShuffleExamples:
    """
    Define what data to store for the beam_shuffle phase of the TrioTrain Pipeline.
    """

    # required values
    itr: Iteration
    slurm_resources: dict
    model_label: str

    # optional values
    benchmarking_file: Union[WriteFiles, None] = None
    make_examples_jobs: Union[List[Union[str, None]], None] = field(
        default_factory=list
    )
    overwrite: bool = False
    shuffle_examples_job_nums: List = field(default_factory=list)
    train_mode: bool = True
    track_resources: bool = False

    # internal, imutable values
    _existing_config: bool = field(default=False, init=False, repr=False)
    _ignoring_make_examples: Union[bool, None] = field(
        default=None, init=False, repr=False
    )
    _ignoring_restart_jobs: Union[bool, None] = field(
        default=None, init=False, repr=False
    )
    _outputs_exist: bool = field(default=False, init=False, repr=False)
    _phase: str = field(default="beam_shuffle", init=False, repr=False)
    _re_shuffle_dependencies: Union[List[Union[str, None]], None] = field(
        default_factory=list, init=False, repr=False
    )
    _skipped_counter: int = field(default=0, init=False, repr=False)
    _total_regions: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.track_resources:
            assert (
                self.benchmarking_file is not None
            ), "unable to proceed, missing a WriteFiles object to save SLURM job numbers"

    def set_region(self, current_region: Union[int, str, None] = None) -> None:
        """
        Define the current region
        """
        if self.itr.demo_mode:
            self.current_region = self.itr.demo_chromosome
            if "chr" in self.itr.demo_chromosome.lower():
                self.prefix = f"{self.genome}.{self.itr.demo_chromosome}"
                self.job_label = f"{self.genome}{self.itr.current_trio_num}-{self.itr.demo_chromosome}"
                self.region_logger_msg = f" - [{self.itr.demo_chromosome.upper()}]"
            else:
                self.prefix = f"{self.genome}.chr{self.itr.demo_chromosome}"
                self.job_label = f"{self.genome}{self.itr.current_trio_num}-chr{self.itr.demo_chromosome}"
                self.region_logger_msg = f" - [CHR{self.itr.demo_chromosome}]"
        elif current_region == 0 or current_region is None:
            self.current_region = None
            self.prefix = self.genome
            self.job_label = f"{self.genome}{self.itr.current_trio_num}"
            self.region_logger_msg = ""
        else:
            self.current_region = current_region
            self.prefix = f"{self.genome}.region{self.current_region}"
            self.job_label = (
                f"{self.genome}{self.itr.current_trio_num}-region{self.current_region}"
            )
            self.region_logger_msg = f" - [region{self.current_region}]"

        if self.itr.demo_mode:
            self.logger_msg = (
                f"{self.itr._mode_string} - [{self._phase}] - [{self.genome}]"
            )
        else:
            self.logger_msg = f"{self.itr._mode_string} - [{self._phase}] - [{self.genome}]{self.region_logger_msg}"

    def set_genome(self) -> None:
        """
        Assign a genome + region label
        """
        self.n_parts = self.slurm_resources["make_examples"]["ntasks"]
        self.total_shards = self.n_parts - 1

        if self.itr.demo_mode:
            self._total_regions = 1
            self.genome = self.itr.train_genome
        elif self.itr.debug_mode:
            self._total_regions = 5
            self.genome = self.itr.train_genome

        if self.train_mode and self.itr.train_num_regions is not None:
            self._total_regions = self.itr.train_num_regions
            self.genome = self.itr.train_genome
            self.genome_index = 0
            self.trio_dependency = self.itr.current_genome_dependencies[0]
        elif self.train_mode is False and self.itr.eval_num_regions is not None:
            self._total_regions = self.itr.eval_num_regions
            self.genome = self.itr.eval_genome
            self.genome_index = 1
            self.trio_dependency = self.itr.current_genome_dependencies[1]

        # The final remainder region (e.g. #168) could have plenty of examples to be shuffled and would also be sharded during beam shuffling
        self.total_shuffle_outputs_expected1 = int((self._total_regions) * self.n_parts)

        # Alternatively, the final remainder region (e.g. #61), could have very few examples
        # to be shuffled, so it is not sharded like the other regions
        self.total_shuffle_outputs_expected2 = int(
            (self._total_regions - 1) * self.n_parts + 1
        )

        # There should be one pbtxt created per region
        self.total_pbtxt_outputs_expected = int(self._total_regions)

        self._re_shuffle_dependencies = create_deps(self._total_regions)
        self.logger_msg = f"{self.itr._mode_string} - [{self._phase}] - [{self.genome}]"

        self.set_region()

    def find_restart_jobs(self) -> None:
        """
        Collect any SLURM job ids for running tests to avoid submitting a job while it's already running.
        """
        self._ignoring_make_examples = check_if_all_same(self.make_examples_jobs, None)
        self._ignoring_restart_jobs = check_if_all_same(
            self.shuffle_examples_job_nums, None
        )

        if not self._ignoring_make_examples:
            self._jobs_to_run = find_not_NaN(self.make_examples_jobs)
            self._num_to_run = len(self._jobs_to_run)
            self._num_to_ignore = len(find_NaN(self.make_examples_jobs))

        elif not self._ignoring_restart_jobs:
            self._jobs_to_run = find_not_NaN(self.shuffle_examples_job_nums)
            self._num_to_run = len(self._jobs_to_run)
            self._num_to_ignore = len(find_NaN(self.shuffle_examples_job_nums))

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
                    if is_jobid(self.shuffle_examples_job_nums[index]):
                        self._num_to_run -= 1
                        self._num_to_ignore += 1
                        self._skipped_counter += 1
                        self._re_shuffle_dependencies[index] = str(
                            self.shuffle_examples_job_nums[index]
                        )
                    elif is_job_index(
                        self.shuffle_examples_job_nums[index],
                        max_jobs=self._total_regions,
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
            if self.shuffle_examples_job_nums:
                self.itr.logger.info(
                    f"{self.logger_msg}: completed '{self._phase}:{self.genome}'... SKIPPING AHEAD"
                )
        else:
            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"{self.logger_msg}: --running-jobids triggered reprocessing {self._num_to_run} jobs"
                )
            self.itr.logger.error(
                f"{self.logger_msg}: incorrect format for 'shuffle_examples' SLURM job numbers"
            )
            self.itr.logger.error(
                f"{self.logger_msg}: expected a list of {self._total_regions} SLURM jobs (or 'None' as a place holder)"
            )

    def benchmark(self) -> None:
        """
        Save the SLURM job numbers to a file for future resource usage metrics.
        """
        headers = ["AnalysisName", "RunName", "Parent", "Phase", "JobList"]

        if self.track_resources:
            if self._re_shuffle_dependencies is None:
                deps_string = "None"
            else:
                deps_string = ",".join(filter(None, self._re_shuffle_dependencies))
            if deps_string is None:
                self.itr.logger.warning(
                    f"{self.logger_msg}: unable to perform benchmarking, as SLURM job id(s) are missing",
                )
            else:
                data = {
                    "AnalysisName": self.model_label,
                    "RunName": self.itr.run_name,
                    "Phase": self._phase,
                    "Parent": self.itr.train_genome,
                    "JobList": deps_string,
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
        """
        Define the contents of the SLURM job for the beam_shuffle phase for TrioTrain Pipeline.
        """
        # Initialize a SBATCH Object
        self.job_name = f"beam-shuffle-{self.job_label}"
        self.handler_label = f"{self._phase}: {self.prefix}"

        slurm_job = SBATCH(
            self.itr,
            self.job_name,
            self.model_label,
            self.handler_label,
            self.logger_msg,
            self.logger_msg,
        )

        if slurm_job.check_sbatch_file():
            if index < len(self.make_examples_jobs):
                prior_jobs = self.make_examples_jobs[index] is not None
            else:
                prior_jobs = False

            if index < len(self.shuffle_examples_job_nums):
                resub_jobs = self.shuffle_examples_job_nums[index] is not None
            else:
                resub_jobs = False

            if (prior_jobs or resub_jobs) and self.overwrite:
                self.itr.logger.info(
                    f"{self.logger_msg}: --overwrite=True; re-writing the existing SLURM job now... "
                )
            else:
                self.itr.logger.info(
                    f"{self.logger_msg}: --overwrite=False; SLURM job file already exists... SKIPPING AHEAD"
                )
                return
        else:
            if self.itr.debug_mode:
                self.itr.logger.debug(f"{self.logger_msg}: creating job file now... ")

        command_list = slurm_job._start_conda + [
            f"conda run --no-capture-output -p ./miniconda_envs/beam_v2.30 python3 triotrain/model_training/prep/shuffle_tfrecords_beam.py --input_pattern_list={self.itr.examples_dir}/{self.prefix}.labeled.tfrecords-?????-of-000??.gz --output_pattern_prefix={self.itr.examples_dir}/{self.prefix}.labeled.shuffled --output_dataset_config_pbtxt={self.itr.examples_dir}/{self.prefix}.labeled.shuffled.dataset_config.pbtxt --output_dataset_name={self.genome} --runner=DirectRunner --direct_num_workers={self.n_parts} --direct_running_mode='in_memory'",
        ]
        # --direct_running_mode='in_memory'
        # --direct_running_mode='multi_processing'
        ## NOTE TO FUTURE SELF: To use multi_processing, try submitting the Beam jobs as a SLURM array

        slurm_job.create_slurm_job(
            self.handler_label,
            command_list=command_list,
            **self.slurm_resources[self._phase],
            overwrite=self.overwrite,
        )
        return slurm_job

    def find_beam_shuffled_examples(
        self, phase: Union[str, None] = None, find_all: bool = False
    ) -> None:
        """
        Search for existing shuffled.tfrecords, based on expected output patterns.

        Count existing outputs to determine if all were made correctly.

        Confirm that Shuffled examples do NOT already exist before attempting to create them.
        """
        # Define the regrex pattern of expected output
        if self.itr.demo_mode:
            if "chr" in self.itr.demo_chromosome:
                shuff_examples_pattern = rf"{self.genome}\.{self.itr.demo_chromosome}\.labeled\.shuffled-\d+-of-\d+\.tfrecord\.gz"
            else:
                shuff_examples_pattern = rf"{self.genome}\.chr{self.itr.demo_chromosome}\.labeled\.shuffled-\d+-of-\d+\.tfrecord\.gz"
        elif find_all:
            shuff_examples_pattern = (
                rf"{self.genome}\.region\d+\.labeled.shuffled-\d+-of-\d+\.tfrecord\.gz"
            )
        elif self.current_region is not None:
            shuff_examples_pattern = rf"{self.genome}\.region{self.current_region}\.labeled.shuffled-\d+-of-\d+\.tfrecord\.gz"
        else:
            shuff_examples_pattern = (
                rf"{self.genome}\.labeled\.shuffled-\d+-of-\d+\.tfrecord\.gz"
            )

        # self.itr.logger.info(f"SHUFFLE PATTERN: {shuff_examples_pattern}")
        # breakpoint()

        if phase is None:
            log_msg = self.logger_msg
        else:
            log_msg = f"{self.itr._mode_string} - [{phase}] - [{self.genome}]"

            if not self.itr.demo_mode:
                log_msg = f"{log_msg}{self.region_logger_msg}"

        if find_all:
            msg = "all labeled.shuffled.tfrecords"
        else:
            msg = "labeled.shuffled.tfrecords"

        # Confirm examples do not already exist
        (
            self._existing_shuff_examples,
            self._num_shuff_tfrecords_found,
            shuff_tfrecord_files,
        ) = check_if_output_exists(
            shuff_examples_pattern,
            msg,
            self.itr.examples_dir,
            log_msg,
            self.itr.logger,
            debug_mode=self.itr.debug_mode,
            dryrun_mode=self.itr.dryrun_mode,
        )

        # self.itr.logger.info(
        #     f"NUM FOUND: {self._num_shuff_tfrecords_found}")
        # breakpoint()

    def find_beam_shuffled_pbtxt(self, phase: str, find_all: bool = False) -> None:
        """
        Search for existing shuffled.dataset_config.pbtxt, based on expected output patterns.
        """
        # Define the regrex pattern of expected output
        if self.itr.demo_mode:
            if "chr" in self.itr.demo_chromosome.lower():
                shuffled_config_regex = rf"{self.genome}.{self.itr.demo_chromosome}.labeled.shuffled.dataset_config.pbtxt"
            else:
                shuffled_config_regex = rf"{self.genome}.chr{self.itr.demo_chromosome}.labeled.shuffled.dataset_config.pbtxt"
        elif find_all:
            shuffled_config_regex = (
                rf"{self.genome}.region\d+.labeled.shuffled.dataset_config.pbtxt"
            )
        elif self.current_region is not None:
            shuffled_config_regex = rf"{self.genome}.region{self.current_region}.labeled.shuffled.dataset_config.pbtxt"
        else:
            shuffled_config_regex = (
                rf"{self.genome}.labeled.shuffled.dataset_config.pbtxt"
            )

        if phase is None:
            log_msg = self.logger_msg
        else:
            log_msg = f"{self.itr._mode_string} - [{phase}] - [{self.genome}]"

            if not self.itr.demo_mode:
                log_msg = f"{log_msg}{self.region_logger_msg}"

        if find_all:
            msg = "all labeled.shuffled.pbtxt files"
        else:
            msg = "labeled.shuffled.pbtxt file(s)"

        # Confirm region#'s config does not already exist
        (
            self._existing_config,
            self._num_config_found,
            config_files,
        ) = check_if_output_exists(
            shuffled_config_regex,
            msg,
            self.itr.examples_dir,
            log_msg,
            self.itr.logger,
            debug_mode=self.itr.debug_mode,
            dryrun_mode=self.itr.dryrun_mode,
        )

    def find_outputs(
        self, phase: Union[str, None] = None, find_all: bool = False
    ) -> Union[bool, None]:
        """
        Determine if shuffling outputs already exist
        """
        if phase is None:
            log_msg = f"{self.itr._mode_string} - [{self._phase}] - [{self.genome}]"
            if not self.itr.demo_mode:
                log_msg = f"{log_msg}{self.region_logger_msg}"
            self.find_beam_shuffled_examples(find_all=find_all)
        else:
            log_msg = f"{self.itr._mode_string} - [{phase}] - [{self.genome}]"
            if not self.itr.demo_mode:
                log_msg = f"{log_msg}{self.region_logger_msg}"
            self.find_beam_shuffled_examples(phase=phase, find_all=find_all)

        if find_all:
            expected_shuffle_outputs = self.total_shuffle_outputs_expected1
            expected_config_outputs = self.total_pbtxt_outputs_expected
            file_type1 = "total labeled.shuffled.tfrecords"
            file_type2 = "total labeled.shuffled.pbtxt files"
        else:
            expected_shuffle_outputs = self.n_parts
            expected_config_outputs = 1
            file_type1 = "the labeled.shuffled.tfrecords"
            file_type2 = "the labeled.shuffled.pbtxt file"

        if (
            self._existing_shuff_examples
            and self._num_shuff_tfrecords_found is not None
        ):
            missing_shuffled_files1 = check_expected_outputs(
                self._num_shuff_tfrecords_found,
                expected_shuffle_outputs,
                log_msg,
                file_type1.split(" ")[1],
                self.itr.logger,
            )
        else:
            missing_shuffled_files1 = True

        if find_all:
            if missing_shuffled_files1 and self._num_shuff_tfrecords_found > 0:
                self.itr.logger.info(
                    f"{log_msg}: double-checking if last region produced very few examples...",
                )
                missing_shuffled_files2 = check_expected_outputs(
                    self._num_shuff_tfrecords_found,
                    self.total_shuffle_outputs_expected2,
                    log_msg,
                    file_type1.split(" ")[1],
                    self.itr.logger,
                )
            else:
                missing_shuffled_files2 = True
        else:
            missing_shuffled_files2 = False

        # handling multiple numbers of outputs, depending on contents shuffled
        if missing_shuffled_files1 and missing_shuffled_files2:
            missing_shuffled_files = True
        elif missing_shuffled_files1 and not missing_shuffled_files2:
            missing_shuffled_files = False
        else:
            missing_shuffled_files = False

        if phase is None:
            self.find_beam_shuffled_pbtxt(phase=self._phase, find_all=find_all)
        else:
            self.find_beam_shuffled_pbtxt(phase=phase, find_all=find_all)

        if self._existing_config and self._num_config_found is not None:
            missing_config_file = check_expected_outputs(
                self._num_config_found,
                expected_config_outputs,
                log_msg,
                file_type2,
                self.itr.logger,
            )
        else:
            missing_config_file = True

        if missing_shuffled_files or missing_config_file:
            self._outputs_exist = False
        else:
            self._outputs_exist = True

        if self.itr.debug_mode:
            self._total_regions = 5

        assert (
            self._total_regions is not None
        ), f"unable to proceed; expected a value for total_regions, and None was provided"

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
                    f"{self.logger_msg}: --overwrite=False; skipping job because found all labeled.shuffled.tfrecords"
                )
            return

        slurm_job = self.make_job(index=dependency_index)

        if slurm_job is not None:
            if self.itr.dryrun_mode:
                slurm_job.display_job()
            else:
                slurm_job.write_job()

        num_missing_files = int(self.n_parts) - int(self._num_shuff_tfrecords_found)  # type: ignore

        if not self.overwrite and self._ignoring_make_examples:
            self.itr.logger.info(
                f"{self.logger_msg}: --overwrite=False; {msg}mitting job because missing {num_missing_files} labeled.shuffled.tfrecords"
            )
        elif self.overwrite and self._outputs_exist:
            self.itr.logger.info(
                f"{self.logger_msg}: --overwrite=True; {msg}mitting job because replacing existing labeled.shuffled.tfrecords"
            )
        else:
            self.itr.logger.info(
                f"{self.logger_msg}: {msg}mitting job to create {num_missing_files} labeled.shuffled.tfrecords"
            )

        slurm_job = SubmitSBATCH(
            self.itr.job_dir,
            f"{self.job_name}.sh",
            self.handler_label,
            self.itr.logger,
            self.logger_msg,
        )

        if self.make_examples_jobs is not None and len(self.make_examples_jobs) == int(
            self._total_regions
        ):
            slurm_job.build_command(
                prior_job_number=self.make_examples_jobs[dependency_index]
            )
        else:
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
            self._re_shuffle_dependencies[dependency_index] = generate_job_id()
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
                self._re_shuffle_dependencies[dependency_index] = slurm_job.job_number
            else:
                self.itr.logger.error(
                    f"{self.logger_msg}: unable to {msg}mit SLURM job",
                )

    def check_submissions(self) -> None:
        """
        Check if the SLURM job file was submitted to the SLURM queue successfully
        """
        self.logger_msg = f"{self.itr._mode_string} - [{self._phase}] - [{self.genome}]"

        if self.itr.debug_mode:
            self._total_regions = 5

        if self._re_shuffle_dependencies is None:
            no_beam_jobs_submitted = True
        else:
            no_beam_jobs_submitted = check_if_all_same(
                self._re_shuffle_dependencies, None
            )

        if no_beam_jobs_submitted is False:
            if len(self._re_shuffle_dependencies) == 1:
                print(
                    f"============ {self.logger_msg} Job Number - {self._re_shuffle_dependencies} ============"
                )

            else:
                print(
                    f"============ {self.logger_msg} Job Numbers ============\n{self._re_shuffle_dependencies}\n============================================================"
                )

            if self.track_resources and self.benchmarking_file is not None:
                self.benchmark()

        elif self._skipped_counter != 0:
            if self._skipped_counter == self._total_regions:
                self._re_shuffle_dependencies = None
        else:
            self.itr.logger.error(
                f"{self.logger_msg}: expected SLURM jobs to be submitted, but they were not",
            )
            self._re_shuffle_dependencies = None
            self.itr.logger.warning(
                f"{self.logger_msg}: fatal error encountered, unable to proceed further with pipeline.\nExiting... ",
            )
            exit(1)

    def run(self) -> Union[List[Union[str, None]], None]:
        """
        Combine all the steps for making jobs for all regions into one step
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

        skip_re_runs = check_if_all_same(self.shuffle_examples_job_nums, None)

        if skip_re_runs and self._outputs_exist is False:
            msg = "sub"
        else:
            msg = "re-sub"

        # Determine if we are re-running some of the regions for make_examples
        if not self._ignoring_make_examples or not self._ignoring_restart_jobs:
            if self._num_to_run == 0:
                self._skipped_counter = self._num_to_ignore
                if (
                    self._re_shuffle_dependencies
                    and check_if_all_same(self._re_shuffle_dependencies, None) is False
                ):
                    self.itr.logger.info(
                        f"{self.logger_msg}: 're_shuffle' dependencies updated | '{self._re_shuffle_dependencies}'"
                    )
                else:
                    self._re_shuffle_dependencies = None
            else:
                if not self._ignoring_make_examples:
                    self.itr.logger.info(
                        f"{self.logger_msg}: 'make_examples' jobs were submitted...",
                    )

                if self._num_to_run <= self._total_regions:
                    self.itr.logger.info(
                        f"{self.logger_msg}: attempting to {msg}mit {self._num_to_run}-of-{self._total_regions} SLURM jobs to the queue",
                    )

                else:
                    self.itr.logger.error(
                        f"{self.logger_msg}: max number of SLURM jobs for {msg}mission is {self._total_regions} but {self._num_to_run} were provided.\nExiting... ",
                    )
                    exit(1)

                for i, r in enumerate(self._jobs_to_run):
                    if skip_re_runs:
                        region_index = r
                    # handle issues that occur when missing make_examples outputs but 're-start' beam_shuffle
                    elif find_not_NaN(self._jobs_to_run) != find_not_NaN(
                        self.shuffle_examples_job_nums
                    ):
                        unique__jobs_to_run = list(
                            set(self._jobs_to_run + self.shuffle_examples_job_nums)
                        )
                        new_jobs_list = [
                            j for j in unique__jobs_to_run if j is not None
                        ]  # remove 'None' values
                        region_index = new_jobs_list[i]
                    else:
                        region_input = self.shuffle_examples_job_nums[r]
                        if is_jobid(region_input):
                            region_index = r
                        elif is_job_index(region_input, max_jobs=self._total_regions):
                            region_index = region_input

                    self.job_num = (
                        int(region_index) + 1
                    )  # THIS HAS TO BE +1 to avoid starting with a region0

                    self.set_region(current_region=self.job_num)
                    if not self.itr.demo_mode:
                        self.find_outputs()

                    if not check_if_all_same(self.make_examples_jobs, None):
                        self.submit_job(
                            msg=msg,
                            dependency_index=region_index,
                            resubmission=True,
                            total_jobs=self._num_to_run,
                        )
                    elif skip_re_runs or not self._outputs_exist:
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
                return self._re_shuffle_dependencies

            self.set_genome()
            for r in range(0, int(self._total_regions)):
                self.job_num = (
                    r + 1
                )  # THIS HAS TO BE +1 to avoid starting with a region0
                self.set_region(current_region=self.job_num)
                self.find_outputs()
                self.submit_job(
                    msg=msg, dependency_index=r, total_jobs=int(self._total_regions)
                )

        self.check_submissions()
        return self._re_shuffle_dependencies
