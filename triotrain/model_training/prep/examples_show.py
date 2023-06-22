#!/usr/bin/python3
"""
description: for each line in the <regions.bed> file, create a corresponding sbatch job file. Then, produce a PNG image with the channel layers in a subset of examples given to the model for re-training.

example:

    python3 show_examples.py                        \\
        --env-file </path/to/environment.env>       \\
        --regions-file </path/to/regions.bed>       \\
        --resources </path/to/cluster_config.json>  \\
        --genome Mother                             \\
        --demo-chr 24
"""

# Load python libs
import argparse
import json
import sys
from dataclasses import dataclass, field
from logging import Logger
from os import environ, getcwd, path
from pathlib import Path
from typing import List, Union

from regex import Pattern, findall

# get the relative path to the triotrain/ dir
h_path = str(Path(__file__).parent.parent.parent)
sys.path.append(h_path)
import helpers
import model_training.prep as prep
import model_training.slurm as s


def collect_args():
    """
    Process the command line arguments.
    """
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--env-file",
        dest="env_file",
        help="[REQUIRED]\ninput file (.env)\ncurrent environment",
        type=str,
        metavar="</path/to/environment.env>",
    )
    parser.add_argument(
        "--show-regions-file",
        dest="show_regions_file",
        help="[REQUIRED]\ninput file (.bed or .txt)\ncontains location(s) to visualize by creating images of the multi-channel tensor vector(s)\n==== .bed format ====\nCHROM\tSTART\tSTOP\n=====================\n==== .txt format ====\nCHROM:START-STOP\n=====================",
        type=str,
        metavar="</path/to/regions_file>",
    )
    parser.add_argument(
        "-r",
        "--resources",
        dest="resource_config",
        help="[REQUIRED]\ninput file (.json)\ndefines HPC cluster resources for SLURM",
        type=str,
        metavar="</path/to/cluster_config.json>",
    )
    parser.add_argument(
        "-d",
        "--debug",
        dest="debug",
        help="printing detailed messages",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--demo-mode",
        dest="demo_mode",
        help="creates images for the demo chromosome only\n(default: %(default)s)",
        default=True,
        action="store_true",
    )
    parser.add_argument(
        "--demo-chr",
        dest="demo_chr",
        default="29",
        help="set the chromosome used during make_examples\nREQUIRED if using <genome>.<chr#> naming convention for tfrecords\n(default: %(default)s)",
    )
    parser.add_argument(
        "--dependencies",
        dest="dependencies",
        help=f"comma-delimited list of (1+) SLURM job number(s) that must complete successfully before submitting show_examples job(s)",
        type=str,
        metavar="<'24485783,24485784'>",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        help="display show_examples job contents to the screen",
        action="store_true",
    )
    parser.add_argument(
        "--genome",
        dest="genome",
        help="which individual in the trio to use\n(default: %(default)s)",
        default="Mother",
        choices=["Mother", "Father", "Child"],
    )
    parser.add_argument(
        "-o",
        "--overwrite",
        dest="overwrite",
        help="enable potential overwritting of existing pngs files\n(default: %(default)s)",
        action="store_true",
    )

    return parser.parse_args()
    # return parser.parse_args(
    #     [
    #         "--env-file",
    #         "envs/DEMO2-run1.env",
    #         "--show-regions-file",
    #         "DEMO_PASS1.show_regions.bed",
    #         "--resources",
    #         "resources_used.json",
    #         "--genome",
    #         "Father",
    #     ]
    # )


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
        logger.info("[DRY_RUN]: output will display to screen and not write to a file")

    assert (
        args.env_file
    ), "Missing --env-file; Please provide a file with environment variables for the current analysis"
    assert (
        args.show_regions_file
    ), "Missing --show-regions-file; Please provide the path to either a BED or TXT file containing CHROM POS information"
    assert (
        args.resource_config
    ), "Missing --resource_config; Please designate a path to pipeline compute resources in JSON format"


@dataclass
class ShowExamples:
    """
    Define what data to store for the 'show_examples' phase of the TrioTrain Pipeline.
    """

    # required values
    itr: helpers.Iteration
    slurm_resources: dict
    model_label: str
    show_regions_file: Union[str, Path]

    # optional values
    make_examples_jobs: Union[List[Union[str, None]], None] = field(
        default_factory=list
    )
    overwrite: bool = False
    train_mode: bool = True

    # internal, imutable values
    _examples_regex: Union[str, Pattern] = field(
        default=r"labeled.tfrecords-\d+-of-\d+.gz",
        init=False,
        repr=False,
    )
    _existing_pngs: bool = field(default=False, init=False, repr=False)
    _existing_tfrecords: Union[bool, None] = field(
        default=False, init=False, repr=False
    )
    _list_of_slurm_jobs: List = field(default_factory=list, init=False, repr=False)
    _output_jobnum: List[Union[str, None]] = field(
        default_factory=list, init=False, repr=False
    )
    _phase: str = field(default="show_examples", init=False, repr=False)
    _skipped_counter: int = field(default=0, init=False, repr=False)
    _version: Union[str, None] = field(
        default=environ.get("BIN_VERSION_DV"), init=False, repr=False
    )

    def set_genome(self) -> None:
        """
        Define the current genome
        """
        if self.train_mode:
            self.genome = self.itr.train_genome
            self.index = 0
        else:
            self.genome = self.itr.eval_genome
            self.index = 1

        if self.itr.demo_mode:
            self.logger_msg = f"[{self.itr._mode_string}] - [{self._phase}] - [{self.genome}] - [CHR{self.itr.demo_chromosome}]"
            self.prefix = f"{self.genome}.chr{self.itr.demo_chromosome}"
            self.job_label = f"{self.genome}{self.itr.current_trio_num}.chr{self.itr.demo_chromosome}"
            self.error_label = f"demo-{self.prefix}"
        else:
            self.logger_msg = (
                f"[{self.itr._mode_string}] - [{self._phase}] - [{self.genome}]"
            )
            self.prefix = f"{self.genome}"
            self.job_label = f"{self.genome}{self.itr.current_trio_num}"
            self.error_label = f"{self.genome}"

        if self.itr.debug_mode:
            self.itr.logger.debug(f"{self.logger_msg}: current iteration | {self.itr}")
            self.itr.logger.debug(
                f"{self.logger_msg}: search pattern prefix | {self.prefix}"
            )

    def set_inputs(self) -> None:
        """
        Define the show_regions BED file
        """
        self.regions_path = Path(self.show_regions_file)

        if str(self.regions_path.parent) == ".":
            self.regions_dir = getcwd()
        else:
            self.regions_dir = str(Path(self.show_regions_file).parent)

        self.region_file = self.regions_path.name

    def set_output(self) -> None:
        """
        Make a new directory to store pileup-style, TensorFlow vector PNGs
        """
        self.pileup_path = self.itr.examples_dir / "pileups" / str(self.genome)

        if self.pileup_path.is_dir():
            self.itr.logger.info(
                f"{self.logger_msg}: image path already exists... SKIPPING AHEAD"
            )
        else:
            self.itr.logger.info(
                f"{self.logger_msg}: creating a new directory to store pileup image vectors"
            )
            self.pileup_path.mkdir(parents=True)

    def prepare_file_labels(self) -> None:
        """
        Set up the prefix patterns for both inputs and outputs
        """
        make_examples = prep.MakeExamples(
            self.itr, self.slurm_resources, self.model_label, train_mode=self.train_mode
        )
        make_examples.set_genome()
        make_examples.find_outputs(phase="show_examples")
        self._existing_tfrecords = make_examples._existing_tfrecords

        if self._existing_tfrecords:
            # Build slurm command based on existing files found
            tfrecord = make_examples._tfrecord_files_list[1]
            tfrecord_components = tfrecord.split("-")
            n_shards = tfrecord_components[3].split(".")[0].lstrip("0")
            self.tfrecord_pattern = f"{tfrecord_components[0]}@{n_shards}.gz"

            # NOTE: You only need to provide one 'example_info'
            #       file when working with sharded files, since
            #       they will all be made the same way.
            self.example_info_pattern = f"{tfrecord}.example_info.json"
        else:
            if self.make_examples_jobs is None:
                self.itr.logger.warning(
                    f"{self.logger_msg}: expected --dependencies, provide a list of PD or R Slurm job numbers to procced"
                )
                raise FileNotFoundError(
                    f"{self.logger_msg}: unable to find existing tfrecords"
                )
            elif (
                self.make_examples_jobs is not None
                and len(self.make_examples_jobs) == 0
            ):
                self.itr.logger.warning(
                    f"{self.logger_msg}: expected --dependencies, provide a list of PD or R Slurm job numbers to procced"
                )
                raise FileNotFoundError(
                    f"{self.logger_msg}: unable to find existing tfrecords"
                )
            else:
                n_shards = self.slurm_resources["make_examples"]["ntasks"]
                self.tfrecord_pattern = f"{self.prefix}.labeled.tfrecords@{n_shards}.gz"
                self.example_info_pattern = f"{self.prefix}.labeled.tfrecords-00001-of-000{n_shards}.gz.example_info.json"

        if self.itr.debug_mode:
            self.itr.logger.debug(f"N_SHARDS: {n_shards}")
            self.itr.logger.debug(f"TFRECORD SEARCH PATTERN: {self.tfrecord_pattern}")
            self.itr.logger.debug(
                f"EXAMPLE INFO SEARCH PATTERN: {self.example_info_pattern}"
            )
            self.itr.logger.debug(f"PRIOR JOBS: {self.make_examples_jobs}")

    def make_job(self) -> None:
        """
        Build the Apptainer command to make PNG images based on inputs then create a SLURM job file to run after 'make_examples' phase finishes.
        """
        self.prepare_file_labels()

        # initialize a SBATCH Object
        self.job_name = f"{self._phase}-{self.job_label}"
        self.handler_label = f"{self._phase}: {self.prefix}"

        self.slurm_job = s.SBATCH(
            self.itr,
            self.job_name,
            self.model_label,
            self.handler_label,
            self.logger_msg,
        )

        if self.slurm_job.check_sbatch_file() is not False:
            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"{self.logger_msg}: SLURM job file already exists... SKIPPING AHEAD"
                )
            return

        command = f"time apptainer run -B /usr/lib/locale/:/usr/lib/locale/,{self.itr.examples_dir}/:/examples_dir/,{self.regions_dir}/:/regions_dir/ deepvariant_{self._version}-gpu.sif /opt/deepvariant/bin/show_examples --examples=/examples_dir/{self.tfrecord_pattern} --example_info_json=/examples_dir/{self.example_info_pattern} --output=/examples_dir/pileups/{self.genome}/{self.regions_path.stem} --regions"

        if self.itr.debug_mode:
            self.itr.logger.debug(
                f'{self.logger_msg}: region file bindings | "{str(self.regions_path.parent)}"'
            )

        if "bed" in self.regions_path.suffix:
            self.itr.logger.info(
                f"{self.logger_msg}: writing one SBATCH file for all region(s)... "
            )
            command_list = [
                f"{command} /regions_dir/{self.region_file} --image_type both --num_records 10 --verbose"
            ]

            self.slurm_job.create_slurm_job(
                handler_status_label=self.handler_label,
                command_list=command_list,
                **self.slurm_resources[self._phase],
            )
            if not self.slurm_job.job_file_exists:
                if self.itr.dryrun_mode:
                    self.slurm_job.display_job()
                else:
                    self.slurm_job.write_job()
            else:
                if self.itr.debug_mode:
                    self.itr.logger.debug(
                        f"{self.logger_msg}: SLURM job file already exists... SKIPPING AHEAD"
                    )
            self._list_of_slurm_jobs = [self.slurm_job]
        else:
            self.itr.logger.info(
                f"{self.logger_msg}: writing multiple SBATCH files, line in regions_file input... "
            )
            open_file = open(str(self.regions_path), "r")

            while True:
                line = open_file.readline()
                if not line:
                    break

                command_list = [
                    f"{command} {line.strip()} --image_type both --num_records 1 --verbose"
                ]
                self.slurm_job.create_slurm_job(
                    handler_status_label=f"{self._phase}: {self.prefix}",
                    command_list=command_list,
                    **self.slurm_resources[self._phase],
                )
                if not self.slurm_job.job_file_exists:
                    if self.itr.dryrun_mode:
                        self.slurm_job.display_job()
                    else:
                        self.slurm_job.write_job()
                else:
                    if self.itr.debug_mode:
                        self.itr.logger.debug(
                            f"{self.logger_msg}: SLURM job file already exists... SKIPPING AHEAD"
                        )
                self._list_of_slurm_jobs.append(self.slurm_job)

    def submit_show_examples(self) -> None:
        """
        Submit SLURM jobs to queue.
        """
        self.png_regex = rf"{self.regions_path.stem}\w+:\w+->\w+.\w+.png"

        # See if PNGs made using the region file already exist
        (
            self._existing_pngs,
            pngs_found,
            png_files,
        ) = helpers.h.check_if_output_exists(
            self.png_regex,
            "image PNGs",
            self.pileup_path,
            self.logger_msg,
            self.itr.logger,
            debug_mode=self.itr.debug_mode,
            dryrun_mode=self.itr.dryrun_mode,
        )

        if self._existing_pngs and self.overwrite is False:
            self.itr.logger.warning(
                f"{self.logger_msg}: existing PNGs with '{self.regions_path.stem} pattern detected'"
            )
            self.itr.logger.error(
                f"please provide a unique label prefix for PNGs, or enable possible overwritting of existing files with --overwrite"
            )
            self._skipped_counter += 1
            return
        elif self._existing_pngs and self.overwrite:
            self.itr.logger.warning(
                f"{self.logger_msg}: PNGs with '{self.regions_path.stem}' pattern detected"
            )
            self.itr.logger.warning(
                f"{self.logger_msg}: PNG files may be overwritten by new images"
            )
        else:
            self.itr.logger.info(
                f"{self.logger_msg}: no PNGs with '{self.regions_path.stem}' pattern detected"
            )

        slurm_job = s.SubmitSBATCH(
            self.itr.job_dir,
            f"{self.job_name}.sh",
            self.handler_label,
            self.itr.logger,
            self.logger_msg,
        )
        if self.make_examples_jobs is not None:
            slurm_job.build_command(prior_job_number=self.make_examples_jobs)
        else:
            slurm_job.build_command(prior_job_number=None)

        if self.itr.dryrun_mode:
            slurm_job.display_command(display_mode=self.itr.dryrun_mode)
            self._output_jobnum.append(helpers.h.generate_job_id())
        else:
            slurm_job.display_command(debug_mode=self.itr.debug_mode)
            slurm_job.get_status(debug_mode=self.itr.debug_mode)

            if slurm_job.status == 0:
                self._output_jobnum.append(slurm_job.job_number)
            else:
                self.itr.logger.error(
                    f"{self.logger_msg}: unable to submit SLURM job",
                )
                self._output_jobnum.append(None)

    def check_submission(self) -> None:
        """
        Check if 1+ SLURM job files were submitted to the SLURM queue successfully
        """
        show_examples_results = helpers.h.check_if_all_same(self._output_jobnum, None)
        if show_examples_results is False:
            if len(self._output_jobnum) == 1:
                if self.itr.dryrun_mode:
                    print(
                        f"============ [DRY_RUN] - {self.logger_msg} -  Job Number - {self._output_jobnum} ============"
                    )
                else:
                    print(
                        f"============ {self.logger_msg} - Job Number - {self._output_jobnum} ============"
                    )
            else:
                if self.itr.dryrun_mode:
                    if self.itr.dryrun_mode:
                        print(
                            f"============ [DRY_RUN] - {self.logger_msg} - Job Numbers ============\n{self._output_jobnum}\n============================================================"
                        )
                else:
                    print(
                        f"============ {self.logger_msg} - Job Numbers ============\n{self._output_jobnum}\n============================================================"
                    )

        elif self._skipped_counter != 0:
            self.itr.logger.info(
                f"{self.logger_msg}: found existing tfrecord file(s)... SKIPPING AHEAD"
            )
        else:
            self.itr.logger.error(
                f"{self.logger_msg}: expected SLURM jobs to be submitted, but they were not",
            )
            self.itr.logger.warning(
                f"{self.logger_msg}: fatal error encountered, unable to proceed further with pipeline.\nExiting... ",
            )

    def run(self) -> Union[List[Union[str, None]], None]:
        """
        Combine all the steps required to submit a job to SLURM queue into one step
        """
        self.set_genome()
        self.set_output()
        self.set_inputs()
        self.make_job()
        if len(self._list_of_slurm_jobs) > 1:
            for j in range(0, len(self._list_of_slurm_jobs)):
                self._list_of_slurm_jobs[j].submit_show_examples()
        else:
            self.submit_show_examples()
        self.check_submission()

        if self._output_jobnum is None:
            return [None]
        else:
            return self._output_jobnum


def __init__():
    """
    Command line execution of these functions
    """
    # Collect command line arguments
    args = collect_args()

    # Collect start time
    helpers.h.Wrapper(__file__, "start").wrap_script(helpers.h.timestamp())

    # Create error log
    current_file = path.basename(__file__)
    module_name = path.splitext(current_file)[0]
    logger = helpers.log.get_logger(module_name)

    # Check command line args
    try:
        check_args(args, logger)
    except AssertionError as error:
        logger.error(f"{error}\nExiting... ")
        sys.exit(1)

    # Load in environment vars into Python
    env_path = Path(args.env_file)
    env = helpers.h.Env(str(env_path), logger, dryrun_mode=args.dry_run)

    # Parse out current run name & num
    itr_name = env_path.stem.split("-")[1]
    itr = findall(r"\d+", itr_name)
    itr_num = int(itr[0])

    if args.demo_mode:
        model_label = f"Demo.{args.genome}.CHR{args.demo_chr}"
        prefix = f"[Demo] - [Trio{itr_num}] - [{args.genome}] - [CHR{args.demo_chr}] - [show_examples]"
    else:
        model_label = f"{args.genome}"
        prefix = f"[{args.genome}] - [show_examples]"

    if "TotalTests" in env.contents:
        num_tests = str(env.contents["TotalTests"])
        total_tests = int(num_tests)

        # Confirm SLURM resource config file provide is valid
        resource_file = helpers.h.TestFile(args.resource_config, logger)
        resource_file.check_existing(debug_mode=args.debug)

        if resource_file.file_exists:
            with open(args.resource_config, mode="r") as file:
                resource_dict = json.load(file)
                if args.debug:
                    logger.debug(f"{prefix}: SLURM resources | {resource_dict}")
        else:
            resource_dict = {}
            return

        if not args.demo_mode:
            current_itr = helpers.Iteration(
                current_trio_num=itr_num,
                next_trio_num="None",
                current_genome_num=itr_num,
                total_num_genomes=itr_num + 1,
                total_num_tests=total_tests,
                train_genome=args.genome,
                eval_genome="Child",
                env=helpers.h.Env(args.env_file, logger, dryrun_mode=args.dry_run),
                logger=logger,
                args=args,
            )
        else:
            current_itr = helpers.Iteration(
                current_trio_num=1,
                next_trio_num="None",
                current_genome_num=itr_num,
                total_num_genomes=2,
                total_num_tests=total_tests,
                train_genome=args.genome,
                eval_genome="Child",
                env=helpers.h.Env(args.env_file, logger, dryrun_mode=args.dry_run),
                logger=logger,
                args=args,
            )
    else:
        logger.error(
            f"{prefix}: unable to run ShowExamples, 'TotalTests' is missing from {args.env_file}"
        )
        sys.exit(1)

    convert = lambda i: None if i == "None" else str(i)
    region_files_list = [convert(file) for file in args.show_regions_file.split(",")]

    if args.dependencies:
        dependency_list = [convert(dep) for dep in args.dependencies.split(",")]
        slurm = ShowExamples(
            itr=current_itr,
            slurm_resources=resource_dict,
            model_label=model_label,
            show_regions_file=Path(args.show_regions_file),
            make_examples_jobs=dependency_list,
            overwrite=args.overwrite,
        )
        slurm.run()
    elif len(region_files_list) == 1:
        file_path = region_files_list[0]
        if file_path is not None:
            slurm = ShowExamples(
                itr=current_itr,
                slurm_resources=resource_dict,
                model_label=model_label,
                show_regions_file=Path(file_path),
                overwrite=args.overwrite,
            )
            slurm.run()
        else:
            current_itr.logger.error(
                f"{prefix}: unable to run ShowExamples, regions file is set to 'None'"
            )
    else:
        slurm = ShowExamples(
            itr=current_itr,
            slurm_resources=resource_dict,
            model_label=model_label,
            show_regions_file=Path(*args.show_regions_file),
        )
        slurm.run()

    helpers.h.Wrapper(__file__, "end").wrap_script(helpers.h.timestamp())


# Execute functions created when run from command line
if __name__ == "__main__":
    __init__()
