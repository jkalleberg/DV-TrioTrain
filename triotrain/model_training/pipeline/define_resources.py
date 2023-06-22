#!/bin/python3
"""
Description goes here.

Usage:
    python triotrain/model_training/pipeline/define_resources.py <args>

"""

# load in python libraries
import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Union

# get the relative path to the triotrain/ dir
h_path = str(Path(__file__).parent.parent.parent)
sys.path.append(h_path)
import helpers


def collect_args():
    """Handles the command line arguments.

    Returns
    -------
    argparse.Namespace
        key, value pairs for (argument_name, input_parameter)
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d",
        "--debug",
        dest="debug",
        help="print debug info",
        default=False,
        action="store_true",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--dry-run",
        dest="dry_run",
        help="display SLURM configuration to the screen",
        action="store_true",
    )
    group.add_argument(
        "--output",
        dest="output",
        help="where to write the JSON formatted resource configuration file after editing defaults",
        type=str,
        metavar="</path/to/file.json>",
    )
    parser.add_argument(
        "--rich-partition-list",
        dest="rich",
        help="comma-separated list of resource-rich partitions; include partitions which have the largest mem/cores on your system",
        type=str,
        default="hpc5,hpc6,BioCompute",
        metavar="<list,of,partitions>",
    )
    parser.add_argument(
        "--cpu-rich",
        dest="cpu_rich",
        type=int,
        help="max number of CPUs available for all resource-rich partitions",
        default=40,
        metavar="<int>",
    )
    parser.add_argument(
        "--mem-rich",
        dest="mem_rich",
        type=int,
        help="upper memory limit (M) for all resource-rich partitions",
        default=379067,
        metavar="<int>",
    )

    parser.add_argument(
        "--partition-list",
        dest="broad",
        help="comma-separated list of all partitions; include more partitions to start jobs faster",
        type=str,
        default="BioCompute,Lewis",
        metavar="<list,of,partitions>",
    )
    parser.add_argument(
        "--n-cpu",
        dest="cpus_broad",
        type=int,
        help="max number of CPUs available for all partitions",
        default=24,
        metavar="<int>",
    )
    parser.add_argument(
        "--mem",
        dest="mem_broad",
        type=int,
        help="memory limit (M) for all partitions",
        default=102400,
        metavar="<int>",
    )

    parser.add_argument(
        "--gpu-partition",
        dest="gpu",
        help="comma-separated list of GPU partitions (requires 2 cores per node)",
        type=str,
        default="gpu3",
        metavar="<list,of,partitions>",
    )
    parser.add_argument(
        "--n-gpu",
        dest="gpus",
        type=int,
        help="max number of threads with GPU partitions",
        default=16,
        metavar="<int>",
    )
    parser.add_argument(
        "--gpu-mem",
        dest="gpu_mem",
        type=int,
        help="memory limit (M) for GPU partitions",
        default=122535,
        metavar="<int>",
    )
    parser.add_argument(
        "--account",
        dest="account",
        help="sets SLURM account to charge resource usage and defines job priority; applies to all phases, unless edited interactively",
        choices=["animalsci", "schnabellab", "biocommunity"],
    )
    parser.add_argument(
        "--email",
        dest="email",
        help="email address to send progress updates; applies to all phases, unless edited interactively",
        type=str,
        default="jakth2@mail.missouri.edu",
        metavar="<user@gmail.com>",
    )
    parser.add_argument(
        "--num-nodes",
        dest="nnodes",
        help="number of compute nodes to use; applies to all phases; NOTE: the pipeline is not designed to use MPI, so changing this won't improve performance",
        type=int,
        default=1,
        metavar="<int>",
    )
    return parser.parse_args()


def check_email(email: str):
    """Confirms if a string matches <email@address.com> format

    Parameters
    ----------
    email : str
        where to send SLURM job status emails
    """
    # regular expression representing email format expectations
    regex = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    # pass the string into the fullmatch() method
    assert re.fullmatch(regex, email), f"Email [{email}] is invalid"


def check_time(time_str: str):
    """Confirms if a string matches 0-00:00:00 or days-Hours:Minutes:Seconds format

    Parameters
    ----------
    time_str : str
    """
    regex = r"(\d{1}\-\d{2}\:\d{2}\:\d{2})"
    assert re.fullmatch(regex, time_str), f"Time entry [{time_str}] is invalid"


class UseJSON(Dict[str, str]):
    """convert a Python dictionary to a JSON-formmated file

    Parameters
    ----------
    Dict : _type_
        _description_
    """

    def __str__(self):
        return json.dumps(self)

    def write_to_file(self, output_file: str = "output.json"):
        """
        write the JSON format data to a file
        """
        with open(output_file, mode="w", encoding="UTF-8") as file:
            json.dump(self, file)


class Pipeline:
    """Create a pipeline-specific set of SLURM resources"""

    def __init__(self, defaults: Dict[str, Dict[str, str]], logger: logging.Logger):
        self.valid_phases = [
            "make_examples",
            "beam_shuffle",
            "re_shuffle",
            "train_eval",
            "select_ckpt",
            "call_variants",
            "compare_happy",
            "convert_happy",
            "show_examples",
            "none",
        ]
        self.logger: logging.Logger = logger
        self.max_num_phases = len(self.valid_phases)
        self.phase_input: str = ""
        self.phase_list: List[str] = []
        self.updated_resources: Dict[str, Union[str, int]] = {}
        self.num_resources = 0
        self.resource_name: str = ""
        self.new_value: Union[str, int] = ""
        self.default_dict: Dict[str, Dict[str, str]] = defaults
        self.number_entered: bool = False

    def enter_a_number(self, resources: bool = True) -> None:
        self.number_entered = False
        if resources:
            type = "RESOURCES"
            total: int = len(self.phase_resource_defaults)
        else:
            type = "PHASES"
            total: int = len(self.default_dict.keys())

        n_input = input(f"Enter # of {type} to edit (max={total}): ")
        try:
            int_n_input = int(n_input)

            if resources:
                self.num_resources = int_n_input
                self.number_entered = True
            else:
                if int_n_input > self.max_num_phases:
                    self.num_phases = 0
                    self.number_entered = False
                    self.logger.error(
                        f"You told me to edit {self.num_phases} phases, but there are only {self.max_num_phases} available\nExiting...",
                    )
                    sys.exit(1)
                else:
                    self.num_phases: int = int_n_input
                    self.number_entered = True
        except ValueError:
            self.number_entered = False
            self.num_phases = 0
            self.logger.warning(
                f"You entered '{n_input}', which is not a valid integer... TRY AGAIN"
            )
            raise ValueError

    def edit_resources(self, current_phase: str):
        """_summary_

        Parameters
        ----------
        current_phase : str
            describes the TrioTrain phase to edit, must match the keys in self.default_dict

        Raises
        ------
        KeyError
            invalid resource name was provided
        ValueError
            a non-integer value was provided
        """
        self.phase_resource_defaults: Dict[str, str] = self.default_dict[current_phase]
        self.logger.info(f"{self.phase_label} defaults are:")
        self.logger.info("---------------")
        for key, value in self.phase_resource_defaults.items():
            self.logger.info(f"[{current_phase}] {key} = {value}")
        self.logger.info("---------------")

        print("NUMBER ENTERED?", self.number_entered)
        breakpoint()
        self.enter_a_number()
        print("NUMBER ENTERED?", self.number_entered)
        if self.num_resources != 0:
            for index in range(0, self.num_resources):
                self.logger.info("---------------")
                valid_resources_list: List[str] = [
                    key.lower() for key in self.phase_resource_defaults.keys()
                ]
                self.logger.info(
                    f"{self.phase_label} - Valid RESOURCES: {list(self.phase_resource_defaults.keys())}",
                )
                self.logger.info("---------------")
                resource_label = f"RESOURCE {index + 1}-of-{self.num_resources}"
                self.resource_name: str = helpers.h.process_resource(
                    str(
                        input(
                            f"{self.phase_label} --- {resource_label} | Enter a valid RESOURCE name: "
                        )
                    )
                )
                if self.resource_name.lower() not in valid_resources_list:
                    self.logger.error(
                        f"[{self.resource_name}] not found in {valid_resources_list}",
                    )
                    raise KeyError
                else:
                    self.logger.info(
                        f"{self.phase_label} --- {resource_label} @ [{self.resource_name}] default is '{self.phase_resource_defaults[self.resource_name]}'",
                    )
                    self.new_value = input(
                        f"{self.phase_label} --- {resource_label} @ [{self.resource_name}] | Enter a new VALUE : "
                    )

                    # type checking user input values
                    if self.resource_name in ["nodes", "ntasks", "CPUmem"]:
                        try:
                            self.new_value = int(self.new_value)
                        except ValueError:
                            self.logger.error(
                                f"Input for [{self.resource_name}] was [{self.new_value}], which must be an integer"
                            )
                    elif self.resource_name == "mem":
                        if (
                            "G" in self.new_value.upper()
                            or "M" in self.new_value.upper()
                        ):
                            self.logger.info(
                                f"[{self.resource_name}] contains units of either M or G"
                            )
                        else:
                            self.new_value = int(self.new_value)
                            self.logger.info(
                                f"[{self.resource_name}] is represented with bytes, and does not contains units (M or G)"
                            )
                    elif self.resource_name == "time":
                        try:
                            check_time(self.new_value)
                        except AssertionError as error_msg:
                            self.logger.error(error_msg)
                            self.logger.error("Default value will remain")
                            continue
                    elif self.resource_name == "email":
                        try:
                            check_email(self.new_value)
                        except AssertionError as error_msg:
                            self.logger.error(error_msg)
                            self.logger.error("Default value will remain")
                            continue

                    if str(self.new_value) == str(
                        self.phase_resource_defaults[self.resource_name]
                    ):
                        self.logger.warning(
                            f"{self.phase_label} --- {resource_label} @ [{self.resource_name}] was not changed"
                        )
                        continue
                    else:
                        if self.resource_name not in self.updated_resources.keys():
                            self.updated_resources[self.resource_name] = self.new_value
                            self.logger.info(
                                f"{self.phase_label} --- {resource_label} @ [{self.resource_name}] resources were updated",
                            )
                            self.prior_resources = self.updated_resources
                        elif self.resource_name in self.prior_resources.keys():
                            if (
                                self.new_value
                                != self.prior_resources[self.resource_name]
                            ):
                                self.logger.warning(
                                    f"[{self.resource_name}] was previously updated to [{self.prior_resources[self.resource_name]}]"
                                )
                                self.logger.info("---------------")
                                self.logger.info("Do you want to use:")
                                self.logger.info(
                                    f"\t(D)efault Value: [{self.phase_resource_defaults[self.resource_name]}]"
                                )
                                self.logger.info(
                                    f"\t(P)rior Value: [{self.prior_resources[self.resource_name]}]"
                                )
                                self.logger.info(
                                    f"\tor (N)ew Value: [{self.new_value}]?"
                                )
                                self.logger.info("---------------")
                                response = str(
                                    input(
                                        f"{self.phase_label} | Enter your choice [D, P, or N] now: "
                                    )
                                ).upper()
                                if response == "N":
                                    self.updated_resources[
                                        self.resource_name
                                    ] = self.new_value
                                    self.logger.info(
                                        f"{self.phase_label} --- {resource_label} @ [{self.resource_name}] was updated again",
                                    )
                                elif response == "P":
                                    self.updated_resources[
                                        self.resource_name
                                    ] = self.prior_resources[self.resource_name]
                                    self.logger.info(
                                        f"{self.phase_label} --- {resource_label} @ [{self.resource_name}] will stay [{self.prior_resources[self.resource_name]}]"
                                    )
                                elif response == "D":
                                    self.updated_resources[
                                        self.resource_name
                                    ] = self.phase_resource_defaults[self.resource_name]
                                    self.logger.info(
                                        f"{self.phase_label} --- {resource_label} @ [{self.resource_name}] was reverted back to defaults"
                                    )
                                self.prior_resources = self.updated_resources
                            else:
                                continue
        else:
            self.logger.warning(f"[{current_phase}] will have resource defaults only")

    def edit_phase(self, index: int, num_phases_to_edit: int):
        """
        change resources in PHASE from user input, and
        handle weird inputs from the user.
        """
        phase_counter = f"PHASE {index + 1}-of-{num_phases_to_edit}"
        phase_input = str(
            input(f"{phase_counter} | Enter a valid PHASE name: ").lower()
        )
        self.phase_input = helpers.h.process_phase(phase_input)
        if self.phase_input == "none":
            self.logger.warning(f"[{phase_counter}] SKIPPING AHEAD...")
        elif self.phase_input not in self.valid_phases:
            self.logger.error(
                f"PHASE '{self.phase_input}' not found in {self.valid_phases}",
            )
            raise KeyError
        else:
            try:
                self.phase_label = f"{phase_counter} @ [{self.phase_input}]"
                self.phase_list.insert(index, self.phase_input)
                self.edit_resources(self.phase_input)
                self.final_resources: Dict[str, str] = self.default_dict[
                    self.phase_input
                ]
                if len(self.updated_resources.keys()) > 0:
                    for key, value in self.updated_resources.items():
                        self.final_resources[key] = str(value)
                self.logger.info(f"{self.phase_label} = {self.final_resources}")
                self.updated_resources = {}
            except KeyError as error_msg:
                self.logger.error(f"Invalid key entered: {error_msg}")
                return
            except AssertionError as error_msg:
                self.logger.error(error_msg)
                return


def edit_pipeline(default_dict: Dict[str, Dict[str, str]], logger: logging.Logger):
    """_summary_

    Parameters
    ----------
    total_num_phases : int
        how many of the default phases you would like to edit SLURM resources for
    default_dict : Dict[str, Dict[str, str]]
        the current default SLURM resources
    logger : logging.Logger
        _description_

    Returns
    -------
    _type_
        _description_
    """
    trio_train = Pipeline(defaults=default_dict, logger=logger)
    print("NUMBER ENTERED?", trio_train.number_entered)
    breakpoint()
    while trio_train.number_entered is False:
        try:
            trio_train.enter_a_number(resources=False)
        except ValueError:
            continue

    if trio_train.num_phases != 0:
        output = default_dict
        for index in range(0, trio_train.num_phases):
            try:
                logger.info("---------------")
                logger.info(f"Valid PHASES: {list(default_dict.keys())}")
                logger.info("---------------")
                trio_train.edit_phase(index, trio_train.num_phases)
                if len(trio_train.final_resources.keys()) > 0:
                    output[trio_train.phase_input] = trio_train.final_resources
                    trio_train.updated_resources = {}
                else:
                    logger.warning("No PHASES were changed")
                    logger.warning("RESOURCES set to defaults")
                    output = default_dict

            except KeyError:
                logger.warning(
                    f"[PHASE {index+1}-of-{trio_train.max_num_phases}] RESOURCES will remain defaults... SKIPPING AHEAD"
                )
                continue
        return output
    else:
        logger.warning("You are not changing any PHASES")
        logger.warning("RESOURCES will remain defaults")
        return default_dict


def __init__():
    # Collect command line arguments
    args = collect_args()

    # Collect start time
    helpers.Wrapper(__file__, "start").wrap_script(helpers.h.timestamp())

    # Create error log
    current_file = os.path.basename(__file__)
    module_name = os.path.splitext(current_file)[0]
    logger: logging.Logger = helpers.log.get_logger(module_name)

    # Check command line args
    _version = os.environ.get("BIN_VERSION_DV")
    if args.debug:
        str_args = "COMMAND LINE ARGS USED: "
        for key, val in vars(args).items():
            str_args += f"{key}={val} | "
        logger.debug(str_args)
        logger.debug(f"Using DeepVariant version {_version}")

    try:
        check_email(args.email)
    except AssertionError as error:
        logger.exception(f"{error}\nExiting... ")
        sys.exit(1)

    # Memory requested for each CPU
    mem_per_core_mb = int(args.mem_rich / args.cpu_rich)
    # nnodes = args.nnodes

    defaults: Dict[str, Dict[str, Union[str, int]]] = {
        "make_examples": {
            "partition": args.rich,
            "nodes": args.nnodes,
            "ntasks": args.cpu_rich,
            "mem": args.mem_rich,
            "CPUmem": mem_per_core_mb,
            "time": "0-2:00:00",
            "account": args.account,
            "email": args.email,
        },
        "beam_shuffle": {
            "partition": args.rich,
            "nodes": args.nnodes,
            "ntasks": args.cpu_rich,
            "mem": args.mem_rich,
            "time": "0-2:00:00",
            "account": args.account,
            "email": args.email,
        },
        "re_shuffle": {
            "partition": args.broad,
            "nodes": args.nnodes,
            "ntasks": 1,
            "mem": "1G",
            "time": "0-01:00:00",
            "account": args.account,
            "email": args.email,
        },
        "train_eval": {
            "partition": args.gpu,
            "gres": "gpu:2",
            "nodes": args.nnodes,
            "ntasks": args.gpus,
            "mem": args.gpu_mem,
            "time": "2-00:00:00",
            "account": args.account,
            "email": args.email,
        },
        "select_ckpt": {
            "partition": args.broad,
            "nodes": args.nnodes,
            "ntasks": 1,
            "mem": "1G",
            "time": "0-00:30:00",
            "account": args.account,
            "email": args.email,
        },
        "call_variants": {
            "partition": args.rich,
            "nodes": args.nnodes,
            "ntasks": args.cpu_rich,
            "mem": args.mem_rich,
            "time": "2-00:00:00",
            "account": args.account,
            "email": args.email,
        },
        "compare_happy": {
            "partition": args.broad,
            "nodes": args.nnodes,
            "ntasks": args.cpus_broad,
            "mem": args.mem_broad,
            "time": "0-01:00:00",
            "account": args.account,
            "email": args.email,
        },
        "convert_happy": {
            "partition": args.broad,
            "nodes": args.nnodes,
            "ntasks": args.cpus_broad,
            "mem": args.mem_broad,
            "time": "0-01:00:00",
            "account": args.account,
            "email": args.email,
        },
        "show_examples": {
            "partition": args.broad,
            "nodes": args.nnodes,
            "mem": args.mem_broad,
            "time": "0-02:00:00",
            "account": args.account,
            "email": args.email,
        },
    }

    logger.info(f"Pipeline Resource Defaults are currently:")
    logger.info("---------------")
    for key, value in defaults.items():
        logger.info(f"[{key}] = {value}")
    logger.info("---------------")
    output: Dict[str, Dict[str, str]] = edit_pipeline(defaults, logger)
    if not args.debug and not args.dry_run:
        json_output = UseJSON(output)
        if Path(args.output).exists():
            logger.warning("Attempting to overwrite an exiting output")
        else:
            logger.info(f"Writing [{args.output}]")
            json_output.write_to_file(args.output)
    else:
        logger.info("Final Resources Written:")
        for key, value in output.items():
            logger.info(f"[{key}] = {value}")

    helpers.Wrapper(current_file, "end").wrap_script(helpers.h.timestamp())


# Execute functions created
if __name__ == "__main__":
    __init__()
