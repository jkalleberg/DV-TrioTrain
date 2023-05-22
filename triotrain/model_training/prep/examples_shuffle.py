#!/usr/bin/python3
"""
description: contains all of the functions specific to the Beam shuffle_examples phase of TrioTrain.

usage:
    from examples_beam_shuffle import BeamShuffleExamples
"""
import sys
from dataclasses import dataclass, field
from typing import List, Union
from pathlib import Path

# get the relative path to the triotrain/ dir
h_path = str(Path(__file__).parent.parent.parent)
sys.path.append(h_path)
import helpers
import model_training.slurm as s


@dataclass
class BeamShuffleExamples:
    """
    Define what data to store for the beam_shuffle phase of the TrioTrain Pipeline.
    """

    # required values
    itr: helpers.Iteration
    slurm_resources: dict
    model_label: str

    # optional values
    benchmarking_file: Union[helpers.h.WriteFiles, None] = None
    make_examples_jobs: Union[List[Union[str, None]], None] = field(
        default_factory=list
    )
    overwrite: bool = False
    shuffle_examples_job_nums: List = field(default_factory=list)
    train_mode: bool = True
    track_resources: bool = False

    # internal, imutable values
    _existing_config: bool = field(default=False, init=False, repr=False)
    _outputs_exist: bool = field(default=False, init=False, repr=False)
    _phase: str = field(default="beam_shuffle", init=False, repr=False)
    _re_shuffle_dependencies: Union[List[Union[str, None]], None] = field(
        default_factory=list, init=False, repr=False
    )
    _run_jobs: Union[bool, None] = field(default=None, init=False, repr=False)
    _skipped_counter: int = field(default=0, init=False, repr=False)
    _total_regions: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.track_resources:
            assert (
                self.benchmarking_file is not None
            ), "unable to proceed, missing a h.WriteFiles object to save SLURM job IDs"

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

        self._re_shuffle_dependencies = helpers.h.create_deps(self._total_regions)

        # The final remainder region (e.g. #168) could have plenty of examples to be shuffled and would also be sharded during beam shuffling
        self.total_shuffle_outputs_expected1 = int((self._total_regions) * self.n_parts)

        # Alternatively, the final remainder region (e.g. #61), could have very few examples
        # to be shuffled, so it is not sharded like the other regions
        self.total_shuffle_outputs_expected2 = int(
            (self._total_regions - 1) * self.n_parts + 1
        )

        # There should be one pbtxt created per region
        self.total_pbtxt_outputs_expected = int(self._total_regions)

        self.logger_msg = (
            f"[{self.itr._mode_string}] - [{self._phase}] - [{self.genome}]"
        )

    def set_region(self, current_region: Union[int, str, None] = None) -> None:
        """
        Define the current region
        """
        if self.itr.demo_mode:
            self.current_region = self.itr.demo_chromosome
            self.prefix = f"{self.genome}.chr{self.itr.demo_chromosome}"
            self.job_label = f"{self.genome}{self.itr.current_trio_num}-chr{self.itr.demo_chromosome}"
            self.region_logger_msg = f" - [CHR{self.itr.demo_chromosome}]"
            self.msg = self.region_logger_msg
        elif current_region == 0:
            self.current_region = None
            self.prefix = self.genome
            self.job_label = f"{self.genome}{self.itr.current_trio_num}"
            self.region_logger_msg = ""
            self.msg = ""
        else:
            self.current_region = current_region
            self.prefix = f"{self.genome}.region{self.current_region}"
            self.job_label = (
                f"{self.genome}{self.itr.current_trio_num}-region{self.current_region}"
            )
            self.region_logger_msg = f" - [region{self.current_region}]"
            self.msg = self.genome

    def find_restart_jobs(self) -> None:
        """
        Collect any SLURM job ids for running tests to avoid submitting a job while it's already running.
        """
        self._ignoring_make_examples = helpers.h.check_if_all_same(
            self.make_examples_jobs, None
        )

        if not self._ignoring_make_examples:
            self._num_to_ignore = len(helpers.h.find_NaN(self.make_examples_jobs))
            self.jobs_to_run = helpers.h.find_not_NaN(self.make_examples_jobs)
            self._num_to_run = len(self.jobs_to_run)
            self._run_jobs = True

        elif self.shuffle_examples_job_nums:
            if self.overwrite and self._outputs_exist:
                self.itr.logger.info(
                    f"{self.logger_msg}: --overwrite=True, any exiting results files will be re-written..."
                )

            num_job_ids = len(self.shuffle_examples_job_nums)
            if num_job_ids == self._total_regions:
                self.jobs_to_run = helpers.h.find_not_NaN(self.shuffle_examples_job_nums)
                self._num_to_run = len(self.jobs_to_run)
                self._num_to_ignore = len(helpers.h.find_NaN(self.shuffle_examples_job_nums))
                self._re_shuffle_dependencies = helpers.h.create_deps(self._total_regions)

                if self.jobs_to_run:
                    self._run_jobs = True
                    for index in self.jobs_to_run:
                        if index is not None:
                            if (
                                isinstance(self.shuffle_examples_job_nums[index], str)
                                or self.shuffle_examples_job_nums[index]
                                > self._total_regions
                                or self.shuffle_examples_job_nums[index] is None
                            ):
                                if len(str(self.shuffle_examples_job_nums[index])) != 8:
                                    self.itr.logger.error(
                                        f"{self.logger_msg}: invalid input for SLURM job ID | {self.shuffle_examples_job_nums[index]}"
                                    )
                                    self.itr.logger.error(
                                        f"{self.logger_msg}: an 8-digit value must be provided for any number greater than {self._total_regions}.\nExiting..."
                                    )
                                    sys.exit(1)

                                self._num_to_run -= 1
                                self._num_to_ignore += 1
                                self._skipped_counter += 1
                                self._re_shuffle_dependencies[index] = str(
                                    self.shuffle_examples_job_nums[index]
                                )
                else:
                    self._run_jobs = False

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
                    f"{self.logger_msg}: incorrect format for 'shuffle_examples_job_nums'"
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
                    self.itr.logger.info(
                        f"[DRY RUN] - {self.logger_msg}: benchmarking is active"
                    )

    def make_job(self, index: int = 0) -> Union[s.SBATCH, None]:
        """
        Define the contents of the SLURM job for the beam_shuffle phase for TrioTrain Pipeline.
        """
        # Initialize a SBATCH Object
        self.job_name = f"beam-shuffle-{self.job_label}"
        self.handler_label = f"{self._phase}: {self.prefix}"

        slurm_job = s.SBATCH(
            self.itr,
            self.job_name,
            self.model_label,
            self.handler_label,
            f"{self.logger_msg}{self.region_logger_msg}",
        )

        if slurm_job.check_sbatch_file():
            if (
                self.make_examples_jobs
                and self.make_examples_jobs[index] is not None
                and self.overwrite
            ):
                self.itr.logger.info(
                    f"{self.logger_msg}{self.region_logger_msg}: re-writing job file now... "
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

        command_list = slurm_job._start_conda + [
            f"conda run --no-capture-output -p ./miniconda_envs/beam_v2.30 python3 scripts/model_training/shuffle_tfrecords_beam.py --input_pattern_list={self.itr.examples_dir}/{self.prefix}.labeled.tfrecords-?????-of-000??.gz --output_pattern_prefix={self.itr.examples_dir}/{self.prefix}.labeled.shuffled --output_dataset_config_pbtxt={self.itr.examples_dir}/{self.prefix}.labeled.shuffled.dataset_config.pbtxt --output_dataset_name={self.genome} --runner=DirectRunner --direct_num_workers={self.n_parts} --direct_running_mode='in_memory'",
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

    def find_beam_shuffled_examples(self, phase: str, find_all: bool = False) -> None:
        """
        Search for existing shuffled.tfrecords, based on expected output patterns.

        Count existing outputs to determine if all were made correctly.

        Confirm that Shuffled examples do NOT already exist before attempting to create them.
        """
        # Define the regrex pattern of expected output
        if self.itr.demo_mode:
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

        if find_all:
            logger_msg = f"[{self.itr._mode_string}] - [{phase}] - [{self.genome}]"
        else:
            logger_msg = f"[{self.itr._mode_string}] - [{phase}] - [{self.genome}]{self.region_logger_msg}"

        # Confirm examples do not already exist
        (
            self._existing_shuff_examples,
            self._num_shuff_tfrecords_found,
            shuff_tfrecord_files,
        ) = helpers.h.check_if_output_exists(
            shuff_examples_pattern,
            "shuffled tfrecord shards",
            self.itr.examples_dir,
            logger_msg,
            self.itr.logger,
            debug_mode=self.itr.debug_mode,
        )

    def find_beam_shuffled_pbtxt(self, phase: str, find_all: bool = False) -> None:
        """
        Search for existing shuffled.dataset_config.pbtxt, based on expected output patterns.
        """
        # Define the regrex pattern of expected output
        if self.itr.demo_mode:
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

        if find_all:
            logger_msg = f"[{self.itr._mode_string}] - [{phase}] - [{self.genome}]"
        else:
            logger_msg = f"[{self.itr._mode_string}] - [{phase}] - [{self.genome}]{self.region_logger_msg}"

        # Confirm region#'s config does not already exist
        (
            self._existing_config,
            self._num_config_found,
            config_files,
        ) = helpers.h.check_if_output_exists(
            shuffled_config_regex,
            "shuffled pbtxt files",
            self.itr.examples_dir,
            logger_msg,
            self.itr.logger,
            debug_mode=self.itr.debug_mode,
        )

    def submit_job(
        self, dependency_index: int = 0, resubmission: bool = False, total_jobs: int = 1
    ) -> None:
        """
        Submit SLURM jobs to queue.
        """
        self.find_outputs()

        slurm_job = self.make_job(index=dependency_index)
        if slurm_job is not None:
            if self.itr.dryrun_mode:
                slurm_job.display_job()
            else:
                slurm_job.write_job()

        slurm_job = s.SubmitSBATCH(
            self.itr.job_dir,
            f"{self.job_name}.sh",
            self.handler_label,
            self.itr.logger,
            f"{self.logger_msg}{self.region_logger_msg}",
        )

        if self.make_examples_jobs is not None and len(self.make_examples_jobs) == int(
            self._total_regions
        ):
            slurm_job.build_command(
                prior_job_number=self.make_examples_jobs[dependency_index]
            )
        else:
            slurm_job.build_command(prior_job_number=None)

        if self.itr.dryrun_mode:
            slurm_job.display_command(
                current_job=self.job_num,
                total_jobs=total_jobs,
                display_mode=self.itr.dryrun_mode,
            )
            if self._re_shuffle_dependencies:
                self._re_shuffle_dependencies[dependency_index] = helpers.h.generate_job_id()
        else:
            slurm_job.display_command(debug_mode=self.itr.debug_mode)
            slurm_job.get_status(
                current_job=self.job_num,
                total_jobs=total_jobs,
                debug_mode=self.itr.debug_mode,
            )

            if slurm_job.status == 0:
                if self._re_shuffle_dependencies:
                    self._re_shuffle_dependencies[
                        dependency_index
                    ] = slurm_job.job_number
            else:
                self.itr.logger.error(
                    f"{self.logger_msg}: unable to submit SLURM job",
                )

    def check_submissions(self) -> None:
        """
        Check if the SLURM job file was submitted to the SLURM queue successfully
        """
        if self.itr.debug_mode:
            self._total_regions = 5

        if self._re_shuffle_dependencies is None:
            no_beam_jobs_submitted = True
        else:
            no_beam_jobs_submitted = helpers.h.check_if_all_same(
                self._re_shuffle_dependencies, None
            )

        if no_beam_jobs_submitted is False:
            if self.itr.dryrun_mode:
                print(
                    f"============ [DRY RUN] - {self.logger_msg} Job Numbers ============\n{self._re_shuffle_dependencies}\n============================================================"
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
                self.itr.logger.info(
                    f"{self.logger_msg}: skipping {self._skipped_counter} regions"
                )
        else:
            self.itr.logger.error(
                f"{self.logger_msg}: expected SLURM jobs to be submitted, but they were not",
            )
            self._re_shuffle_dependencies = None
            self.itr.logger.warning(
                f"{self.logger_msg}: fatal error encountered, unable to proceed further with pipeline.\nExiting... ",
            )
            sys.exit(1)

    def find_outputs(
        self, phase: Union[str, None] = None, find_all: bool = False
    ) -> Union[bool, None]:
        """
        Determine if shuffling outputs already exist
        """
        self.set_genome()

        # determine if outputs already exist
        # and skip this phase if they do
        if phase is None:
            logger_msg = (
                f"[{self.itr._mode_string}] - [{self._phase}] - [{self.genome}]"
            )
            self.find_beam_shuffled_examples(phase=self._phase, find_all=find_all)
        else:
            logger_msg = f"[{self.itr._mode_string}] - [{phase}] - [{self.genome}]"
            self.find_beam_shuffled_examples(phase=phase, find_all=find_all)

        if not find_all:
            logger_msg = logger_msg + self.region_logger_msg
            expected_shuffle_outputs = self.n_parts
            expected_config_outputs = 1
            file_type1 = "shuffled tfrecord shards"
            file_type2 = "config file"
        else:
            expected_shuffle_outputs = self.total_shuffle_outputs_expected1
            expected_config_outputs = self.total_pbtxt_outputs_expected
            file_type1 = "total shuffled files"
            file_type2 = "total config files"

        if (
            self._existing_shuff_examples
            and self._num_shuff_tfrecords_found is not None
        ):
            missing_shuffled_files1 = helpers.h.check_expected_outputs(
                self._num_shuff_tfrecords_found,
                expected_shuffle_outputs,
                logger_msg,
                file_type1,
                self.itr.logger,
            )
        else:
            missing_shuffled_files1 = True

        if find_all:
            if missing_shuffled_files1:
                self.itr.logger.info(
                    f"{logger_msg}: determining if incomplete shuffled files is due to the final region producing very few examples...",
                )
                missing_shuffled_files2 = helpers.h.check_expected_outputs(
                    self._num_shuff_tfrecords_found,
                    self.total_shuffle_outputs_expected2,
                    logger_msg,
                    file_type1,
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

        if self.overwrite and (
            self.make_examples_jobs or not self._ignoring_make_examples
        ):
            self._outputs_exist = False
        else:
            if self._existing_config and self._num_config_found is not None:
                missing_config_file = helpers.h.check_expected_outputs(
                    self._num_config_found,
                    expected_config_outputs,
                    logger_msg,
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

        # Determine if we are re-running only demo regions for make_examples
        if self.itr.demo_mode:
            self.set_genome()
            self.set_region(current_region=self._total_regions)
            self.find_outputs()
            self.submit_job()

        # Determine if we are re-running some of the regions for make_examples
        if (
            self.make_examples_jobs or not self._ignoring_make_examples
        ) and self._run_jobs is not None:
            if self._num_to_run == 0:
                self._skipped_counter = self._num_to_ignore
                if (
                    self._re_shuffle_dependencies
                    and helpers.h.check_if_all_same(self._re_shuffle_dependencies, None)
                    is False
                ):
                    self.itr.logger.info(
                        f"{self.logger_msg}: re_shuffle dependencies updated to {self._re_shuffle_dependencies}"
                    )
                else:
                    self._re_shuffle_dependencies = None
            else:
                if not self._ignoring_make_examples:
                    self.itr.logger.info(
                        f"{self.logger_msg}: make-examples was submitted...",
                    )

                if self._num_to_run <= self._total_regions:
                    if self.overwrite:
                        self.itr.logger.info(
                            f"{self.logger_msg}: re-submitting {self._num_to_run}-of-{self._total_regions} SLURM jobs",
                        )
                        self.itr.logger.info(
                            f"{self.logger_msg}: --overwrite=True, any exiting results files will be re-written..."
                        )
                    else:
                        self.itr.logger.info(
                            f"{self.logger_msg}: submitting {self._num_to_run}-of-{self._total_regions} SLURM jobs",
                        )
                else:
                    self.itr.logger.error(
                        f"{self.logger_msg}: max number of re-submission SLURM jobs is {self._total_regions} but {self._num_to_run} were provided.\nExiting... ",
                    )
                    sys.exit(1)

                for r in self.jobs_to_run:
                    skip_re_runs = helpers.h.check_if_all_same(
                        self.shuffle_examples_job_nums, None
                    )
                    if skip_re_runs:
                        region_index = r
                    else:
                        region_index = self.shuffle_examples_job_nums[r]
                        # remove the place holder job num
                        if self._re_shuffle_dependencies:
                            del self._re_shuffle_dependencies[region_index]

                    self.job_num = (
                        region_index + 1
                    )  # THIS HAS TO BE +1 to avoid starting with a region0
                    self.set_genome()
                    self.set_region(current_region=self.job_num)
                    self.submit_job(
                        dependency_index=region_index,
                        resubmission=True,
                        total_jobs=self._num_to_run,
                    )  # THIS (^) HAS TO BE region_index to ensure the dependencies maintain appropriate order

        # run all regions for the first time
        else:
            # determine if jobs need to be submitted
            if self._skip_phase:
                return

            self.find_outputs(find_all=True)
            if self._outputs_exist:
                return

            for r in range(0, int(self._total_regions)):
                self.job_num = (
                    r + 1
                )  # THIS HAS TO BE +1 to avoid starting with a region0
                self.set_genome()
                self.set_region(current_region=self.job_num)
                self.submit_job(
                    dependency_index=r, total_jobs=int(self._total_regions)
                )  # THIS HAS TO BE r because indexing of the list of job ids starts with 0

        self.check_submissions()
        return self._re_shuffle_dependencies
