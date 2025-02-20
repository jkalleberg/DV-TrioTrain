#!/usr/bin/python3
"""
description: contains all of the functions specific to comparing variants against a truth set with hap.py for the TrioTrain pipeline.

usage:
    from compare import CompareHappy
"""
from dataclasses import dataclass, field
from pathlib import Path
from sys import exit
from typing import List, Union

from helpers.files import TestFile, Files
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
from variant_calling.convert import ConvertHappy


@dataclass
class CompareHappy:
    """
    Define what data to store for the compare_happy phase of the TrioTrain Pipeline.
    """

    # required values
    itr: Iteration
    slurm_resources: dict
    model_label: str

    # optional values
    benchmarking_file: Union[Files, None] = None
    call_variants_jobs: Union[List[Union[str, None]], None] = field(
        default_factory=list
    )
    compare_happy_job_nums: List = field(default_factory=list)
    overwrite: bool = False
    track_resources: bool = False
    create_plot: bool = False

    # internal, imutable values
    _convert_happy_dependencies: Union[List[Union[str, None]], None] = field(
        default_factory=list, init=False, repr=False
    )
    _ignoring_call_variants: bool = field(default=True, init=False, repr=False)
    _phase: str = field(default="compare_happy", init=False, repr=False)
    _skipped_counter: int = field(default=0, init=False, repr=False)
    _skip_phase: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        self._convert_happy_dependencies = create_deps(self.itr.total_num_tests)

        self.converting = ConvertHappy(
            itr=self.itr,
            slurm_resources=self.slurm_resources,
            model_label=self.model_label,
        )
        if self._phase in self.slurm_resources.keys():
            self.n_parts = self.slurm_resources[self._phase]["ntasks"]
        else:
            self.n_parts = self.slurm_resources["ntasks"]

        if self.itr.train_genome is None:
            self.logger_msg = f"{self.itr._mode_string} - [{self._phase}]"
        else:
            self.logger_msg = (
                f"{self.itr._mode_string} - [{self._phase}] - [{self.itr.train_genome}]"
            )

        if self.track_resources:
            assert (
                self.benchmarking_file is not None
            ), "missing a Files object to save SLURM job numbers"

        if self.itr.env is not None:
            if "N_Parts" not in self.itr.env.contents:
                self.itr.env.add_to(
                    "N_Parts",
                    str(self.n_parts),
                    dryrun_mode=self.itr.dryrun_mode,
                    msg=self.logger_msg,
                )

    def set_genome(self, outdir: Union[str, Path, None] = None) -> None:
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
            elif self.itr.current_trio_num is None:
                self.genome = None
                self.outdir = str(self.itr.env.contents["OutPath"])
            else:
                self.genome = self.itr.train_genome
                self.outdir = str(self.itr.env.contents[f"{self.genome}CompareDir"])
        elif outdir is not None:
            self.genome = None
            self.outdir = str(outdir)
        else:
            self.genome = None
            self.outdir = None

    def find_restart_jobs(self) -> None:
        """
        Collect any SLURM job ids for running tests to avoid submitting a job while it's already running.
        """
        self._ignoring_call_variants = check_if_all_same(self.call_variants_jobs, None)
        self._ignoring_restart_jobs = check_if_all_same(
            self.compare_happy_job_nums, None
        )

        if not self._ignoring_call_variants:
            self._jobs_to_run = find_not_NaN(self.call_variants_jobs)
            self._num_to_run = len(self._jobs_to_run)
            self._num_to_ignore = len(find_NaN(self.call_variants_jobs))

        elif not self._ignoring_restart_jobs:
            self._jobs_to_run = find_not_NaN(self.compare_happy_job_nums)
            self._num_to_run = len(self._jobs_to_run)
            self._num_to_ignore = len(find_NaN(self.compare_happy_job_nums))

        else:
            self._jobs_to_run = None
            self._num_to_run = 0
            self._num_to_ignore = self.itr.total_num_tests

        if 0 < self._num_to_run <= self.itr.total_num_tests:
            if self._jobs_to_run and not self._ignoring_restart_jobs:
                updated_jobs_list = []

                for index in self._jobs_to_run:
                    if is_jobid(self.compare_happy_job_nums[index]):
                        self._num_to_run -= 1
                        self._num_to_ignore += 1
                        self._skipped_counter += 1
                        self._convert_happy_dependencies[index] = str(
                            self.compare_happy_job_nums[index]
                        )
                    elif is_job_index(
                        self.compare_happy_job_nums[index],
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
            if self.compare_happy_job_nums:
                self.itr.logger.info(
                    f"{self.logger_msg}: completed '{self._phase}'... SKIPPING AHEAD"
                )
        else:
            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"{self.logger_msg}: --running-jobids triggered reprocessing {self._num_to_run} jobs"
                )
            self.itr.logger.error(
                f"{self.logger_msg}: incorrect format for '{self._phase}' SLURM job numbers"
            )
            self.itr.logger.error(
                f"{self.logger_msg}: expected a list of {self.itr.total_num_tests} SLURM jobs (or 'None' as a place holder)"
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
        Saves the SLURM job numbers to a file for future resource usage metrics.
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
            self.itr.logger.info(f"{self.logger_msg}: --keep-jobids=True")

    def make_job(self, index: int = 0) -> Union[SBATCH, None]:
        """
        Defines the contents of the SLURM job for the 'compare_happy' phase for TrioTrain Pipeline.
        """
        if self.itr.env is None:
            return
        # initialize a SBATCH Object
        self.handler_label = f"{self._phase}: {self.prefix}"

        slurm_job = SBATCH(
            self.itr,
            self.job_name,
            self.model_label,
            self.handler_label,
            f"{self.logger_msg} - [{self.test_logger_msg}]",
        )

        if slurm_job.check_sbatch_file():
            if index < len(self.call_variants_jobs):
                prior_jobs = self.call_variants_jobs[index] is not None
            else:
                prior_jobs = False

            if index < len(self.compare_happy_job_nums):
                resub_jobs = self.compare_happy_job_nums[index] is not None
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

        ### ----- NOTE TO SELF: DO NOT USE 'CONDA RUN' WITH APPTAINER HAPPY ----- ###

        # determine if GIAB benchmarking is being performed
        if "first_genome" not in self.itr.args or self.itr.args.first_genome is None:
            additional_flag = " --benchmark"
        else:
            additional_flag = ""

        # define which regions to include when comparing against truth variants
        # under demo mode...
        if self.itr.demo_mode:
            self.command_list = slurm_job._start_conda + [
                "conda activate miniconda_envs/beam_v2.30",
                f"python3 -u triotrain/model_training/slurm/compare_hap.py --env-file {self.itr.env.env_file} --train-genome {self.genome} --test-num {self.test_num} --demo --location {self.itr.demo_chromosome}",
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
                f"python3 -u triotrain/model_training/slurm/compare_hap.py --env-file {self.itr.env.env_file} --train-genome {self.genome} --test-num {self.test_num} --regions-file {str(self.itr.default_region_file)}{additional_flag}",
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

            regions = TestFile(
                Path(regions_file_path) / regions_file_name, logger=self.itr.logger
            )
            regions.check_existing()
            if not regions.file_exists:
                self.itr.logger.error(
                    f"{self.test_logger_msg}: a Callable Regions file is required to run Hap.py\nExiting..."
                )
                exit(1)

            self.command_list = slurm_job._start_conda + [
                "conda activate miniconda_envs/beam_v2.30",
                f"python3 -u triotrain/model_training/slurm/compare_hap.py --env-file {self.itr.env.env_file} --train-genome {self.genome} --test-num {self.test_num} --regions-file {regions.file}{additional_flag}",
            ]
        
        if self.create_plot:
            self.command_list.append(f"python3 triotrain/visualize/plot_PR_ROC.py -I {str(self.outdir)} -O {str(self.outdir)}")

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
            if self.itr.train_genome is None:
                logging_msg = f"{self.itr._mode_string} - [{phase}]"
            else:
                logging_msg = (
                    f"{self.itr._mode_string} - [{phase}] - [{self.itr.train_genome}]"
                )

        # Define the regrex pattern of expected output
        if find_all:
            msg = "all hap.py output files"
            self._expected_outputs = int(self.itr.total_num_tests * outputs_per_test)

            # Define the regrex pattern of expected output
            compare_happy_regex = rf"^(happy\d+).+\.(?![out$|\.sh$]).+$"
            # This ^ regex says: match if it starts with
            # 'happy#-no-flags', then allow any number of matches
            # between the pattern and the extension
            # finally, exclude any file with a .out or .sh extension
            # which is required for Baseline
        else:
            msg = "hap.py output files"
            self._expected_outputs = outputs_per_test
            compare_happy_regex = rf"^({self.prefix}).+\.(?![out$|\.sh$]).+$"
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
        ) = check_if_output_exists(
            compare_happy_regex,
            msg,
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
                "hap.py output files",
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
        Submits SLURM jobs to the queue.
        """
        if (self._outputs_exist and self.overwrite is False) or (
            self._outputs_exist
            and self._ignoring_restart_jobs
            and self.overwrite is False
        ):
            self._skipped_counter += 1
            self._convert_happy_dependencies[dependency_index] = None
            if resubmission:
                self.itr.logger.info(
                    f"{self.logger_msg} - [{self.test_logger_msg}]: --overwrite=False; skipping job because found DeepVariant VCF file"
                )
            return

        slurm_job = self.make_job(index=dependency_index)

        if slurm_job is not None:
            if self.itr.dryrun_mode:
                slurm_job.display_job()
            else:
                slurm_job.write_job()

        if not self.overwrite and self._ignoring_call_variants and resubmission:
            self.itr.logger.info(
                f"{self.test_logger_msg}: --overwrite=False; {msg}mitting job because missing hap.py output files"
            )

        elif self.overwrite and self._outputs_exist:
            self.itr.logger.info(
                f"{self.logger_msg} - [{self.test_logger_msg}]: --overwrite=True; {msg}mitting job because replacing existing hap.py output files"
            )

        else:
            self.itr.logger.info(
                f"{self.logger_msg} - [{self.test_logger_msg}]: {msg}mitting job to compare results using hap.py"
            )

        self._slurm_job = SubmitSBATCH(
            self.itr.job_dir,
            f"{self.job_name}.sh",
            self.handler_label,
            self.itr.logger,
            f"{self.logger_msg} - [{self.test_logger_msg}]",
        )

        # If there is a running call-variants job...
        if self.call_variants_jobs and len(self.call_variants_jobs) > 0:
            # ...include it as a dependency
            self._slurm_job.build_command(self.call_variants_jobs[dependency_index])
        else:
            self._slurm_job.build_command(None)

        self._slurm_job.display_command(
            current_job=self.job_num,
            total_jobs=total_jobs,
            display_mode=self.itr.dryrun_mode,
        )

        if self.itr.dryrun_mode:
            self._slurm_job.job_number = generate_job_id()
            self._convert_happy_dependencies[dependency_index] = self._slurm_job.job_number
        else:
            self._slurm_job.get_status(
                current_job=self.job_num,
                total_jobs=total_jobs,
                debug_mode=self.itr.debug_mode,
            )

            if self._slurm_job.status == 0:
                self._convert_happy_dependencies[dependency_index] = (
                    self._slurm_job.job_number
                )
            else:
                self.itr.logger.warning(
                    f"{self.logger_msg} - [{self.test_logger_msg}]: unable to {msg}mit SLURM job",
                )
                self._convert_happy_dependencies[dependency_index] = None

    def check_submissions(self) -> None:
        """
        Checks if the SLURM job files were submitted to the SLURM queue successfully.
        """
        compare_results = check_if_all_same(self._convert_happy_dependencies, None)

        if compare_results is False:
            if (
                self._convert_happy_dependencies
                and len(self._convert_happy_dependencies) == 1
            ):
                print(
                    f"============ {self.logger_msg} Job Number - {self._convert_happy_dependencies} ============"
                )
            else:
                print(
                    f"============ {self.logger_msg} Job Numbers ============\n{self._convert_happy_dependencies}\n============================================================"
                )

            if self.track_resources and self.benchmarking_file is not None:
                self.benchmark()
        elif self._skipped_counter != 0:
            if self._skipped_counter == self.itr.total_num_tests:
                self._compare_dependencies = None
        else:
            self.itr.logger.error(
                f"{self.logger_msg}: expected SLURM jobs to be submitted, but they were not",
            )
            self._convert_happy_dependencies = None
            self.itr.logger.warning(
                f"{self.logger_msg}: fatal error encountered, unable to proceed further with pipeline.\nExiting... ",
            )
            exit(1)

    def run(self) -> Union[List[Union[str, None]], None]:
        """
        Combines all the steps for assessing a DV model into one step.
        """
        self.set_genome()
        self.find_restart_jobs()

        skip_re_runs = check_if_all_same(self.compare_happy_job_nums, None)

        if skip_re_runs and self._outputs_exist is False:
            msg = "sub"
        else:
            msg = "re-sub"

        # Determine if we are re-running some of the compare jobs
        if not self._ignoring_restart_jobs or not self._ignoring_call_variants:
            if self._num_to_run == 0:
                self._skipped_counter = self._num_to_ignore
                if (
                    self._convert_happy_dependencies
                    and check_if_all_same(self._convert_happy_dependencies, None)
                    is False
                ):
                    self.itr.logger.info(
                        f"{self.logger_msg}: 'convert_happy' dependencies updated | '{self._convert_happy_dependencies}'"
                    )
                else:
                    self._convert_happy_dependencies = None
            else:
                if not self._ignoring_call_variants:
                    self.itr.logger.info(
                        f"{self.logger_msg}: 'call_variants' jobs were submitted...",
                    )

                if self._num_to_run <= self.itr.total_num_tests:
                    if self._expected_outputs > self._outputs_found > 0:
                        self.converting._outputs_found = self._outputs_found
                        self.converting.double_check(phase_to_check="process_happy")
                else:
                    self.itr.logger.error(
                        f"{self.logger_msg}: max number of re-submission SLURM jobs is {self.itr.total_num_tests} but {self._num_to_run} were provided.\nExiting... ",
                    )
                    exit(1)

                for t in self._jobs_to_run:
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
                            msg=msg,
                            total_jobs=self.itr.total_num_tests,
                            dependency_index=test_index,
                            resubmission=True,
                        )

        # Determine if we are submitting all tests
        else:
            if self._outputs_exist:
                return self._convert_happy_dependencies

            for t in range(0, int(self.itr.total_num_tests)):
                self.job_num = t + 1
                # THIS HAS TO BE +1 to avoid labeling files Test0
                self.set_test_genome(current_test_num=self.job_num)

                if self.test_genome is None:
                    continue
                else:
                    self.find_outputs()
                    self.submit_job(
                        msg=msg,
                        dependency_index=t,
                        total_jobs=int(self.itr.total_num_tests),
                    )

        self.check_submissions()
        return self._convert_happy_dependencies
