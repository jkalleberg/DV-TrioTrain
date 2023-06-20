#!/bin/python3
"""
description: contains Iteration-specific helper functions

usage:
    from pipeline_helpers import Setup
"""
import sys
import argparse
import json
from dataclasses import dataclass, field
from logging import Logger
from pathlib import Path
from typing import List, Union
from regex import compile

# get the relative path to the triotrain/ dir
h_path = str(Path(__file__).parent.parent.parent)
sys.path.append(h_path)
import helpers
from model_training.prep.create_environment import Environment

@dataclass
class Setup:
    """
    Collect and check command line arguments, and load in metadata file to create Python variables.
    """
    logger: Logger
    args: argparse.Namespace
    eval_genome: str = "Child"
    demo_mode: bool = False
    demo_chr: str = "29"
    current_genome_deps: List[Union[str, None]] = field(default_factory=helpers.h.create_deps)
    next_genome_deps: List[Union[str, None]] = field(default_factory=helpers.h.create_deps)
    _checkpoint_used: Union[str, None] = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.sum_pattern = compile(r"\d+")
        self.metadata_path = Path(self.args.metadata)
        self.num_show_regions_jobs: int = 0
        self.prior_trio_num: Union[int, None] = None
        self.prior_genome: Union[str, None] = None
        self.current_trio_num: int = 0
        self.current_genome: Union[str, None] = None
        self.next_trio_num: Union[int, None] = None
        self.next_genome: Union[str, None] = None

    def load_resource_file(self) -> dict:
        """
        load in SLURM cluster resources from a JSON file
        """
        with open(self.args.resource_config, mode="r") as file:
            resource_dict = json.load(file)
        return resource_dict

    def process_env(self, itr_num: int = 0) -> helpers.h.Env:
        """
        use the metadata csv file to build analysis structure.
        """
        file_path = Path(self.args.metadata)
        self.meta = Environment(
            input_csv=file_path,
            logger=self.logger,
            itr_num=itr_num,
            first_genome=self.args.first_genome,
            expected_num_tests=self.args.num_tests,
            dryrun_mode=self.args.dry_run, 
            debug_mode=self.args.debug,
            demo_mode=self.args.demo_mode,
            checkpoint_name=self.args.custom_ckpt,
            channel_info=self.args.channel_info,
            update=self.args.update,
        )

        self.meta.run(
            self.args.name,
            self.args.num_epochs,
            self.args.learning_rate,
            self.args.batch_size,
        )
        return self.meta.env

    def find_show_regions_file(self):
        """
        Confirm that the show_regions file input exists first, and throw and error if missing.
        """
        regions = helpers.h.TestFile(self.args.show_regions_file, self.logger)
        regions.check_existing()
        if regions.file_exists:
            self._regions_path = regions.path
            if self.args.debug:
                self.logger.debug(
                    f"[{self.meta.mode}] - [show_examples]: region file location | {self._regions_path}"
                )
            else:

                if "bed" in self._regions_path.suffix:
                    self.logger.info(
                        f"[{self.meta.mode}] - [show_examples]: a BED file was provided as input"
                    )
                    self.num_show_regions_jobs += 1
                else:
                    self.logger.info(
                        f"[{self.meta.mode}] - [show_examples]: provided a non-BED file input"
                    )
                    open_file = open(str(self._regions_path), "r")

                    while True:
                        self.num_show_regions_jobs += 1
                        line = open_file.readline()
                        if not line:
                            break
        else:
            raise FileNotFoundError(
                f"[{self.meta.mode}] - [show_examples]: unable to find the region file input"
            )

    def start_iteration(
        self,
        current_deps=[None, None, None, None],
        next_deps=[None, None, None, None],
    ) -> None:
        """
        Create lists to keep track of entire analysis pipeline.

        Pretty-print a header for each analysis run.
        """
        no_current_deps = helpers.h.check_if_all_same(self.current_genome_deps, None)
        no_updated_deps = helpers.h.check_if_all_same(current_deps, None)
        no_next_deps = helpers.h.check_if_all_same(self.next_genome_deps, None)
        no_new_next_deps = helpers.h.check_if_all_same(next_deps, None)

        if no_current_deps and no_updated_deps is False:
            self.current_genome_deps = current_deps
        if no_next_deps and no_new_next_deps is False:
            self.next_genome_deps = next_deps

        if self.meta.itr_num is None:
            raise ValueError(
                f"process_iteration() has invalid iteration number {self.meta.itr_num}"
            )
        
        if self.meta.first_genome is None:
            self.prior_trio_num = None
            self.current_trio_num = self.meta.itr_num
            self.next_trio_num = None

            self.prior_genome = None
            self.current_genome = None
            self.next_genome = None
        else:
            if self.meta.itr_num == 0:
                self.prior_trio_num = None
                self.current_trio_num = self.meta._trio_nums_list[self.meta.itr_num]
                self.next_trio_num = self.meta.itr_num + 1

                self.prior_genome = None
                self.current_genome = None
                self.next_genome = self.meta._genome_list[self.meta.itr_num]
            
            elif self.meta.itr_num == 1:
                self.prior_trio_num = self.meta.itr_num - 1
                self.current_trio_num = self.meta._trio_nums_list[self.meta.itr_num - 1]
                self.next_trio_num = self.meta._trio_nums_list[self.meta.itr_num]

                self.prior_genome = None
                self.current_genome = self.meta._genome_list[self.meta.itr_num - 1]
                self.next_genome = self.meta._genome_list[self.meta.itr_num]

            elif self.meta.num_of_parents is not None and 1 < self.meta.itr_num < self.meta.num_of_parents:
                self.prior_trio_num = self.meta._trio_nums_list[self.meta.itr_num - 2]
                self.current_trio_num = self.meta._trio_nums_list[self.meta.itr_num - 1]
                self.next_trio_num = self.meta._trio_nums_list[self.meta.itr_num]

                self.prior_genome = self.meta._genome_list[self.meta.itr_num - 2]
                self.current_genome = self.meta._genome_list[self.meta.itr_num - 1]
                self.next_genome = self.meta._genome_list[self.meta.itr_num]
            else:
                self.prior_trio_num = self.meta._trio_nums_list[self.meta.itr_num - 2]
                self.current_trio_num = self.meta._trio_nums_list[self.meta.itr_num - 1]
                self.next_trio_num = None

                self.prior_genome = self.meta._genome_list[self.meta.itr_num - 2]
                self.current_genome = self.meta._genome_list[self.meta.itr_num - 1]
                self.next_genome = None

        if self.args.debug is False:
            if self.meta.first_genome is None:
                print(
                    f"============================================================\nStarting GIAB Benchmarking Iteration {self.meta.itr_num}-of-{self.meta.num_of_iterations} @ {helpers.h.timestamp()}\n============================================================"
                ) 
            elif self.demo_mode:
                print(
                    f"============================================================\nStarting Demo CHR{self.demo_chr} Iteration {self.meta.itr_num}-of-{self.meta.num_of_iterations} @ {helpers.h.timestamp()}\nINFO: Current [Genome={self.current_genome}; Trio={self.current_trio_num}]\nINFO: Next [Genome={self.next_genome}; Trio={self.next_trio_num}]\n============================================================"
                )
            elif self.demo_mode is False:
                if self.meta.itr_num == 0:
                    print(
                        f"============================================================\nStarting Baseline-DV Iteration {self.meta.itr_num}-of-{self.meta.num_of_iterations} @ {helpers.h.timestamp()}\n============================================================"
                    )
                elif 1 <= self.meta.itr_num < self.meta.num_of_iterations:
                    print(
                        f"============================================================\nStarting Iteration {self.meta.itr_num}-of-{self.meta.num_of_iterations} @ {helpers.h.timestamp()}\nINFO: Prior [Genome={self.prior_genome}; Trio={self.prior_trio_num}]\nINFO: Current [Genome={self.current_genome}; Trio={self.current_trio_num}]\nINFO: Next [Genome={self.next_genome}; Trio={self.next_trio_num}]\nINFO: Current Genome Job Dependencies: {self.current_genome_deps}\nINFO: Next Genome Job Dependencies: {self.next_genome_deps}\n============================================================"
                    )
                elif self.meta.itr_num == self.meta.num_of_iterations:
                    print(
                        f"============================================================\nStarting Final Iteration {self.meta.itr_num}-of-{self.meta.num_of_iterations}\nINFO: Prior: [Genome={self.prior_genome}]; Trio={self.prior_trio_num}]\nINFO: Current: [Genome={self.current_genome}; Trio={self.current_trio_num}\nINFO: Current Genome Job Dependencies: {self.current_genome_deps}\nINFO: Next Genome Job Dependencies: {self.next_genome_deps}\n============================================================"
                    )

    def end_iteration(self) -> None:
        """
        Pretty-print a terminal wrapper for each analysis run
        """
        print(
            f"============================================================\nEnd of Iteration {self.meta.itr_num}-of-{self.meta.num_of_iterations} @ {helpers.h.timestamp()}\nCURRENT DEPS: {self.current_genome_deps}\nNEXT DEPS: {self.next_genome_deps}\n============================================================"
        )
