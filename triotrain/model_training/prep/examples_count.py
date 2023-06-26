#!/usr/bin/python3
"""
description: contains all of the functions specific to the count_examples phase of TrioTrain.

usage:
    from examples_count import CountExamples
"""
from dataclasses import dataclass, field
from subprocess import getstatusoutput
from typing import Union

from helpers.iteration import Iteration


@dataclass
class CountExamples:
    """
    Define what data to store for the count_examples phase of the TrioTrain Pipeline
    """

    # required values
    itr: Iteration

    # optional values
    train_mode: bool = True

    # internal, imutable values
    _existing_merged_config: bool = field(default=False, init=False, repr=False)
    _n_examples: int = field(default=0, init=False, repr=False)
    _phase: str = field(default="count_examples", init=False, repr=False)

    def set_genome(self) -> None:
        """
        Assign genome and total number of regions used
        """
        if self.train_mode:
            self.genome = self.itr.train_genome
            self._total_regions = self.itr.train_num_regions
        else:
            self.genome = self.itr.eval_genome
            self._total_regions = self.itr.eval_num_regions

        self.variable_name = f"{self.genome}_Examples"

    def set_search_pattern(self, region: Union[int, None] = None) -> None:
        """
        Define the file labeling pattern for sharded examples log files
        """
        if self.itr.demo_mode:
            self.current_region = self.itr.demo_chromosome
            
            if "chr" in self.itr.demo_chromosome.lower():
                self.region_string = self.itr.demo_chromosome
                self.logger_msg = self.genome
            else:
                self.region_string = f"chr{self.itr.demo_chromosome}"
                self.logger_msg = self.genome

        elif region is not None:
            self.current_region = region
            self.region_string = f"region{self.current_region}"
            self.logger_msg = (
                f"{self.genome}] - [region{region}-of-{self._total_regions}"
            )
            
        self.prefix = f"{self.genome}-{self.region_string}"
        self.itr.logger.info(
            f"[{self.itr._mode_string}] - [{self._phase}] - [{self.logger_msg}]: counting examples made now... "
        )

    def search_log_files(self) -> None:
        """
        If all the log files exist,
        find the line in every sharded log file
        created during 'make_examples'
        which contains the total number of examples made
        per shard.

        Then, sum the total number of examples made
        per genome across all regions and shards.

        Finally, create a new env_file variable
        with the individual's number of examples
        """
        if self.itr.env is not None and self.variable_name not in self.itr.env.contents:
            # Count the number of examples made
            # For individual from log files
            cmd = f"find {self.itr.log_dir} -type f -iname \"examples.{self.prefix}-part*-of-*.log\" -exec grep 'Create' {'{}'} \+ | cut -d ' ' -f 8 | awk '{'{s+=$1}'} END {'{print s}'}'"

            ##--- THE CMD ABOVE STATES: ----##
            # Grab lines from the Individual's
            # Examples .log files that match "Created"
            # Use cut to select only the number
            # of  examples created
            # for each of the N_PARTS made
            # sum these numbers together to
            # get a total number of examples made
            ##--------------------------------##
            status, examples_found = getstatusoutput(cmd)
            if status == 0:
                if examples_found == "":
                    examples_found = None
                    self._n_examples += 0
                    self.itr.logger.error(
                        f"[{self.itr._mode_string}] - [{self._phase}] - [{self.logger_msg}]: no examples were found"
                    )
                else:
                    self._n_examples += int(examples_found)
                    self.itr.logger.info(
                        f"[{self.itr._mode_string}] - [{self._phase}] - [{self.logger_msg}]: running total number of examples | '{int(self._n_examples):,}'"
                    )
            else:
                if examples_found == "":
                    examples_found = None
                    self._n_examples += 0
                    self.itr.logger.error(
                        f"[{self.itr._mode_string}] - [{self._phase}] - [{self.logger_msg}]: no examples were found"
                    )

        else:
            if self.itr.env is not None and self.variable_name in self.itr.env.contents:
                variable_value = str(self.itr.env.contents[self.variable_name])
                self._n_examples = int(variable_value)

    def run(self) -> Union[int, None]:
        """
        Combine all the steps required to count examples made into one step.

        Then, add the sum total of examples made per region as a variable in the ENV file.
        """
        if self.itr.env is None:
            return

        self.set_genome()

        if self._total_regions is not None:
            if self._total_regions > 1:
                for r in range(0, self._total_regions):
                    region_num = r + 1
                    self.set_search_pattern(region=region_num)
                    self.search_log_files()
            else:
                self.set_search_pattern()
                self.search_log_files()

            self.itr.env.add_to(
                self.variable_name,
                str(self._n_examples),
                dryrun_mode=self.itr.dryrun_mode,
            )

        if self._n_examples is not None:
            if self.itr.demo_mode:
                self.itr.logger.info(
                    f"[{self.itr._mode_string}] - [{self._phase}] - [{self.logger_msg}]: found {int(self._n_examples):,} examples"
                )
            else:
                self.itr.logger.info(
                    f"[{self.itr._mode_string}] - [{self._phase}] - [{self.genome}]: found {int(self._n_examples):,} examples"
                )
        return self._n_examples
