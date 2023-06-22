#!/usr/bin/python3
"""
description: contains all of the functions specific to comparing variants against a truth set with hap.py for the TrioTrain pipeline.

usage:
    from compare import CompareHappy
"""
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Union

# get the relative path to the triotrain/ dir
h_path = str(Path(__file__).parent.parent.parent)
sys.path.append(h_path)
import helpers
import model_training.slurm as s
from variant_calling.convert import ConvertHappy


@dataclass
class CompareHappy:
    """
    Define what data to store for the 'compare_happy' phase of the TrioTrain Pipeline.
    """

    # required values
    itr: helpers.Iteration
    slurm_resources: dict
    model_label: str

    # optional values
    benchmarking_file: Union[helpers.h.WriteFiles, None] = None
    call_variants_jobs: Union[List[Union[str, None]], None] = field(
        default_factory=list
    )
    compare_happy_job_nums: List = field(default_factory=list)
    overwrite: bool = False
    track_resources: bool = False

    # internal, imutable values
    _convert_happy_dependencies: Union[List[Union[str, None]], None] = field(
        default_factory=list, init=False, repr=False
    )
    _phase: str = field(default="compare_happy", init=False, repr=False)
    _skipped_counter: int = field(default=0, init=False, repr=False)
    _skip_phase: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.itr.env is None:
            return
        self.logger_msg = f"[{self.itr._mode_string}] - [{self._phase}]"
        self.n_parts = self.slurm_resources[self._phase]["ntasks"]

        if "N_Parts" not in self.itr.env.contents:
            self.itr.env.add_to(
                "N_Parts", str(self.n_parts), self.itr.dryrun_mode, msg=self.logger_msg
            )

        if self.track_resources:
            assert (
                self.benchmarking_file is not None
            ), "missing a h.WriteFiles object to save SLURM job IDs"

        self._convert_happy_dependencies = helpers.h.create_deps(
            self.itr.total_num_tests
        )

        self.converting = ConvertHappy(
            itr=self.itr,
            slurm_resources=self.slurm_resources,
            model_label=self.model_label,
        )

    def set_genome(self) -> None:
        """
        Assign a genome label.
        """
        if self.itr.env is not None:
            if (
                "baseline" in self.model_label.lower()
                or self.itr.current_genome_num == 0
            ):
                self.genome = None
                self.outdir = str(self.itr.env.contents["BaselineModelResultsDir"])
            elif self.itr.train_genome is not None:
                self.genome = self.itr.train_genome
                self.outdir = str(self.itr.env.contents[f"{self.genome}CompareDir"])
            elif self.itr.current_trio_num is None:
                self.genome = None
                self.outdir = str(self.itr.env.contents["RunDir"])
            else:
                self.genome = self.model_label.split("-")[1]
                self.outdir = str(self.itr.env.contents[f"{self.genome}CompareDir"])

    def find_restart_jobs(self) -> None:
        """
        Collect any SLURM job ids for running tests to avoid submitting a job while it's already running.
        """
        self._ignoring_call_variants = helpers.h.check_if_all_same(
            self.call_variants_jobs, None
        )
        if not self._ignoring_call_variants:
            self._num_to_ignore = len(helpers.h.find_NaN(self.call_variants_jobs))
            select_ckpt_run = helpers.h.find_not_NaN(self.call_variants_jobs)
            if select_ckpt_run:
                self.jobs_to_run = select_ckpt_run
            else:
                self.jobs_to_run = list(range(0, self.itr.total_num_tests))

            self._num_to_run = len(self.jobs_to_run)
            self._run_jobs = True

        elif self.compare_happy_job_nums:
            num_job_ids = len(self.compare_happy_job_nums)
            if num_job_ids == self.itr.total_num_tests:
                self.jobs_to_run = helpers.h.find_not_NaN(self.compare_happy_job_nums)
                self._num_to_run = len(self.jobs_to_run)
                self._num_to_ignore = len(
                    helpers.h.find_NaN(self.compare_happy_job_nums)
                )

                if self.jobs_to_run:
                    self._run_jobs = True
                    for index in self.jobs_to_run:
                        if index is not None:
                            if (
                                isinstance(self.compare_happy_job_nums[index], str)
                                or self.compare_happy_job_nums[index]
                                > self.itr.total_num_tests
                                or self.compare_happy_job_nums[index] is None
                            ):
                                if len(str(self.compare_happy_job_nums[index])) != 8:
                                    self.itr.logger.error(
                                        f"{self.logger_msg}: invalid input for SLURM job ID | {self.compare_happy_job_nums[index]}"
                                    )
                                    self.itr.logger.error(
                                        f"{self.logger_msg}: an 8-digit value must be provided for any number greater than {self.itr.total_num_tests}.\nExiting..."
                                    )
                                    sys.exit(1)
                                self._num_to_run -= 1
                                self._num_to_ignore += 1
                                self._skipped_counter += 1
                                if self._convert_happy_dependencies:
                                    self._convert_happy_dependencies[index] = str(
                                        self.compare_happy_job_nums[index]
                                    )
                else:
                    self._run_jobs = False

                if 0 < self._num_to_ignore < self.itr.total_num_tests:
                    self.itr.logger.info(
                        f"{self.logger_msg}: ignoring {self._num_to_ignore}-of-{self.itr.total_num_tests} SLURM jobs"
                    )
                else:
                    self.itr.logger.info(
                        f"{self.logger_msg}: there are no jobs to re-submit for '{self._phase}'... SKIPPING AHEAD"
                    )
                    self._skip_phase = True
            else:
                if self.itr.debug_mode:
                    self.itr.logger.debug(
                        f"{self.logger_msg}: --running-jobids triggered reprocessing {num_job_ids} job"
                    )
                self.itr.logger.error(
                    f"{self.logger_msg}: incorrect format for 'compare_happy_job_nums'"
                )
                self.itr.logger.error(
                    f"{self.logger_msg}: expected a list of {self.itr.total_num_tests} SLURM jobs (or 'None' as a place holder)"
                )
                self._run_jobs = None
        else:
            self._run_jobs = True
            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"{self.logger_msg}: running job ids were NOT provided"
                )

    def set_test_genome(self, current_test_num: int = 0) -> None:
        """
        Defines print msgs and variables for the genome to compare with hap.py.
        """
        self.test_num = current_test_num
        self.test_logger_msg = f"test{self.test_num}"
        if self.itr.env is not None:
            if f"Test{self.test_num}ReadsBAM" in self.itr.env.contents:
                self.test_genome = None
                return
            else:
                self.test_genome = f"test{self.test_num}"
        else:
            return

        # NOTE: happy only needs the prefix, so
        # do NOT include .vcf.gz extension in output_name!!
        if self.itr.demo_mode:
            self.prefix = f"happy{self.test_num}-no-flags-chr{self.itr.demo_chromosome}"
        else:
            self.prefix = f"happy{self.test_num}-no-flags"

        if self.itr.train_genome is None:
            self.job_name = self.prefix
        else:
            self.job_name = (
                f"{self.prefix}-{self.itr.train_genome}{self.itr.current_trio_num}"
            )

    def benchmark(self) -> None:
        """
        Saves the SLURM job IDs to a file for future resource usage metrics.
        """
        headers = ["AnalysisName", "RunName", "Parent", "Phase", "JobList"]
        if self._convert_happy_dependencies is None:
            deps_string = "None"
        else:
            deps_string = ",".join(filter(None, self._convert_happy_dependencies))
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
            self.benchmarking_file.add_rows(headers, data_dict=data)
        else:
            self.itr.logger.info(
                f"[DRY_RUN] - {self.logger_msg}: benchmarking is active"
            )

    def make_job(self, index: int = 0) -> Union[s.SBATCH, None]:
        """
        Defines the contents of the SLURM job for the 'compare_happy' phase for TrioTrain Pipeline.
        """
        if self.itr.env is None:
            return
        # initialize a SBATCH Object
        self.handler_label = f"{self._phase}: {self.prefix}"

        slurm_job = s.SBATCH(
            self.itr,
            self.job_name,
            self.model_label,
            self.handler_label,
            f"{self.logger_msg} - [{self.test_logger_msg}]",
        )

        if slurm_job.check_sbatch_file():
            if (
                self.compare_happy_job_nums
                and self.compare_happy_job_nums[index] is not None
                and self.overwrite
            ):
                self.itr.logger.info(
                    f"{self.logger_msg}: --overwrite=True, re-writing the existing SLURM job now..."
                )
            else:
                self.itr.logger.info(
                    f"{self.logger_msg} - [{self.test_logger_msg}]: SLURM job file already exists... SKIPPING AHEAD"
                )
                return
        else:
            self.itr.logger.info(
                f"{self.logger_msg} - [{self.test_logger_msg}]: creating job file now... "
            )

        ### ----- NOTE TO SELF: DO NOT USE 'CONDA RUN' WITH APPTAINER HAPPY ----- ###

        # determine if GIAB benchmarking is being performed
        if self.itr.args.first_genome is None:
            additional_flag = " --benchmark "
        else:
            additional_flag = ""

        # define which regions to include when comparing against truth variants
        # under demo mode...
        if self.itr.demo_mode:
            self.command_list = slurm_job._start_conda + [
                "conda activate miniconda_envs/beam_v2.30",
                f"python3 -u scripts/model_training/slurm_compare_hap.py --env-file {self.itr.env.env_file} --train-genome {self.genome} --test-num {self.test_num} --demo --location {self.itr.demo_chromosome}",
            ]

        # and when testing a new model, limit the regions evaluated with hap.py
        elif (
            self.itr.default_region_file is not None
            and self.itr.default_region_file.exists()
        ):
            # NOTE: this should be the autosomes + X chromosome only!
            #       in the default regions file created by the pipeline
            self.command_list = slurm_job._start_conda + [
                "conda activate miniconda_envs/beam_v2.30",
                f"python3 -u scripts/model_training/slurm_compare_hap.py --env-file {self.itr.env.env_file} --train-genome {self.genome} --test-num {self.test_num} --regions-file {str(self.itr.default_region_file)}{additional_flag}",
            ]
        else:
            # if missing a default region, look only at the CallableBED file
            vars = [
                f"Test{self.test_num}CallableBED_Path",
                f"Test{self.test_num}CallableBED_File",
            ]
            try:
                regions_file_path, regions_file_name = self.itr.env.load(*vars)
            except KeyError:
                self.itr.logger.info(
                    f"{self.logger_msg}: env is missing variables for Test{self.test_num}... SKIPPING AHEAD"
                )
                return

            regions = helpers.h.TestFile(
                Path(regions_file_path) / regions_file_name, logger=self.itr.logger
            )
            regions.check_existing()
            if not regions.file_exists:
                self.itr.logger.error(
                    f"{self.test_logger_msg}: a Callable Regions file is required to run Hap.py\nExiting..."
                )
                sys.exit(1)

            self.command_list = slurm_job._start_conda + [
                "conda activate miniconda_envs/beam_v2.30",
                f"python3 -u scripts/model_training/slurm_compare_hap.py --env-file {self.itr.env.env_file} --train-genome {self.genome} --test-num {self.test_num} --regions-file {regions.file}{additional_flag}",
            ]

        slurm_job.create_slurm_job(
            self.handler_label,
            command_list=self.command_list,
            overwrite=self.overwrite,
            **self.slurm_resources[self._phase],
        )

        return slurm_job

    def find_outputs(
        self,
        phase: Union[str, None] = None,
        find_all: bool = False,
        outputs_per_test=11,
    ) -> None:
        """
        Determines if convert_happy phase has completed successfully.
        """
        self.set_genome()
        if phase is None:
            logging_msg = self.logger_msg
        else:
            logging_msg = f"[{self.itr._mode_string}] - [{phase}]"

        # Define the regrex pattern of expected output
        if find_all:
            expected_outputs = int(self.itr.total_num_tests * outputs_per_test)

            # Define the regrex pattern of expected output
            compare_happy_regex = rf"^(happy\d+).+\.(?!out$|\.sh$).+$"
            # This ^ regex says: match if it starts with
            # 'happy#-no-flags', then allow any number of matches
            # between the pattern and the extension
            # finally, exclude any file with a .out or .sh extension
            # which is required for Baseline
        else:
            expected_outputs = outputs_per_test
            compare_happy_regex = rf"^({self.prefix}).+\.(?!out$|\.sh$).+$"
            logging_msg = f"{logging_msg} - [{self.test_logger_msg}]"

        if self.itr.args.debug:
            self.itr.logger.debug(
                f"{logging_msg}: regular expression used | {compare_happy_regex}"
            )

        # Confirm happy outputs do not already exist
        self._outputs_found = None
        (
            existing_results_files,
            self._outputs_found,
            files,
        ) = helpers.h.check_if_output_exists(
            compare_happy_regex,
            "hap.py output files",
            Path(self.outdir),
            logging_msg,
            self.itr.logger,
            debug_mode=self.itr.debug_mode,
            dryrun_mode=self.itr.dryrun_mode,
        )

        if existing_results_files:
            if self.overwrite:
                self._outputs_exist = False
            else:
                missing_files = helpers.h.check_expected_outputs(
                    self._outputs_found,
                    expected_outputs,
                    logging_msg,
                    "hap.py output files",
                    self.itr.logger,
                )
                if missing_files:
                    if find_all:
                        self._num_to_ignore = self._outputs_found
                        self._num_to_run = int(expected_outputs - self._outputs_found)
                    self._outputs_exist = False
                else:
                    self._outputs_exist = True
        else:
            self._outputs_exist = False

    def submit_job(self, dependency_index: int = 0, total_jobs: int = 1) -> None:
        """
        Submits SLURM jobs to the queue.
        """
        if self._outputs_exist:
            self._skipped_counter += 1
            if self._convert_happy_dependencies:
                self._convert_happy_dependencies[dependency_index] = None
        else:
            slurm_job = self.make_job(index=dependency_index)
            if slurm_job is not None:
                if self.itr.dryrun_mode:
                    slurm_job.display_job()
                else:
                    slurm_job.write_job()

            submit_slurm_job = s.SubmitSBATCH(
                self.itr.job_dir,
                f"{self.job_name}.sh",
                self.handler_label,
                self.itr.logger,
                f"{self.logger_msg} - [{self.test_logger_msg}]",
            )
            # If there is a running call-variants job...
            if self.call_variants_jobs and len(self.call_variants_jobs) > 0:
                # ...include it as a dependency
                submit_slurm_job.build_command(
                    self.call_variants_jobs[dependency_index]
                )
            else:
                if self.itr.debug_mode:
                    self.itr.logger.debug(
                        f"{self.logger_msg} - [{self.test_logger_msg}]: calling variants completed, submitting without a SLURM dependency",
                    )
                submit_slurm_job.build_command(None)

            if self.itr.dryrun_mode:
                submit_slurm_job.display_command(
                    current_job=self.job_num,
                    total_jobs=total_jobs,
                    display_mode=self.itr.dryrun_mode,
                )
                if self._convert_happy_dependencies:
                    self._convert_happy_dependencies[
                        dependency_index
                    ] = helpers.h.generate_job_id()
            else:
                submit_slurm_job.display_command(debug_mode=self.itr.debug_mode)
                submit_slurm_job.get_status(
                    current_job=self.job_num,
                    total_jobs=total_jobs,
                    debug_mode=self.itr.debug_mode,
                )
                if self._convert_happy_dependencies and submit_slurm_job.status == 0:
                    self._convert_happy_dependencies[dependency_index] = str(
                        submit_slurm_job.job_number
                    )

                else:
                    self.itr.logger.error(
                        f"{self.logger_msg} - [{self.test_logger_msg}]: unable to submit SLURM job",
                    )
                    if self._convert_happy_dependencies:
                        self._convert_happy_dependencies[dependency_index] = None

    def check_submissions(self) -> None:
        """
        Checks if the SLURM job files were submitted to the SLURM queue successfully.
        """
        if self._skip_phase:
            return

        if (
            self._convert_happy_dependencies
            and len(self._convert_happy_dependencies) != self.itr.total_num_tests
        ):
            self.itr.logger.error(
                f"{self.logger_msg}: only {len(self._convert_happy_dependencies)}-of-{self.itr.total_num_tests} were submitted correctly. Exiting... "
            )
            sys.exit(1)
        compare_results = helpers.h.check_if_all_same(
            self._convert_happy_dependencies, None
        )

        if compare_results is False:
            if (
                self._convert_happy_dependencies
                and len(self._convert_happy_dependencies) == 1
            ):
                if self.itr.dryrun_mode:
                    print(
                        f"============ [DRY_RUN] - {self.logger_msg} Job Number - {self._convert_happy_dependencies} ============"
                    )
                else:
                    print(
                        f"============ {self.logger_msg} Job Number - {self._convert_happy_dependencies} ============"
                    )
            else:
                if self.itr.dryrun_mode:
                    print(
                        f"============ [DRY_RUN] - {self.logger_msg} Job Numbers ============\n{self._convert_happy_dependencies}\n============================================================"
                    )
                else:
                    print(
                        f"============ {self.logger_msg} Job Numbers ============\n{self._convert_happy_dependencies}\n============================================================"
                    )
        else:
            self.itr.logger.error(
                f"{self.logger_msg}: expected SLURM jobs to be submitted, but they were not",
            )
            self._convert_happy_dependencies = None
            self.itr.logger.warning(
                f"{self.logger_msg}: fatal error encountered, unable to proceed further with pipeline.\nExiting... ",
            )
            sys.exit(1)

        if self.track_resources and self.benchmarking_file is not None:
            self.benchmark()

    def run(self) -> Union[List[Union[str, None]], None]:
        """
        Combines all the steps for assessing a DV model into one step.
        """
        self.set_genome()
        self.find_restart_jobs()

        # Determine if we are re-running only demo test
        if self.itr.demo_mode:
            self.set_test_genome(current_test_num=self.itr.total_num_tests)
            self.submit_job()

        # determine if we should avoid certain tests because they are currently running
        elif (
            self.compare_happy_job_nums or not self._ignoring_call_variants
        ) and self._run_jobs is not None:
            if self._num_to_run == 0:
                self._skipped_counter = self._num_to_ignore
                if (
                    self._convert_happy_dependencies
                    and helpers.h.check_if_all_same(
                        self._convert_happy_dependencies, None
                    )
                    is False
                ):
                    self.itr.logger.info(
                        f"{self.logger_msg}: convert_happy dependencies updated to {self._convert_happy_dependencies}"
                    )
                else:
                    self._convert_happy_dependencies = [None]
            else:
                if not self._ignoring_call_variants:
                    self.itr.logger.info(
                        f"{self.logger_msg}: call_variants was submitted...",
                    )

                if self._num_to_run <= self.itr.total_num_tests:
                    self.converting.find_outputs(find_all=True, phase=self._phase)
                    self._outputs_exist = self.converting._outputs_exist
                    self._outputs_found = self.converting._outputs_found
                    self.converting.double_check(phase_to_check=self._phase)

                    if self.overwrite:
                        self.itr.logger.info(
                            f"{self.logger_msg}: re-submitting {self._num_to_run}-of-{self.itr.total_num_tests} SLURM jobs",
                        )
                        if self._outputs_exist:
                            self.itr.logger.info(
                                f"{self.logger_msg}: --overwrite=True, any exiting results files will be re-written..."
                            )
                    else:
                        self.itr.logger.info(
                            f"{self.logger_msg}: submitting {self._num_to_run}-of-{self.itr.total_num_tests} SLURM jobs",
                        )
                elif self._num_to_run == 0:
                    self.itr.logger.info(
                        f"{self.logger_msg}: there are no jobs to re-submit for '{self._phase}'... SKIPPING AHEAD"
                    )
                else:
                    self.itr.logger.error(
                        f"{self.logger_msg}: max number of re-submission SLURM jobs is {self.itr.total_num_tests} but {self._num_to_run} were provided.\nExiting... ",
                    )
                    sys.exit(1)

                for t in self.jobs_to_run:
                    skip_re_runs = helpers.h.check_if_all_same(
                        self.compare_happy_job_nums, None
                    )
                    if skip_re_runs:
                        test_index = t
                    else:
                        test_index = self.compare_happy_job_nums[t]

                    self.job_num = (
                        test_index + 1
                    )  # THIS HAS TO BE +1 to avoid labeling files with test0
                    self.set_test_genome(current_test_num=self.job_num)

                    if self.test_genome is None:
                        continue
                    else:
                        # Indexing of the list of job ids starts with 0
                        self.submit_job(
                            total_jobs=self.itr.total_num_tests,
                            dependency_index=test_index,
                        )

        # Determine if we are submitting all tests
        else:
            if self._skip_phase:
                return

            # determine if jobs need to be submitted
            self.find_outputs(find_all=True)

            if self._outputs_exist:
                return
            for t in range(0, int(self.itr.total_num_tests)):
                self.job_num = t + 1
                # THIS HAS TO BE +1 to avoid labeling files Test0
                self.set_test_genome(current_test_num=self.job_num)
                if self.test_genome is None:
                    continue
                else:
                    self.find_outputs(find_all=False)

                    # re-submit 'compare_happy' if 'call_variants' was re-submitted
                    self.submit_job(
                        dependency_index=t, total_jobs=int(self.itr.total_num_tests)
                    )

        self.check_submissions()
        return self._convert_happy_dependencies
