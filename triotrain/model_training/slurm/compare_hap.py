#!/bin/python3
"""
description: compares a VCF produced by DeepVariant against a Truth VCF produced by GATK v4. Uses the spython package to execute commmands within the hap.py container.

example:
    python3 triotrain/model_training/slurm/compare_hap.py           \\
        --env-file envs/demo.env                            \\
        --dry-run
"""
import argparse
from dataclasses import dataclass, field
from logging import Logger
from os import environ
from os import path as p
from pathlib import Path
from sys import exit, path

from spython.main import Client

abs_path = Path(__file__).resolve()
module_path = str(abs_path.parent.parent.parent)
path.append(module_path)
from helpers.environment import Env
from helpers.wrapper import timestamp


def collect_args() -> argparse.Namespace:
    """
    Process command line argument to execute script.
    """
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--benchmark",
        dest="benchmark_mode",
        help="if True, search for files where GIAB benchmarking results exist",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "-e",
        "--env-file",
        dest="env_file",
        help="[REQUIRED]\ninput file (.env)\nprovides environment variables",
        type=str,
        metavar="</path/file>",
    )
    # ENSURE THAT METRICS DO NOT INCLUDE THE Y CHROM
    parser.add_argument(
        "--regions-file",
        dest="regions_file",
        help="[REQUIRED]\ninput file (.BED)\ndefines the genomic regions to use for comparision between TRUTH & QUERY\n(default: %(default)s)",
        type=str,
        default=None,
        metavar="</path/file>",
    )
    parser.add_argument(
        "-g",
        "--train-genome",
        dest="train_genome",
        choices=["Mother", "Father", "None"],
        help="sets the genome to use within a Trio\n(default: %(default)s)",
        default="None",
    )
    parser.add_argument(
        "-t",
        "--test-num",
        dest="test_num",
        help="sets a QUERY test genome number to compare against a TRUTH vcf\n(default: %(default)s)",
        type=int,
        default=1,
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
        "--demo",
        dest="demo_mode",
        help="if True, compare only a subset of the entire genome",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        help="if True, display total hap.py metrics to the screen",
        action="store_true",
    )
    parser.add_argument(
        "--happy-help",
        dest="happy_help",
        help="if True, display container's hap.py man page to the screen",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-l",
        "--location",
        dest="location",
        help="a comma-separated list of genomic regions\n[REQUIRED] with '--demo'\nmust match the format in the reference genome\ndefines a subset of the QUERY genome to comare against a TRUTH vcf\n(default: %(default)s)",
        type=str,
        default="29",
        metavar="<#,#,#>",
    )
    parser.add_argument(
        "-o",
        "--overwrite",
        dest="overwrite",
        help="if True, enable replacing existing pngs files\n(default: %(default)s)",
        default=False,
        action="store_true",
    )
    return parser.parse_args()
    # return parser.parse_args(["--env-file", "envs/new_trios_test-run0.env", "--debug"])


def check_args(args: argparse.Namespace, logger: Logger) -> None:
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

    if args.happy_help is False:
        assert (
            args.env_file
        ), "Missing --env-file; Please provide a file with environment variables for the current analysis"
        if args.demo_mode is False:
            assert (
                args.regions_file
            ), "Missing --regions-file; Please provide a BED file to use as default genomic regions to compare"
        else:
            assert (
                args.location
            ), "Missing --location; Please provide a comma-separated list of valid positions in the genome to compare."


@dataclass
class Happy:
    """
    Define what data to keep when comparing a query vcf against a truth vcf using hap.py
    """

    args: argparse.Namespace
    logger: Logger
    image_name: str = "hap.py_v0.3.12"
    _base_binding: str = field(
        default="/usr/lib/locale/:/usr/lib/locale/", init=False, repr=False
    )
    _bindings: list = field(default_factory=list, init=False, repr=False)
    _phase: str = field(default="compare_happy", init=False, repr=False)
    _version: str = field(
        default=str(environ.get("BIN_VERSION_DV")), init=False, repr=False
    )

    def __post_init__(self) -> None:
        self._image = f"{self.image_name}.sif"
        if self.args.train_genome == "None":
            self.args.train_genome = None

    def load_variables(self) -> None:
        """
        Load in variables from the env file, and define python variables.
        """
        self.env = Env(self.args.env_file, self.logger, dryrun_mode=self.args.dry_run, debug_mode=self.args.debug)
        env_vars = [
            "RunOrder",
            "N_Parts",
            "RefFASTA_Path",
            "RefFASTA_File",
            f"Test{self.args.test_num}TruthVCF_Path",
            f"Test{self.args.test_num}TruthVCF_File",
            f"Test{self.args.test_num}CallableBED_Path",
            f"Test{self.args.test_num}CallableBED_File",
        ]

        (
            self._trio_num,
            self._n_proc,
            self._ref_dir,
            self._ref_file,
            self._truth_dir,
            self._truth_vcf_file,
            self._callable_dir,
            self._callable_file,
        ) = self.env.load(*env_vars)

        if self.args.demo_mode:
            self._test_dir = str(self.env.contents[f"{self.args.train_genome}TestDir"])
            self._out_dir = str(
                self.env.contents[f"{self.args.train_genome}CompareDir"]
            )
            self._query_vcf_name = (
                f"test{self.args.test_num}_chr{self.args.location}.vcf.gz"
            )
            self._mode = "demo"
            self._logger_msg = f"v{self._version}] - [test{self.args.test_num}"
        elif self.args.benchmark_mode:
            self._test_dir = str(self.env.contents["RunDir"])
            self._out_dir = str(self.env.contents["RunDir"])
            self._query_vcf_name = f"test{self.args.test_num}.vcf.gz"
            self._mode = "Benchmark"
            self._logger_msg = f"v{self._version}] - [test{self.args.test_num}"
        elif self.args.train_genome is None:
            self._test_dir = str(self.env.contents["BaselineModelResultsDir"])
            self._out_dir = str(self.env.contents["BaselineModelResultsDir"])
            self._query_vcf_name = f"test{self.args.test_num}.vcf.gz"
            self._mode = "baseline"
            self._logger_msg = f"v{self._version}] - [test{self.args.test_num}"
        else:
            self._test_dir = str(self.env.contents[f"{self.args.train_genome}TestDir"])
            self._out_dir = str(
                self.env.contents[f"{self.args.train_genome}CompareDir"]
            )
            self._query_vcf_name = (
                f"test{self.args.test_num}-{self.args.train_genome}.vcf.gz"
            )
            self._mode = "custom model"
            self._logger_msg = (
                f"{self.args.train_genome}{self._trio_num}] - [test{self.args.test_num}"
            )

    def filter_regions(self) -> None:
        """
        Define which regions to include in model_testing, using the default regions file created by the pipeline.

        NOTE: this should be the autosomes + X chromosome only.
        """
        if self.args.regions_file is not None:
            self.default_regions_path = Path(self.args.regions_file)

            if self.default_regions_path.exists():
                self._default_regions_bindings = (
                    f"{str(self.default_regions_path.parent)}/:/default_region_dir/"
                )
                self._default_regions_file = str(self.default_regions_path.name)
            else:
                self.logger.error(
                    f"[{self._mode}] - [{self._phase}] - [{self._logger_msg}]: default regions file must be an existing file [{str(self.default_regions_path)}]. Exiting... "
                )
                exit(1)

    def set_test_genome(self) -> None:
        """
        Define which test genome number to compare with hap.py.
        """
        self._reference = Path(self._ref_dir) / self._ref_file
        self._truth_vcf = Path(self._truth_dir) / self._truth_vcf_file
        self._query_vcf = Path(self._test_dir) / self._query_vcf_name
        self._callable_bed = Path(self._callable_dir) / self._callable_file
        assert (
            self._reference.exists()
        ), f"Reference Genome FASTA file [{str(self._reference)}] does not exist"
        assert (
            self._truth_vcf.exists()
        ), f"TruthVCF file [{str(self._truth_vcf)}] does not exist"
        assert (
            self._query_vcf.exists()
        ), f"QueryVCF file [{str(self._query_vcf)}] does not exist"
        assert (
            self._callable_bed.exists()
        ), f"CallableBED file [{str(self._callable_bed)}] does not exist"

        if self.args.demo_mode:
            self._output_prefix = (
                f"happy{self.args.test_num}-no-flags-chr{self.args.location}"
            )
        else:
            self._output_prefix = f"happy{self.args.test_num}-no-flags"
        self._output = Path(self._out_dir) / self._output_prefix

        self._scratch_dir = Path(self._out_dir) / "scratch"

        if self._scratch_dir.is_dir():
            if self.args.debug:
                self.logger.debug(
                    f"[{self._mode}] - [{self._phase}] - [{self._logger_msg}]: directory found '{self._scratch_dir}'"
                )
        else:
            self._scratch_dir.mkdir()
            if self._scratch_dir.is_dir():
                self.logger.info(
                    f"[{self._mode}] - [{self._phase}] - [{self._logger_msg}]: created a new directory - [{self._scratch_dir}]"
                )

    def build_bindings(self) -> None:
        """
        Build the Apptainer Bindings using Path variables.
        """
        self._truth_binding = f"{self._truth_dir}/:/truth/"
        self._query_binding = f"{self._test_dir}/:/query/"
        self._ref_binding = f"{self._ref_dir}/:/ref/"
        self._callable_binding = f"{self._callable_dir}/:/callable/"
        self._output_binding = f"{self._out_dir}/:/output/"

        if self.args.demo_mode:
            self._bindings = [
                self._base_binding,
                self._truth_binding,
                self._query_binding,
                self._ref_binding,
                self._callable_binding,
                self._output_binding,
            ]
            self.logger.info(
                f"[{self._mode}] - [{self._phase}] - [{self._logger_msg}]: Using the following existing hap.py inputs\n\tTRUTH_FILE='{str(self._truth_vcf)}'\n\tCALLABLE_REGIONS='{str(self._callable_bed)}'\n\tTEST_FILE='{str(self._query_vcf)}'\n\tREFERENCE_GENOME='{str(self._reference)}'\n\tOUTPUT_PREFIX='{str(self._output)}'"
            )
        else:
            self._bindings = [
                self._base_binding,
                self._truth_binding,
                self._query_binding,
                self._ref_binding,
                self._callable_binding,
                self._output_binding,
                self._default_regions_bindings,
            ]

            self.logger.info(
                f"[{self._mode}] - [{self._phase}] - [{self._logger_msg}]: Using the following existing hap.py inputs\n\tTRUTH_FILE='{str(self._truth_vcf)}'\n\tCALLABLE_REGIONS='{str(self._callable_bed)}'\n\tDEFAULT_REGIONS='{str(self.default_regions_path)}'\n\tTEST_FILE='{str(self._query_vcf)}'\n\tREFERENCE_GENOME='{str(self._reference)}'\n\tOUTPUT_PREFIX='{str(self._output)}'"
            )

        self.logger.info(f"Bindings Include:")
        for b in self._bindings:
            print(b)

    def build_command(self) -> None:
        """
        Build the Apptainer 'Exectute' Command using variables.
        """
        if self.args.demo_mode:
            self._command = [
                "/opt/hap.py/bin/hap.py",
                f"/truth/{self._truth_vcf_file}",
                f"/query/{self._query_vcf_name}",
                "-r",
                f"/ref/{self._ref_file}",
                "-f",
                f"/callable/{self._callable_file}",
                "-o",
                f"/output/{self._output_prefix}",
                "--write-counts",
                # "--output-vtc",  # test to see what this does?
                "--keep-scratch",
                "--scratch-prefix",
                "/output/scratch",
                "--engine",
                "vcfeval",
                "--threads",
                self._n_proc,
                "--location",
                f"{self.args.location}",
            ]

        else:
            self._command = [
                "/opt/hap.py/bin/hap.py",
                f"/truth/{self._truth_vcf_file}",
                f"/query/{self._query_vcf_name}",
                "-r",
                f"/ref/{self._ref_file}",
                "-f",
                f"/callable/{self._callable_file}",
                "-o",
                f"/output/{self._output_prefix}",
                "--write-counts",
                # "--output-vtc",  # test to see what this does?
                "--keep-scratch",
                "--scratch-prefix",
                "/output/scratch",
                "--engine",
                "vcfeval",
                "--threads",
                self._n_proc,
                "--target-regions",
                f"/default_region_dir/{self._default_regions_file}",
            ]

        command_str = "\n".join(self._command)
        if self.args.debug:
            self.logger.debug(
                f"[{self._mode}] - [{self._phase}] - [{self._logger_msg}]: command | '{command_str}'"
            )

    def happy_help(self) -> None:
        """
        Get the help page for hap.py within the container used
        """
        for line in Client.execute(  # type: ignore
            self._image,
            ["/opt/hap.py/bin/hap.py", "--help"],
            bind=[self._base_binding],
            stream=True,
        ):
            print(line, end="")

    def run(self) -> None:
        """
        Combine all the steps required to compare a TRUTH + QUERY vcfs with hap.py into one step.
        """
        if self.args.happy_help is False:
            self.load_variables()
            if not self.args.demo_mode:
                self.filter_regions()
            self.set_test_genome()
            if self._output.exists():
                if self.args.overwrite:
                    self.logger.warning(
                        f"[{self._mode}] - [{self._phase}] - [{self._logger_msg}]: overwriting results from running hap.py"
                    )
                    pass
                else:
                    self.logger.warning(
                        f"[{self._mode}] - [{self._phase}] - [{self._logger_msg}]: results from running hap.py with prefix [{self._output_prefix}] already exist"
                    )
                    self.logger.warning(
                        f"[{self._mode}] - [{self._phase}] - [{self._logger_msg}]: please specify a unique file prefix, or enable overwritting existing files by including the --overwrite flag"
                    )
                    return
            self.build_bindings()
            self.build_command()
            print(f"----- Starting hap.py now @ {timestamp()} -----")
            self.logger.info(
                f"[{self._mode}] - [{self._phase}] - [{self._logger_msg}]: command |"
            )
            for line in Client.execute(  # type: ignore
                self._image,
                self._command,
                bind=self._bindings,
                stream=True,
                quiet=False,
            ):
                print(line, end="")
            print(f"----- End of hap.py @ {timestamp()} -----")
        else:
            self.happy_help()


def __init__() -> None:
    """
    Final function to compare_happy within a SLURM job
    """
    from helpers.utils import get_logger
    from helpers.wrapper import Wrapper

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
    Happy(args, logger).run()

    # Collect start time
    Wrapper(__file__, "end").wrap_script(timestamp())


# Execute functions created
if __name__ == "__main__":
    __init__()
