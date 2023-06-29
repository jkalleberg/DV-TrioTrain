#!/bin/python3
"""
description: removes all temporary files made for the entire trio.

example:
    python3 triotrain/model_training/slurm/clean_tmp.py              \\
        --env-file envs/demo.env                             \\
        --dry-run
"""

# load python libraries
import argparse
from dataclasses import dataclass, field
from logging import Logger
from os import environ, path as p
from pathlib import Path
from shutil import copy2, rmtree
from sys import exit, path
from typing import Dict, List

from natsort import natsorted
from regex import compile, search

abs_path = Path(__file__).resolve()
module_path = str(abs_path.parent.parent.parent)
path.append(module_path)
from helpers.environment import Env
from helpers.files import TestFile


def collect_args() -> argparse.Namespace:
    """
    Require three command line arguments to execute script.
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
        help="pretend to remove files only",
        action="store_true",
    )
    # return parser.parse_args(
    #     ["--env-file", "envs/TriosPASS_30PopBeam-run1.env", "--genome", "Mother", "--mode", "custom", "--dry-run"]
    # )
    return parser.parse_args()


def check_args(args: argparse.Namespace, logger: Logger):
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
        logger.info("[DRY_RUN] - output will display to screen only")

    assert (
        args.env_file
    ), "Missing --env-file; Please provide a file with environment variables for the current analysis"


@dataclass
class ClearTmp:
    """
    Define what data to store for the model_train
    and model_eval phases of the TrioTrain Pipeline.
    """

    args: argparse.Namespace
    logger: Logger
    _examples_files: List = field(default_factory=list, init=False, repr=False)
    _total_files: int = field(default=0, init=False, repr=False)
    _valid_dirs_and_files: Dict = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        # Confirm that the env file exists before setting variables
        self.dryrun_mode: bool = self.args.dry_run
        self.debug_mode: bool = self.args.debug
        self.env = Env(self.args.env_file, self.logger, dryrun_mode=self.args.dry_run)
        self.parents = ["Mother", "Father"]
        self.trio = self.parents + ["Child"]
        self._phase = "clean_tmp"
        self._baseline_mode = False

    def set_trio(self) -> None:
        """
        Determine trio number for logging.
        """
        iteration_name = compile(r"run\d+")
        digits_only = compile(r"\d+")

        if isinstance(self.env.env_file, str):
            result = iteration_name.search(self.env.env_file)
            if result:
                trio_name = result.group()
                second_result = digits_only.search(trio_name)
                if second_result:
                    self.trio_num = second_result.group()
                    if int(self.trio_num) == 0:
                        self.logger_msg = f"[Baseline] - [{self._phase}]"
                        self._baseline_mode = True
                    else:
                        self.logger_msg = f"[TRIO{self.trio_num}] - [{self._phase}]"
                else:
                    self.logger.error(
                        f"[set_trio]: missing a current trio number\nExiting..."
                    )
                    exit(2)
            else:
                self.logger.error(
                    f"[set_trio]: expected a 'run#' pattern, but none was found\nExiting..."
                )
                exit(2)
        else:
            self.logger.error(
                f"[set_trio]: please provide a str object to search\nExiting..."
            )
            exit(2)

    def set_genome(self, genome: str = "Mother") -> None:
        """
        Defines which genome in a trio to work with.
        """
        if self._baseline_mode:
            # Load in environment variables
            vars = ["BaselineModelResultsDir"]
            results = Env.load(self.env, *vars)
            self.results_dir = Path(str(results))
            self.genome = None
        else:
            self.genome = genome
            # Load in environment variables
            if "ExamplesDir" in self.env.contents:
                examples = self.env.contents["ExamplesDir"]
                self.examples_dir = Path(str(examples))
            else:
                self.logger.error(
                    f"{self.logger_msg}: missing the 'ExamplesDir' variable in {self.env.env_file}\nExiting..."
                )
                exit(1)

            if self.genome in self.parents:
                vars = [f"{self.genome}TestDir", f"{self.genome}CompareDir"]
                test, compare = Env.load(self.env, *vars)
                self.test_dir = Path(test)
                self.compare_dir = Path(compare)

    def keep_example_info(self) -> None:
        """
        Save one copy of example shape/channel info as a new file, rather than one per region.

        This file is required to use show_examples, which may need to be run after a training iteration.
        """
        files = []
        if self._baseline_mode:
            logging_msg = self.logger_msg
            for f in self.results_dir.iterdir():
                file_found = search(
                    r"make_examples\.tfrecord-00001-of-000\d+\.gz\.example_info\.json",
                    str(f),
                )
                if file_found is not None:
                    files.append(self.results_dir / file_found.group())

            new_file = "example_info.json"
            new = TestFile(file=self.results_dir / new_file, logger=self.logger)
        else:
            logging_msg = f"{self.logger_msg} - [{self.genome}]"
            for f in self.examples_dir.iterdir():
                file_found = search(
                    rf"{self.genome}\.region1\.labeled\.tfrecords-0000\d-of-000\d+\.gz\.example_info\.json",
                    str(f),
                )
                if file_found is not None:
                    files.append(self.examples_dir / file_found.group())

            new_file = f"{self.genome}.example_info.json"
            new = TestFile(file=self.examples_dir / new_file, logger=self.logger)

        new.check_missing(logger_msg=logging_msg, debug_mode=True)

        if new.file_exists:
            return

        files = natsorted(files, key=str)
        keep_file = files[0]

        keep = TestFile(file=keep_file, logger=self.logger)
        keep.check_existing(logger_msg=logging_msg, debug_mode=True)
        if not keep.file_exists:
            self.logger.error(
                f"{logging_msg} - [{self.genome}]: missing '{str(keep_file)}' to save example_info...\nExiting"
            )
            exit(1)

        if keep.file_exists and not new.file_exists:
            if self.dryrun_mode:
                self.logger.info(
                    f"[DRY_RUN] - {logging_msg}: pretending to copy '{keep_file.name}'..."
                )
            else:
                self.logger.info(
                    f"{logging_msg}  - [{self.genome}]: copying '{keep_file.name}' now..."
                )
                copy2(str(keep_file), new.file)

    def create_search_patterns(self) -> None:
        """
        Defines the fnmatch search pattern for temporary files in multiple directories.
        """
        # handle baseline temp files
        tmp_files = [
            [
                r"make_examples\.tfrecord-\d+-of-\d+\.gz",
                r"make_examples\.tfrecord-\d+-of-\d+\.gz\.example_info\.json",
                r"call_variants_output\.tfrecord\.gz",
            ],
            [
                r".*\.vcf\.gz",
                r".*\.vcf\.gz\.tbi",
                r".*\.bed",
            ],
        ]

        if self._baseline_mode:
            # Create file search pattern
            self._valid_dirs_and_files = {
                f"{self.results_dir}/tmp/": tmp_files[0],
                f"{self.results_dir}/scratch": tmp_files[1],
            }

        # handle new model temp files
        else:
            # Create file search pattern
            if r".*\.bed" not in self._examples_files:
                self._examples_files.append(r".*\.bed")
            self._examples_files.append(
                compile(
                    rf"{self.genome}.region\d+.labeled.tfrecords-\d+-of-\d+.gz.example_info.json(*SKIP)(*FAIL)|{self.genome}.region\d+.labeled.tfrecords-\d+-of-\d+.gz"
                )
            )
            self._examples_files.append(
                rf"{self.genome}\.region\d+\.labeled\.tfrecords-\d+-of-\d+\.gz\.example_info\.json",
            )
            self._examples_files.append(
                rf"{self.genome}\.region\d+\.labeled\.shuffled-\d+-of-\d+\.tfrecord\.gz",
            )
            self._examples_files.append(
                rf"{self.genome}\.region\d+\.labeled\.shuffled\.dataset_config\.pbtxt",
            )
            self._valid_dirs_and_files.update(
                {
                    str(self.examples_dir): self._examples_files,
                }
            )

            if self.genome in self.parents:
                self._valid_dirs_and_files.update(
                    {
                        f"{self.test_dir}/tmp/": tmp_files[0],
                        f"{self.compare_dir}/scratch": tmp_files[1],
                    }
                )

    def remove_file(self, file_path: Path, extensions_list: List) -> None:
        """
        Deletes file_path if it has an extension found extensions_list.
        """

        # iterate through file_extension_list
        for match_pattern in extensions_list:
            # if a file matches an extension,
            file = search(pattern=match_pattern, string=str(file_path.name))

            if file is not None:
                file_found = file.group()
                self.num_files += 1

                # if DRY RUN, nothing will be deleted
                # otherwise, EXISTING FILES WILL BE DELETED PERMANENTLY
                if not self.dryrun_mode:
                    if self.debug_mode:
                        self.logger.debug(
                            f"{self.logger_msg}: remove the following tmp file | '{file_found}'"
                        )
                    file_path.unlink(missing_ok=True)

                if self.num_files % 100 == 0:
                    if self.dryrun_mode:
                        self.logger.info(
                            f"[DRY_RUN] - {self.logger_msg}: running total of files for removal | {int(self.num_files):,}-of-{int(self._total_files):,}"
                        )
                        self.logger.info(
                            f"[DRY_RUN] - {self.logger_msg}: pretending to remove the following tmp file | '{file_found}'"
                        )

                    elif not self.dryrun_mode and self.debug_mode:
                        self.logger.debug(
                            f"{self.logger_msg}: running total of files for removal | {int(self.num_files):,}-of-{int(self._total_files):,}"
                        )
                        self.logger.debug(
                            f"{self.logger_msg}: removed the following tmp file | '{file_path.name}'"
                        )
                    else:
                        self.logger.info(
                            f"{self.logger_msg}: running total of files removed | {int(self.num_files):,}-of-{int(self._total_files):,}"
                        )

            else:
                continue

    def remove_dirs(self, dir_path: Path) -> None:
        """
        Handle any sub-files. Then, remove an empty dir.
        """
        remove_all = ["scratch", "tmp", "regions", ".dir"]
        if dir_path.name in remove_all:
            self.num_sub_dirs += 1
            if self.dryrun_mode:
                self.logger.info(
                    f"[DRY_RUN] - {self.logger_msg}: pretending to remove the following tmp directory + contents | '{str(dir_path)}'"
                )
            else:
                rmtree(dir_path)
                self.logger.info(
                    f"{self.logger_msg}: removed the following tmp directory + contents | '{str(dir_path)}'"
                )
        else:
            self.num_sub_dirs += 1
            if self.dryrun_mode:
                self.logger.info(
                    f"[DRY_RUN] - {self.logger_msg}: pretending to remove the following empty tmp directory | '{str(dir_path)}'"
                )
            else:
                dir_path.rmdir()
                self.logger.info(
                    f"{self.logger_msg}: removed the following empty tmp directory directory | '{str(dir_path)}'"
                )

    def run(self) -> None:
        """
        1) Deletes unshuffled example files located in examples/

        2) Deletes all vcf.gz, vcf.gz.tbi and .bed files located in compare_<Genome>/scratch/

        3) Deletes all directories + tmp files generated during calling variants when testing a model ckpt.
        """
        self.set_trio()

        for g in self.trio:
            self.set_genome(genome=g)
            self.keep_example_info()
            self.create_search_patterns()

        self.num_files = 0
        self.num_sub_dirs = 0

        # iterate through {valid dir: file_extension_list} pairs
        for dir, file_patterns in self._valid_dirs_and_files.items():
            if Path(dir).exists():
                if Path(dir).is_dir():
                    file_list = natsorted(Path(dir).iterdir(), key=str)
                    short_path = "/".join(Path(dir).parts[-2:])
                    current_total = len(file_list)
                    self._total_files += current_total
                    self.logger.info(
                        f"{self.logger_msg}: '{short_path}' currently contains {current_total:,} items"
                    )

                    if "tmp" in Path(dir).name or "scratch" in Path(dir).name:
                        self.remove_dirs(Path(dir))
                        self.num_files += current_total
                        continue

                    # iterate through all items in a dir
                    for item in natsorted(file_list, key=str):
                        # handle files first
                        if item.exists() and item.is_file():
                            self.remove_file(item, extensions_list=file_patterns)

                        # handle directories second
                        elif item.exists() and item.is_dir():
                            if "regions" in item.name:
                                short_path = "/".join(item.parts[-2:])
                                file_list = natsorted(item.iterdir(), key=str)
                                current_total = len(file_list)
                                self._total_files += current_total
                                self.logger.info(
                                    f"{self.logger_msg}: '{short_path}' currently contains {current_total:,} items"
                                )
                                # handle directories second
                                self.remove_dirs(item)
                                self.num_files += current_total
            else:
                self.logger.info(
                    f"{self.logger_msg}: TMP directory [{str(dir)}] removed previously... SKIPPING AHEAD"
                )
                continue

        percent_removed = (
            round(int(self.num_files) / int(self._total_files), ndigits=4) * 100
        )
        self.logger.info(
            f"{self.logger_msg}: removed {int(self.num_files):,}-of-{int(self._total_files):,} ({percent_removed}%) of total files"
        )


def __init__():
    """
    Loads in command line arguments and cleans up temporary files accordingly.
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

    wipe_files = ClearTmp(args, logger)

    wipe_files.run()
    Wrapper(__file__, "end").wrap_script(timestamp())


# Execute all functions
if __name__ == "__main__":
    __init__()
