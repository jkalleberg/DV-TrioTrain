#!/usr/bin/python3
"""
description: collects all the data used for an Iteration.

usage:
    from iteration import Iteration
"""
import sys
from argparse import Namespace
from dataclasses import dataclass, field
from logging import Logger
from os import environ, getcwd
from pathlib import Path
from typing import Union

from helpers.environment import Env
from helpers.outputs import check_expected_outputs, check_if_output_exists
from helpers.utils import create_deps


@dataclass
class Iteration:
    """
    Defines what data to store for an Iteration.
    """

    # required values
    args: Namespace
    logger: Logger

    # optional values
    current_genome_dependencies: list = field(default_factory=create_deps)
    current_genome_num: Union[int, None] = None
    current_trio_num: Union[int, str, None] = None

    default_region_file: Union[Path, None] = None
    env: Union[Env, None] = None
    eval_genome: Union[str, None] = None
    eval_num_regions: Union[int, None] = None

    next_genome: Union[str, None] = None
    next_genome_dependencies: list = field(default_factory=create_deps)
    next_trio_num: Union[int, str, None] = None

    prior_genome: Union[str, None] = None

    train_genome: Union[str, None] = None
    train_num_regions: Union[int, None] = None

    total_num_iterations: Union[int, None] = None
    total_num_tests: int = 1

    # internal, imutable values
    _mode_string: str = field(init=False, repr=False)
    _version: Union[str, None] = field(
        default=environ.get("BIN_VERSION_DV"), init=False, repr=False
    )

    def __post_init__(self) -> None:
        if "demo_mode" in self.args:
            self.demo_mode: bool = self.args.demo_mode
            self.demo_chromosome: Union[str, int, None] = self.args.demo_chr
        else:
            self.demo_mode = False
            self.demo_chromosome = None

        self.debug_mode: bool = self.args.debug
        self.dryrun_mode: bool = self.args.dry_run

        if self.demo_mode or self.total_num_tests is None:
            self.total_num_tests = 1

        if self._version is None:
            raise ValueError(
                f"Unable to proceed, setup() function failed to determine which version of DeepVariant is being used.\nDid you forget to run: 'source scripts/setup/modules.sh'?"
            )

        if self.demo_mode and self.current_trio_num is not None:
            if "chr" in self.demo_chromosome.lower():
                _mode = f"DEMO] - [TRIO{self.current_trio_num}] - [{self.demo_chromosome.upper()}"
            else:
                _mode = f"DEMO] - [TRIO{self.current_trio_num}] - [CHR{self.demo_chromosome}"
        elif self.current_genome_num == 0 and self.train_genome is None:
            _mode = f"Baseline-v{self._version}"
        elif (
            self.current_genome_num != 0
            and self.current_trio_num is not None
            and self.train_genome is not None
        ):
            _mode = f"TRIO{self.current_trio_num}"
        elif self.current_trio_num is None and self.train_genome is None:
            _mode = f"Benchmark"
        else:
            _mode = f"TRIO{self.current_trio_num}"

        if self.dryrun_mode:
            self._mode_string = f"[DRY_RUN] - [{_mode}]"
        else:
            self._mode_string = f"[{_mode}]"

        # Do not load any variables from a file
        if self.env is None:
            if "outpath" in self.args and self.args.outpath is not None:
                self.job_dir = Path(self.args.outpath)
                self.log_dir = Path(self.args.outpath)
                self.test_dir = Path(self.args.outpath)
                self.compare_dir = Path(self.args.outpath)
                self.results_dir = Path(self.args.outpath)
            return

        if "ConditionsUsed" in self.env.contents:
            self._conditions = self.env.contents["ConditionsUsed"]
        else:
            self._conditions = "withIS"

        if self.train_genome == "None":
            self.train_genome = None

        # THIS IS THE REGION FILE THAT WILL BE USED FOR CALLING VARIANTS
        # either provided as part of the metadata.csv,
        # or create species-specific defaults
        if self.train_genome is None:
            logging_msg = f"{self._mode_string} - [setup]"
        else:
            logging_msg = f"{self._mode_string} - [setup] - [{self.train_genome}]"

        if all(
            key in self.env.contents for key in ("RegionsFile_Path", "RegionsFile_File")
        ):
            self.default_region_file = Path(
                str(self.env.contents["RegionsFile_Path"])
            ) / str(self.env.contents["RegionsFile_File"])
        elif self.default_region_file is None:
            reference_dir = Path(self.env.contents["RefFASTA_Path"])
            self._reference_genome = reference_dir / self.env.contents["RefFASTA_File"]
            _regex = r".*_autosomes_withX.bed"

            (
                default_exists,
                outputs_found,
                files,
            ) = check_if_output_exists(
                match_pattern=_regex,
                file_type="default BED file",
                search_path=reference_dir,
                msg=logging_msg,
                logger=self.logger,
                debug_mode=self.debug_mode,
                dryrun_mode=self.dryrun_mode,
            )

            if default_exists:
                missing_default_file = check_expected_outputs(
                    outputs_found=outputs_found,
                    outputs_expected=1,
                    msg=logging_msg,
                    file_type="default BED file",
                    logger=self.logger,
                )
                if not missing_default_file:
                    self.default_region_file = reference_dir / files[0]

        if self.demo_mode and self.current_trio_num is not None:
            self.train_num_regions = 1
            self.eval_num_regions = 1
            self.run_name = self.env.contents["RunName"]
            self.code_path = self.env.contents["CodePath"]
            self.examples_dir = Path(str(self.env.contents["ExamplesDir"]))
            self.job_dir = Path(str(self.env.contents["JobDir"]))
            self.log_dir = Path(str(self.env.contents["LogDir"]))
            self.model_label = f"{self.run_name}"
            self.results_dir = Path(str(self.env.contents["ResultsDir"]))

        elif self.current_genome_num == 0 and self.train_genome is None:
            self.run_name = "baseline-DV"
            self.code_path = self.env.contents["CodePath"]
            self.examples_dir = Path(str(self.env.contents["BaselineModelResultsDir"]))
            self.job_dir = Path(str(self.env.contents["BaselineModelResultsDir"]))
            self.log_dir = Path(str(self.env.contents["BaselineModelResultsDir"]))
            self.test_dir = Path(str(self.env.contents["BaselineModelResultsDir"]))
            self.compare_dir = Path(str(self.env.contents["BaselineModelResultsDir"]))
            self.results_dir = Path(str(self.env.contents["BaselineModelResultsDir"]))
            self.model_label = f"{self.run_name}-{self._version}"

        elif self.current_genome_num != 0 and self.current_trio_num is not None:
            self.run_name = self.env.contents["RunName"]
            self.code_path = self.env.contents["CodePath"]
            self.examples_dir = Path(str(self.env.contents["ExamplesDir"]))
            self.job_dir = Path(str(self.env.contents["JobDir"]))
            self.log_dir = Path(str(self.env.contents["LogDir"]))
            self.results_dir = Path(str(self.env.contents["ResultsDir"]))
            if self.train_genome is not None:
                self.train_dir = Path(
                    str(self.env.contents[f"{self.train_genome}TrainDir"])
                )
                self.test_dir = Path(
                    str(self.env.contents[f"{self.train_genome}TestDir"])
                )
                self.compare_dir = Path(
                    str(self.env.contents[f"{self.train_genome}CompareDir"])
                )
            self.model_label = f"{self.run_name}-{self.train_genome}"
        else:
            self.run_name = self.env.contents["RunName"]
            self.code_path = self.env.contents["CodePath"]
            self.job_dir = Path(str(self.env.contents["JobDir"]))
            self.log_dir = Path(str(self.env.contents["LogDir"]))
            self.model_label = self.run_name

    def check_working_dir(self) -> None:
        """
        Require that all code is executed from
        within the expected working directory.
        """
        if self.env is None:
            return

        if self.dryrun_mode:
            result = self.env.contents["CodePath"]
            working_dir = str(result)
        else:
            working_dir = self.code_path

        try:
            assert (
                getcwd() == working_dir
            ), f"run the workflow in the {working_dir} directory only"
        except AssertionError as error_msg:
            self.logger.error(f"{error_msg}.\nExiting... ")
            sys.exit(1)
