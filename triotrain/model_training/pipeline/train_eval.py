#!/usr/bin/python3
"""
description: contains all of the functions specific to
the re-training and evaluating new models of TrioTrain.

usage: 
    from model_training.pipeline.train_eval import TrainEval
"""
from dataclasses import dataclass, field
from math import floor
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
from model_training.pipeline.select_ckpt import SelectCheckpoint
from model_training.slurm.sbatch import SBATCH, SubmitSBATCH
from regex import compile


@dataclass
class TrainEval:
    """
    Define what data to store for the model_train
    and model_eval phases of the TrioTrain Pipeline.
    """

    # required values
    itr: Iteration
    slurm_resources: dict
    model_label: str

    # optional values
    benchmarking_file: Union[Files, None] = None
    constrain_training_regions: bool = False
    overwrite: bool = False
    track_resources: bool = False
    train_job_num: List = field(default_factory=list)

    # internal, imutable values
    _gpu_mem: Union[str, int, None] = field(default=None, init=False, repr=False)
    _per_gpu_mem: Union[str, int, None] = field(default=None, init=False, repr=False)
    _phase: str = field(default="train_eval", init=False, repr=False)
    _select_ckpt_dependency: List = field(default_factory=list, repr=False, init=False)
    _skipped_counter: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.itr.env is None:
            return

        self.logger_msg = (
            f"{self.itr._mode_string} - [{self._phase}] - [{self.itr.train_genome}]"
        )

        ### HANDLE CPUS
        if "ntasks" in self.slurm_resources["train_eval"]:
            self._total_ntasks = self.slurm_resources["train_eval"]["ntasks"]
            self._ntasks_per_gpu = 1
            if int(self._total_ntasks) % 2 != 0:
                self.itr.logger.warning(f"{self.logger_msg}: odd number detected")
                self._cpus_per_task = int((self._total_ntasks - 1) / 2)
            else:
                self._cpus_per_task = int(self._total_ntasks / 2)

        else:
            self.itr.logger.error(
                f"{self.logger_msg}: missing 'ntasks' key in --slurm-resources file for 'train_eval'\nExiting..."
            )
            exit(1)

        ### HANDLE CPU MEM
        if "mem" in self.slurm_resources["train_eval"]:
            self._gpu_mem = self.slurm_resources["train_eval"]["mem"]
            self._cpu_mem = None
        elif "mem-per-cpu" in self.slurm_resources["train_eval"]:
            self._cpu_mem = self.slurm_resources["train_eval"]["mem-per-cpu"]
        else:
            self._cpu_mem = None

        ### HANDLE GPUS
        if "gres" in self.slurm_resources["train_eval"]:
            _gres_input = self.slurm_resources["train_eval"]["gres"]
            _gres_items = _gres_input.split(":")
            if len(_gres_items) == 3:
                _total_gpus = int(_gres_items[2])
                _gres_string = ":".join(_gres_items[0:2])
            else:
                _total_gpus = int(_gres_items[1])
                _gres_string = _gres_items[0]

            _gpus_per_task = int(_total_gpus / 2)
            self._gres = f"{_gres_string}:{_gpus_per_task}"
        else:
            self._gres = None

        self.epochs = self.itr.env.contents["N_Epochs"]
        self.batches = self.itr.env.contents["BatchSize"]

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
            ), "unable to proceed, missing a Files object to save SLURM job numbers"

        self._select_ckpt_dependency = create_deps(1)

    def find_restart_jobs(self) -> None:
        """
        collect any SLURM job ids for running tests to avoid
        submitting a job while it's already running
        """
        self._ignoring_re_shuffle = check_if_all_same(
            self.itr.current_genome_dependencies[0:2], None
        )
        self._ignoring_restart_jobs = check_if_all_same(self.train_job_num, None)

        if not self._ignoring_re_shuffle:
            self._jobs_to_run = [0]
            self._num_to_run = 1
            self._num_to_ignore = 0

        elif not self._ignoring_restart_jobs:
            self._jobs_to_run = find_not_NaN(self.train_job_num)
            self._num_to_run = len(self._jobs_to_run)
            self._num_to_ignore = len(find_NaN(self.train_job_num))

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
                    if is_jobid(self.train_job_num[index]):
                        self._num_to_run -= 1
                        self._num_to_ignore += 1
                        self._select_ckpt_dependency = [str(self.train_job_num[index])]
                    elif is_job_index(self.train_job_num[index]):
                        updated_jobs_list.append(index)

                if updated_jobs_list:
                    self._jobs_to_run = updated_jobs_list

        elif self._num_to_ignore == 1:
            if self.train_job_num:
                self.itr.logger.info(
                    f"{self.logger_msg}: completed '{self._phase}'... SKIPPING AHEAD"
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
            self._num_to_run = 0

    def find_outputs(
        self, number_outputs_expected: int = 2, phase: Union[str, None] = None
    ) -> None:
        """
        Search for model-ckpts, based on expected output patterns.

        Tests to see if training has already begun.
        """
        if phase is None:
            logging_msg = f"{self.itr._mode_string} - [{self._phase}]"
        else:
            logging_msg = f"{self.itr._mode_string} - [{phase}]"

            if self.itr.train_genome is not None:
                logging_msg = f"{logging_msg} - [{self.itr.train_genome}]"

        eval_path = Path(self.itr.train_dir) / f"eval_{self.itr.eval_genome}"

        # if eval dir exists, then...
        if eval_path.is_dir():
            # confirm a best_ckpt txt file is present
            # NOTE: these will start being created at the
            best_ckpt_pattern = compile(r"best_checkpoint.*")

            # Confirm best_ckpt files do not already exist
            (
                _existing_best_ckpt_file,
                _best_ckpt_files_found,
                best_ckpt_files,
            ) = check_if_output_exists(
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
            _existing_best_ckpt_file = False

        if _existing_best_ckpt_file:
            missing_ckpt_files = check_expected_outputs(
                _best_ckpt_files_found,
                number_outputs_expected,
                logging_msg,
                "best_checkpoint files",
                self.itr.logger,
            )
        else:
            missing_ckpt_files = True
        
        if missing_ckpt_files is True:
            self._outputs_exist = False
        else:
            self._outputs_exist = True

    def find_all_outputs(
        self, phase: str = "find_outputs", verbose: bool = False
    ) -> Union[bool, None]:
        """
        Determine if re-shuffle or beam outputs already exist, skip ahead if they do.
        """
        self._selecting_ckpt = SelectCheckpoint(
            itr=self.itr,
            slurm_resources=self.slurm_resources,
            model_label=self.model_label,
            track_resources=self.track_resources,
            benchmarking_file=self.benchmarking_file,
            overwrite=self.overwrite,
        )
        if verbose:
            self._selecting_ckpt.find_outputs(phase=phase)
            self.find_outputs(phase=phase)
        else:
            self._selecting_ckpt.find_selected_ckpt_vars(phase=phase)
            self._outputs_exist = False
        
        self._select_ckpt_outputs_exist = self._selecting_ckpt._outputs_exist

    def benchmark(self) -> None:
        """
        Save the SLURM job numbers to a file for future resource usage metrics.
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
            self.itr.logger.info(f"{self.logger_msg}: --keep-jobids=True")

    def process_mem(self) -> None:
        """
        Behave differently if memory is provided in GB vs MB
        """
        if self.itr.debug_mode:
            self.itr.logger.debug(
                f"{self.logger_msg}: processing memory inputs now... "
            )

        # search patterns
        digits_only = compile(r"\d+")
        letters_only = compile(r"[a-zA-Z]+")

        # determine max mem format
        if self._gpu_mem is None:
            self._per_gpu_mem = None
            self._ntasks_per_gpu = int(floor(int(self._total_ntasks) / 2))
        elif isinstance(self._gpu_mem, str):
            mem_value = digits_only.search(self._gpu_mem)
            if mem_value:
                total_mem = int(mem_value.group())
            else:
                total_mem = 0

            mem_unit = letters_only.search(self._gpu_mem)
            if mem_unit:
                unit = str(mem_unit.group())

            if total_mem == 0:
                self._per_gpu_mem = "50G"
                if self.itr.debug_mode:
                    self.itr.logger.debug(
                        f"{self.logger_msg}: dividing 100G mem across 2 GPU cards to ensure exclusive usage"
                    )
            elif mem_value and mem_unit:
                self._per_gpu_mem = f"{int(total_mem/ 2)}{unit}"
            elif mem_value:
                self._per_gpu_mem = f"{int(total_mem/ 2)}"
            else:
                self.itr.logger.warning(
                    f"{self.logger_msg}: unexpected input format for gpu_mem: [{type(self._gpu_mem)}={self._gpu_mem}]"
                )
                raise ValueError("invalid GPU mem input")
        else:
            self._per_gpu_mem = int(self._gpu_mem / 2)

        if self._cpu_mem is None:
            self._per_cpu_mem = None
        else:
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
                        f"{self.logger_msg}: unexpected input format for cpu_mem: [{type(self._cpu_mem)}={self._cpu_mem}]"
                    )
                    raise ValueError("invalid CPU mem input")
            else:
                self._per_cpu_mem = int(self._cpu_mem / 2)
                self._per_cpu_mem_string = f"{int(self._cpu_mem / 2)}"

        if self._per_gpu_mem is None and self._per_cpu_mem is not None:
            self._srun_mem = f"--mem-per-cpu={self._per_cpu_mem_string}"
            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"{self.logger_msg}: using {int(self._per_cpu_mem) * int(self._ntasks_per_gpu)} memory for each GPU srun task"
                )
        else:
            self._srun_mem = f"--mem={self._per_gpu_mem}"
            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"{self.logger_msg}: using {self._per_gpu_mem} memory for each GPU srun task"
                )

    def make_job(self) -> Union[SBATCH, None]:
        """
        Define the contents of the SLURM job for the train + eval phases for TrioTrain Pipeline.
        """
        # initialize a SBATCH Object
        self.job_name = f"train-{self.itr.train_genome}{self.itr.current_trio_num}-eval-{self.itr.eval_genome}"
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
                self.train_job_num
                and self.train_job_num[0] is not None
                and self.overwrite
            ) or (not self._ignoring_re_shuffle and self.overwrite):
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
                    f"srun -l --gres={self._gres} --ntasks={self._ntasks_per_gpu} --cpus-per-task={self._cpus_per_task} bash ./scripts/run/train_model.sh {self.itr.train_genome} >& \"{self.itr.log_dir}/train-{self.itr.train_genome}-{'${NUM_STEPS}'}steps.log\"",
                ]
            )

        else:
            training_command_list.extend(
                [
                    f"srun -l --gres={self._gres} --ntasks={self._ntasks_per_gpu} --cpus-per-task={self._cpus_per_task} {self._srun_mem} bash ./scripts/run/train_model.sh {self.itr.train_genome} >& \"{self.itr.log_dir}/train-{self.itr.train_genome}-{'${NUM_STEPS}'}steps.log\"",
                ]
            )

        slurm_job.create_slurm_job(
            self.handler_label,
            command_list=training_command_list,
            overwrite=self.overwrite,
            **self.slurm_resources[self._phase],
        )

        if not slurm_job.job_file_exists:
            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"{self.logger_msg}: adding additional lines for model_eval... "
                )

        # link training with evaluation
        if self._per_gpu_mem is None and self._per_cpu_mem is None:
            evaluation_command_list = [
                f"srun -l --gres={self._gres} --ntasks={self._ntasks_per_gpu} --cpus-per-task={self._cpus_per_task} bash ./scripts/run/eval_model.sh {self.itr.eval_genome} >& \"{self.itr.log_dir}/train-{self.itr.train_genome}-eval-{self.itr.eval_genome}-{'${NUM_STEPS}'}steps.log\""
            ]
        else:
            evaluation_command_list = [
                f"srun -l --gres={self._gres} --ntasks={self._ntasks_per_gpu} --cpus-per-task={self._cpus_per_task} {self._srun_mem} bash ./scripts/run/eval_model.sh {self.itr.eval_genome} >& \"{self.itr.log_dir}/train-{self.itr.train_genome}-eval-{self.itr.eval_genome}-{'${NUM_STEPS}'}steps.log\""
            ]

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

    def submit_job(self, msg: str = "sub", resubmission: bool = False) -> None:
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
                    f"{self.logger_msg}: --overwrite=False; skipping job because found all model checkpoint files"
                )
            return

        slurm_job = self.make_job()

        if slurm_job is not None:
            if self.itr.dryrun_mode:
                slurm_job.display_job()
            else:
                slurm_job.write_job()

        if not self.overwrite and self._ignoring_re_shuffle:
            self.itr.logger.info(
                f"{self.logger_msg}: --overwrite=False; {msg}mitting job because missing model checkpoint files"
            )
        elif self.overwrite and self._outputs_exist:
            self.itr.logger.info(
                f"{self.logger_msg}: --overwrite=True; {msg}mitting job because replacing existing model checkpoint files"
            )
        else:
            self.itr.logger.info(
                f"{self.logger_msg}: {msg}mitting job to create the model checkpoint files"
            )

        # identify any iteration dependencies
        # current_genome_dependencies[3] is the SLURM
        # job number for select-ckpt, so only submit
        # again, if that value is None
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
                prior_job_number=self.itr.current_genome_dependencies
            )

            if self.itr.dryrun_mode:
                slurm_job.display_command(display_mode=self.itr.dryrun_mode)
                self._select_ckpt_dependency = [generate_job_id()]

            else:
                slurm_job.display_command(debug_mode=self.itr.debug_mode)
                slurm_job.get_status(debug_mode=self.itr.debug_mode)

                if slurm_job.status == 0:
                    self._select_ckpt_dependency = [slurm_job.job_number]
                else:
                    self.itr.logger.error(
                        f"{self.logger_msg}: unable to {msg}mit SLURM job",
                    )
                    self._select_ckpt_dependency = [None]

    def check_submission(self) -> None:
        """
        Check if the SLURM job file was submitted to the SLURM queue successfully
        """
        # look at job number list to see if all items are 'None'
        train_eval_results = check_if_all_same(self._select_ckpt_dependency, None)
        if train_eval_results is False:
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
            exit(1)

        if self.track_resources and self.track_resources is not None:
            self.benchmark()

    def run(self) -> List[Union[str, None]]:
        """
        Combine all the steps required to submit a job to SLURM queue into one step
        """
        self.find_restart_jobs()

        skip_re_runs = check_if_all_same(self.train_job_num, None)

        if skip_re_runs and self._outputs_exist is False:
            msg = "sub"
        else:
            msg = "re-sub"

        # Determine if we are re-running training
        if self.train_job_num or not self._ignoring_re_shuffle:
            if self._num_to_run == 0:
                self._skipped_counter = self._num_to_ignore
                if (
                    self._select_ckpt_dependency
                    and self._select_ckpt_dependency[0] is not None
                ):
                    self.itr.logger.info(
                        f"{self.logger_msg}: select_ckpt dependency updated | '{self._select_ckpt_dependency[0]}'"
                    )
                else:
                    self._select_ckpt_dependency[0] = None
            else:
                if not self._ignoring_re_shuffle:
                    self.itr.logger.info(
                        f"{self.logger_msg}: re_shuffle job(s) were submitted...",
                    )

                if self._num_to_run != 1:
                    self.itr.logger.error(
                        f"{self.logger_msg}: max number of SLURM jobs for {msg}mission is 1 but {self._num_to_run} were provided.\nExiting... ",
                    )
                    exit(1)

                self.submit_job(msg=msg, resubmission=True)

        # or running it for the first time
        else:
            # self.find_outputs()
            self.submit_job(msg=msg)

        self.check_submission()
        return self._select_ckpt_dependency
