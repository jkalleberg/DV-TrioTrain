# #!/bin/python3
"""
description: tests a selected model checkpoint by calling variants with independent genomes.

example:
    python3 triotrain/model_training/slurm/call_variants.py           \\
        --env-file envs/demo.env                              \\
        --dry-run
"""
import argparse
from dataclasses import dataclass, field
from logging import Logger
from os import environ, path, sched_getaffinity
from pathlib import Path
from typing import Union

from spython.main import Client




def collect_args() -> argparse.Namespace:
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
        "-g",
        "--train-genome",
        dest="train_genome",
        choices=["Mother", "Father", "None"],
        help="string\nsets the genome to use within a Trio\n(default: %(default)s)",
        default=None,
    )
    parser.add_argument(
        "-t",
        "--test-num",
        dest="test_num",
        help="integer\nvalue ranges from 1 to total number of test genomes in 'metadata.csv'\n(default: %(default)s)",
        type=int,
        default=0,
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
        help="if True, display commands to the screen",
        action="store_true",
    )
    parser.add_argument(
        "--get-help",
        dest="get_help",
        help="if True, display DV 'run_deepvariant' man page to the screen",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--use-gpu",
        dest="use_gpu",
        help=f"if True, use the GPU container to accelerate re-training\n\tNOTE: requires running with GPU partition/resources from SLURM\nif False, use the CPU container\n(default: %(default)s)",
        default=False,
        action="store_true",
    )

    customize = parser.add_argument_group("call variants with custom model weights")
    customize.add_argument(
        "--use-custom-model",
        dest="use_custom_model",
        help="if True, call variants will use non-default model weights\n(default: %(default)s)",
        action="store_true",
        default=False,
    )
    customize.add_argument(
        "--custom-checkpoint",
        dest="custom_ckpt",
        help="input file (model.ckpt)\n[REQUIRED] with '--use-custom-model'\nprovides model weights to use when calling variants",
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

    if args.use_custom_model:
        assert (
            args.custom_ckpt
        ), "Missing --custom-checkpoint; Please provide a file model weights to initialize re-training"


@dataclass
class TestModel:
    """
    define what data to keep when testing the re-trained DeepVariant model
    """

    args: argparse.Namespace
    logger: Logger
    demo_chromosome: Union[str, int, None] = "29"
    _phase: str = field(default="testing_model", init=False, repr=False)
    _base_binding: str = field(
        default="/usr/lib/locale/:/usr/lib/locale/", init=False, repr=False
    )
    _version: str = field(
        default=str(environ.get("BIN_VERSION_DV")), init=False, repr=False
    )
    _hostname: str = field(default=str(environ.get("hostname")), init=False, repr=False)
    _bindings: list = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        self.logger.info(f"Using node | {self._hostname}")
        if self.args.use_gpu:
            self._image = f"deepvariant_{self._version}-gpu.sif"
            self.logger.warning(f"Using the GPU container | {self._image}")
        else:
            self._image = f"deepvariant_{self._version}.sif"
            self.logger.info(f"Using the CPU container | {self._image}")

        # identify the num processors available via slurm
        task_ids = sched_getaffinity(0)
        self._nproc = len(task_ids)

    def load_variables(self) -> None:
        """
        load in variables from the env file, and define python variables
        """
        self.env = Env(self.args.env_file, self.logger, dryrun_mode=self.args.dry_run)

        if "N_Parts" not in self.env.contents:
            self._n_shards = self._nproc
            self.env.add_to("N_Parts", str(self._nproc), dryrun_mode=self.args.dry_run)
        else:
            self._n_shards = self.env.contents["N_Parts"]

        env_vars = [
            "RunOrder",
            "CodePath",
            "CodePath",
            "RefFASTA_Path",
            "RefFASTA_File",
            f"Test{self.args.test_num}ReadsBAM_Path",
            f"Test{self.args.test_num}ReadsBAM_File",
        ]

        if self.args.train_genome == "None":
            self.args.train_genome = None
            extra_vars = ["BaselineModelResultsDir"]
        else:
            extra_vars = [f"{self.args.train_genome}TestDir"]

        vars = env_vars + extra_vars

        (
            self._trio_num,
            self._code_path,
            self._code_path,
            self._ref_dir,
            self._ref_file,
            self._bam_dir,
            self._bam_file,
            self._output_dir,
        ) = self.env.load(*vars)

    def set_genome(self) -> None:
        """
        define which genome from a Trio to make examples for
        """
        if self.args.train_genome is None:
            self.model_label = "default_model"
            self.output_name = f"test{self.args.test_num}"
            self._logger_msg = (
                f"{self._phase}] - [v{self._version}] - [test{self.args.test_num}"
            )
        else:
            self.model_label = f"{self.args.genome}{self._trio_num}"
            self.output_name = f"test{self.args.test_num}-{self.args.genome}"
            self._logger_msg = (
                f"{self._phase}] - [{self.args.genome}] - [test{self.args.test_num}"
            )

        self._reference = Path(self._ref_dir) / self._ref_file
        self._bam = Path(self._bam_dir) / self._bam_file

        assert (
            self._reference.exists()
        ), f"Reference Genome FASTA file [{self._reference.name}] does not exist"

        assert self._bam.exists(), f"BAM file [{self._bam.name}] does not exist"

        self._output_dir = Path(self._output_dir)
        assert (
            self._output_dir.is_dir()
        ), f"Output Directory [{self._output_dir}] does not exist"

        self.logger.info(
            f"[{self._logger_msg}]: saving call variants output(s) here: '{str(self._output_dir)}'"
        )

    def set_ckpt(self) -> None:
        """
        define which model weights to use
        """
        if self.args.use_custom_model:
            self._checkpoint = Path(self.args.custom_ckpt)
            assert (
                self._checkpoint.exists()
            ), f"Custom checkpoint file [{self._checkpoint.name}] does not exist"

            self._ckpt_path = self._checkpoint.parent
            self._ckpt_file = self._checkpoint.name
            self._ckpt_bindings = f"{self._ckpt_path}/:/start_dir/"
            self._custom_flags = [
                "--customized_model",
                f"/start_dir/{self._ckpt_file}",
            ]
            self.logger.info(
                f"[{self._logger_msg}]: Using Custom Model Checkpoint to Call Variants | {str(self._checkpoint)}"
            )
        else:
            self._custom_flags = None
            self._ckpt_bindings = None
            self.logger.info(
                f"[{self._logger_msg}]: Using Default Human Checkpoint to Call Variants | v{self._version}"
            )

    def process_region(self) -> None:
        """
        determine if regions-Beam shuffling is being performed
        """
        self._region_bindings = None
        self._regions_flags = None
        self._exclude_flags = None
        self.exclude_chroms = "Y"

        if (
            "RegionsFile_Path" in self.env.contents
            and "RegionsFile_File" in self.env.contents
        ):
            self._exclude_flags = ["--exclude_regions", f"{self.exclude_chroms}"]
            self._output_prefix = f"{self.args.genome}.region_file"
            self._mode = "region_file"
            self._logger_msg = self.args.genome
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

            # if self.args.region not in self.CHR:
            #     missing_var4 = True
            #     self.logger.info(
            #         f"[{self._mode}] - [{self._logger_msg}]: a valid region was not provided via command line arguments"
            #     )

    def process_pop_vcf(self) -> None:
        """
        determine if allele frequency channel should be added to the example tensor vector images
        """
        self._popvcf_bindings = None
        self._popvcf_flags = None
        if "PopVCF_Path" in self.env.contents and "PopVCF_File" in self.env.contents:
            self._mode = "popvcf_file"
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
                        "--make_examples_extra_args",
                        f"use_allele_frequency=true,population_vcfs=/popVCF_dir/{self._popvcf_file}",
                    ]
                    self._popvcf_bindings = f"{str(self._popvcf_dir)}/:/popVCF_dir/"
                    self.logger.info(
                        f"[{self._mode}] - [{self._logger_msg}]: bindings for Apptainer will now include | {self._popvcf_bindings}"
                    )
        else:
            if "PopVCF" not in self.env.contents:
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
        build the Apptainer Bindings using Path variables
        """
        self._cwd_binding = f"{self._code_path}/:/run_dir/"
        self._ref_binding = f"{self._ref_dir}/:/ref_dir/"
        self._bam_binding = f"{self._bam_dir}/:/bam_dir/"
        self._out_binding = f"{self._output_dir}/:/out_dir/"

        self._bindings = [
            self._base_binding,
            self._cwd_binding,
            self._ref_binding,
            self._bam_binding,
            self._out_binding,
        ]

        if self._ckpt_bindings is not None:
            self._bindings.append(self._ckpt_bindings)

        if self._region_bindings is not None:
            self._bindings.append(self._region_bindings)

        if self._popvcf_bindings is not None:
            self._bindings.append(self._popvcf_bindings)

        bindings_str = ",".join(self._bindings)

        self.logger.info(
            f"[{self._logger_msg}]: Using the following paths for Apptainer bindings | {bindings_str}"
        )

    def build_command(self) -> None:
        """
        build the Singularity-Python 'Exectute' Command using Variables
        """
        self._command = [
            "/opt/deepvariant/bin/run_deepvariant",
            "--model_type",
            "WGS",
            "--ref",
            f"/ref_dir/{self._ref_file}",
            "--reads",
            f"/bam_dir/{self._bam_file}",
            "--output_vcf",
            f"/out_dir/{self.output_name}.vcf.gz",
            "--intermediate_results_dir",
            f"/out_dir/tmp/{self.output_name}/",
            "--num_shards",
            f"{self._n_shards}",
        ]

        if self._custom_flags is not None:
            for flag in self._custom_flags:
                self._command.append(flag)

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
                f"[{self._logger_msg}]: excluding Chromosome '{self.exclude_chroms} examples"
            )

        command_str = "\n".join(self._command)
        self.logger.info(f"[{self._logger_msg}]: Command Used | \n{command_str}")

    def get_help(self) -> None:
        """
        disply the help page for the program within the container used (make_examples)
        """
        get_help = Client.execute(  # type: ignore
            self._image,
            ["/opt/deepvariant/bin/run_deepvariant", "--helpfull"],
            bind=[self._base_binding],
        )
        print(get_help["message"][0])

    def execute_command(self) -> None:
        """
        execute a command to the Apptainer Container
        """
        print(
            f"----- Starting run-deepvariant with {self.model_label} for {self.output_name} via Apptainer Container -----"
        )
        run_deepvariant = Client.execute(  # type: ignore
            self._image,
            self._command,
            bind=self._bindings,
        )

        if isinstance(run_deepvariant, dict):
            print(run_deepvariant["message"][0])
            self.command_worked = False
        else:
            self.command_worked = True
            print(run_deepvariant)

        print(
            f"----- End run-deepvariant with {self.model_label} for {self.output_name} via Apptainer Container -----"
        )

    def run(self) -> None:
        """
        combine all the steps required to create labeled examples into one step
        """
        if self.args.get_help is False:
            self.load_variables()
            self.set_genome()
            self.set_ckpt()
            self.process_region()
            self.process_pop_vcf()
            self.build_bindings()
            self.build_command()
            self.execute_command()
        else:
            self.get_help()


def __init__() -> None:
    """
    Final function to call_variants within a SLURM job
    """
    from helpers.utils import get_logger
    from helpers.wrapper import Wrapper, timestamp

    # Collect command line arguments
    args = collect_args()

    # Collect start time
    Wrapper(__file__, "start").wrap_script(timestamp())

    # Create error log
    current_file = path.basename(__file__)
    module_name = path.splitext(current_file)[0]
    logger = get_logger(module_name)

    # Check command line args
    check_args(args, logger)
    TestModel(args, logger).run()

    # Collect start time
    Wrapper(__file__, "end").wrap_script(timestamp())


# Execute functions created
if __name__ == "__main__":
    __init__()
