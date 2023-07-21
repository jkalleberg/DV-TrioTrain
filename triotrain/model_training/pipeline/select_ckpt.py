#!/usr/bin/python3
"""
description: contains all of the functions specific to selecting a new model of TrioTrain.

usage:
    from select_ckpt import SelectCheckpoint
"""
from dataclasses import dataclass, field
from sys import exit
from typing import List, Union

from helpers.environment import Env
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
from regex import compile


@dataclass
class SelectCheckpoint:
    """
    Define what data to store for the select_ckpt phase of the TrioTrain Pipeline.
    """

    # required values
    itr: Iteration
    slurm_resources: dict
    model_label: str

    # optional values
    benchmarking_file: Union[WriteFiles, None] = None
    overwrite: bool = False
    select_ckpt_job_num: List = field(default_factory=list)
    track_resources: bool = False
    train_eval_job_num: List[Union[str, None]] = field(default_factory=list)

    # internal, imutable values
    _model_testing_dependency: List[Union[str, None]] = field(
        default_factory=list, init=False, repr=False
    )
    _ignoring_training: bool = field(default=True, init=False, repr=False)
    _outputs_exist: bool = field(default=False, init=False, repr=False)
    _phase: str = field(default="select_ckpt", init=False, repr=False)
    _skipped_counter: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        self.logger_msg = (
            f"{self.itr._mode_string} - [{self._phase}] - [{self.itr.train_genome}]"
        )
        if self.track_resources:
            assert (
                self.benchmarking_file is not None
            ), "unable to proceed, missing a WriteFiles object to save SLURM job numbers"

        self._model_testing_dependency = create_deps(1)

    def find_restart_jobs(self) -> None:
        """
        Collect any SLURM job ids for running tests to avoid
        submitting a job while it's already running
        """
        self._ignoring_training = check_if_all_same(self.train_eval_job_num, None)
        self._ignoring_restart_jobs = check_if_all_same(self.select_ckpt_job_num, None)

        if not self._ignoring_training:
            self._jobs_to_run = [0]
            self._num_to_ignore = 0
            self._num_to_run = 1

        elif not self._ignoring_restart_jobs:
            self._jobs_to_run = find_not_NaN(self.select_ckpt_job_num)
            self._num_to_run = len(self._jobs_to_run)
            self._num_to_ignore = len(find_NaN(self.select_ckpt_job_num))

        else:
            self._num_to_run = 0
            self._num_to_ignore = 1
            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"{self.logger_msg}: running job ids were NOT provided"
                )

        if self._num_to_run == 1:
            if not self._ignoring_restart_jobs:
                updated_jobs_list = []
                for index in self._jobs_to_run:
                    if is_jobid(self.train_eval_job_num[index]):
                        self._num_to_run -= 1
                        self._num_to_ignore += 1
                        self._model_testing_dependency[0] = str(
                            self.select_ckpt_job_num[index]
                        )
                    elif is_job_index(self.train_eval_job_num[index]):
                        updated_jobs_list.append(index)

                if updated_jobs_list:
                    self.jobs_to_run = updated_jobs_list

        elif self._num_to_ignore == 1:
            print("SELECT CKPT JOB:", self.select_ckpt_job_num)
            breakpoint()
            self.itr.logger.info(
                f"{self.logger_msg}: there are no jobs to re-submit for '{self._phase}'... SKIPPING AHEAD"
            )

        else:
            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"{self.logger_msg}: --running-jobids triggered reprocessing {self._num_to_run} jobs"
                )
            self.itr.logger.error(
                f"{self.logger_msg}: incorrect format for 'train_eval' SLURM job number"
            )
            self.itr.logger.error(
                f"{self.logger_msg}: expected a list of 1 SLURM jobs (or 'None' as a place holder)"
            )

    def find_outputs(
        self, number_outputs_expected: int = 3, phase: Union[str, None] = None
    ) -> None:
        """
        Determines if select_ckpt phase has completed successfully.
        """
        if phase is None:
            logging_msg = self.logger_msg
        else:
            logging_msg = (
                f"{self.itr._mode_string} - [{phase}] - [{self.itr.train_genome}]"
            )

        self.find_selected_ckpt_vars(phase=phase)

        if self.ckpt_selected:
            self.find_selected_ckpt_files(phase=phase)
            missing_files = check_expected_outputs(
                self.num_model_files_found,
                number_outputs_expected,
                logging_msg,
                "new model weights files",
                self.itr.logger,
            )
            if missing_files:
                self._outputs_exist = False
            else:
                self._outputs_exist = True
        else:
            self._outputs_exist = False

    def benchmark(self) -> None:
        """
        Save the SLURM job numbers to a file for future resource usage metrics.
        """
        headers = ["AnalysisName", "RunName", "Parent", "Phase", "JobList"]
        deps_string = ",".join(filter(None, self._model_testing_dependency))
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
                    f"{self.logger_msg} - [{self.itr.train_genome}]: benchmarking is active"
                )

    def make_job(self) -> Union[SBATCH, None]:
        """
        Define the contents of the SLURM job for selecting the next checkpoint for TrioTrain Pipeline.
        """
        if self.itr.env is None:
            return
        # initialize a SBATCH Object
        self.job_name = (
            f"select-ckpt-{self.itr.train_genome}{self.itr.current_trio_num}"
        )
        self.handler_label = f"{self._phase}: {self.itr.train_genome}"

        slurm_job = SBATCH(
            self.itr,
            self.job_name,
            self.model_label,
            self.handler_label,
            self.logger_msg,
        )

        if slurm_job.check_sbatch_file():
            if (
                self.select_ckpt_job_num
                and self.select_ckpt_job_num[0] is not None
                and self.overwrite
            ) or (not self._ignoring_training and self.overwrite):
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

        # MOVING PARSE EVAL METRICS HERE,
        # in case eval job doesn't finish
        parse_metrics_command_list = slurm_job._start_conda + [
            f"numEvals=$(ls {self.itr.train_dir}/eval_Child| grep 'model\.ckpt\-[0-9]\+\.metrics' | wc -l)",
            'echo "SUCCESS: Performed ${numEvals} evaluations"',
            'echo "INFO: Parsing evaluation metrics:"',
            f"conda run --no-capture-output -p miniconda_envs/beam_v2.30 python3 triotrain/model_training/slurm/parse_metrics.py --env-file {self.itr.env.env_file} --genome {self.itr.train_genome}",
        ]

        # Selecting the next checkpoint
        if (
            self.itr.next_genome is not None
            and self.itr.current_genome_num is not None
            and self.itr.next_trio_num is not None
        ):
            command_list = parse_metrics_command_list + [
                f"conda run --no-capture-output -p miniconda_envs/beam_v2.30 python3 triotrain/model_training/slurm/select_ckpt.py --next-genome {self.itr.next_genome} --next-run {self.itr.next_trio_num} --current-ckpt {self.itr.train_dir}/eval_Child/best_checkpoint.txt --env-file {self.itr.env.env_file}",
            ]
        else:
            command_list = parse_metrics_command_list + [
                f"conda run --no-capture-output -p miniconda_envs/beam_v2.30 python3 triotrain/model_training/slurm/select_ckpt.py --next-genome None --next-run None --current-ckpt {self.itr.train_dir}/eval_Child/best_checkpoint.txt --env-file {self.itr.env.env_file}",
            ]

        slurm_job.create_slurm_job(
            self.handler_label,
            command_list=command_list,
            overwrite=self.overwrite,
            **self.slurm_resources[self._phase],
        )
        return slurm_job

    def find_selected_ckpt_vars(self, phase: Union[str, None] = None) -> None:
        """
        Determine if selected checkpoint has been identified previously and saved as a variable in the env file
        """
        if phase is None:
            logger_msg = self.logger_msg
        else:
            logger_msg = (
                f"{self.itr._mode_string} - [{phase}] - [{self.itr.train_genome}]"
            )

        # confirm if select-ckpt job has already finished correctly
        if (
            self.itr.env is not None
            and f"{self.itr.train_genome}TestCkptName" in self.itr.env.contents
        ):
            self.itr.logger.info(
                f"{logger_msg}: {self.itr.train_genome}{self.itr.current_trio_num} testing checkpoint exits... SKIPPING AHEAD"
            )
            self.ckpt_name = self.itr.env.contents[
                f"{self.itr.train_genome}TestCkptName"
            ]
            # confirm if new ckpt was saved for next training round correctly
            if self.itr.next_genome is not None and self.itr.next_trio_num is not None:
                if self.itr.next_trio_num == self.itr.current_trio_num:
                    if f"{self.itr.next_genome}StartCkptName" in self.itr.env.contents:
                        self.ckpt_selected = True
                        self.itr.logger.info(
                            f"{logger_msg}: {self.itr.next_genome}{self.itr.next_trio_num} starting checkpoint exists... SKIPPING AHEAD"
                        )
                    else:
                        self.ckpt_selected = False
                        self.itr.logger.info(
                            f"{logger_msg}: but {self.itr.next_genome}{self.itr.next_trio_num} starting checkpoint does not"
                        )
                else:
                    current_env_str = self.itr.env.env_path.name
                    analysis_name = current_env_str.split("-")[0]
                    next_env_file = (
                        f"envs/{analysis_name}-run{self.itr.next_trio_num}.env"
                    )
                    next_env = Env(
                        next_env_file,
                        self.itr.logger,
                        dryrun_mode=self.itr.args.dry_run,
                    )

                    if f"{self.itr.next_genome}StartCkptName" in next_env.contents:
                        self.ckpt_selected = True
                        self.itr.logger.info(
                            f"{logger_msg}: {self.itr.next_genome}{self.itr.next_trio_num} starting checkpoint exits... SKIPPING AHEAD"
                        )
                    else:
                        self.ckpt_selected = False
                        self.itr.logger.info(
                            f"{logger_msg}: but {self.itr.next_genome}{self.itr.next_trio_num} starting checkpoint does not"
                        )
        else:
            self.ckpt_selected = False
            self.itr.logger.info(f"{logger_msg}: testing checkpoint does not exist")

        self._outputs_exist = self.ckpt_selected

    def find_selected_ckpt_files(self, phase: Union[str, None] = None) -> None:
        """
        Determine if the new model weight files exist
        """
        if phase is None:
            logger_msg = self.logger_msg
        else:
            logger_msg = f"{self.itr._mode_string} - [{phase}]"
        # confirm model weights files are present
        model_weights_pattern = compile(f"{self.ckpt_name}.*")

        # Confirm if files do not already exist
        (
            self.existing_model_weights,
            self.num_model_files_found,
            model_weights_files,
        ) = check_if_output_exists(
            model_weights_pattern,
            "new model weights files",
            self.itr.train_dir,
            logger_msg,
            self.itr.logger,
            debug_mode=self.itr.debug_mode,
            dryrun_mode=self.itr.dryrun_mode,
        )

    def submit_job(self, resubmission: bool = False) -> None:
        """
        Submit SLURM jobs to queue.
        """
        if not self.overwrite and self._outputs_exist:
            self._skipped_counter += 1
            if resubmission:
                self.itr.logger.info(
                    f"{self.logger_msg}: --overwrite=False; skipping job because found best checkpoint file"
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
                if self._ignoring_training:
                    self.itr.logger.info(
                        f"{self.logger_msg}: --overwrite=False; re-submitting job because missing best checkpoint file"
                    )
            else:
                self.itr.logger.info(
                    f"{self.logger_msg}: submitting job to find the best checkpoint"
                )
        else:
            if self._outputs_exist:
                self.itr.logger.info(
                    f"{self.logger_msg}: --overwrite=True; re-submitting job because replacing existing best checkpoint"
                )
            else:
                self.itr.logger.info(
                    f"{self.logger_msg}: submitting job to find the best checkpoint"
                )

        if self.itr.current_genome_dependencies[3] is None:
            # submit the training eval job to queue
            slurm_job = SubmitSBATCH(
                self.itr.job_dir,
                f"{self.job_name}.sh",
                self.handler_label,
                self.itr.logger,
                self.logger_msg,
            )
            slurm_job.build_command(
                prior_job_number=self.train_eval_job_num, allow_dep_failure=True
            )
            if self.itr.dryrun_mode:
                slurm_job.display_command(display_mode=self.itr.dryrun_mode)
                self._model_testing_dependency[0] = generate_job_id()
                self.itr.current_genome_dependencies[
                    3
                ] = self._model_testing_dependency[0]
                self.itr.next_genome_dependencies[2] = self._model_testing_dependency[0]

            else:
                slurm_job.display_command(debug_mode=self.itr.debug_mode)
                slurm_job.get_status(debug_mode=self.itr.debug_mode)

                if slurm_job.status == 0:
                    self._model_testing_dependency[0] = slurm_job.job_number
                    self.itr.current_genome_dependencies[3] = slurm_job.job_number
                    self.itr.next_genome_dependencies[2] = slurm_job.job_number
                else:
                    self.itr.logger.error(
                        f"{self.logger_msg}: unable to submit SLURM job",
                    )
                    self._model_testing_dependency[0] = None
                    self.itr.current_genome_dependencies[3] = None
                    self.itr.next_genome_dependencies[2] = None

    def check_submission(self) -> None:
        """
        Check if the SLURM job file was submitted to the SLURM queue successfully
        """
        select_ckpt_results = check_if_all_same(self._model_testing_dependency, None)
        if select_ckpt_results is False:
            print(
                f"============ {self.logger_msg} Job Number - {self._model_testing_dependency} ============"
            )
        elif self._skipped_counter == 1:
            self._model_testing_dependency = [None]
        else:
            self.itr.logger.warning(
                f"{self.logger_msg}: expected SLURM jobs to be submitted, but they were not",
            )
            self.itr.logger.warning(
                f"{self.logger_msg}: fatal error encountered, unable to proceed further with pipeline\nExiting... ",
            )
            exit(1)

        if self.track_resources and self.benchmarking_file is not None:
            self.benchmark()

    def run(self) -> Iteration:
        """
        Combine all the steps required to submit a job to SLURM queue into one step
        """
        if self.itr.current_genome_dependencies[2] is None:
            if (
                self.itr.current_genome_num is not None
                and self.itr.current_genome_num != 0
            ):
                self.itr.logger.info(
                    f"{self.logger_msg}: no additional dependencies are required because missing a select_ckpt job number for prior iteration"
                )
        else:
            self.itr.logger.info(
                f"{self.logger_msg}: prior iteration select-ckpt job number | '{self.itr.current_genome_dependencies[2]}'"
            )

        self.find_restart_jobs()

        # determine if we are re-running select-ckpt
        if self.select_ckpt_job_num or not self._ignoring_training:
            if self._num_to_run == 0:
                self._skipped_counter = self._num_to_ignore
                if (
                    self._model_testing_dependency
                    and self._model_testing_dependency[0] is not None
                ):
                    self.itr.logger.info(
                        f"{self.logger_msg}: call_variants dependency updated | '{self._model_testing_dependency}'"
                    )
                else:
                    self._model_testing_dependency[0] = None
            else:
                if not self._ignoring_training:
                    self.itr.logger.info(
                        f"{self.logger_msg}: train_eval job was submitted...",
                    )

                skip_re_runs = check_if_all_same(self.train_eval_job_num, None)

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

                self.find_outputs()
                self.submit_job(resubmission=True)

        # or running it for the first time
        else:
            if self._skip_phase:
                return
            self.find_outputs()
            self.submit_job()

        self.check_submission()
        return self.itr
