#!/usr/bin/python3
"""
description: load in the metadata input file and create environment variable file(s) for each row.

example:
    from model_training.prep.create_environment import Environment
"""
import json
import sys
from dataclasses import dataclass, field
from logging import Logger
from math import ceil, isnan
from os import environ, getcwd, path
from pathlib import Path
from typing import List, Union

import numpy as np
import regex
from helpers.environment import Env
from helpers.files import TestFile
from helpers.wrapper import timestamp
from pandas import DataFrame, read_csv


@dataclass
class Environment:
    """
    Define what data data to store for a when processing the Metadata csv input for the TrioTrain Pipeline.
    """

    # required values
    input_csv: Path
    logger: Logger
    itr_num: int

    # optional values
    additional_channels: dict = field(default_factory=dict)
    expected_num_tests: int = 13
    first_genome: Union[str, None] = None
    channel_info: Union[str, None, Path] = None
    checkpoint_name: Union[str, None] = None
    conditions_used: Union[str, None] = None
    debug_mode: bool = False
    demo_mode: bool = False
    demo_chr: str = "29"
    dryrun_mode: bool = False
    output_dir: Union[str, Path] = "../TRIO_TRAINING_OUTPUTS"
    working_dir: Path = Path(getcwd())
    update: bool = False

    # internal, imutable values
    _checkpoint_path: Union[Path, None] = field(default=None, init=False, repr=False)
    _genome_list: list = field(default_factory=list, init=False, repr=False)
    _output_dict: dict = field(default_factory=dict, init=False, repr=False)
    _stable_vars: dict = field(default_factory=dict, init=False, repr=False)
    _trio_nums_list: list = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        self.data: DataFrame
        self.column_names: List
        self.num_envs: int
        if self.itr_num != 0:
            self.trio_num = int(ceil(self.itr_num / 2))
        elif self.itr_num == 0:
            self.trio_num = 0
        else:
            self.trio_num = None

        self._version = environ.get("BIN_VERSION_DV")
        self._phase: str = "create_environment"

        if self.first_genome is None:
            self.train_order = [None]
            self.output_dir_name = "VARIANT_CALLING_OUTPUTS"
            self.trio_num = self.itr_num
        elif self.first_genome.lower() == "father":
            self.output_dir_name: str = "TRIO_TRAINING_OUTPUTS"
            self.train_order = ["Father", "Mother"]
        else:
            self.output_dir_name: str = "TRIO_TRAINING_OUTPUTS"
            self.train_order = ["Mother", "Father"]

        output_path_entered = Path(self.output_dir).resolve()
        output_path_default = (
            Path(path.dirname(self.working_dir)) / self.output_dir_name
        )

        if output_path_entered == output_path_default:
            self.output_dir = output_path_default
        else:
            self.output_dir = output_path_entered

        # Define the regrex pattern of expected output
        if self.demo_mode:
            if "chr" in self.demo_chr.lower():
                self.mode = f"DEMO] - [TRIO{self.trio_num}] - [{self.demo_chr.upper()}"
            else:
                self.mode = f"DEMO] - [TRIO{self.trio_num}] - [CHR{self.demo_chr}"
        elif self.trio_num is None:
            self.mode = "Pipeline Setup"
        elif self.trio_num == 0:
            self.mode = f"Baseline-v{self._version}"
        elif None in self.train_order:
            self.mode = "Benchmark"
        else:
            self.mode = f"TRIO{self.trio_num}"

        if self.dryrun_mode:
            self.logging_msg = f"[DRY_RUN] - [{self.mode}] - [{self._phase}]"
        else:
            self.logging_msg = f"[{self.mode}] - [{self._phase}]"

        # set defaults for channels...
        self.use_insert_size = True
        self.use_allele_freq = False
        self.set_conditions()

    def load_metadata(self) -> None:
        """
        confirm that metadata file exists.

        Returns:
            1) a pandas dataframe of contents
            2) the columns to add to environment variables file.
            3) the number of test columns in input file
            4) how many env files will need to be created

        """
        # Confirm data input is an existing file
        metadata = TestFile(self.input_csv, self.logger)
        metadata.check_existing()
        if metadata.file_exists:
            # Read in file
            self.data = read_csv(metadata.file)
            self.column_names = list(self.data)
            self.num_rows = len(self.data)
            if self.demo_mode:
                self.num_envs = self.num_rows
            else:
                self.num_envs = self.num_rows + 1
            if None in self.train_order:
                self.num_of_parents = None
                self.num_of_iterations = self.num_envs
            else:
                self.num_of_parents = self.num_rows * 2
                self.num_of_iterations = self.num_of_parents + 1
        else:
            self.logger.error(
                f"{self.logging_msg}: unable to load metadata file [{self.input_csv}]"
            )
            raise ValueError("Invalid Input File")

    def check_input(self) -> None:
        """
        confirm working with a pair and create additional attributes, which are then used to confirm valid inputs were provided
        """
        # Confirm only processing a train-eval pair
        if None not in self.train_order:
            assert (
                len(self.train_order) == 2
            ), f"Invalid train pair provided | {self.train_order} does not have 2 genomes"

        # Load in the metadata file
        self.load_metadata()

        # Confirm that the itr_num is valid
        if self.itr_num <= self.num_of_iterations:
            if self.debug_mode:
                self.logger.debug(
                    f"{self.logging_msg}: valid iteration number provided"
                )
        else:
            self.logger.error(
                f"{self.logging_msg}: an invalid iteration number '{self.itr_num}' was provided"
            )
            self.logger.error(
                f"{self.logging_msg}: maximum iteration number is '{self.num_of_iterations}'"
            )
            raise ValueError("Invalid Iteration Number")

        # Identify test columns
        num_test_columns = sum((itm.count("Test") for itm in self.column_names))

        # Given the requirements outlined in metadata spec sheet:
        if len(self.column_names) > 24:
            # There are 3 input file columns per test in metadata
            # So the number of tests == testing columns divided by 3
            self.num_tests = int(num_test_columns / 3)
        elif len(self.column_names) == 24:
            # Performing trio-training with only 1 test genome would result in 24 columns
            self.num_tests = 1
        else:
            # If there aren't 24 columns, then metadata file is made incorrectly
            self.num_tests = 0
            assert len(self.column_names) >= 24, "No test genomes files provided"

        assert (
            self.num_tests == self.expected_num_tests
        ), f"Check your metadata file structure; found {self.num_tests}, but expected {self.expected_num_tests}"

        if self.debug_mode:
            self.logger.debug(
                f"{self.logging_msg}: number of runs | {self.num_rows}",
            )
            self.logger.debug(
                f"{self.logging_msg}: number of environment files, including one for Baseline-v{self._version} | {self.num_envs}"
            )
            self.logger.debug(
                f"{self.logging_msg}: number of tests to perform | {self.num_tests}"
            )

    def create_lists(self) -> None:
        """
        create lists to iterate through for pipeline
        """
        for r in range(self.num_rows):
            self._trio_nums_list.append(r + 1)
            self._trio_nums_list.append(r + 1)
            self._genome_list.append(self.train_order[0])
            self._genome_list.append(self.train_order[1])

        if self.debug_mode:
            self.logger.debug(f"{self.logging_msg}: run list | {self._trio_nums_list}")
            self.logger.debug(f"{self.logging_msg}: genome order | {self._genome_list}")
            self.logger.debug(
                f"{self.logging_msg}: number of parents | {self.num_of_parents}",
            )
            self.logger.debug(
                f"{self.logging_msg}: number of iterations | {self.num_of_iterations}"
            )

        # Require that everything matches metadata expectations
        assert (
            len(self._trio_nums_list) == len(self._genome_list) == self.num_of_parents
        ), "Metadata file does not match expectations"

        if len(self._trio_nums_list) != 0 and len(self._genome_list) == 0:
            raise ValueError(
                "create_iteration_lists() from Metadata failed to create _trio_nums_list and _genome_list items"
            )

    def create_env(self) -> None:
        """
        initialize an empty h.Env object which variables
        can be added.
        """
        if self.trio_num is None:
            raise ValueError(
                f"create_env() has invalid iteration number {self.trio_num}"
            )

        # Set the naming convention
        env_dir = self.output_dir / self.analysis_name / "envs"
        if not env_dir.exists():
            if self.dryrun_mode:
                self.logger.info(
                    f"{self.logging_msg}: env directory would be created | '{env_dir}'"
                )
            else:
                self.logger.info(
                    f"{self.logging_msg}: creating env directory | '{env_dir}'"
                )
                env_dir.mkdir(parents=True)

        env_path = env_dir / f"run{self.trio_num}.env"

        # Test for existing ENV file name
        env_file = TestFile(env_path, self.logger)
        env_file.check_missing()

        # Only create a new ENV object if non-existant, or if --update=True
        if env_file.file_exists:
            self.file_made = False
            if self.update:
                msg = "update"
            else:
                msg = "use existing"
        else:
            self.file_made = True
            msg = "create"

        if self.dryrun_mode:
            self.logger.info(
                f"{self.logging_msg}: pretending to {msg} env file | '{env_path}'"
            )
        else:
            self.logger.info(f"{self.logging_msg}: {msg} env file | '{env_path}'")

        # Load in the env file to write any missing variables to
        self.env = Env(
            env_path,
            self.logger,
            logger_msg=self.logging_msg,
            debug_mode=self.debug_mode,
            dryrun_mode=self.dryrun_mode,
        )

        # Define the row index to use
        if self.trio_num == 0:
            self.index = self.trio_num
        else:
            self.index = self.trio_num - 1

        if not self.demo_mode:
            if self.dryrun_mode:
                self.logger.info(
                    f"{self.logging_msg}: {msg} environment file {self.trio_num + 1}-of-{self.num_of_iterations}"
                )
            else:

                self.logger.info(
                    f"{self.logging_msg}: {msg} environment file {self.trio_num + 1}-of-{self.num_of_iterations}"
                )

        if self.debug_mode:
            self.logger.debug(f"{self.logging_msg}: current trio | {self.trio_num}")
            self.logger.debug(f"{self.logging_msg}: index used | {self.index}")

    def identify_channels(
        self,
        default_channels: str = '{"channels": [1, 2, 3, 4, 5, 6, 19]}',
        update: bool = False,
    ) -> None:
        """
        Flexibly handle multiple channel options, rather than hard-coding based on current defaults.
        """
        base_channels = [1, 2, 3, 4, 5, 6]
        valid_channels = {
            0: "unspecified",  # Default should be unspecified.
            1: "read_base",  # 6 channels that exist in all DeepVariant production models.
            2: "base_quality",
            3: "mapping_quality",
            4: "strand",
            5: "read_supports_variant",
            6: "base_differes_from_ref",
            7: "haplotype_tag",  # haplotype information
            8: "allele_frequency",  # population data
            9: "alternate_allele1",  # two extra channels for diff_channels
            10: "alternate_allele2",
            11: "read_mapping_percent",  # Opt Channels
            12: "avg_base_quality",
            13: "identity",
            14: "gap_compressed_identity",
            15: "gc_content",
            16: "is_homeopolymer",
            17: "homeopolymer_weighted",
            18: "blank",
            19: "insert_size",
            20: "base_channels_alt_allele1",  # two extra channels for base_channels
            21: "base_channels_alt_allele2",
        }

        if (
            self.channel_info is not None
            and self.channel_info != default_channels
            and ".json" in str(self.channel_info)
        ):
            if Path(str(self.channel_info)).is_file():
                with Path(str(self.channel_info)).open(mode="r") as read_file:
                    channels_found = json.load(read_file)["channels"]
            else:
                channels_found = []
        else:
            channels_found = json.loads(str(self.channel_info))["channels"]

        for c in channels_found:
            if c not in base_channels:
                if c in valid_channels.keys():
                    self.additional_channels[c] = valid_channels[c]

        if "insert_size" in self.additional_channels.values():
            self.use_insert_size = True

        if "allele_frequency" in self.additional_channels.values():
            self.use_allele_freq = True
        else:
            self.use_allele_freq = False

        if update:
            self.logger.info(
                f"{self.logging_msg}: updated channels include | {self.additional_channels}"
            )

    def set_conditions(self, update: bool = False) -> None:
        """
        Create a label for the current analysis to keep track of the channels included with make_examples.
        """
        conditions = []
        if self.use_insert_size:
            conditions.append("withIS")

        if self.use_allele_freq:
            conditions.append("withAF")
        else:
            conditions.append("noAF")

        if conditions:
            self.conditions_used = "_".join(conditions)

        if update:
            self.logger.info(
                f"{self.logging_msg}: updated conditions used | '{self.conditions_used}'"
            )
            if self.conditions_used is not None:
                self._output_dict["ConditionsUsed"] = self.conditions_used
        elif self.debug_mode:
            self.logger.debug(
                f"{self.logging_msg}: initial conditions | '{self.conditions_used}'"
            )

    def identify_checkpoint(self) -> None:
        """
        Determine which model ckpt point to use, default, or custom.
        """

        if self.checkpoint_name is not None:
            self._checkpoint_path = Path(str(self.checkpoint_name)).parent.resolve()
            self.checkpoint_name = Path(str(self.checkpoint_name)).name
            found_non_default_ckpt = regex.search(r"-\d+", self.checkpoint_name)

            if "wgs_af" in self.checkpoint_name:
                self.logger.info(
                    f"{self.logging_msg}: using a default model's weights to initalize DeepVariant-v{self._version}"
                )
                self.use_allele_freq = True
                self.set_conditions(update=True)
                self._checkpoint_path = (
                    self._checkpoint_path.parent
                    / f"v{self._version}_{self.conditions_used}/"
                )
                self.channel_info = (
                    self._checkpoint_path / f"{self.checkpoint_name}.example_info.json"
                )
                self.identify_channels(update=True)
            elif found_non_default_ckpt:
                self.logger.info(
                    f"{self.logging_msg}: using a custom model's weights to initalize DeepVariant-v{self._version}"
                )
                if None in self.train_order:
                    self.channel_info = (
                        self._checkpoint_path
                        / f"{self.checkpoint_name}.example_info.json"
                    )

        else:
            if self.itr_num < 2:
                self._checkpoint_path = (
                    Path.cwd()
                    / "triotrain"
                    / "model_training"
                    / "pretrained_models"
                    / f"v{self._version}_{self.conditions_used}/"
                )
                self.checkpoint_name = "model.ckpt"
                self.channel_info = (
                    self._checkpoint_path / f"{self.checkpoint_name}.example_info.json"
                )
                self.logger.info(
                    f"{self.logging_msg}: using a default model's weights to initalize DeepVariant-v{self._version}"
                )
                if self.itr_num == 0:
                    self._output_dict["BaselineTestCkptPath"] = str(
                        self._checkpoint_path
                    )
                    self._output_dict["BaselineTestCkptName"] = str(
                        self.checkpoint_name
                    )

            elif self.itr_num >= 2 and self.trio_num is not None and self.trio_num > 0:
                self.logger.info(
                    f"{self.logging_msg}: using model weights from previously re-training to initalize DeepVariant-v{self._version}"
                )
                self.logger.info(
                    f"{self.logging_msg}: warm-starting checkpoint will be determined shortly..."
                )

        if self._checkpoint_path is not None and self.checkpoint_name is not None:
            self.logger.info(
                f"{self.logging_msg}: warm-starting checkpoint | '{self._checkpoint_path}/{self.checkpoint_name}'"
            )

    def add_empty_variable(self, key: str) -> None:
        """
        create a variable='' within the EnvFile
        """
        if self.debug_mode:
            self.logger.debug(
                f"[{self.mode}]  - [{self._phase}]: the add_to() function created an empty variable [{key}]",
            )
        self.env.add_to(
            key,
            "",
            dryrun_mode=self.dryrun_mode,
            msg=self.logging_msg,
            update=self.update,
        )

    def iterate_metadata(self, missing_values=["nan", "", None, "NaN", np.nan]):
        """
        Iterate through each row in the metadata dataframe.

        Create a new env file for each row, plus an extra env file for baseline tests.
        """
        if self._output_dict:
            self._output_dict.update(self._stable_vars)
        else:
            self._output_dict = self._stable_vars.copy()

        # handle the baseline model outputs
        if self.conditions_used is not None:
            self._output_dict["BaselineModelResultsDir"] = (
                f"{str(self.output_dir)}/baseline_v{self._version}_{self.conditions_used}"
            )
        else:
            self._output_dict["BaselineModelResultsDir"] = (
                f"{str(self.output_dir)}/baseline_v{self._version}"
            )

        if not self.env.env_path.exists and self.dryrun_mode:
            print(
                f"-----------------------------  [DRY_RUN] Start of Environment File [{self.env.env_file}] -----------------------------"
            )

        col_num = 0
        for col in self.column_names:
            # New variable for each column in the df
            col_num = col_num + 1
            # Record column number working on
            value = self.data[col][self.index]

            if col_num >= 10:
                # Columns 10+ are paths. Confirm that the paths given exist
                absolute_path = TestFile(str(value), self.logger)
                try:
                    if absolute_path.file in missing_values:
                        raise AssertionError(
                            f"{self.logging_msg}: missing value detected | {col}='{absolute_path.file}'"
                        )
                    else:
                        absolute_path.check_existing(logger_msg=self.logging_msg)
                        if not absolute_path.file_exists:
                            raise FileNotFoundError(
                                f"{self.logging_msg}: non-existant file provided | '{absolute_path.file}'"
                            )

                        if col == "PopVCF":
                            
                            if absolute_path.file_exists:
                                self.use_allele_freq = True
                            
                            if self.use_allele_freq and self.trio_num > 0:
                                # If adding PopVCF data to new model, update conditions accordingly...
                                if 8 not in self.additional_channels.keys():
                                    self.additional_channels[8] = "allele_frequency"
                                    self.set_conditions(update=True)

                                # Separate out path from file for Apptainer bindings
                                # Add the PopVCF_File + PopVCF_Path for non-baseline envs
                                self.env.add_to(
                                    f"{col}_Path",
                                    str(absolute_path.path.parent),
                                    dryrun_mode=self.dryrun_mode,
                                    msg=self.logging_msg,
                                    update=self.update,
                                )
                                self.env.add_to(
                                    f"{col}_File",
                                    str(absolute_path.path.name),
                                    dryrun_mode=self.dryrun_mode,
                                    msg=self.logging_msg,
                                    update=self.update,
                                )
                            else:
                                # Remove PopVCF path from baseline env
                                if (
                                    f"{col}_Path" not in self.env.contents
                                    and f"{col}_File" not in self.env.contents
                                ):
                                    self.add_empty_variable(col)
                        else:
                            # Separate out remaining path variables
                            self.env.add_to(
                                f"{col}_Path",
                                str(absolute_path.path.parent),
                                dryrun_mode=self.dryrun_mode,
                                msg=self.logging_msg,
                                update=self.update,
                            )
                            # Create a separate variable
                            # for just the file name
                            self.env.add_to(
                                f"{col}_File",
                                str(absolute_path.path.name),
                                dryrun_mode=self.dryrun_mode,
                                msg=self.logging_msg,
                                update=self.update,
                            )

                except AssertionError as error:
                    if self.trio_num == 0:
                        if "Test" not in col:
                            self.add_empty_variable(col)
                            continue

                    if None in self.train_order:
                        if (
                            "Child" in col
                            or "Mother" in col
                            or "Father" in col
                            or "Test" in col
                        ):
                            self.add_empty_variable(col)
                            continue
                    
                    if "PopVCF" in col or "Region" in col:
                        self.add_empty_variable(col)
                        continue

                except FileNotFoundError as error:
                    # handle a non-existant or empty value for required inputs
                    if (
                        "BAM" in col
                        or "CRAM" in col
                        or "BED" in col
                        or "TruthVCF" in col
                    ):
                        self.logger.error(error)
                        self.logger.error(
                            f"{self.logging_msg}: a required BAM/CRAM/BED/TruthVCF does not exist"
                        )
                        self.logger.error(
                            f"{self.logging_msg}: unable to set a required variable | '{col}'"
                        )
                        self.logger.error(
                            f"{self.logging_msg}: unable to finish defining environment | '{self.env.env_file}'\nExiting...",
                        )
                        sys.exit(2)
                    else:
                        self.logger.info(error)
                        self.add_empty_variable(col)

            # Other columns in df are NOT paths so they can be added directly
            else:
                # Determine if value is not a string and is 'nan'
                if isinstance(value, str) is False and isnan(value):
                    # if 'nan', add an empty variable
                    self.add_empty_variable(key=col)
                # Otherwise, add whatever was saved in the metadata file
                else:
                    self.env.add_to(
                        col,
                        str(value),
                        dryrun_mode=self.dryrun_mode,
                        msg=self.logging_msg,
                        update=self.update,
                    )

                # Add additional stable variables based on mode
                if col == "RunName" and self._output_dict is not None:
                    self._run_name = str(value)
                    run_dir = Path(self._stable_vars["OutPath"]) / self._run_name

                    if self.trio_num != 0:
                        more_vars = {
                            "RunDir": f"{str(run_dir)}",
                            "JobDir": f"{str(run_dir / 'jobs')}",
                            "LogDir": f"{str(run_dir / 'logs')}",
                        }
                    else:
                        more_vars = {"RunDir": f"{str(run_dir)}"}

                    self._output_dict.update(more_vars)

                    if None in self.train_order:
                        self._output_dict["BaselineModelResultsDir"] = f"{str(run_dir)}"

                    # Only need these variables with TrioTrain
                    else:
                        train_vars = {
                            "ExamplesDir": f"{str(run_dir / 'examples')}",
                            "FatherTrainDir": f"{str(run_dir / 'train_Father')}",
                            "MotherTrainDir": f"{str(run_dir / 'train_Mother')}",
                            "FatherTestDir": f"{str(run_dir / 'test_Father')}",
                            "MotherTestDir": f"{str(run_dir / 'test_Mother')}",
                            "FatherCompareDir": f"{str(run_dir / 'compare_Father')}",
                            "MotherCompareDir": f"{str(run_dir / 'compare_Mother')}",
                        }
                        self._output_dict.update(train_vars)

        if self._output_dict is not None:
            # For each item in stable_vars dict
            # add them AFTER the custom variables are added
            for key, val in self._output_dict.items():
                self.env.add_to(
                    str(key),
                    str(val),
                    dryrun_mode=self.dryrun_mode,
                    msg=self.logging_msg,
                    update=self.update,
                )

        # Keep a record if any keys are changed
        if self.env.updated_keys.keys():
            keys_str = ",".join(self.env.updated_keys.keys())
            time_updated = timestamp()
            comment = f"# {time_updated}: updated the following keys | '{keys_str}'"
            self.env.add_to(
                key=comment,
                value=None,
                dryrun_mode=self.dryrun_mode,
                msg=self.logging_msg,
            )
            # ^ No need to include the update variable as the 'key' is really a text string

        if not self.env.env_path.exists and self.dryrun_mode:
            print(
                f"----------------------------- [DRY_RUN] End of Environment File [{self.env.env_file}]----------------------------- "
            )

    def create_dirs(self) -> None:
        """
        Make directories for analyses, depending on environment
        """
        vars_list = [
            "OutPath",
            "ResultsDir",
        ]
        if self.trio_num == 0:
            vars_list.append("BaselineModelResultsDir")
        else:
            # Define required directories
            vars_list = vars_list + ["RunDir", "JobDir", "LogDir"]

            # Only need these directories with TrioTrain
            if None not in self.train_order:
                vars_list = vars_list + [
                    "ExamplesDir",
                    "FatherTrainDir",
                    "MotherTrainDir",
                    "FatherTestDir",
                    "MotherTestDir",
                    "FatherCompareDir",
                    "MotherCompareDir",
                ]

        if self.dryrun_mode:
            for var in vars_list:
                if not Path(str(self.env.contents[var])).is_dir():
                    self.logger.info(
                        f"{self.logging_msg}: directory would be created | '{var}'"
                    )
            return
        else:
            if self.trio_num == 0:
                outpath, results_dir, baseline_results_dir = self.env.load(*vars_list)
                dirs = [outpath, results_dir, baseline_results_dir]
            elif None in self.train_order:
                outpath, results_dir, run_dir, job_dir, log_dir = self.env.load(
                    *vars_list
                )
                dirs = [outpath, results_dir, run_dir, job_dir, log_dir]
            else:
                (
                    outpath,
                    results_dir,
                    run_dir,
                    job_dir,
                    log_dir,
                    example_dir,
                    father_train_dir,
                    father_test_dir,
                    mother_train_dir,
                    mother_test_dir,
                    father_compare_dir,
                    mother_compare_dir,
                ) = self.env.load(*vars_list)
                dirs = [
                    outpath,
                    results_dir,
                    run_dir,
                    job_dir,
                    log_dir,
                    example_dir,
                    father_train_dir,
                    father_test_dir,
                    mother_train_dir,
                    mother_test_dir,
                    father_compare_dir,
                    mother_compare_dir,
                ]

            # Create required directories
            for new_dir in dirs:
                if new_dir is not None:
                    if Path(new_dir).is_dir():
                        if self.debug_mode:
                            self.logger.debug(
                                f"{self.logging_msg}: directory found | '{new_dir}'"
                            )
                    else:
                        Path(new_dir).mkdir()
                        if Path(new_dir).is_dir():
                            self.logger.info(
                                f"{self.logging_msg}: created a new directory | '{new_dir}'"
                            )

    def test_env(self) -> None:
        """
        Confirm if a env file was written
        """
        if self.dryrun_mode and self.update is False:
            if self.env.env_path.exists() is False:
                self.logger.info(f"{self.logging_msg}: no file(s) created, as expected")
        else:
            assert (
                self.env.env_path.is_file()  # type: ignore
            ), "expected a file to be written, but none found"
            if self.debug_mode:
                self.logger.debug(f"{self.logging_msg}: loading environment now... ")
            if self.update:
                return
            else:
                self.env = Env(
                    self.env.env_file,
                    self.logger,
                    logger_msg=self.logging_msg,
                    debug_mode=self.debug_mode,
                    dryrun_mode=self.dryrun_mode,
                )
                self.logger.info(
                    f"{self.logging_msg}: loaded environment variables from | '{self.env.env_file}'"
                )

    def make_a_file(self) -> None:
        """
        Putting together the functions to create one (1) env file into a single function.
        """
        # Process the variables from both Metadata and Stable Vars
        self.create_env()
        self.iterate_metadata()
        self.test_env()
        self._stable_vars["EnvFile"] = self.env.env_file

    def run(
        self,
        analysis_name: str,
        num_epochs: int,
        learning_rate: float,
        batch_size: int,
    ) -> None:
        """
        Consolidating functions to be used with both command line args and as a module.
        """
        # ---NOTE TO FUTURE SELF---#
        #   If you define outpath by referencing RootPath, it won't work
        #   The way it's set up is repetative, but don't mess
        #   with it because it works!
        # -------------------------#
        self.analysis_name = analysis_name

        self._stable_vars = {
            "CodePath": f"{str(self.working_dir)}",
            "RootPath": f"{str(self.output_dir)}",
            "OutPath": f"{str(self.output_dir / self.analysis_name)}",
            "ResultsDir": f"{str(self.output_dir / self.analysis_name / 'summary')}",
            "BaselineModelInputDir": f"{str(self.working_dir /'pretrained_models')}",
            "N_Epochs": num_epochs,
            "LearnRate": learning_rate,
            "BatchSize": batch_size,
        }
        try:
            self.check_input()
        except ValueError as E:
            self.logger.error(f"{self.logging_msg}: {E} Exiting... ")
            sys.exit(1)

        self.identify_checkpoint()
        self.identify_channels()

        if None not in self.train_order:
            self.create_lists()

        if self.trio_num is not None:
            self.make_a_file()
            self.create_dirs()
        else:
            # Create all analyses env files, as many the number of rows in metadata
            for row in range(0, self.num_envs):
                self.trio_num = row
                self.make_a_file()
                self.create_dirs()
