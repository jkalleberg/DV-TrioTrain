#!/bin/python3
"""
description: confirms log files from both training and evaluation contain expected completion strings, then adds the selected best checkpoint to the environment file (.env) as:
    <CurrentGenome>_TestCkpt - used to call variants
    <NextGenome>_StartCkpt - used as the warm-starting model weights for the next iteration

example:
    python3 triotrain/model_training/slurm/select_ckpt.py       \\
        --env-file envs/demo.env                                \\ 
        --current-ckpt /path/to/best_ckpt.txt                   \\
        --next-genome Mother                                    \\
        --next-run 2                                            \\
        --dry-run
"""
# load in python libraries
import argparse
from dataclasses import dataclass, field
from logging import Logger
from os import environ
from os import path as p
from pathlib import Path
from re import findall, sub
from sys import exit, path
from typing import Union

from regex import compile, search

abs_path = Path(__file__).resolve()
module_path = str(abs_path.parent.parent.parent)
path.append(module_path)
from helpers.environment import Env
from helpers.files import Files


# Parsing command line inputs function
def collect_args() -> argparse.Namespace:
    """
    Process the command line arguments to execute script.
    """
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "-c",
        "--current-ckpt",
        dest="current_ckpt",
        help="[REQUIRED]\ninput file (.txt)\ncontains the current best checkpoint",
        type=str,
        metavar="</path/file>",
    )
    parser.add_argument(
        "-e",
        "--env-file",
        dest="env_file",
        help="[REQUIRED]\ninput file (.env)\nprovides environment variables",
        type=str,
        metavar="</path/file>",
    )
    parser.add_argument(
        "-g",
        "--next-genome",
        dest="next_genome",
        choices=["Mother", "Father", "None"],
        help="[REQUIRED]\nsets the next training genome",
    )
    parser.add_argument(
        "-r",
        "--next-run",
        dest="next_run",
        help="[REQUIRED]\nselects the next iteration",
        metavar="<int>",
    )
    parser.add_argument(
        "-d",
        "--debug",
        dest="debug",
        help="if True, enables printing detailed messages",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        help="if True, display commands to the screen",
        action="store_true",
    )
    return parser.parse_args()
    # return parser.parse_args(
    #     [
    #         "--next-genome",
    #         "Mother",
    #         "--next-run",
    #         "2",
    #         "--current-ckpt",
    #         "/storage/hpc/group/UMAG_test/WORKING/jakth2/TRIO_TRAINING_OUTPUTS/new_trios_test/PASS1/train_Father/eval_Child/best_checkpoint.txt",
    #         "--env-file",
    #         "envs/new_trios_test-run1.env",
    #         "--debug",
    #         "--dry-run",
    #     ]
    # )


def check_args(args: argparse.Namespace, logger: Logger) -> None:
    """
    With "--debug", display command line args provided.

    With "--dry-run", display a msg.

    Then, check to make sure all required flags are provided.
    """
    if args.debug:
        str_args = "COMMAND LINE ARGS USED: "
        for key, val in vars(args).items():
            str_args += f"{key}={val} | "

        logger.debug(str_args)
        logger.debug(f"using DeepVariant version | {environ.get('BIN_VERSION_DV')}")

    if args.dry_run:
        logger.info("[DRY_RUN]: output will display to screen and not write to a file")

    assert (
        args.current_ckpt
    ), "Missing --current-ckpt; Please provide a best_checkpoint.txt file"
    assert (
        args.env_file
    ), "Missing --env-file; Please provide a file with environment variables for the current analysis"
    assert (
        args.next_genome
    ), "Missing --next-genome; Please designate the next genome that will use the selected checkpoint as the warm-starting point for training; ['Mother', 'Father', 'None']"
    assert (
        args.next_run
    ), "Missing --next-run; Please designate the next iteration number using the selected checkpoint as the warm-starting point for training"


@dataclass
class MergeSelect:
    """
    Define what data to store for the select_ckpt phase of the TrioTrain Pipeline.
    """

    ckpt_file: Path
    logger: Logger
    env: Env
    next_genome: Union[str, None] = None
    next_run: Union[int, None] = None
    _debug_mode: bool = False
    _dryrun_mode: bool = False
    _lines_with_pattern: int = field(default=0, init=False, repr=False)
    _phase: str = field(default="select_ckpt", init=False, repr=False)

    def __post_init__(self) -> None:
        # Identify current_genome
        valid_genomes = ["Father", "Mother", "None"]
        if self.next_genome is None:
            train_path = self.ckpt_file.parent.parent
            self.current_genome = train_path.stem.split("_")[1]

        elif self.next_genome not in valid_genomes:
            self.logger.error(
                f"Invalid value for provided. | 'next_genome={self.next_genome}'\nPlease enter one of the following valid options: {valid_genomes}.\nExiting... "
            )
            exit(1)
        else:
            index = valid_genomes.index(self.next_genome)
            if index == 0:
                self.current_genome = valid_genomes[1]
            elif index == 1:
                self.current_genome = valid_genomes[0]
            else:
                self.logger.error(
                    f"Unable to identify a current_genome index\nExiting... "
                )
                exit(1)

        if self._dryrun_mode:
            self._logger_msg = f"[DRY_RUN] - [{self._phase}] - [{self.current_genome}]"
        else:
            self._logger_msg = f"[{self._phase}] - [{self.current_genome}]"    
        self.logger.info(f"{self._logger_msg}: found the next genome\t\t\t| '{self.next_genome}'")

        if self.next_run is None:
            run_path = str(self.ckpt_file.parent.parent.parent.stem)
            run_num = findall(r"[0-9]+", run_path)
            if run_num:
                self.current_run = int(run_num[0])
            else:
                self.current_run = None
        else:
            self.current_run = int(self.next_run - 1)

        vars_list = [
            "RunName",
            "LogDir",
            f"{self.current_genome}_Examples",
            "N_Epochs",
            "BatchSize",
            "ExamplesDir",
            "N_Parts",
            f"{self.current_genome}TrainDir",
        ]

        (
            self.run_name,
            self.log_dir,
            self.num_examples,
            self.epochs,
            self.batch_size,
            self.examples_dir,
            self.n_parts,
            self.train_dir,
        ) = self.env.load(*vars_list)

        # Calculate the number of training steps used
        self.num_training_steps = int(
            (int(self.num_examples) / int(self.batch_size)) * int(self.epochs)
        )

    def find_log_file(self) -> None:
        """
        If a valid log file exists, open it. Used internally by count_log_lines() only.
        """
        assert (
            self.slurm_log_file.exists()
        ), f"{self._logger_msg}: required input file does not exist | '{self.slurm_log_file.name}'"
        self.logging_file = open(str(self.slurm_log_file), mode="r")

    def count_log_lines(self, train_mode=True) -> None:
        """
        If a log file contains at least one line matching a pattern, then, print the first matching line and return a value of 1.
        """
        if train_mode:
            # Check on the Model_Training Phase
            self.slurm_log_file = Path(
                f"{self.log_dir}/train-{self.current_genome}-{self.num_training_steps}steps.log"
            )
            pattern = compile(r"Loss for final step: (.*)$")
            mode = "training  "
        else:
            # Check on the Model_Evaluation Phase
            self.slurm_log_file = Path(
                f"{self.log_dir}/train-{self.current_genome}-eval-Child-{self.num_training_steps}steps.log"
            )
            pattern = compile(r"Terminating eval after(.*)$")
            # NOTE: (.*)$ regex prints to the end of the line
            mode = "evaluation"

        try:
            self.find_log_file()
        except AssertionError as e:
            self.logger.error(e)
            print("Exiting...")
            exit(1)

        for line in self.logging_file:
            match = search(pattern, line)
            if match:
                self._lines_with_pattern += 1
                if self._dryrun_mode:
                    msg = f"successfully completed {mode}\t"
                else:
                    msg = f"successfully completed {mode}\t\t"
                self.logger.info(
                    f"{self._logger_msg}: {msg}| '{self.slurm_log_file.name}'"
                )
                if self._debug_mode:
                    self.logger.debug(f"{self._logger_msg}: matching line contents\t\t\t| '{match.group(0)}'")
                self.logging_file.close()
                break
            else:
                continue

        if self._lines_with_pattern == 0:
            self.logger.warning(
                f"{self._logger_msg}: no lines in {self.slurm_log_file.name} match {pattern} pattern",
            )
            if train_mode:
                self.training_worked = False
                self.logger.error(f"{self._logger_msg}: training did not finish!\nExiting...")
            else:
                self.eval_worked = False
                self.logger.error(f"{self._logger_msg}: model evaluation did not finish!\nExiting...")
            exit(1)

        else:
            if train_mode:
                self.training_worked = True
            else:
                self.eval_worked = True

    def find_ckpt_file(self) -> None:
        """
        If a valid model.ckpt file exists, open it. Used interally by select_ckpt_name() only.
        """
        assert (
            self.ckpt_file.exists()
        ), f"{self._logger_msg}: required input file does not exist | '{self.ckpt_file.name}'"
        self.model_ckpt = open(str(self.ckpt_file), mode="r")

    def select_ckpt_name(self) -> None:
        """
        Identify which checkpoint was selected as "Best" during re-training and create new Env Variables for current iteration.
        """
        try:
            self.find_ckpt_file()
        except AssertionError as e:
            self.logger.error(e)
            print("Exiting...")
            exit(1)
        
        pattern = compile(r"model.ckpt-\d+")

        match = None
        for line in self.model_ckpt:
            match = search(pattern, line)
            if match:
                self.checkpoint = match.group(0)
                self.model_ckpt.close()
                break
            else:
                continue

        if match is None:
            self.logger.warning(f"{self._logger_msg}: unable to identify a new checkpoint")
            self.checkpoint = None
        else:
            current_model_name = (
                f"{self.run_name}-run{self.current_run}:{self.current_genome}"
            )
            self.logger.info(
                f"{self._logger_msg}: current testing ckpt identified\t\t| '{self.checkpoint}'",
            )

        if self.next_run is not None:
            next_model_name = f"{self.run_name}-run{self.next_run}:{self.next_genome}"
            self.logger.info(
                f"{self._logger_msg}: next starting ckpt identified\t\t| '{self.checkpoint}'",
            )
    
    def update_example_info(self) -> None:
        """
        Record the example format which is compatible with the new checkpoint.
        """
        _input_path = Path(self.examples_dir) / f"{self.current_genome}.region1.labeled.tfrecords-00001-of-000{self.n_parts}.gz.example_info.json"
        _input_json = Files(
            path_to_file = _input_path,
            logger = self.logger,
            logger_msg = self._logger_msg,
            debug_mode = self._debug_mode,
            dryrun_mode = self._dryrun_mode,
        )
        _input_json.check_status(should_file_exist=True)
        _input_json.load_json_file()
        
        _output_path = Path(self.train_dir) / f"{self.checkpoint}.example_info.json"
        _output_json = Files(
            path_to_file = _output_path,
            logger = self.logger,
            logger_msg = self._logger_msg,
            debug_mode = self._debug_mode,
            dryrun_mode = self._dryrun_mode,
        )
        _output_json.check_status()
        _output_json.file_dict = _input_json.file_dict        
        _output_json.write_json_file()

    def record_results(self) -> None:
        """
        Add the number of successfully run training steps to EnvFile as a record of experiement.
        """
        if f"{self.current_genome}_N_Steps" not in self.env.contents:
            self.env.add_to(
                f"{self.current_genome}_N_Steps",
                str(self.num_training_steps),
                dryrun_mode=self._dryrun_mode,
                msg=self._logger_msg
            )

        # Add the new checkpoint to current Env File
        if (
            f"{self.current_genome}TestCkptName" not in self.env.contents
            and self.checkpoint is not None
        ):
            self.env.add_to(
                f"{self.current_genome}TestCkptName", self.checkpoint, dryrun_mode=self._dryrun_mode, msg=self._logger_msg
            )

        # Add the new checkpoint to next Env File
        if self.next_genome is not None and self.next_run is not None:
            if self.next_run == self.current_run:
                if (
                    f"{self.next_genome}StartCkptName" not in self.env.contents
                    and self.checkpoint is not None
                ):
                    self.env.add_to(
                        f"{self.next_genome}StartCkptName",
                        self.checkpoint,
                        dryrun_mode=self._dryrun_mode,
                        msg=self._logger_msg
                    )
            else:
                analysis_name = self.env.env_path.name.split("-")[0]
                new_env_name = sub(r'\d+', str(self.next_run), analysis_name)
                next_env_file = self.env.env_path.parent / new_env_name
                next_env = Env(next_env_file, self.logger, logger_msg=self._logger_msg, debug_mode=self._debug_mode, dryrun_mode=self._dryrun_mode)

                if (
                    f"{self.next_genome}StartCkptName" not in next_env.contents
                    and self.checkpoint is not None
                ):
                    next_env.add_to(
                        f"{self.next_genome}StartCkptName",
                        self.checkpoint,
                        dryrun_mode=self._dryrun_mode,
                        msg=self._logger_msg
                    )

    def run(self) -> None:
        """
        Combine the entire select_ckpt phase into one callable function.
        """
        self.count_log_lines()
        self.count_log_lines(train_mode=False)
        self.select_ckpt_name()
        self.update_example_info()
        self.record_results()


def __init__() -> None:
    """
    Final function to perform select_ckpt within a SLURM job
    """
    from helpers.utils import get_logger
    from helpers.wrapper import Wrapper, timestamp

    # Collect command line arguments
    args = collect_args()

    # Collect start time
    Wrapper(__file__, "start").wrap_script(timestamp())

    # Create error log
    current_file = p.basename(__file__)
    module_name = p.splitext(current_file)[0]
    logger = get_logger(module_name)

    # Check command line args
    check_args(args, logger)

    if "None" in args.next_genome:
        next_genome = None
    else:
        next_genome = str(args.next_genome)

    if "None" in args.next_run:
        next_run = None
    else:
        next_run = int(args.next_run)

    env = Env(args.env_file, logger, dryrun_mode=args.dry_run, debug_mode=args.debug)
    ckpt_file = Path(args.current_ckpt)

    MergeSelect(
        ckpt_file,
        logger,
        env,
        next_genome,
        next_run,
        _debug_mode=args.debug,
        _dryrun_mode=args.dry_run,
    ).run()

    Wrapper(__file__, "end").wrap_script(timestamp())


# Execute functions created
if __name__ == "__main__":
    __init__()
