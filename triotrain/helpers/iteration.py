#!/usr/bin/python3
"""
description: collects all the data used for an Iteration of the TrioTrain pipeline.

usage:
    from iteration import Iteration
"""
from argparse import Namespace
import sys
from dataclasses import dataclass, field
from logging import Logger
from os import environ, getcwd
from pathlib import Path
from typing import Union
import helpers.helper_func as h

@dataclass
class Iteration:
    """
    Define what data to store for an Iteration of the TrioTrain Pipeline.
    """

    # required values
    current_trio_num: Union[int, str, None]
    next_trio_num: Union[int, str, None]
    current_genome_num: Union[int, None]
    total_num_genomes: Union[int, None]
    train_genome: Union[str, None]
    eval_genome: Union[str, None]
    env: Union[h.Env,None]
    logger: Logger
    args: Namespace

    # optional values
    prior_genome: Union[str, None] = None
    current_genome_dependencies: list = field(default_factory=h.create_deps)
    next_genome: Union[str, None] = None
    next_genome_dependencies: list = field(default_factory=h.create_deps)
    total_num_tests: int = 1
    train_num_regions: Union[int, None] = None
    eval_num_regions: Union[int, None] = None
    default_region_file: Union[Path, None] = None
    # cow: bool = True

    # internal, imutable values
    _mode_string: str = field(init=False, repr=False)
    _version: Union[str, None] = field(
        default=environ.get("BIN_VERSION_DV"), init=False, repr=False
    )

    def __post_init__(self) -> None:
            
        if self.env is not None and self.train_genome is not None:
            self.demo_mode: bool = self.args.demo_mode
            self.demo_chromosome: Union[str, int, None] = self.args.demo_chr
        else:
            self.demo_mode = False
            self.demo_chromosome = None
        self.debug_mode: bool = self.args.debug
        self.dryrun_mode: bool =self.args.dry_run
        
        if self.demo_mode or self.debug_mode or self.total_num_tests is None:
            self.total_num_tests = 1            
        
        if self._version is None:
            raise ValueError(
                "Unable to proceed, setup() function failed to determine which version of DeepVariant is being used"
            )

        if self.demo_mode and self.current_trio_num is not None:
            self._mode_string = f"Demo-{self.train_genome}{self.current_trio_num}"
        elif self.current_genome_num == 0 and self.train_genome is None:
            self._mode_string = f"Baseline-DV] - [v{self._version}"
        elif (
            self.current_genome_num != 0
            and self.current_trio_num is not None
            and self.train_genome is not None
        ):
            self._mode_string = f"Trio-{self.train_genome}{self.current_trio_num}"
        elif self.train_genome is None:
            self._mode_string = f"Benchmark"
        else:
            self._mode_string = f"Trio{self.current_trio_num}"

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
        if all(
            key in self.env.contents for key in ("RegionsFile_Path", "RegionsFile_File")
        ):
            self.default_region_file = Path(
                str(self.env.contents["RegionsFile_Path"])
            ) / str(self.env.contents["RegionsFile_File"])
        elif self.args.species.lower() == "cow":
            CHR = list(map(str, range(1, 30))) + ["X"]
            self.CHR_Order = {k: v for v, k in enumerate(CHR)}
            self.default_region_file = (
                Path(getcwd()) / "region_files" / "cow_autosomes_withX.bed"
            )
        elif self.args.species.lower() == "human":
            CHR_num = list(map(str, range(1, 22))) + ["X"]
            # human genome adds the "chr" prefix to chromosomes...
            CHR = list()
            for c in CHR_num:
                CHR.append(f"chr{c}")
            self.CHR_Order = {k: v for v, k in enumerate(CHR)}
            self.default_region_file = (
                Path(getcwd()) / "region_files" / "human_autosomes_withX.bed"
            )
        else:
            self.logger.error("ADD LOGIC FOR ANY SPECIES BESIDES COW AND HUMANS!")
            sys.exit(1)

        if self.dryrun_mode:
            if not self.env.env_path.exists():
                self.logger.info(
                    f"[DRY RUN] - [{self._mode_string}] - [setup]: env file [{self.env.env_file}] does not exist"
                )

        if self.demo_mode and self.current_trio_num is not None:
            self.train_num_regions = 1
            self.eval_num_regions = 1
            self.run_name = self.env.contents["RunName"]
            self.code_path = self.env.contents["CodePath"]
            self.examples_dir = Path(str(self.env.contents["ExamplesDir"]))
            self.job_dir = Path(str(self.env.contents["JobDir"]))
            self.log_dir = Path(str(self.env.contents["LogDir"]))
            self.model_label = f"{self.run_name}"

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

        elif self.train_genome is not None and self.current_genome_num != 0 and self.current_trio_num is not None:
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
            ), "Run the workflow in the deep-variant/ directory only"
        except AssertionError as error_msg:
            self.logger.error(f"{error_msg}.\nExiting... ")
            sys.exit(1)

