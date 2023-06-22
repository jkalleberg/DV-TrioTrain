#!/usr/bin/python3
"""
description: contains all of the functions specific to selecting a new model of TrioTrain.

usage:
    from select_ckpt import SelectCheckpoint
"""
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Union

from regex import compile

# get the relative path to the triotrain/ dir
h_path = str(Path(__file__).parent.parent.parent)
sys.path.append(h_path)
import helpers
import model_training.slurm as s


@dataclass
class SelectCheckpoint:
    """
    Define what data to store for the select_ckpt phase of the TrioTrain Pipeline.
    """

    # required values
    itr: helpers.Iteration
    slurm_resources: dict
    model_label: str

    # optional values
    benchmarking_file: Union[helpers.h.WriteFiles, None] = None
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
        self.logger_msg = f"[{self.itr._mode_string}] - [{self._phase}]"
        if self.track_resources:
            assert (
                self.benchmarking_file is not None
            ), "unable to proceed, missing a h.WriteFiles object to save SLURM job IDs"

        self._model_testing_dependency = helpers.h.create_deps(1)

    def find_restart_jobs(self) -> None:
        """
        Collect any SLURM job ids for running tests to avoid
        submitting a job while it's already running
        """
        self._ignoring_training = helpers.h.check_if_all_same(
            self.train_eval_job_num, None
        )

        if not self._ignoring_training:
            self.itr.logger.info(f"{self.logger_msg}: training was submitted...")
            self._num_to_ignore = 0
            self._num_to_run = 1
            self._run_jobs = True

        elif self.select_ckpt_job_num:
            if self.overwrite and self._outputs_exist:
                self.itr.logger.info(
                    f"{self.logger_msg}: --overwrite=True, any exiting results files will be re-written..."
                )
            num_job_ids = len(self.select_ckpt_job_num)
            if num_job_ids == 1:
                jobs_to_run = helpers.h.find_not_NaN(self.select_ckpt_job_num)
                jobs_to_ignore = helpers.h.find_NaN(self.select_ckpt_job_num)
                self._num_to_run = len(jobs_to_run)
                self._num_to_ignore = len(jobs_to_ignore)
                self._model_testing_dependency = helpers.h.create_deps(1)
                if jobs_to_run:
                    self._run_jobs = True
                    for index in jobs_to_run:
                        if index is not None:
                            if (
                                isinstance(self.select_ckpt_job_num[index], str)
                                or self.select_ckpt_job_num[index] > 1
                                or self.select_ckpt_job_num[index] is None
                            ):
                                self._num_to_run -= 1
                                self._num_to_ignore += 1
                                self._model_testing_dependency[0] = str(
                                    self.select_ckpt_job_num[index]
                                )
                                if self.itr.debug_mode:
                                    self.itr.logger.debug(
                                        f"{self.logger_msg}: model_testing dependency updated to {self.select_ckpt_job_num}"
                                    )

                if self._num_to_ignore == 1:
                    self.itr.logger.info(
                        f"{self.logger_msg}: there are no jobs to re-submit for '{self._phase}'... SKIPPING AHEAD"
                    )
            else:
                if self.itr.debug_mode:
                    self.itr.logger.debug(
                        f"{self.logger_msg}: --running-jobids triggered reprocessing {num_job_ids} job"
                    )
                self.itr.logger.error(
                    f"{self.logger_msg}: incorrect format for 'train_job_num'"
                )
                self.itr.logger.error(
                    f"{self.logger_msg}: expected a list of 1 SLURM jobs (or 'None' as a place holder)"
                )
                self._run_jobs = None
        else:
            self._run_jobs = True
            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"{self.logger_msg}: running job ids were NOT provided"
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
            logging_msg = f"[{self.itr._mode_string}] - [{phase}]"

        self.find_selected_ckpt_vars(phase=phase)

        if self.ckpt_selected:
            if self.overwrite and (
                self.select_ckpt_job_num or not self._ignoring_training
            ):
                self._outputs_exist = False
            else:
                self.find_selected_ckpt_files(phase=phase)
                missing_files = helpers.h.check_expected_outputs(
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
        Save the SLURM job IDs to a file for future resource usage metrics.
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
                    f"[DRY_RUN] - {self.logger_msg} - [{self.itr.train_genome}]: benchmarking is active"
                )

    def make_job(self) -> Union[s.SBATCH, None]:
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

        slurm_job = s.SBATCH(
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
            ):
                self.itr.logger.info(
                    f"{self.logger_msg}: --overwrite=True, re-writing the existing SLURM job now..."
                )
            else:
                self.itr.logger.info(
                    f"{self.logger_msg}: SLURM job file already exists... SKIPPING AHEAD"
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
            f"conda run --no-capture-output -p miniconda_envs/beam_v2.30 python3 scripts/model_training/parse_tfmetrics.py --env-file {self.itr.env.env_file} --genome {self.itr.train_genome}",
        ]

        # Selecting the next checkpoint
        if (
            self.itr.next_genome is not None
            and self.itr.current_genome_num is not None
            and self.itr.next_trio_num is not None
        ):
            command_list = parse_metrics_command_list + [
                f"conda run --no-capture-output -p miniconda_envs/beam_v2.30 python3 scripts/model_training/slurm_select_ckpt.py --next-genome {self.itr.next_genome} --next-run {self.itr.next_trio_num} --current-ckpt {self.itr.train_dir}/eval_Child/best_checkpoint.txt --env-file {self.itr.env.env_file}",
            ]
        else:
            command_list = parse_metrics_command_list + [
                f"conda run --no-capture-output -p miniconda_envs/beam_v2.30 python3 scripts/model_training/slurm_select_ckpt.py --next-genome None --next-run None --current-ckpt {self.itr.train_dir}/eval_Child/best_checkpoint.txt --env-file {self.itr.env.env_file}",
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
            logger_msg = f"[{self.itr._mode_string}] - [{phase}]"

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
                    next_env = helpers.h.Env(next_env_file, self.itr.logger, dryrun_mode=self.itr.args.dry_run)

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
            self.itr.logger.info(
                f"{logger_msg}: {self.itr.train_genome}{self.itr.current_trio_num} testing checkpoint does not exist"
            )

        self._outputs_exist = self.ckpt_selected

    def find_selected_ckpt_files(self, phase: Union[str, None] = None) -> None:
        """
        Determine if the new model weight files exist
        """
        if phase is None:
            logger_msg = self.logger_msg
        else:
            logger_msg = f"[{self.itr._mode_string}] - [{phase}]"
        # confirm model weights files are present
        model_weights_pattern = compile(f"{self.ckpt_name}.*")

        # Confirm if files do not already exist
        (
            self.existing_model_weights,
            self.num_model_files_found,
            model_weights_files,
        ) = helpers.h.check_if_output_exists(
            model_weights_pattern,
            "new model weights files",
            self.itr.train_dir,
            logger_msg,
            self.itr.logger,
            debug_mode=self.itr.debug_mode,
            dryrun_mode=self.itr.dryrun_mode,
        )

    def submit_job(self) -> None:
        """
        Submit SLURM jobs to queue.
        """
        if self.itr.current_genome_dependencies[3] is None:
            slurm_job = self.make_job()
            if slurm_job is not None:
                if self.itr.dryrun_mode:
                    slurm_job.display_job()
                else:
                    slurm_job.write_job()

            # submit the training eval job to queue
            slurm_job = s.SubmitSBATCH(
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
                self._model_testing_dependency[0] = helpers.h.generate_job_id()
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
        select_ckpt_results = helpers.h.check_if_all_same(
            self._model_testing_dependency, None
        )
        if select_ckpt_results is False:
            if self.itr.dryrun_mode:
                print(
                    f"============ [DRY_RUN] - {self.logger_msg} Job Number - {self._model_testing_dependency} ============"
                )
            else:
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
            sys.exit(1)

        if self.track_resources and self.benchmarking_file is not None:
            self.benchmark()

    def run(self) -> helpers.Iteration:
        """
        Combine all the steps required to submit a job to SLURM queue into one step
        """
        if self.itr.current_genome_dependencies[2] is None:
            if (
                self.itr.current_genome_num is not None
                and self.itr.current_genome_num != 0
            ):
                self.itr.logger.info(
                    f"{self.logger_msg}: prior iteration [#{int(self.itr.current_genome_num) - 1}] select-ckpt's SLURM job ID is 'None', no additional dependncies required."
                )
        else:
            self.itr.logger.info(
                f"{self.logger_msg}: prior iteration select-ckpt job number | {self.itr.current_genome_dependencies[2]}"
            )

        self.find_restart_jobs()

        # if (self.select_ckpt_job_num or not self._ignoring_training) and self._run_jobs is not None:
        # determine if we are re-running select-ckpt
        if self._num_to_run == 0:
            self._skipped_counter = self._num_to_ignore
            if (
                self._model_testing_dependency
                and self._model_testing_dependency[0] is not None
            ):
                self.itr.logger.info(
                    f"{self.logger_msg}: call_variants dependency updated to {self._model_testing_dependency}"
                )
            else:
                self._model_testing_dependency[0] = None
        else:
            self.find_outputs()

            if self._num_to_run == 1:
                if self.overwrite:
                    self.itr.logger.info(
                        f"{self.logger_msg}: re-submitting {self._num_to_run}-of-1 SLURM jobs",
                    )
                    if self._outputs_exist:
                        self.itr.logger.info(
                            f"{self.logger_msg}: --overwrite=True, any exiting results files will be re-written..."
                        )
                else:
                    self.itr.logger.info(
                        f"{self.logger_msg}: submitting {self._num_to_run}-of-1 SLURM jobs",
                    )
            else:
                self.itr.logger.error(
                    f"{self.logger_msg}: there should only be one train_eval_job, but {self._num_to_run} were provided.\nExiting... ",
                )
                sys.exit(1)

            self.submit_job()

        # # or running it for the first time
        # else:
        #     self.submit_job()

        self.check_submission()
        return self.itr
