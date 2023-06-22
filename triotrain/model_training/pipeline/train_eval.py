#!/usr/bin/python3
"""
description: contains all of the functions specific to
the re-training and evaluating new models of TrioTrain.

usage: 
    from model_train_eval import TrainEval
"""
import sys
from dataclasses import dataclass, field
from math import floor
from pathlib import Path
from typing import List, Union

from regex import compile

# get the relative path to the triotrain/ dir
h_path = str(Path(__file__).parent.parent.parent)
sys.path.append(h_path)
import helpers
import model_training.slurm as s
from model_training.pipeline.select_ckpt import SelectCheckpoint


@dataclass
class TrainEval:
    """
    Define what data to store for the model_train
    and model_eval phases of the TrioTrain Pipeline.
    """

    # required values
    itr: helpers.Iteration
    slurm_resources: dict
    model_label: str

    # optional values
    benchmarking_file: Union[helpers.h.WriteFiles, None] = None
    constrain_training_regions: bool = False
    overwrite: bool = False
    track_resources: bool = False
    train_job_num: List = field(default_factory=list)

    # internal, imutable values
    _gpu_mem: Union[str, int, None] = field(default=None, init=False, repr=False)
    _per_gpu_mem: Union[str, int, None] = field(default=None, init=False, repr=False)
    _phase: str = field(default="train_eval", init=False, repr=False)
    _run_jobs: Union[bool, None] = field(default=None, init=False, repr=False)
    _select_ckpt_dependency: List = field(default_factory=list, repr=False, init=False)
    _skipped_counter: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.itr.env is None:
            return
        if "mem" in self.slurm_resources["train_eval"]:
            self._gpu_mem = self.slurm_resources["train_eval"]["mem"]
            self._cpu_mem = None
        elif "mem-per-cpu" in self.slurm_resources["train_eval"]:
            self._cpu_mem = self.slurm_resources["train_eval"]["mem-per-cpu"]
        else:
            self._cpu_mem = None

        self.logger_msg = f"[{self.itr._mode_string}] - [{self._phase}]"
        self.epochs = self.itr.env.contents["N_Epochs"]
        self.batches = self.itr.env.contents["BatchSize"]
        self._total_ntasks = self.slurm_resources["train_eval"]["ntasks"]
        self._ntasks_per_gpu = 1

        if f"{self.itr.train_genome}_Examples" in self.itr.env.contents:
            self.train_examples = self.itr.env.contents[
                f"{self.itr.train_genome}_Examples"
            ]
            self._num_training_steps = int((int(self.epochs) * int(self.train_examples)) / int(self.batches))  # type: ignore
            # prevent repeatedly adding *_N_Steps to the env file
            if f"{self.itr.train_genome}_N_Steps" not in self.itr.env.contents:
                self.itr.env.add_to(
                    f"{self.itr.train_genome}_N_Steps",
                    str(self._num_training_steps),
                    dryrun_mode=self.itr.dryrun_mode,
                    msg=self.logger_msg,
                )
        else:
            self._num_training_steps = (
                f"$((({self.epochs}*{self.itr.train_genome}_Examples)/{self.batches}))"
            )

        if self.track_resources:
            assert (
                self.benchmarking_file is not None
            ), "unable to proceed, missing a h.WriteFiles object to save SLURM job IDs"

        self._select_ckpt_dependency = helpers.h.create_deps(1)

    def find_restart_jobs(self) -> None:
        """
        collect any SLURM job ids for running tests to avoid
        submitting a job while it's already running
        """
        self._ignoring_re_shuffle = helpers.h.check_if_all_same(
            self.itr.current_genome_dependencies[0:2], None
        )
        if not self._ignoring_re_shuffle:
            self.itr.logger.info(f"{self.logger_msg}: re-shuffle was submitted...")
            self._num_to_ignore = 0
            self._num_to_run = 1
            self._run_jobs = True

        elif self.train_job_num:
            if self.overwrite and self._outputs_exist:
                self.itr.logger.info(
                    f"{self.logger_msg}: --overwrite=True, any exiting results files will be re-written..."
                )
            num_job_ids = len(self.train_job_num)
            if num_job_ids == 1:
                jobs_to_run = helpers.h.find_not_NaN(self.train_job_num)
                self._num_to_run = len(jobs_to_run)
                self._num_to_ignore = len(helpers.h.find_NaN(self.train_job_num))
                self._select_ckpt_dependency = helpers.h.create_deps(1)

                if jobs_to_run:
                    self._run_jobs = True
                    for index in jobs_to_run:
                        if index is not None:
                            if (
                                isinstance(self.train_job_num[index], str)
                                or self.train_job_num[index] > 1
                                or self.train_job_num[index] is None
                            ):
                                if len(str(self.train_job_num[index])) != 8:
                                    self.itr.logger.error(
                                        f"{self.logger_msg}: invalid input for SLURM job ID | {self.train_job_num[index]}"
                                    )
                                    self.itr.logger.error(
                                        f"{self.logger_msg}: an 8-digit value must be provided for any number greater than one.\nExiting..."
                                    )
                                    sys.exit(1)
                                self._num_to_run -= 1
                                self._num_to_ignore += 1
                                self._select_ckpt_dependency = [
                                    str(self.train_job_num[index])
                                ]
                                if self.itr.debug_mode:
                                    self.itr.logger.debug(
                                        f"{self.logger_msg}: select_ckpt dependency updated to {self.train_job_num}"
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
        self, number_outputs_expected: int = 2, phase: Union[str, None] = None
    ) -> None:
        """
        Determine if model_train and model_eval results already exist
        """
        if phase is None:
            logging_msg = f"[{self.itr._mode_string}] - [{self._phase}]"
        else:
            logging_msg = f"[{self.itr._mode_string}] - [{phase}]"

        self.find_training_outputs()
        if self.existing_best_ckpt:
            if self.overwrite and (self.train_job_num or not self._ignoring_re_shuffle):
                self._outputs_exist = False
            else:
                missing_files = helpers.h.check_expected_outputs(
                    self.best_ckpt_files_found,
                    number_outputs_expected,
                    logging_msg,
                    "best_checkpoint files",
                    self.itr.logger,
                )
                if missing_files is True:
                    self._outputs_exist = False
                else:
                    self._outputs_exist = True
        else:
            self._outputs_exist = False

    def find_all_outputs(self, phase: str = "find_outputs") -> Union[bool, None]:
        """
        Determine if re-shuffle or beam outputs already exist, skip ahead if they do.
        """
        selecting_ckpt = SelectCheckpoint(
            itr=self.itr,
            slurm_resources=self.slurm_resources,
            model_label=self.model_label,
            track_resources=self.track_resources,
            benchmarking_file=self.benchmarking_file,
            overwrite=self.overwrite,
        )

        selecting_ckpt.find_outputs(phase=phase)

        if selecting_ckpt._outputs_exist:
            self.find_outputs(phase=phase)
        else:
            self._outputs_exist = False

    def benchmark(self) -> None:
        """
        Save the SLURM job IDs to a file for future resource usage metrics.
        """
        headers = ["AnalysisName", "RunName", "Parent", "Phase", "JobList"]
        deps_string = ",".join(filter(None, self._select_ckpt_dependency))
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

    def process_mem(self) -> None:
        """
        Behave differently if memory is provided in GB vs MB
        """
        self.itr.logger.info(f"{self.logger_msg}: processing memory inputs now... ")

        # search patterns
        digits_only = compile(r"\d+")
        letters_only = compile(r"[a-zA-Z]+")

        # determine max mem format
        if self._gpu_mem is None:
            self._per_gpu_mem = None
            self._ntasks_per_gpu = int(floor(int(self._total_ntasks) / 2))
        elif int(self._gpu_mem) == 0:
            self._per_gpu_mem = "50G"
            self.itr.logger.info(
                f"{self.logger_msg}: exclusively using all mem across 2 GPU cards"
            )
        elif isinstance(self._gpu_mem, str):
            mem_value = digits_only.search(self._gpu_mem)
            mem_unit = letters_only.search(self._gpu_mem)
            if mem_value and mem_unit:
                unit = str(mem_unit.group())
                total_mem = int(mem_value.group())
                self._per_gpu_mem = f"{int(total_mem/ 2)}{unit}"
            else:
                self.itr.logger.warning(
                    f"Unexpected input format for gpu_mem: [{type(self._gpu_mem)}={self._gpu_mem}]"
                )
                raise ValueError("invalid GPU mem input")
        else:
            self._per_gpu_mem = int(self._gpu_mem / 2)

        if self._cpu_mem is not None:
            if isinstance(self._cpu_mem, str):
                mem_value = digits_only.search(self._cpu_mem)
                mem_unit = letters_only.search(self._cpu_mem)
                if mem_value and mem_unit:
                    unit = str(mem_unit.group())
                    total_mem = int(mem_value.group())
                    self._per_cpu_mem_string = f"{int(total_mem/ 2)}{unit}"
                    self._per_cpu_mem = int(total_mem / 2)
                else:
                    self.itr.logger.warning(
                        f"Unexpected input format for cpu_mem: [{type(self._cpu_mem)}={self._cpu_mem}]"
                    )
                    raise ValueError("invalid CPU mem input")
            else:
                self._per_cpu_mem = int(self._cpu_mem / 2)
                self._per_cpu_mem_string = f"{int(self._cpu_mem / 2)}"

        if self._per_gpu_mem is None and self._per_cpu_mem is not None:
            self._srun_mem = f"--mem-per-cpu={self._per_cpu_mem_string}"
            self.itr.logger.info(
                f"{self.logger_msg}: using [{int(self._per_cpu_mem) * int(self._ntasks_per_gpu)}] memory for each GPU srun task"
            )
        else:
            self._srun_mem = f"--mem={self._per_gpu_mem}"
            self.itr.logger.info(
                f"{self.logger_msg}: using [{self._per_gpu_mem}] memory for each GPU srun task"
            )

    def make_job(self) -> Union[s.SBATCH, None]:
        """
        Define the contents of the SLURM job for the train + eval phases for TrioTrain Pipeline.
        """
        # initialize a SBATCH Object
        self.job_name = f"train-{self.itr.train_genome}{self.itr.current_trio_num}-eval-{self.itr.eval_genome}"
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
                self.train_job_num
                and self.train_job_num[0] is not None
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
                self.itr.logger.debug(f"{self.logger_msg}: creating file job now... ")

        self.process_mem()
        # define model starting points
        ##----- non-baseline initial weights ------##
        if self.itr.current_genome_num is not None and self.itr.current_genome_num > 0:
            training_command_list = [
                f"export CHKPT_PATH=${self.itr.train_genome}StartCkptPath",
                f"export CHKPT_NAME=${self.itr.train_genome}StartCkptName",
                f"export NUM_STEPS={self._num_training_steps}",
            ]
        else:
            training_command_list = []

        if self.constrain_training_regions and self.itr.default_region_file is not None:
            training_command_list.extend(
                [
                    f"export REGION_PATH={self.itr.default_region_file.parent}",
                    f"export REGION_FILE={self.itr.default_region_file.name}",
                ]
            )

        training_command_list.extend(
            [
                f"export TRAIN_GENOME={self.itr.train_genome}",
                f"export TRAIN_DIR=${self.itr.train_genome}TrainDir",
                "export USE_GPU=true",
                "export SLURM_EXPORT_ENV=ALL",
            ]
        )

        if self._per_gpu_mem is None and self._per_cpu_mem is None:
            training_command_list.extend(
                [
                    f"srun -l --gres=gpu:1 --ntasks={self._ntasks_per_gpu} scripts/run/train_model.sh {self.itr.train_genome} >& \"{self.itr.log_dir}/train-{self.itr.train_genome}-{'${NUM_STEPS}'}steps.log\"",
                ]
            )

        else:
            training_command_list.extend(
                [
                    f"srun -l --gres=gpu:1 --ntasks={self._ntasks_per_gpu} {self._srun_mem} scripts/run/train_model.sh {self.itr.train_genome} >& \"{self.itr.log_dir}/train-{self.itr.train_genome}-{'${NUM_STEPS}'}steps.log\"",
                ]
            )
        #     self._starting_path = self.itr.env.contents[
        #         f"{self.itr.train_genome}StartCkptPath"
        #     ]
        #     if f"{self.itr.train_genome}StartCkptName" in self.itr.env.contents:
        #         self._starting_ckpt = self.itr.env.contents[
        #             f"{self.itr.train_genome}StartCkptName"
        #         ]
        #     else:
        #         self._starting_ckpt = f"${self.itr.train_genome}StartCkptName"

        #     training_command_list = slurm_job._start_conda + [
        #         "export SLURM_EXPORT_ENV=ALL",
        #         f"export NUM_STEPS=$((({self.epochs}*{self.itr.train_genome}_Examples)/{self.batches}))",
        #         f"srun -l --gres=gpu:1 --ntasks=1 --mem={self._per_gpu_mem} conda run --no-capture-output -p miniconda_envs/beam_v2.30 python3 scripts/model_training/slurm_train_model.py --env-file {self.itr.env.env_file} --train-genome {self.itr.train_genome} --use-custom-model --custom-checkpoint {self._starting_path}/{self._starting_ckpt} >& \"{self.itr.log_dir}/train-{self.itr.train_genome}-{'${NUM_STEPS}'}steps.log\"",
        #     ]
        # else:
        #     training_command_list = slurm_job._start_conda + [
        #         "export SLURM_EXPORT_ENV=ALL",
        #         f"export NUM_STEPS=$((({self.epochs}*{self.itr.train_genome}_Examples)/{self.batches}))",
        #         f"srun -l --gres=gpu:1 --ntasks=1 --mem={self._per_gpu_mem} conda run --no-capture-output -p miniconda_envs/beam_v2.30 python3 scripts/model_training/slurm_train_model.py --env-file {self.itr.env.env_file} --train-genome {self.itr.train_genome} >& \"{self.itr.log_dir}/train-{self.itr.train_genome}-{'${NUM_STEPS}'}steps.log\"",
        #     ]

        slurm_job.create_slurm_job(
            self.handler_label,
            command_list=training_command_list,
            overwrite=self.overwrite,
            **self.slurm_resources[self._phase],
        )

        if not slurm_job.job_file_exists:
            self.itr.logger.info(
                f"{self.logger_msg}: adding additional lines for model_eval... "
            )

        # link training with evaluation
        if self._per_gpu_mem is None and self._per_cpu_mem is None:
            evaluation_command_list = [
                f"srun -l --gres=gpu:1 --ntasks={self._ntasks_per_gpu} scripts/run/eval_model.sh {self.itr.eval_genome} >& \"{self.itr.log_dir}/train-{self.itr.train_genome}-eval-{self.itr.eval_genome}-{'${NUM_STEPS}'}steps.log\""
            ]
        else:
            evaluation_command_list = [
                f"srun -l --gres=gpu:1 --ntasks={self._ntasks_per_gpu} {self._srun_mem} scripts/run/eval_model.sh {self.itr.eval_genome} >& \"{self.itr.log_dir}/train-{self.itr.train_genome}-eval-{self.itr.eval_genome}-{'${NUM_STEPS}'}steps.log\""
            ]

        # evaluation_command_list = [
        #     f"srun -l --gres=gpu:1 --ntasks=1 --mem={self._per_gpu_mem} conda run --no-capture-output -p miniconda_envs/beam_v2.30 python3 scripts/model_training/slurm_eval_model.py --env-file {self.itr.env.env_file} --train-genome {self.itr.train_genome} >& \"{self.itr.log_dir}/train-{self.itr.train_genome}-eval-{self.itr.eval_genome}-{'${NUM_STEPS}'}steps.log\""
        # ]

        group_srun_commands = f"{slurm_job._line_list[-1]} &"
        slurm_job._line_list[-1] = group_srun_commands
        line_list = slurm_job._line_list

        self.handler_label = f"{self._phase}: {self.itr.train_genome}"

        slurm_job.create_slurm_job(
            self.handler_label,
            command_list=evaluation_command_list,
            overwrite=self.overwrite,
            **self.slurm_resources[self._phase],
        )
        slurm_job._line_list.extend(slurm_job._line_list)
        slurm_job._line_list = line_list

        return slurm_job

    def find_training_outputs(self, phase: Union[str, None] = None) -> None:
        """
        Search for model-ckpts, based on expected output patterns.

        Test to see if training has already begun

        Confirm that a best-ckpt does NOT already exist before re-training.
        """
        if phase is None:
            logging_msg = f"[{self.itr._mode_string}] - [{self._phase}]"
        else:
            logging_msg = f"[{self.itr._mode_string}] - [{phase}]"

        eval_path = Path(self.itr.train_dir) / f"eval_{self.itr.eval_genome}"

        # if eval dir exists, then...
        if eval_path.is_dir():
            # confirm a best_ckpt txt file is present
            # NOTE: these will start being created at the
            best_ckpt_pattern = compile(r"best_checkpoint.*")

            # Confirm examples do not already exist
            (
                self.existing_best_ckpt,
                self.best_ckpt_files_found,
                best_ckpt_files,
            ) = helpers.h.check_if_output_exists(
                best_ckpt_pattern,
                "best_checkpoint files",
                self.itr.train_dir / f"eval_{self.itr.eval_genome}",
                logging_msg,
                self.itr.logger,
                debug_mode=self.itr.debug_mode,
                dryrun_mode=self.itr.dryrun_mode,
            )

        # if eval dir doesn't exist, then...
        else:
            self.existing_best_ckpt = False

    def submit_job(self) -> None:
        """
        Submit SLURM jobs to queue.
        """
        self.find_outputs()

        slurm_job = self.make_job()

        if slurm_job is not None:
            if self.itr.dryrun_mode:
                slurm_job.display_job()
            else:
                slurm_job.write_job()

        # identify any iteration dependencies
        # current_genome_dependencies[3] is the SLURM
        # job number for select-ckpt, so only submit
        # again, if that value is None
        if self.itr.current_genome_dependencies[3] is None:
            # submit the training eval job to queue
            slurm_job = s.SubmitSBATCH(
                self.itr.job_dir,
                f"{self.job_name}.sh",
                self.handler_label,
                self.itr.logger,
                self.logger_msg,
            )
            slurm_job.build_command(
                prior_job_number=self.itr.current_genome_dependencies
            )

            if self.itr.dryrun_mode:
                slurm_job.display_command(display_mode=self.itr.dryrun_mode)
                self._select_ckpt_dependency = [helpers.h.generate_job_id()]

            else:
                slurm_job.display_command(debug_mode=self.itr.debug_mode)
                slurm_job.get_status(debug_mode=self.itr.debug_mode)

                if slurm_job.status == 0:
                    self._select_ckpt_dependency = [slurm_job.job_number]
                else:
                    self.itr.logger.error(
                        f"{self.logger_msg}: unable to submit SLURM job",
                    )
                    self._select_ckpt_dependency = [None]

    def check_submission(self) -> None:
        """
        Check if the SLURM job file was submitted to the SLURM queue successfully
        """
        # look at job number list to see if all items are 'None'
        train_eval_results = helpers.h.check_if_all_same(
            self._select_ckpt_dependency, None
        )
        if train_eval_results is False:
            if self.itr.dryrun_mode:
                print(
                    f"============ [DRY_RUN] - {self.logger_msg} Job Number - {self._select_ckpt_dependency} ============"
                )
            else:
                print(
                    f"============ {self.logger_msg} Job Number - {self._select_ckpt_dependency} ============"
                )

        elif (
            self._skipped_counter == 1
            or self.itr.current_genome_dependencies[3] is not None
        ):
            # if submitting a re-training job
            # to the SLURM queue was skipped completely,
            # then there is no dependency for selecting a ckpt
            self._select_ckpt_dependency = [None]
        else:
            self.itr.logger.warning(
                f"{self.logger_msg}: expected SLURM jobs to be submitted, but they were not",
            )
            self.itr.logger.warning(
                f"{self.logger_msg}: fatal error encountered, unable to proceed further with pipeline.\nExiting... ",
            )
            sys.exit(1)

        if self.track_resources and self.track_resources is not None:
            self.benchmark()

    def run(self) -> List[Union[str, None]]:
        """
        Combine all the steps required to submit a job to SLURM queue into one step
        """
        self.find_restart_jobs()
        # determine if we are re-running the training
        # if (self.train_job_num or not self._ignoring_re_shuffle) and self._run_jobs is not None:
        if self._num_to_run == 0:
            self._skipped_counter = self._num_to_ignore
            if (
                self._select_ckpt_dependency
                and self._select_ckpt_dependency[0] is not None
            ):
                self.itr.logger.info(
                    f"{self.logger_msg}: select_ckpt dependency updated to {self._select_ckpt_dependency}"
                )
            else:
                self._select_ckpt_dependency[0] = None
        else:
            if self._num_to_run == 1:
                if self.overwrite:
                    self.itr.logger.info(
                        f"{self.logger_msg}: re-submitting {self._num_to_run}-of-1 SLURM job",
                    )
                    if self._outputs_exist:
                        self.itr.logger.info(
                            f"{self.logger_msg}: --overwrite=True, any exiting results files will be re-written..."
                        )
                else:
                    self.itr.logger.info(
                        f"{self.logger_msg}: submitting {self._num_to_run}-of-1 SLURM job",
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
        return self._select_ckpt_dependency
