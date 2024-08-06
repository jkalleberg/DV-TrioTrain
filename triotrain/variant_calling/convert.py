#!/usr/bin/python3
"""
description: contains all of the functions specific to comparing variants against a truth set with hap.py for the TrioTrain pipeline.

usage:
    from convert import ConvertHappy
"""
from dataclasses import dataclass, field
from pathlib import Path
from sys import exit
from typing import List, Union

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
from model_training.slurm.sbatch import SBATCH, SubmitSBATCH
from regex import compile


@dataclass
class ConvertHappy:
    """
    Define what data to store for the 'convert_happy' phase of the TrioTrain Pipeline.
    """

    # required values
    itr: Iteration
    slurm_resources: dict
    model_label: str

    # optional values
    benchmarking_file: Union[Files, None] = None
    compare_happy_jobs: Union[List[Union[str, None]], None] = field(
        default_factory=list
    )
    convert_happy_job_nums: List = field(default_factory=list)
    overwrite: bool = False
    test_genome_metadata: dict = field(default_factory=dict)
    track_resources: bool = False

    # internal, imutable values
    _final_jobs: Union[List[Union[str, None]], None] = field(
        default_factory=list, init=False, repr=False
    )
    _ignoring_compare_happy: bool = field(default=True, init=False,repr=False)
    _jobs_to_run: List[int] = field(default_factory=list, init=False, repr=False)
    _num_to_ignore: int = field(default=0, init=False, repr=False)
    _num_to_run: int = field(default=0, init=False, repr=False)
    _phase: str = field(default="convert_happy", init=False, repr=False)
    _skipped_counter: int = field(default=0, init=False, repr=False)
    _skip_phase: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.track_resources:
            assert (
                self.benchmarking_file is not None
            ), "missing a Files object to save SLURM job numbers"

        self._final_jobs = create_deps(self.itr.total_num_tests)
        if self.itr.train_genome is None:
            self.logger_msg = f"{self.itr._mode_string} - [{self._phase}]"
        else:
            self.logger_msg = (
                f"{self.itr._mode_string} - [{self._phase}] - [{self.itr.train_genome}]"
            )

    def set_genome(self) -> None:
        """
        Defines the genome to have hap.py outputs processed.
        """
        if self.itr.env is not None:
            if self.itr.demo_mode:
                self.genome = self.itr.train_genome
                self.outdir = str(self.itr.env.contents[f"{self.genome}CompareDir"])
            elif (
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
                self.outdir = str(self.itr.env.contents["OutPath"])
            else:
                self.genome = self.model_label.split("-")[1]
                self.outdir = str(self.itr.env.contents[f"{self.genome}CompareDir"])

    def find_restart_jobs(self) -> None:
        """
        Collect any SLURM job ids for running tests to avoid submitting a job while it's already running.
        """
        self._ignoring_compare_happy = check_if_all_same(self.compare_happy_jobs, None)
        self._ignoring_restart_jobs = check_if_all_same(
            self.convert_happy_job_nums, None
        )

        if not self._ignoring_compare_happy:
            self._jobs_to_run = find_not_NaN(self.compare_happy_jobs)
            self._num_to_ignore = len(find_NaN(self.compare_happy_jobs))
            self._num_to_run = len(self._jobs_to_run)

        elif not self._ignoring_restart_jobs:
            self._jobs_to_run = find_not_NaN(self.convert_happy_job_nums)
            self._num_to_run = len(self._jobs_to_run)
            self._num_to_ignore = len(find_NaN(self.convert_happy_job_nums))

        else:
            self._num_to_run = 0
            self._num_to_ignore = self.itr.total_num_tests
            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"{self.logger_msg}: running job ids were NOT provided"
                )

        if 0 < self._num_to_run <= self.itr.total_num_tests:
            if self._jobs_to_run and not self._ignoring_restart_jobs:
                updated_jobs_list = []

                for index in self._jobs_to_run:
                    if is_jobid(self.convert_happy_job_nums[index]):
                        self._num_to_run -= 1
                        self._num_to_ignore += 1
                        self._skipped_counter += 1
                        self._final_jobs[index] = str(
                            self.convert_happy_job_nums[index]
                        )
                    elif is_job_index(
                        self.convert_happy_job_nums[index],
                        max_jobs=self.itr.total_num_tests,
                    ):
                        updated_jobs_list.append(index)

                if updated_jobs_list:
                    self._jobs_to_run = updated_jobs_list

        if self._num_to_ignore == 0:
            return
        elif 0 < self._num_to_ignore < self.itr.total_num_tests:
            self.itr.logger.info(
                f"{self.logger_msg}: ignoring {self._num_to_ignore}-of-{self.itr.total_num_tests} SLURM jobs"
            )
        elif self._num_to_ignore == self.itr.total_num_tests:
            if self.convert_happy_job_nums:
                self.itr.logger.info(
                    f"{self.logger_msg}: completed '{self._phase}'... SKIPPING AHEAD"
                )
        else:
            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"{self.logger_msg}: --running-jobids triggered reprocessing {self._nu} jobs"
                )
            self.itr.logger.error(
                f"{self.logger_msg}: incorrect format for '{self._phase}' SLURM job numbers"
            )
            self.itr.logger.error(
                f"{self.logger_msg}: expected a list of {self.itr.total_num_tests} SLURM jobs (or 'None' as a place holder)"
            )

    def set_test_genome(self, current_test_num: int = 0) -> None:
        """
        Defines print msgs and variables for the genome that was compared with hap.py.
        """
        self.test_num = current_test_num
        if self.itr.env is not None:
            if f"Test{self.test_num}ReadsBAM" in self.itr.env.contents:
                self.test_genome = None
                return
            else:
                self.test_genome = f"test"
        else:
            self.test_genome = None

        # NOTE: happy only needs the prefix, so
        # do NOT include .vcf.gz extension in output_name!!
        self.prefix = f"happy{self.test_num}"
        self.test_name = f"Test{self.test_num}"
        self.test_logger_msg = f"test{self.test_num}"

    def benchmark(self) -> None:
        """
        Saves the SLURM job numbers to a file for future resource usage metrics.
        """
        headers = ["AnalysisName", "RunName", "Parent", "Phase", "JobList"]
        if self._final_jobs is None:
            deps_string = "None"
        else:
            deps_string = ",".join(filter(None, self._final_jobs))
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
            self.itr.logger.info(f"{self.logger_msg}: --keep-jobids=True")

    def make_job(self, index: int = 0) -> Union[SBATCH, None]:
        """
        Define the contents of the SLURM job for the 'convert_happy' phase for TrioTrain Pipeline.
        """
        # initialize a SBATCH Object
        self.handler_label = f"{self._phase}: {self.prefix}"

        if self.itr.train_genome is None:
            self.job_name = f"convert-{self.prefix}"
        else:
            self.job_name = f"convert-{self.prefix}-{self.itr.train_genome}{self.itr.current_trio_num}"

        slurm_job = SBATCH(
            self.itr,
            self.job_name,
            self.model_label,
            self.handler_label,
            f"{self.logger_msg} - [{self.test_logger_msg}]",
        )

        if slurm_job.check_sbatch_file():
            if index < len(self.compare_happy_jobs):
                prior_jobs = self.compare_happy_jobs[index] is not None
            else:
                prior_jobs = False

            if index < len(self.convert_happy_job_nums):
                resub_jobs = self.convert_happy_job_nums[index] is not None
            else:
                resub_jobs = False

            if (prior_jobs or resub_jobs) and self.overwrite:
                self.itr.logger.info(
                    f"{self.logger_msg} - [{self.test_logger_msg}]: --overwrite=True; re-writing the existing SLURM job now... "
                )
            else:
                self.itr.logger.info(
                    f"{self.logger_msg} - [{self.test_logger_msg}]: --overwrite=False; SLURM job file already exists."
                )
                return
        else:
            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"{self.logger_msg} - [{self.test_logger_msg}]: creating job file now... "
                )

        if len(self.test_genome_metadata) > 0:
            if self.itr.demo_mode:
                self.command_list = slurm_job._start_conda + [
                    f"conda run --no-capture-output -p miniconda_envs/beam_v2.30 python3 triotrain/model_training/slurm/process_hap.py --env-file {self.itr.env.env_file} --vcf-file {self.outdir}/{self.prefix}-no-flags-chr{self.itr.demo_chromosome}.vcf.gz --metadata '{self.test_genome_metadata}'",
                ]
            else:
                self.command_list = slurm_job._start_conda + [
                    f"conda run --no-capture-output -p miniconda_envs/beam_v2.30 python3 triotrain/model_training/slurm/process_hap.py --env-file {self.itr.env.env_file} --vcf-file {self.outdir}/{self.prefix}-no-flags.vcf.gz --metadata '{self.test_genome_metadata}'",
                ]
        else:
            if self.itr.demo_mode:
                self.command_list = slurm_job._start_conda + [
                    f"conda run --no-capture-output -p miniconda_envs/beam_v2.30 python3 triotrain/model_training/slurm/process_hap.py --env-file {self.itr.env.env_file} --vcf-file {self.outdir}/{self.prefix}-no-flags-chr{self.itr.demo_chromosome}.vcf.gz",
                ]
            else:
                self.command_list = slurm_job._start_conda + [
                    f"conda run --no-capture-output -p miniconda_envs/beam_v2.30 python3 triotrain/model_training/slurm/process_hap.py --env-file {self.itr.env.env_file} --vcf-file {self.outdir}/{self.prefix}-no-flags.vcf.gz ",
                ]

        slurm_job.create_slurm_job(
            self.handler_label,
            command_list=self.command_list,
            overwrite=self.overwrite,
            **self.slurm_resources[self._phase],
        )
        return slurm_job

    def find_outputs(
        self, phase: Union[str, None] = None, find_all: bool = False, outputs_per_test=2
    ) -> None:
        """
        Determines if convert_happy phase has completed successfully.
        """
        self.set_genome()
        if phase is None:
            logging_msg = self.logger_msg
        else:
            if self.itr.train_genome is None:
                logging_msg = f"{self.itr._mode_string} - [{phase}]"
            else:
                logging_msg = (
                    f"{self.itr._mode_string} - [{phase}] - [{self.itr.train_genome}]"
                )

        # Count how many outputs were made when converting Hap.py VCFs into Metrics Values
        # Define the regrex pattern of expected output
        if phase == "compare_happy":
            self._output_type = "hap.py output file(s)"
        elif phase == "convert_happy":
            self._output_type = "converted hap.py file(s)"
        elif phase == "process_happy":
            self._output_type = "processed hap.py file(s)"
        else:
            self._output_type = f"intermediate metrics file(s)"

        if find_all:
            final_msg = f"all {self._output_type}"
            if phase == "compare_happy":
                self._expected_outputs = int(self.itr.total_num_tests * 11)
                _regex = rf"^(happy\d+).+\.(?![out$|\.sh$]).+$"
            elif phase == "convert_happy":
                self._expected_outputs = self.itr.total_num_tests
                _regex = compile(r"^Test\d+.converted\-metrics\.tsv$")
            else:
                self._expected_outputs = int(
                    self.itr.total_num_tests * outputs_per_test
                )
                _regex = compile(
                    r"^Test\d+.(converted\-|total\.)metrics(\.csv$|\.tsv$)"
                )
        else:
            final_msg = self._output_type
            if phase == "compare_happy":
                self._expected_outputs = 11
                _regex = rf"^({self.prefix}).+\.(?!out$|\.sh$).+$"
            elif phase == "convert_happy":
                self._expected_outputs = 1
                _regex = compile(rf"^{self.test_name}.converted\-metrics\.tsv$")
            elif phase == "process_happy":
                self._expected_outputs = 1
                _regex = compile(rf"^{self.test_name}\.total\.metrics\.csv$")
            else:
                self._expected_outputs = outputs_per_test
                _regex = compile(
                    rf"^{self.test_name}\.(converted\-|total\.)metrics(\.csv$|\.tsv$)"
                )
            logging_msg = f"{logging_msg} - [{self.test_logger_msg}]"

        if self.itr.args.debug:
            self.itr.logger.debug(f"{logging_msg}: regular expression used | {_regex}")

        # Confirm intermediate files do not already exist
        self._outputs_found = None
        (
            existing_results_files,
            self._outputs_found,
            files,
        ) = check_if_output_exists(
            _regex,
            final_msg,
            Path(self.outdir),
            logging_msg,
            self.itr.logger,
            debug_mode=self.itr.debug_mode,
            dryrun_mode=self.itr.dryrun_mode,
        )

        if existing_results_files:
            missing_files = check_expected_outputs(
                self._outputs_found,
                self._expected_outputs,
                logging_msg,
                self._output_type,
                self.itr.logger,
            )

            if missing_files:
                if find_all:
                    self._num_to_ignore = self._outputs_found
                    self._num_to_run = int(self._expected_outputs - self._outputs_found)
                self._outputs_exist = False
            else:
                self._outputs_exist = True
        else:
            self._outputs_exist = False

    def submit_job(
        self,
        msg: str = "sub",
        dependency_index: int = 0,
        total_jobs: int = 1,
        resubmission: bool = False,
    ) -> None:
        """
        Submit SLURM job to the queue.
        """
        if (self._outputs_exist and self.overwrite is False) or (
            self._outputs_exist
            and self._ignoring_restart_jobs
            and self.overwrite is False
        ):
            self._skipped_counter += 1
            self._final_jobs[dependency_index] = None
            if resubmission:
                self.itr.logger.info(
                    f"{self.logger_msg} - [{self.test_logger_msg}]: --overwrite=False; skipping job because found {self._output_type}"
                )
            return

        slurm_job = self.make_job(index=dependency_index)

        if slurm_job is not None:
            if self.itr.dryrun_mode:
                slurm_job.display_job()
            else:
                slurm_job.write_job()

        if not self.overwrite and self._ignoring_compare_happy and resubmission:
            self.itr.logger.info(
                f"{self.logger_msg} - [{self.test_logger_msg}]: --overwrite=False; {msg}mitting job because missing {self._output_type}"
            )

        elif self.overwrite and self._outputs_exist:
            self.itr.logger.info(
                f"{self.logger_msg} - [{self.test_logger_msg}]: --overwrite=True; {msg}mitting job because replacing existing {self._output_type}"
            )

        else:
            self.itr.logger.info(
                f"{self.logger_msg} - [{self.test_logger_msg}]: {msg}mitting job to process hap.py outputs"
            )

        self._slurm_job = SubmitSBATCH(
            self.itr.job_dir,
            f"{self.job_name}.sh",
            self.handler_label,
            self.itr.logger,
            f"{self.logger_msg} - [{self.test_logger_msg}]",
        )

        # If there is a running job...
        if self.compare_happy_jobs and len(self.compare_happy_jobs) > 0:
            # ...include it as a dependency
            self._slurm_job.build_command(self.compare_happy_jobs[dependency_index])
        else:
            self._slurm_job.build_command(None)

        self._slurm_job.display_command(
            current_job=self.job_num,
            total_jobs=total_jobs,
            display_mode=self.itr.dryrun_mode,
        )

        if self.itr.dryrun_mode:
            self._slurm_job.job_number = generate_job_id()
            self._final_jobs[dependency_index] = self._slurm_job.job_number
        else:
            self._slurm_job.get_status(
                current_job=self.job_num,
                total_jobs=total_jobs,
                debug_mode=self.itr.debug_mode,
            )

            if self._slurm_job.status == 0:
                self._final_jobs[dependency_index] = str(self._slurm_job.job_number)
            else:
                self._final_jobs[dependency_index] = None

    def check_submissions(self) -> None:
        """
        Check if the SLURM job files were submitted to the queue successfully.
        """
        convert_results = check_if_all_same(self._final_jobs, None)

        if convert_results is False:
            if len(self._final_jobs) == 1:
                print(
                    f"============ {self.logger_msg} - Job Number - {self._final_jobs} ============"
                )
            else:
                print(
                    f"============ {self.logger_msg} - Job Numbers ============\n{self._final_jobs}\n============================================================"
                )

            if self.track_resources and self.benchmarking_file is not None:
                self.benchmark()
        elif self._skipped_counter != 0:
            if self._skipped_counter == self.itr.total_num_tests:
                self._final_jobs = [None]
        else:
            self.itr.logger.error(
                f"{self.logger_msg}: expected SLURM jobs to be submitted, but they were not",
            )
            self.itr.logger.warning(
                f"{self.logger_msg}: fatal error encountered, unable to proceed further with pipeline.\nExiting... ",
            )
            exit(1)

    def unique_values_in_list_of_lists(self, lst: list) -> list:
        """
        Identify unique values between list
        """
        result = set(x for l in lst for x in l)
        return list(result)

    def double_check(self, phase_to_check: str, find_all: bool = False) -> None:
        """
        Check if we have a converted-metrics file, but are missing the total.metrics file, and re-run convert-happy
        """
        new_jobs_to_run = []

        if self._outputs_found is None:
            difference = self._num_to_ignore
        else:
            difference = self._num_to_ignore - int(self._outputs_found)

        if self._outputs_found != self._num_to_ignore:
            self._num_to_ignore -= difference
            self._num_to_run += difference

        if find_all:
            self.find_outputs(phase=phase_to_check, find_all=find_all)
        else:
            for test in range(0, int(self.itr.total_num_tests)):
                self.job_num = test + 1
                # THIS HAS TO BE +1 to avoid labeling files test0
                self.set_test_genome(current_test_num=self.job_num)
                if self.test_genome is None:
                    continue
                else:
                    self.find_outputs(phase=phase_to_check)
                    if self._outputs_exist is False:
                        new_jobs_to_run.append(test)

            if self._jobs_to_run != new_jobs_to_run:
                unique_runs = self.unique_values_in_list_of_lists(
                    lst=[self._jobs_to_run, new_jobs_to_run]
                )
                self._jobs_to_run = unique_runs

    def run(self) -> List[Union[str, None]]:
        """
        Combines all the steps for comparing model testing results into one step.
        """
        self.set_genome()
        self.find_restart_jobs()

        skip_re_runs = check_if_all_same(self.convert_happy_job_nums, None)

        if skip_re_runs and self._outputs_exist is False:
            msg = "sub"
        else:
            msg = "re-sub"

        # Determine if we are re-running some of the compare jobs
        if not self._ignoring_restart_jobs or not self._ignoring_compare_happy:
            if self._num_to_run == 0:
                self._skipped_counter = self._num_to_ignore
                if (
                    self._final_jobs
                    and check_if_all_same(self._final_jobs, None) is False
                ):
                    self.itr.logger.info(
                        f"{self.logger_msg}: final SLURM jobs updated | '{self._final_jobs}'"
                    )
            else:
                if not self._ignoring_compare_happy:
                    self.itr.logger.info(
                        f"{self.logger_msg}: 'compare_happy' jobs were submitted...",
                    )

                if self._num_to_run > self.itr.total_num_tests:
                    self.itr.logger.error(
                        f"{self.logger_msg}: max number of re-submission SLURM jobs is {self.itr.total_num_tests} but {self._num_to_run} were provided.\nExiting... ",
                    )
                    exit(1)

                for t in self._jobs_to_run:
                    if skip_re_runs:
                        test_index = t
                    else:
                        test_index = self.convert_happy_job_nums[t]

                    self.job_num = (
                        test_index + 1
                    )  # THIS HAS TO BE +1 to avoid labeling files Test0

                    self.set_test_genome(current_test_num=self.job_num)

                    if self.test_genome is None:
                        continue
                    else:
                        # Indexing of the list of job ids starts with 0
                        self.submit_job(
                            msg=msg,
                            total_jobs=self.itr.total_num_tests,
                            dependency_index=test_index,
                            resubmission=True,
                        )

        # Determine if we are submitting all tests
        else:
            if self._outputs_exist:
                return self._final_jobs

            for test_index in range(0, int(self.itr.total_num_tests)):
                self.job_num = (
                    test_index + 1
                )  # THIS HAS TO BE +1 to avoid labeling files Test0

                self.set_test_genome(current_test_num=self.job_num)
                if self.test_genome is None:
                    continue
                else:
                    # re-submit 'convert_happy' if 'compare_happy' was re-run
                    self.submit_job(
                        msg=msg,
                        total_jobs=int(self.itr.total_num_tests),
                        dependency_index=test_index,
                    )

        self.check_submissions()
        return self._final_jobs
