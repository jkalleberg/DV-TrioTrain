# /usr/bin/python3
"""
description: merges a region's shuffled examples shards into (1) tfrecord file, then, creates a re-shuffled config file (.dataset_config.pbtxt containing a randomized list of Apptainer binding paths for all regions' tfrecord files, then counts the total number of examples created across all regions, and finally, adds a new environment variable to the environment file (.env).

example:
    python3 triotrain/model_training/slurm/re_shuffle.py           \\
        --env-file envs/demo.env                           \\
        --genome Mother                                    \\
        --start-itr
        --dry-run
"""
# Load python libraries
import argparse
from dataclasses import dataclass, field
from logging import Logger
from os import environ
from os import path as p
from pathlib import Path
from random import random, sample
from subprocess import getstatusoutput
from sys import exit, path
from typing import List, Union

abs_path = Path(__file__).resolve()
module_path = str(abs_path.parent.parent.parent)
path.append(module_path)
from helpers.iteration import Iteration
from helpers.wrapper import timestamp
from model_training.prep.examples_count import CountExamples
from model_training.prep.examples_re_shuffle import ReShuffleExamples


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
        "-e",
        "--env-file",
        dest="env_file",
        help="[REQUIRED]\ninput file (.env)\nprovides environment variables",
        type=str,
        metavar="</path/file>",
    )
    parser.add_argument(
        "-g",
        "--genome",
        dest="genome",
        choices=["Mother", "Father", "Child"],
        help="[REQUIRED]\nsets the genome to use within a Trio",
        type=str,
    )
    parser.add_argument(
        "--start-itr",
        dest="restart",
        help="[REQUIRED]\nstart a pipeline at a specified genome iteration.\nexample: to start @ Trio2-Parent1, set --start-itr=3",
        type=int,
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
        "--demo-mode",
        dest="demo_mode",
        help="if True, indicates that re-shuffling will use a demo chromosome",
        action="store_true",
    )
    parser.add_argument(
        "--demo-chr",
        dest="demo_chr",
        help="sets which chromosome to use for demo mode\n(default: %(default)s)",
        default="29",
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
    #         "--debug",
    #         "--demo-mode",
    #         "-e",
    #         "envs/DemoPass-run1.env",
    #         "-g",
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
    ), "Missing --env-file; Please provide a file with environment variables for the current analysis"
    assert (
        args.genome
    ), "Missing --genome; Please designate which genome to re-shuffle ['Mother', 'Father', 'Child']"
    assert (
        args.restart
    ), "Missing --start-itr; Please designate the iteration number you'd like to re-shuffle"


@dataclass
class ReShuffle:
    """
    Define what data to store for the re_shuffle_examples phase of the TrioTrain Pipeline.
    """

    itr: Iteration
    train_mode: bool = True
    _n_examples: Union[int, None] = field(default=None, init=False, repr=False)
    _num_merged_regions: int = field(default=0, init=False, repr=False)
    _phase: str = field(default="re_shuffle", init=False, repr=False)
    _re_shuffled_regions: List[str] = field(
        default_factory=list, init=False, repr=False
    )
    _string_of_files: Union[str, None] = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.itr.env is None:
            return
        self.re_shuffling = ReShuffleExamples(
            itr=self.itr, slurm_resources={}, model_label="", train_mode=self.train_mode
        )
        self.re_shuffling.set_genome()
        self.re_shuffling.find_outputs(phase="find_outputs", find_all=True)

        if self.itr.demo_mode:
            self._total_regions = 1
        else:
            self._total_regions = str(
                self.itr.env.contents[f"{self.re_shuffling.genome}_NumRegionFiles"]
            )

    def set_region(self, current_region: Union[int, str, None] = None) -> None:
        """
        Define the current region
        """
        if self.itr.demo_mode:
            if "chr" in self.itr.demo_chromosome.lower():
                self.region_string = f"{self.itr.demo_chromosome}"
            else:
                self.region_string = f"chr{self.itr.demo_chromosome}"

            self.logger_msg = f"{self.itr._mode_string} - [{self._phase}] - [{self.re_shuffling.genome}]"
        else:
            if current_region is None:
                self.region_string = None
                self.logger_msg = f"{self.itr._mode_string} - [{self._phase}] - [{self.re_shuffling.genome}]"
            else:
                self.region_string = f"region{current_region}"
                self.logger_msg = f"{self.itr._mode_string} - [{self._phase}] - [{self.re_shuffling.genome}] - [{self.region_string}]"

        self.merged_msg = (
            f"{self.itr._mode_string} - [merge] - [{self.re_shuffling.genome}]"
        )

    def merge_shuffled_tfrecords_shards(self) -> None:
        """
        Merge each region's sharded tfrecords into one file.
        """
        self.output = (
            self.itr.examples_dir
            / f"{self.re_shuffling.genome}.{self.region_string}.labeled.shuffled.merged.tfrecord.gz"
        )

        if self.output.is_file() and self.re_shuffling._merged_tfrecords_exist:
            self._num_merged_regions += 1
        else:
            # use bash 'concat' to join tfrecords together
            cmd = f"time cat {self.itr.examples_dir}/{self.re_shuffling.genome}.{self.region_string}.labeled.shuffled-*.gz > {str(self.output)}"
            status, result = getstatusoutput(cmd)
            try:
                assert (
                    status == 0
                ), f"failed to merge the shuffled tfrecords shards for [{self.re_shuffling.genome}-{self.region_string}] into a single file"
                self._num_merged_regions += 1
                self.itr.logger.info(
                    f"{self.itr._mode_string} - [merge] - [{self.re_shuffling.genome}] - [region {self._num_merged_regions}-of-{self._total_regions}]: merging beam-shuffled shards into a single file",
                )
            except AssertionError as error_msg:
                self.itr.logger.error(f"{error_msg}\nExiting... ")
                exit(1)

    def merge_regions(self) -> None:
        """
        Iterate through all regions and merge.
        """
        for region in range(0, int(self._total_regions)):
            file_num = region + 1
            self.set_region(current_region=file_num)
            self.merge_shuffled_tfrecords_shards()

    def randomize_regions(self) -> None:
        """
        Sample the regions numbers without replacement.
        """
        if self.itr.demo_mode:
            self.itr.logger.info(
                f"{self.logger_msg}: no need to randomize regions for demo... SKIPPING AHEAD",
            )
            self._string_of_files = f"/examples_dir/{self.output.name}"
        else:
            self.itr.logger.info(
                f"{self.logger_msg}: randomizing the order of merged regions now... ",
            )
            random_regions = sample(
                range(1, self._num_merged_regions + 1), self._num_merged_regions
            )

            for rando in random_regions:
                self._re_shuffled_regions.append(
                    f"/examples_dir/{self.re_shuffling.genome}.region{rando}.labeled.shuffled.merged.tfrecord.gz"
                )

            if self._re_shuffled_regions:
                self._string_of_files = ",".join(self._re_shuffled_regions)
            else:
                self.itr.logger.error(
                    f"{self.logger_msg}: randomizing did not work\nExiting...",
                )
                exit(1)

    def create_merged_pbtxt(self) -> None:
        """
        Create one final, merged.pbtxt file with num_examples summed across all regions.
        """
        if self.itr.dryrun_mode:
            self.itr.logger.info(
                f"{self.logger_msg} | new config contents\n---------------------------------------"
            )
            print(
                f"name: {self.re_shuffling.genome}\ntfrecord_path: {self._string_of_files}\nnum_examples: {self._n_examples}\n# Generated by re_shuffle.py on {timestamp()}\n---------------------------------------"
            )
        elif self.re_shuffling.merged_config.file_path.exists() is False:
            self.itr.logger.info(
                f"{self.merged_msg}: writing the final, merged pbtxt file now... "
            )
            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"{self.merged_msg}: new config file | {str(self.re_shuffling.merged_config.file_path)}"
                )
            with open(
                str(self.re_shuffling.merged_config.file_path),
                mode="w",
                encoding="UTF-8",
            ) as text_file:
                text_file.write(
                    f'name: "{self.re_shuffling.genome}"\ntfrecord_path: "{self._string_of_files}"\nnum_examples: {self._n_examples}\n# Generated by re_shuffle.py on {timestamp()}'
                    ""
                )
        else:
            self.itr.logger.info(
                f"{self.merged_msg}: the final, merged pbtxt does not need to be written... SKIPPING AHEAD"
            )

    def run(self) -> None:
        """
        Combine all the steps required to merge and re_shuffle tfrecords into one step.
        """
        self.set_region()

        if self._n_examples is None:
            self._n_examples = CountExamples(self.itr, self.train_mode).run()

        if not self.re_shuffling._merged_config_exists:
            self.merge_regions()
            self.randomize_regions()
            if self.itr.debug_mode:
                self.itr.logger.debug(f"Re-Shuffled Files | {self._string_of_files}")
            self.create_merged_pbtxt()


# Create re-shuffled pbtxt file function
def __init__() -> None:
    """
    Final function to perform re_shuffling within a SLURM job.
    """
    from helpers.environment import Env
    from helpers.utils import get_logger
    from helpers.wrapper import Wrapper

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
    env = Env(args.env_file, logger, dryrun_mode=args.dry_run, debug_mode=args.debug)
    trio_num = str(env.contents["RunOrder"])

    if args.demo_mode:
        total_regions = 1
    else:
        regions_variable_name = f"{args.genome}_NumRegionFiles"
        if regions_variable_name in env.contents.keys():
            total_regions = str(env.contents[regions_variable_name])
        else:
            raise ValueError(
                f"{regions_variable_name} could not be found in {env.env_path.name}"
            )

    if args.genome == "Child":
        train_genome = None
        eval_genome = args.genome
        eval_regions = int(total_regions)
        train_regions = 0
        train_mode = False
    else:
        train_genome = args.genome
        eval_genome = None
        train_regions = int(total_regions)
        eval_regions = 0
        train_mode = True

    current_itr = Iteration(
        current_trio_num=trio_num,
        next_trio_num="None",
        current_genome_num=args.restart,
        total_num_genomes=(args.restart + 1),
        total_num_tests=19,
        train_genome=train_genome,
        eval_genome=eval_genome,
        train_num_regions=int(train_regions),
        eval_num_regions=int(eval_regions),
        env=env,
        logger=logger,
        args=args,
    )
    if args.debug:
        logger.debug(f"Current Iteration | {current_itr}")

    ReShuffle(current_itr, train_mode=train_mode).run()

    Wrapper(__file__, "end").wrap_script(timestamp())


# Execute all functions created
if __name__ == "__main__":
    __init__()
