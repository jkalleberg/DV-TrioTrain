#!/bin/python3
"""
description: creates examples for re-training the DeepVariant model with non-human genomes.

example:
    python3 scripts/model_training/make_examples.py           \\
        --env-file envs/demo.env                              \\
        --task-id 0                                           \\
        --genome Mother                                       \\
        --region 1                                            \\
        --dry-run
"""
import argparse
from dataclasses import dataclass, field
from logging import Logger
from os import environ, path
from pathlib import Path
from sys import exit
from typing import Union

import helpers as h
import helpers_logger
from spython.main import Client


def collect_args():
    """
    Process command line argument to execute script.
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
        "-t",
        "--task-id",
        dest="task_id",
        help="[REQUIRED]\ninteger\nvalue ranges from 0 to [total number of CPU cores requested via SLURM - 1]\n(default: %(default)s)",
        type=int,
        default=0,
        metavar="<int>",
    )
    parser.add_argument(
        "-g",
        "--genome",
        dest="genome",
        choices=["Mother", "Father", "Child"],
        help="[REQUIRED]\nstring\nsets the genome to use within a Trio\n(default: %(default)s)",
        default="Mother",
    )
    parser.add_argument(
        "-r",
        "--region",
        dest="region",
        help="string\nif None, activate 'demo' mode\nif not None, activate 'region-beam shuffling' mode\n\tNOTE: values range from 1 to the total number of region BED files created\n(default: %(default)s)",
        type=str,
        default=None,
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
        "--dry-run",
        dest="dry_run",
        help="if True, display commands to be used to the screen",
        action="store_true",
    )
    parser.add_argument(
        "--get-help",
        dest="get_help",
        help="if True, display DeepVariant container's 'make_examples' man page to the screen",
        action="store_true",
        default=False,
    )
    return parser.parse_args()
    # return parser.parse_args(["--env-file", "envs/new_trios_test-run0.env", "--debug"])


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
        _version = environ.get("BIN_VERSION_DV")
        logger.debug(f"using DeepVariant version | {_version}")

    if args.dry_run:
        logger.info("[DRY_RUN]: output will display to screen and not write to a file")
    if args.get_help is False:
        assert (
            args.env_file
        ), "Missing --env-file; Please provide a file with environment variables for the current analysis"


@dataclass
class Examples:
    """
    Define what data to keep when creating labeled examples for re-training the DeepVariant model.
    """

    args: argparse.Namespace
    logger: h.Logger
    cow: bool = True
    demo_chromosome: Union[str, int, None] = "29"
    _base_binding: str = field(
        default="/usr/lib/locale/:/usr/lib/locale/", init=False, repr=False
    )
    _bindings: list = field(default_factory=list, init=False, repr=False)
    _phase: str = field(default="make_examples", init=False, repr=False)
    _version: str = field(
        default=str(environ.get("BIN_VERSION_DV")), init=False, repr=False
    )

    def __post_init__(self) -> None:
        self._image = f"deepvariant_{self._version}.sif"
        if self.cow:
            self.CHR = list(map(str, range(1, 30))) + ["X", "Y"]
            self.CHR_Order = {k: v for v, k in enumerate(self.CHR)}
        else:
            self.logger.error("ADD LOGIC FOR HANDELING DIFFERENT CHR NUMBERS")
            exit(1)

    def load_variables(self) -> None:
        """
        Load in variables from the env file, and define python variables.
        """
        self.env = h.Env(self.args.env_file, self.logger, dryrun_mode=self.args.dry_run)
        env_vars = [
            "RunOrder",
            "N_Parts",
            "TotalShards",
            "RefFASTA_Path",
            "RefFASTA_File",
            f"{self.args.genome}ReadsBAM_Path",
            f"{self.args.genome}ReadsBAM_File",
            f"{self.args.genome}TruthVCF_Path",
            f"{self.args.genome}TruthVCF_File",
            f"{self.args.genome}CallableBED_Path",
            f"{self.args.genome}CallableBED_File",
            "ExamplesDir",
        ]

        (
            self._trio_num,
            self._n_parts,
            self._total_shards,
            self._ref_dir,
            self._ref_file,
            self._bam_dir,
            self._bam_file,
            self._truth_dir,
            self._truth_vcf_file,
            self._callable_dir,
            self._callable_file,
            self._examples_dir,
        ) = self.env.load(*env_vars)

    def set_genome(self) -> None:
        """
        Define which genome from a Trio to make examples.
        """
        self._reference = Path(self._ref_dir) / self._ref_file
        self._bam = Path(self._bam_dir) / self._bam_file
        self._truth_vcf = Path(self._truth_dir) / self._truth_vcf_file
        self._callable_bed = Path(self._callable_dir) / self._callable_file
        assert (
            self._reference.exists()
        ), f"Reference Genome FASTA file [{self._reference.name}] does not exist"
        assert self._bam.exists(), f"BAM file [{self._bam.name}] does not exist"
        assert (
            self._truth_vcf.exists()
        ), f"TruthVCF file [{self._truth_vcf.name}] does not exist"
        assert (
            self._callable_bed.exists()
        ), f"CallableBED file [{self._callable_bed.name}] does not exist"

    def process_region(self) -> None:
        """
        Determine if regions-beam shuffling is being performed.
        """
        self._region_bindings = None
        self._regions_flags = None
        self._exclude_flags = None
        self.exclude_chroms = "Y"

        if self.args.region.lower() == "none":
            self.args.region = None

        # run 'make_examples' for the demo chromosome only
        if self.args.region is None or self.args.region.lower() == "demo":
            self._output_prefix = f"{self.args.genome}.chr{self.demo_chromosome}"
            self._mode = "demo"
            self._logger_msg = (
                f"{self.args.genome}{self._trio_num}] - [CHR{self.demo_chromosome}"
            )
            self.logger.info(
                f"[{self._mode}] - [{self._logger_msg}]: examples include Chromosome '{self.demo_chromosome}' only"
            )
            self._regions_flags = ["--regions", self.demo_chromosome]

        # run 'make_examples' using the regions file provided in the 'metadata.csv' file
        elif (
            "RegionsFile_Path" in self.env.contents
            and "RegionsFile_File" in self.env.contents
        ):
            self._exclude_flags = ["--exclude_regions", f"{self.exclude_chroms}"]
            self._output_prefix = f"{self.args.genome}.region_file"
            self._mode = "region_file"
            self._logger_msg = f"{self.args.genome}{self._trio_num}"
            self._regions_dir = self.env.contents["RegionsFile_Path"]
            self._region_file = self.env.contents["RegionsFile_File"]
            if self._regions_dir is not None and self._region_file is not None:
                self._region_file_path = Path(self._regions_dir) / self._region_file
                if not self._region_file_path.exists():
                    self.logger.error(
                        f"[{self._mode}] - [{self._logger_msg}]: beam-shuffling regions file '{self._region_file_path.name}' should already exist and it does not. Exiting... "
                    )
                    exit(1)
                else:
                    self.logger.info(
                        f"[{self._mode}] - [{self._logger_msg}]: env file contains existing variables for both 'RegionsFile_Path' & 'RegionsFile_File'"
                    )
                    self._regions_flags = [
                        "--regions",
                        f"/regions_dir/{self._region_file}",
                    ]
                    self._region_bindings = f"{str(self._regions_dir)}/:/regions_dir/"
                    self.logger.info(
                        f"[{self._mode}] - [{self._logger_msg}]: bindings for Apptainer will now include | {self._region_bindings}"
                    )

        # run 'make_examples' using the regions-shuffling files created by the TrioTrain pipeline
        elif (
            self.args.region is not None
            or isinstance(self.args.region, int)
            or self.args.region.lower() != "demo"
        ):
            self._exclude_flags = ["--exclude_regions", f"{self.exclude_chroms}"]
            self._output_prefix = f"{self.args.genome}.region{self.args.region}"
            self._mode = "regions_shuffling"
            self._logger_msg = (
                f"{self.args.genome}{self._trio_num}] - [region{self.args.region}"
            )
            self.logger.info(
                f"[{self._mode}] - [{self._logger_msg}]: examples include the regions from the Beam-Shuffling BED File(s)"
            )

            self._regions_dir = Path(self._examples_dir) / "regions"
            self._region_file = f"{self.args.genome}-region{self.args.region}.bed"
            self._region_file_path = self._regions_dir / self._region_file
            if not self._region_file_path.exists():
                self.logger.error(
                    f"[{self._mode}] - [{self._logger_msg}]: Beam-Shuffling Regions File '{self._region_file_path.name}' should already exist and it does not. Exiting... "
                )
                exit(1)
            else:
                self.logger.info(
                    f"[{self._mode}] - [{self._logger_msg}]: regions were defined by the genome-wide sampling script 'regions_make.py'"
                )
                self._regions_flags = ["--regions", f"/regions_dir/{self._region_file}"]
                self._region_bindings = f"{str(self._regions_dir)}/:/regions_dir/"
                self.logger.info(
                    f"[{self._mode}] - [{self._logger_msg}]: current region file | '{self._region_file}'"
                )
                self.logger.info(
                    f"[{self._mode}] - [{self._logger_msg}]: bindings for Apptainer will now include | '{self._region_bindings}'"
                )

        # run 'make_examples' for the entire genome
        # NOTE: This will not work as of 2022 Sep 19
        #       because TrioTrain pipeline uses
        #      'direct_runner' & 'in_memory' with
        #       Apache Beam because of challenges
        #       configuring SLURM + Spark +
        #       'spark_runner'
        else:
            self._exclude_flags = ["--exclude_regions", f"{self.exclude_chroms}"]
            self._output_prefix = self.args.genome
            self._mode = "genome_wide_shuffling"
            self._logger_msg = self.args.genome

            if "RegionsFile_Path" not in self.env.contents:
                missing_var1 = True
                self.logger.info(
                    f"[{self._mode}] - [{self._logger_msg}]: env file is missing 'RegionsFile_Path'"
                )
            else:
                missing_var1 = False

            if "RegionsFile_File" not in self.env.contents:
                missing_var2 = True
                self.logger.info(
                    f"[{self._mode}] - [{self._logger_msg}]: env file is missing 'RegionsFile_File'"
                )
            else:
                missing_var2 = False

            if "RegionsFile" not in self.env.contents:
                missing_var3 = True
                self.logger.info(
                    f"[{self._mode}] - [{self._logger_msg}]: env file is missing 'RegionsFile'"
                )
            else:
                missing_var3 = False

            if self.args.region not in self.CHR:
                missing_var4 = True
                self.logger.info(
                    f"[{self._mode}] - [{self._logger_msg}]: a valid region was not provided via command line arguments"
                )
            else:
                missing_var4 = False

            if missing_var1 and missing_var2 and missing_var3 and missing_var4:
                self.logger.info(
                    f"[{self._mode}] - [{self._logger_msg}]: missing at least one of the required options. Exiting... "
                )
                exit(1)
            else:
                self.logger.warning(
                    f"[{self._mode}] - [{self._logger_msg}]: genome-wide sub-regions for shuffling were not created"
                )
                self.logger.warning(
                    f"[{self._mode}] - [{self._logger_msg}]: making examples  genome-wide!"
                )
                self.logger.error(
                    "ADD LOGIC TO HANDLE BEAM SHUFFLING THE ENTIRE GENOME IN MEMORY?"
                )
                exit(1)

    def process_pop_vcf(self) -> None:
        """
        Determine if allele frequency channel should be added to the example tensor vector images.
        """
        self._popvcf_bindings = None
        self._popvcf_flags = None
        if "PopVCF_Path" in self.env.contents and "PopVCF_File" in self.env.contents:
            self._mode = "withPopVCF"
            self._popvcf_dir = self.env.contents["PopVCF_Path"]
            self._popvcf_file = self.env.contents["PopVCF_File"]
            if self._popvcf_dir is not None and self._popvcf_file is not None:
                self._pop_vcf_file_path = Path(self._popvcf_dir) / self._popvcf_file
                if not self._pop_vcf_file_path.exists():
                    self.logger.error(
                        f"[{self._mode}] - [{self._logger_msg}]: PopVCF file '{self._pop_vcf_file_path.name}' should already exist and it does not. Exiting... "
                    )
                    exit(1)
                else:
                    self.logger.info(
                        f"[{self._mode}] - [{self._logger_msg}]: adding the allele frequency channel to examples tensor vectors"
                    )
                    self._popvcf_flags = [
                        "--use_allele_frequency=true",
                        "--population_vcfs",
                        f"/popVCF_dir/{self._popvcf_file}",
                    ]
                    self._popvcf_bindings = f"{str(self._popvcf_dir)}/:/popVCF_dir/"
                    self.logger.info(
                        f"[{self._mode}] - [{self._logger_msg}]: bindings for Apptainer will now include | {self._popvcf_bindings}"
                    )
        else:
            self._mode = "noPopVCF"
            if "PopVCF" not in self.env.contents:
                if (
                    "PopVCF_Path" not in self.env.contents
                    or "PopVCF_File" not in self.env.contents
                ):
                    self.logger.warning(
                        f"[{self._mode}] - [{self._logger_msg}]: env file is missing 'PopVCF' or 'PopVCF_Path' & 'PopVCF_File'"
                    )
                    self.logger.warning(
                        f"[{self._mode}] - [{self._logger_msg}]: env file was not made correctly. Exiting... "
                    )
                    exit(1)
            else:
                self.logger.info(
                    f"[{self._mode}] - [{self._logger_msg}]: the allele frequency channel will not be added to examples tensor vectors"
                )

    def build_bindings(self) -> None:
        """
        Build the Apptainer Bindings using Path variables.
        """
        self._ref_binding = f"{self._ref_dir}/:/ref_dir/"
        self._bam_binding = f"{self._bam_dir}/:/bam_dir/"
        self._truth_binding = f"{self._truth_dir}/:/vcf_dir/"
        self._callable_binding = f"{self._callable_dir}/:/bed_dir/"
        self._examples_binding = f"{self._examples_dir}/:/examples_dir/"

        self._bindings = [
            self._base_binding,
            self._ref_binding,
            self._bam_binding,
            self._truth_binding,
            self._callable_binding,
            self._examples_binding,
        ]

        if self._region_bindings is not None:
            self._bindings.append(self._region_bindings)

        if self._popvcf_bindings is not None:
            self._bindings.append(self._popvcf_bindings)

        self.logger.info(
            f"[{self._mode}] - [{self._logger_msg}] - [{self._phase}]: using the following existing inputs\n\tREFERENCE_GENOME='{str(self._reference)}'\n\tBAM_FILE='{str(self._bam)}'\n\tTRUTH_FILE='{str(self._truth_vcf)}'\n\tCALLABLE_REGIONS='{str(self._callable_bed)}'\n\tEXAMPLES='{str(self._examples_dir)}/{self._output_prefix}.labeled.tfrecords@${self._n_parts}.gz'"
        )

    def build_command(self) -> None:
        """
        Build the Singularity-Python 'Exectute' Command using File variables.
        """
        # --channels: Comma-delimited list of optional channels to add. Available
        #             channels: read_mapping_percent,avg_base_quality,identity,
        #                       gap_compressed_identity,gc_content,is_homopolymer,
        #                       homopolymer_weighted,blank,insert_size
        self._command = [
            "/opt/deepvariant/bin/make_examples",
            "--mode",
            "training",
            "--ref",
            f"/ref_dir/{self._ref_file}",
            "--reads",
            f"/bam_dir/{self._bam_file}",
            "--examples",
            f"/examples_dir/{self._output_prefix}.labeled.tfrecords@{self._n_parts}.gz",
            "--truth_variants",
            f"/vcf_dir/{self._truth_vcf_file}",
            "--confident_regions",
            f"/bed_dir/{self._callable_file}",
            "--task",
            f"{self.args.task_id}",
            "--channels",
            "insert_size",
        ]

        if self._regions_flags is not None:
            for flag in self._regions_flags:
                self._command.append(flag)

        if self._popvcf_flags is not None:
            for flag in self._popvcf_flags:
                self._command.append(flag)

        if self._exclude_flags is not None:
            for flag in self._exclude_flags:
                self._command.append(flag)
            self.logger.info(
                f"[{self._phase}] - [{self._logger_msg}]: excluding Chromosome '{self.exclude_chroms}' examples"
            )

        command_str = "\n".join(self._command)
        self.logger.info(
            f"[{self._phase}] - [{self._logger_msg}]: Apptainer command used | \n{command_str}"
        )

    def get_help(self) -> None:
        """
        Disply the help page for make_examples within the container used.
        """
        get_help = Client.execute(  # type: ignore
            self._image,
            ["/opt/deepvariant/bin/make_examples", "--helpfull"],
            bind=[self._base_binding],
        )
        print(get_help["message"][0])

    def execute_command(self) -> None:
        """
        Execute a command within a Apptainer Container.
        """
        print(
            f"----- Starting Making Examples for {self._output_prefix} via Apptainer Container -----"
        )
        run_make_examples = Client.execute(  # type: ignore
            self._image,
            self._command,
            bind=self._bindings,
        )
        if isinstance(run_make_examples, dict):
            msg = run_make_examples["message"]
            status = run_make_examples["return_code"]
            print(msg)
            self.logger.info(
                f"[{self._mode}] - [{self._logger_msg}] - [{self._phase}]: Apptainer Command Return Code | {status}"
            )
            if status != 0:
                self.logger.info(
                    f"[{self._mode}] - [{self._logger_msg}] - [{self._phase}]: Apptainer Command Failed.\nExiting..."
                )
                exit(1)
        else:
            print(run_make_examples)
        print(
            f"----- End Making Examples for {self._output_prefix} via Apptainer Container -----"
        )

    def run(self) -> None:
        """
        Combine all the steps required to create labeled examples into one step.
        """
        if self.args.get_help is False:
            self.load_variables()
            self.set_genome()
            self.process_region()
            self.process_pop_vcf()
            self.build_bindings()
            self.build_command()
            self.execute_command()
        else:
            self.get_help()


def __init__():
    """
    Final function to make_examples within a SLURM job
    """
    # Collect command line arguments
    args = collect_args()

    # Collect start time
    h.Wrapper(__file__, "start").wrap_script(h.timestamp())

    # Create error log
    current_file = path.basename(__file__)
    module_name = path.splitext(current_file)[0]
    logger = helpers_logger.get_logger(module_name)

    # Check command line args
    check_args(args, logger)
    Examples(args, logger).run()

    # Collect start time
    h.Wrapper(__file__, "end").wrap_script(h.timestamp())


# Execute functions created
if __name__ == "__main__":
    __init__()
