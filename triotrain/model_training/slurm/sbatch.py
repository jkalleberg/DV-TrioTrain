#!/bin/python3
"""
description: contains dataclasses for working with SLURM

usage:
    from sbatch import SBATCH, SubmitSBATCH
"""
import random
import time
from dataclasses import dataclass, field
from logging import Logger
from pathlib import Path
from subprocess import run
from typing import Union

import helpers as h
from iteration import Iteration
from regex import compile


@dataclass
class SBATCH:
    """
    Create a custom SBATCH class object, which results in an sbatch file.
    """
    itr: Iteration
    job_name: str
    error_file_label: Union[str, None]
    handler_status_label: Union[str,None]
    logger_msg: str
    _command_list: list = field(init=False, repr=False, default_factory=list)
    _header_lines: list = field(init=False, repr=False, default_factory=list)
    _line_list: list = field(init=False, repr=False, default_factory=list)
    _num_lines: Union[None, int] = None

    def __post_init__(self) -> None:
        self._jobfile = self.itr.job_dir / f"{self.job_name}.sh"
        self._jobfile_str = str(self._jobfile)

        if self.error_file_label is not None:
            self._tracking_file = self.itr.log_dir / f"tracking-{self.error_file_label}.log"

        self._header_lines = ["#!/bin/bash"]

        self._start_conda = [
            "source ${CONDA_BASE}/etc/profile.d/conda.sh",
            "conda deactivate",
        ]

        if self.itr.env is not None:
            self._start_sbatch = [
                ". scripts/setup/modules.sh",
                f". scripts/model_training/slurm_environment.sh {self.itr.env.env_file}",
                "echo '=== Science Starts Now: '$(date '+%Y-%m-%d %H:%M:%S')",
            ]
        else:
            self._start_sbatch = [
                ". scripts/setup/modules.sh",
                "echo '=== Science Starts Now: '$(date '+%Y-%m-%d %H:%M:%S')",
            ]

    def slurm_headers(self, use_job_array=False, **flags) -> None:
        """
        Defines each SLURM flag and writes them in SBATCH header format.

        Usage: slurm_headers(
              partition="BioCompute,Lewis",
              nodes=1,
              ntasks=24,
              mem="30G",
              email="jakth2@mail.missouri.edu"
              )
        """
        if self.itr.debug_mode:
            self.itr.logger.debug(f"{self.logger_msg}: defining SBATCH headers... ")
        for key, value in flags.items():
            if key == "email":
                if value != "":
                    self._header_lines.append(f"#SBATCH --mail-user={value}")
                    # self._header_lines.append("#SBATCH --mail-type=FAIL,TIME_LIMIT,END")
                    # self._header_lines.append("#SBATCH --mail-type=FAIL,END")
                    self._header_lines.append("#SBATCH --mail-type=FAIL")
            elif key == "CPUmem":
                self._header_lines.append("#SBATCH --ntasks-per-core=1")
                self._header_lines.append(f"#SBATCH --mem-per-cpu={str(value)}")
            elif key == "ntasks":
                self._header_lines.append(f"#SBATCH -n {str(value)}")
            elif key == "mem":
                if str(value).isnumeric() and int(value) == 0:
                    self._header_lines.append(f"#SBATCH --{key}={str(value)}")
                    self._header_lines.append(f"#SBATCH --exclusive")
                else:
                    self._header_lines.append(f"#SBATCH --{key}={str(value)}")
            else:
                self._header_lines.append(f"#SBATCH --{key}={str(value)}")

        self._header_lines.append(f"#SBATCH --job-name={self.job_name}")
        if use_job_array is False:
            self._header_lines.append(f"#SBATCH --output={self.itr.log_dir}/%x_%j.out")
        # else:
        #     self.header_lines.append(f"#SBATCH --array=1-{self.n_array_tasks}")
        #     self.header_lines.append(f"#SBATCH --output={self.log_dir}/%x-%A-%a_%j.out")

        self._header_lines.append("echo '=== SBATCH running on: '$(hostname)")
        self._header_lines.append("echo '=== SBATCH running directory: '${PWD}")
        self._header_lines.extend(self._start_sbatch)

    def command_builder(self, command_list: list) -> None:
        """
        Creates a list to store lines of science performed by SBATCH job.
        """
        if self.itr.debug_mode:
            self.itr.logger.debug(f"{self.logger_msg}: building science... ")
        self._line_list.extend(command_list)

    def handle_errors(
        self, message, status_tracker_file, error_handler_index: int = -1
    ) -> None:
        """
        Captures the error code from a command.

        If the job fails (exit != 0), this error handler
        will use the errorcode to trigger a job failure email from
        SLURM.

        Enables interruption of future jobs, if the prior job fails.
        """
        if self.itr.debug_mode:
            self.itr.logger.debug(f"{self.logger_msg}: adding error handler... ")
        last_line = self._line_list[error_handler_index]
        errors = f' && success_exit "{message}" {status_tracker_file} || error_exit "{message}" {status_tracker_file}'
        if error_handler_index != -1:
            errors = errors + " &"
        error_handler = last_line + errors
        self._line_list[error_handler_index] = error_handler

    def check_sbatch_file(self) -> bool:
        """
        Confirms the job file does NOT exist already.
        """
        if self.itr.debug_mode:
            self.itr.logger.debug(f"{self.logger_msg}: checking for prior SBATCH file... ")
        result = h.TestFile(self._jobfile_str, self.itr.logger)
        result.check_missing()
        return result.file_exists

    def create_slurm_job(
        self,
        handler_status_label: Union[str,None],
        command_list: list,
        error_index: int = -1,
        overwrite: bool = False,
        **slurm_resources: dict,
    ) -> None:
        """
        Creates the '---Science Goes Here---' contents
        of a SLURM job using:

            handler_status_label: a file label used for logging msgs

            command_list: a list of each line of 'science'
        """
        self.handler_status_label = handler_status_label
        self.command = command_list
        self.command_builder(self.command)
        if self.handler_status_label is not None:
            self.handle_errors(
                self.handler_status_label,
                self._tracking_file,
                error_handler_index=error_index,
            )
        if overwrite:
            self.job_file_exists = False
        else:
            self.job_file_exists = self.check_sbatch_file()

        if self.job_file_exists is False:
            if len(self._header_lines) == 1:
                self.slurm_headers(**slurm_resources)
            self.all_lines = self._header_lines + self._line_list
            self._num_lines = len(self._line_list)
        elif self.job_file_exists is True:
            self._num_lines = None

    def display_job(self) -> None:
        """
        Prints the SLURM job file contents to the screen.
        """
        if self._num_lines is not None:
            self.itr.logger.info(
                f"[DRY RUN] - {self.logger_msg}: file contents for '{self._jobfile.name}'\n-------------------------------------"
            )
            print(*self.all_lines, sep="\n")
            print("------------------------------------")

    def write_job(self) -> None:
        """
        Writes the SLURM job file contents to a text file.
        """
        if self._num_lines is not None:
            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"{self.logger_msg}: job file [{self._jobfile.name}] has [{self._num_lines}] lines of science"
                )
            with open(self._jobfile_str, mode="w") as file:
                file.writelines(f"{line}\n" for line in self.all_lines)
            self.itr.logger.info(f"{self.logger_msg}: new job file created |  '{self._jobfile.name}'")

class SubmitSBATCH:
    """
    Create a custom SubmitSBATCH object, which submits an SBATCH file to the SLURM queue.

    Examples:
        slurm_job = SubmitSBATCH('this-is-a-slurm_job.sh', 'hello there', 'my name is jenna', 'cats are awesome')

        kwargs = {"partition" : "BioCompute,hpc5,hpc6", "nodes" : 1, "ntasks" : 40, "mem" : "20G", "CPUmem" : 9099, "time" : "2:00:00", "account" : "animalsci", "email" : "jakth2@mail.missouri.edu"}

        headers i slurm_job.slurm_headers(**kwargs)

        slurm_job.displayjob(**kwargs)
    """

    def __init__(self, sbatch_dir: Path, job_file: str, label: str, logger: Logger, logger_msg: str):
        self.job_file = sbatch_dir / job_file
        self.job_label = label
        self.jobnum_pattern = compile(r"\d+")
        self.logger = logger
        self.logger_msg = logger_msg
        self.job_number: str
        self.slurm_dependency: list
        self.cmd: list
        self.prior_job: Union[None, str, list]
        self.status: int

    def build_command(
        self, prior_job_number: Union[None, str, list], allow_dep_failure: bool = False
    ):
        """
        Creates a 'sbatch <job_file>' subprocess command, depending on if there are job dependencies or not.
        """
        if prior_job_number is None:
            self.cmd = ["sbatch", str(self.job_file)]
        else:
            self.prior_job = prior_job_number
            if isinstance(self.prior_job, str):
                if allow_dep_failure:
                    self.slurm_dependency = [
                        f"--dependency=afterany:{self.prior_job}",
                        "--kill-on-invalid-dep=yes",
                    ]
                else:
                    self.slurm_dependency = [
                        f"--dependency=afterok:{self.prior_job}",
                        "--kill-on-invalid-dep=yes",
                    ]
                self.cmd = (
                    ["sbatch"] + self.slurm_dependency + [f"{str(self.job_file)}"]
                )
            elif isinstance(self.prior_job, list):
                no_priors = h.check_if_all_same(self.prior_job, None)
                if no_priors:
                    self.cmd = ["sbatch", str(self.job_file)]
                else:
                    self.slurm_dependency = h.collect_job_nums(
                        self.prior_job, allow_dep_failure=allow_dep_failure
                    )
                    self.cmd = (
                        ["sbatch"] + self.slurm_dependency + [f"{str(self.job_file)}"]
                    )

    def display_command(self, current_job: int = 1, total_jobs: int = 1, display_mode=False, debug_mode=False):
        """
        Prints the sbatch command used to submit a job.
        """
        if display_mode:
            self.logger.info(f"[DRY RUN] - {self.logger_msg}: command used | {' '.join(self.cmd)}")
            self.logger.info(f"[DRY RUN] - {self.logger_msg}: pretending to submit SLURM job {current_job}-of-{total_jobs}") 
        elif debug_mode:
            self.logger.debug(f"{self.logger_msg}: submitting SLURM job with command: {' '.join(self.cmd)}")
    
    def get_status(self, current_job: int = 1, total_jobs: int = 1, debug_mode=False):
        """
        Determines if a SLURM job was submitted correctly.
        """
        # Sleep a bit, for <1 second before
        # submission to SLURM queue
        time.sleep(random.random())
        # wait for previous process to close
        # before opening another
        if debug_mode:
            self.logger.debug(f"{self.logger_msg}: submitting a SLURM job to SLURM... ")
        result = run(self.cmd, capture_output=True, text=True, check=True)
        self.status = result.returncode
        if self.status == 0:
            self.logger.info(f"{self.logger_msg}: submitted SLURM job {current_job}-of-{total_jobs}")
            match = self.jobnum_pattern.search(result.stdout)
            if match:
                self.job_number = str(match.group())
                if debug_mode:
                    self.logger.debug(f"{self.logger_msg}: SLURM Job Number |  {self.job_number}")
            else:
                self.logger.warning(
                    f"{self.logger_msg}: unable to detect SLURM Job Number during submission of: [{self.job_label}]",
                )
                self.logger.info(f"{self.logger_msg}: skipping SLURM job [{self.job_file}]")
        else:
            self.logger.error(f"{self.logger_msg}: unable to submit SLURM Job [{self.job_label}]")
            self.logger.error(f"{self.logger_msg}: process stdout:\n{result}")
            self.logger.info(f"{self.logger_msg}: skipping job [{self.job_file}]")
