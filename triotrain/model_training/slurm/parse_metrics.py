#!/bin/python3
"""
description: process multiple evaluation performance metrics (.JSON) into a single clean (.CSV) for plotting.

example:

    python3 triotrain/model_training/pipeline/parse_metrics.py \\
        --env-file </path/to/ENV_file> \\
        --genome <genome_label>

"""
# Load libraries
import argparse
from sys import exit, path
from dataclasses import dataclass, field
from json import load
from logging import Logger
from os import environ, getcwd, path as p
from pathlib import Path

import pandas as pd

abs_path = Path(__file__).resolve()
module_path = str(abs_path.parent.parent.parent)
path.append(module_path)
from helpers.environment import Env
from helpers.files import WriteFiles


def collect_args() -> argparse.Namespace:
    """
    Require two command line arguments to execute script.
    """
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-e",
        "--env-file",
        dest="env_file",
        help="[REQUIRED]\ninput file (.env)\nprovides environmental variables",
        type=str,
        metavar="</path/file>",
    )
    parser.add_argument(
        "-g",
        "--genome",
        dest="genome",
        choices=["Mother", "Father"],
        help="[REQUIRED]\nsets the genome to process training metrics",
        type=str,
    )
    parser.add_argument(
        "-d",
        "--debug",
        dest="debug",
        help="print debug info",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        help="display evaulation metrics to the screen",
        action="store_true",
    )
    parser.add_argument(
        "--threshold",
        dest="threshold",
        help="defines the proportion of the training genome should be covered by the new model\n(default: %(default)s)",
        type=float,
        default=20.0,
        metavar="<float>"
    )

    return parser.parse_args()
    # return parser.parse_args(
    #     [
    #         "--dry-run",
    #         "--env-file",
    #         "envs/new_trios_test-run1.env",
    #         "--genome",
    #         "Father",
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
        args.env_file
    ), "missing --env-file; Please provide a file with environment variables for the current analysis"
    assert (
        args.vcf_file
    ), "missing --vcf-file; Please designate a hap.py VCF file to process"


@dataclass
class ParseMetrics:
    """
    define what data to keep when parsing tensorflow .metrics files
    """

    genome: str
    env: Env
    logger: Logger
    threshold: float = 20.0
    _debug_mode: bool = False
    _dryrun_mode: bool = False
    _eval_genome: str = "Child"
    _phase: str = field(default="parse_metrics", init=False, repr=False)

    def load_variables(self) -> None:
        """
        load in environment variables
        """
        vars_list = [
            "RunName",
            "RunOrder",
            "CodePath",
            "ResultsDir",
            f"{self.genome}TrainDir",
            f"{self.genome}_N_Steps",
            "N_Epochs",
        ]
        (
            self._run_name,
            self._current_run,
            code_path,
            self._outpath,
            self._train_dir,
            self._total_steps,
            self._epochs,
        ) = self.env.load(*vars_list)

        try:
            assert (
                getcwd() == code_path
            ), f"{self._logger_msg}: run the workflow in the deep-variant/ directory only!"
        except AssertionError as error_msg:
            self.logger.error(f"{error_msg}.\nExiting... ")
            exit(1)

    def set_genome(self) -> None:
        """
        define which genome from a Trio to parse metrics
        """
        if self._dryrun_mode:
            self._logger_msg = f"[DRY_RUN] - [{self._phase}] - [{self.genome}]"
        else:
            self._logger_msg = f"[{self._phase}] - [{self.genome}]"

        self._eval_dir = Path(f"{self._train_dir}/eval_{self._eval_genome}")
        assert (
            self._eval_dir.is_dir()
        ), f"evaluation directory does not exist | '{self._eval_dir}'"

        self._output_dir = Path(self._outpath)
        assert (
            self._output_dir.is_dir()
        ), f"output directory does not exist | '{self._output_dir}'"
        

    def clean_files(self):
        """
        Identify all metrics files from re-training evaulation.

        Clean up duplicate metrics and sort by earliest steps to later steps.

        Include some metadata columns so that multiple CSVs
        from other re-trainings can be plotted together.

        NOTE: used internally by clean_sort_metrics()
        """
        # Identify all files from re-training
        # evaluations using pathlib
        metrics_name, metrics_stem = [], []
        files_in_basepath = (
            entry for entry in self._eval_dir.iterdir() if entry.is_file()
        )

        # Extract the full file name for all
        # evaluation metrics files
        # Extract the file name without extension as well
        # NOTE: this wipes the generator object above clean!!
        # Must be re-run if testing
        for item in files_in_basepath:
            if item.suffix == ".metrics":
                metrics_name.append(item.name)
                metrics_stem.append(item.stem)

        # Count how many files match
        self._total_metrics = len(metrics_stem)
        assert self._total_metrics > 0, f"{self._logger_msg}: no existing evaluation metrics files were found"

        # Create data descriptor columns to keep records unique
        run_order, model, train_order = (
            [self._current_run] * self._total_metrics,
            [self._run_name] * self._total_metrics,
            [self.genome] * self._total_metrics,
        )

        # Create a list of row data
        rows_list = []

        # Read in the file text which is in JSON format
        # RESULT: a dictionary object
        for file in range(len(metrics_stem)):
            metrics = self._eval_dir / metrics_name[file]
            with metrics.open(mode="r") as read_file:
                step_metrics = load(read_file)
                rows_list.append(step_metrics)

        # Create a pandas DataFrame
        data = pd.DataFrame(rows_list)
        data = data.apply(pd.to_numeric)

        # Insert the descriptor columns
        data.insert(0, "Run", run_order)
        data.insert(1, "RunName", model)
        data.insert(2, "Parent", train_order)

        # Insert the checkpoint names for the metrics data
        data.insert(3, "CheckpointName", metrics_stem)

        # Remove the duplicate metrics file for final eval step
        indexes_to_drop1 = data.index[data["CheckpointName"] == "current"]
        indexes_to_drop2 = data.index[data["CheckpointName"] == "best_checkpoint"]
        indexes_to_keep = (
            set(range(data.shape[0])) - set(indexes_to_drop1) - set(indexes_to_drop2)
        )
        data_sliced = data.take(list(indexes_to_keep))
        self._num_metrics = data_sliced.shape[0]
        if self._num_metrics == self._total_metrics - 1:
            self.logger.info(
                f"{self._logger_msg}: ignoring duplicate metrics in file labeled 'current' & 'best_checkpoint'"
            )
            self.logger.info(
                f"{self._logger_msg}: keeping results from {self._num_metrics} metrics files"
            )

        # Sort by step num
        self._sorted_data = data_sliced.sort_values(by=["global_step"])  # type: ignore

    def clean_sort_metrics(self) -> None:
        """
        clean up and sort all metrics files
        """
        try:
            if self._debug_mode:
                self.logger.debug(
                    f"{self._logger_msg}: currently working | '{str(self._eval_dir)}'"
                )
            self.clean_files()
            if self._debug_mode:
                self.logger.debug(
                    f"{self._logger_msg}: found {self._num_metrics} uniqe evaluations\t| {self._run_name}-{self.genome}",
                )
        except AssertionError as error_msg:
            self.logger.error(error_msg)
            exit(1)

        max_f1_all = self._sorted_data[["F1/All"]].idxmax()
        min_loss = self._sorted_data[["loss"]].idxmin()
        self._best_f1_all_ckpt_name = self._sorted_data.loc[
            max_f1_all, "CheckpointName"
        ].item()
        self._best_ckpt_steps = self._best_f1_all_ckpt_name.split("-")[1]
        self._lowest_loss_ckpt_name = self._sorted_data.loc[
            min_loss, "CheckpointName"
        ].item()
        self._lowest_loss_steps_num = self._lowest_loss_ckpt_name.split("-")[1]

    def process_evaluations(self) -> None:
        """
        determine if there is a descrepency between the possible 'best-ckpts'
        """
        self.logger.info(
            f"{self._logger_msg}: using {self._num_metrics}-of-{self._total_metrics} metrics files"
        )
        self.logger.info(
            f"{self._logger_msg}: MAXIMUM F1/All score\t\t| {self._best_f1_all_ckpt_name}"
        )
        self.logger.info(
            f"{self._logger_msg}: MINIMUM Loss\t\t\t| {self._lowest_loss_ckpt_name}"
        )

        if int(self._best_ckpt_steps) != int(self._lowest_loss_steps_num):
            self.logger.warning(
                f"{self._logger_msg}: different best checkpoint\t\t| "
            )
            self.logger.warning(
                f"{self._logger_msg}: consider alternative performance metric for selecting checkpoint\t| "
            )
        else:
            self.logger.info(
                f"{self._logger_msg}: identical best checkpoint\t\t| SUCCESS"
            )
        steps_per_genome = int(self._total_steps) / int(self._epochs)
        self.logger.info(
            f"{self._logger_msg}: training steps per epoch\t\t| '{int(steps_per_genome):,}'"
        )
        prop_genome_used_in_training = (
            int(self._best_ckpt_steps) / steps_per_genome
        ) * 100
        self.logger.info(
            f"{self._logger_msg}: epoch proportion at best-ckpt\t| '{round(prop_genome_used_in_training, 3)}%'",
        )

        # This is a threshold to alert me if the entire re-training
        # worse than the previous model. Alert only, does not interfere
        # with selection or testing.
        # threshold = 20.0
        if prop_genome_used_in_training < self.threshold:
            self.logger.warning(
                f"{self._logger_msg}: new model saw less than {self.threshold}% of the training genome"
            )
            self.logger.warning(
                f"{self._logger_msg}: new checkpoint {self._best_f1_all_ckpt_name} may be very similar to prior model",
            )
            self.logger.warning(
                f"{self._logger_msg}: current used less than{self.threshold}%\t| WARNING"
            )
        else:
            self.logger.info(
                f"{self._logger_msg}: training used more than {self.threshold}%\t| SUCCESS",
            )

    def save_results(self) -> None:
        """
        write the processed metrics to an intermediate file
        """
        if self._dryrun_mode is False:
            self.logger.info(
                f"{self._logger_msg}: parsed metrics CSV directory\t| '{str(self._output_dir)}'"
            )
            # Define the output CSV to be created
            outfile = WriteFiles(
                self._outpath,
                f"{self._run_name}-{self.genome}-evaluation-metrics.csv",
                self.logger,
            )
            outfile.check_missing()

            if outfile.file_exists:
                self.logger.info(f"{self._logger_msg}: CSV output already exists... SKIPPING AHEAD")
            else:
                # Write the sorted data to a CSV
                self._sorted_data.to_csv(outfile.file_path, index=False)
                if self._debug_mode:
                    self.logger.debug(f"{outfile.file} written")

                assert (
                    outfile.file_path.exists()
                ), f"{outfile.file} was not written correctly"
                
        else:
            self.logger.info(
                f"{self._logger_msg}: evaluation metrics contents, sorted by step number"
            )
            print(self._sorted_data)

    def run(self) -> None:
        """
        putting all the steps for parsing metrics into one command
        """
        self.load_variables()
        self.set_genome()
        self.clean_sort_metrics()
        self.process_evaluations()
        self.save_results()


def __init__() -> None:
    """
    Collect evaluation metrics across multiple evaluations
    into a single CSV file.
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
    _version = environ.get("BIN_VERSION_DV")

    if args.debug:
        str_args = "COMMAND LINE ARGS USED: "
        for key, val in vars(args).items():
            str_args += f"{key}={val} | "
        logger.debug(str_args)
        logger.debug(f"using DeepVariant version {_version}")

    if args.dry_run:
        logger.info("option [--dry-run] set; displaying evaluation metrics to screen only")
        pd.set_option("display.max_rows", None)
        pd.set_option("display.max_columns", None)

    env = Env(args.env_file, logger, dryrun_mode=args.dry_run)
    ParseMetrics(args.genome, env, logger, threshold=args.threshold, _debug_mode=args.debug, _dryrun_mode = args.dry_run).run()

    Wrapper(__file__, "end").wrap_script(timestamp())


# Execute functions created
if __name__ == "__main__":
    __init__()
