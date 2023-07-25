#!/bin/python3
"""
description: call variants outside the TrioTrain pipeline with a DeepVariant model 

example:
    python3 scripts/variant_calling/callDV.py               \\
    --metadata metadata/230108_variant_calling.csv          \\
    --resources resource_configs/230108_resources_used.json \\
    --dry-run

"""
import argparse
from csv import DictReader
from dataclasses import dataclass, field
from json import load
from logging import Logger
from os import environ, getcwd
from os import path as p
from pathlib import Path
from sys import exit, path
from typing import List, Union

from spython.main import Client

abs_path = Path(__file__).resolve()
module_path = str(abs_path.parent.parent.parent)
path.append(module_path)
from helpers.files import TestFile
from helpers.iteration import Iteration
from helpers.utils import generate_job_id
from model_training.slurm.sbatch import SBATCH, SubmitSBATCH


def collect_args() -> argparse.Namespace:
    """
    Process command line argument to execute script.
    """
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-M",
        "--metadata",
        dest="metadata",
        type=str,
        help="[REQUIRED]\ninput file (.csv)\ndescribes each sample to produce VCFs",
        metavar="</path/file>",
    )
    parser.add_argument(
        "-r",
        "--resources",
        dest="resource_config",
        help="[REQUIRED]\ninput file (.json)\ndefines HPC cluster resources for SLURM",
        type=str,
        metavar="</path/file>",
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
        help="if True, display, commands to the screen",
        action="store_true",
    )
    parser.add_argument(
        "--get-help",
        dest="get_help",
        help="if True, display DV 'run_deepvariant' man page to the screen",
        action="store_true",
        default=False,
    )
    return parser.parse_args()


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

    if args.get_help is False:
        assert (
            args.metadata
        ), "Missing --metadata; Please provide the path to variant calling run parameters in CSV format"
        assert (
            args.resource_config
        ), "Missing --resources; Please designate a path to pipeline compute resources in JSON format"


@dataclass
class VariantCaller:
    """
    Define what data to keep when generating VCF summary stats
    """

    # required variables
    args: argparse.Namespace
    logger: Logger

    # optional variables
    use_gpu: bool = False
    overwrite: bool = False

    # imutable, interal variables
    _reads_path: Union[Path, None] = None
    _reads_name: Union[str, None] = None
    _base_binding: str = field(
        default="/usr/lib/locale/:/usr/lib/locale/", init=False, repr=False
    )
    _ckpt_path: Union[Path, None] = None
    _ckpt_name: Union[str, None] = None
    _job_nums: Union[List[Union[str, None]], None] = field(
        default_factory=list, repr=False, init=False
    )
    _output_path: Union[Path, None] = None
    _output_name: Union[str, None] = None
    _phase: str = "call_variants"
    _pop_path: Union[Path, None] = None
    _pop_name: Union[str, None] = None
    _ref_path: Union[Path, None] = None
    _ref_name: Union[str, None] = None
    _region_path: Union[Path, None] = None
    _skipped_counter: int = 0
    _region_name: Union[str, None] = None
    _version: str = field(
        default=str(environ.get("BIN_VERSION_DV")), init=False, repr=False
    )

    def __post_init__(self) -> None:
        if not self.args.get_help:
            self._metadata_input = Path(self.args.metadata)
            self._resource_input = Path(self.args.resource_config)
        self._logger_msg = f"[{self._phase}]"

    def set_container(self) -> None:
        """
        Determine which Apptainer container to use.

        NOTE: Much match the hardware requested via SLURM.
        """
        if self.use_gpu:
            type = "GPU"
            self._container = f"deepvariant_{self._version}-gpu.sif"
        else:
            type = "CPU"
            self._container = f"deepvariant_{self._version}.sif"

        self.logger.info(
            f"{self._logger_msg}: using the {type} container | '{self._container}'"
        )

    def get_help(self) -> None:
        """
        disply the help page for the program within the container used (make_examples)
        """
        get_help = Client.execute(  # type: ignore
            self._container,
            ["/opt/deepvariant/bin/run_deepvariant", "--helpfull"],
            bind=[self._base_binding],
        )
        print(get_help["message"][0])

    def load_slurm_resources(self) -> None:
        """
        Collect the SBATCH resources from the config file provided
        """
        # Confirm data input is an existing file
        resources = TestFile(str(self._resource_input), self.logger)
        resources.check_existing(
            logger_msg=self._logger_msg, debug_mode=self.args.debug
        )
        if resources.file_exists:
            # read in the json file
            with open(str(self._resource_input), mode="r") as file:
                resource_dict = load(file)

            if self._phase in resource_dict:
                self._resources = resource_dict[self._phase]
                self._n_parts = self._resources["ntasks"]
            else:
                self.logger.error(
                    f"{self._logger_msg}: unable to load SLURM resources as the current phase '{self._phase}' is not a key in '{self._resource_input}'"
                )
                self.logger.error(
                    f"{self._logger_msg}: contents include | {resource_dict.keys()}"
                )
                self.logger.error(
                    f"{self._logger_msg}: please update --resources to include '{self._phase}'\nExiting..."
                )
                exit(1)
        else:
            self.logger.error(
                f"{self._logger_msg}: please update --resources an existing config file\nExiting..."
            )
            exit(1)

    def load_metadata(self) -> None:
        """
        Read in and save the metadata file as a dictionary.
        """
        # Confirm data input is an existing file
        metadata = TestFile(str(self._metadata_input), self.logger)
        metadata.check_existing(logger_msg=self._logger_msg, debug_mode=self.args.debug)
        if metadata.file_exists:
            # read in the csv file
            with open(
                str(self._metadata_input), mode="r", encoding="utf-8-sig"
            ) as data:
                dict_reader = DictReader(data)
                self._data_list = list(dict_reader)
                self._total_lines = len(self._data_list)
        else:
            self.logger.error(
                f"{self._logger_msg}: unable to load metadata file | '{self._metadata_input}'"
            )
            raise ValueError("Invalid Input File")

    def load_variables(self, index: int = 0) -> None:
        """
        Define python variables.
        """
        self._variant_caller = self._data_list[index]["VariantCaller"]
        self._sampleID = self._data_list[index]["SampleID"]
        self._labID = self._data_list[index]["LabID"]
        self._species = self._data_list[index]["Species"]
        self._label = self._data_list[index]["Info"]
        self._test_logger_msg = f"{self._logger_msg} - [{self._variant_caller}] - [{index+1}-of-{self._total_lines}]"

        input_paths = ["RefFASTA", "PopVCF", "RegionsFile", "ReadsBAM", "ModelCkpt"]

        for k, v in self._data_list[index].items():
            if k in input_paths:
                if v != "NA":
                    if k == "ModelCkpt":
                        testing_file = TestFile(
                            f"{self._data_list[index][k]}.data-00000-of-00001",
                            self.logger,
                        )
                    else:
                        testing_file = TestFile(self._data_list[index][k], self.logger)

                    testing_file.check_existing(
                        logger_msg=self._test_logger_msg, debug_mode=self.args.debug
                    )

                    if testing_file.file_exists:
                        if k == "RefFASTA":
                            if self._ref_path != testing_file.path.parent:
                                self._ref_path = testing_file.path.parent
                                self.logger.info(
                                    f"{self._test_logger_msg}: reference path has changed | '{self._ref_path}'"
                                )

                            if self._ref_name != testing_file.path.name:
                                self._ref_name = testing_file.path.name
                                self.logger.info(
                                    f"{self._test_logger_msg}: reference name has changed | '{self._ref_name}'"
                                )

                        elif k == "PopVCF":
                            if self._pop_path != testing_file.path.parent:
                                self._pop_path = testing_file.path.parent
                                self.logger.info(
                                    f"{self._test_logger_msg}: pop path has changed | '{self._pop_path}'"
                                )

                            if self._pop_name != testing_file.path.name:
                                self._pop_name = testing_file.path.name
                                self.logger.info(
                                    f"{self._test_logger_msg}: pop name has changed | '{self._pop_name}'"
                                )

                        elif k == "RegionsFile":
                            if self._region_path != testing_file.path.parent:
                                self._region_path = testing_file.path.parent
                                self.logger.info(
                                    f"{self._test_logger_msg}: region path has changed | '{self._region_path}'"
                                )

                            if self._region_name != testing_file.path.name:
                                self._region_name = testing_file.path.name
                                self.logger.info(
                                    f"{self._test_logger_msg}: region name has changed | '{self._region_name}'"
                                )

                        elif k == "ReadsBAM":
                            if self._reads_path != testing_file.path.parent:
                                self._reads_path = testing_file.path.parent
                                self.logger.info(
                                    f"{self._test_logger_msg}: bam path has changed | '{self._reads_path}'"
                                )

                            if self._reads_name != testing_file.path.name:
                                self._reads_name = testing_file.path.name
                                self.logger.info(
                                    f"{self._test_logger_msg}: bam name has changed | '{self._reads_name}'"
                                )
                        else:
                            if self._ckpt_path != testing_file.path.parent:
                                self._ckpt_path = testing_file.path.parent
                                self.logger.info(
                                    f"{self._test_logger_msg}: ckpt path has changed | '{self._ckpt_path}'"
                                )

                            if self._ckpt_name != testing_file.path.stem:
                                self._ckpt_name = testing_file.path.stem
                                self.logger.info(
                                    f"{self._test_logger_msg}: ckpt name has changed | '{self._ckpt_name}'"
                                )
                    else:
                        self.logger.warning(
                            f"{self._test_logger_msg}: missing a file provided in {self._metadata_input} | {testing_file.file}... SKIPPING AHEAD"
                        )
                        return
                else:
                    if k == "PopVCF":
                        self._pop_path = None
                        self._pop_name = None
                        self.logger.info(f"{self._test_logger_msg}: SKIPPING | {k}:{v}")
                    elif k == "RegionsFile":
                        self._region_path = None
                        self._region_name = None
                        self.logger.info(f"{self._test_logger_msg}: SKIPPING | {k}:{v}")
                    else:
                        self.logger.warning(
                            f"{self._test_logger_msg}: missing a required item in metadata file | '{k}'... SKIPPING AHEAD"
                        )
                        return

    def set_iteration(self) -> None:
        """
        Create an iteration object for downstream modules
        """
        print("FIX THIS!")
        breakpoint()
        if self._species.lower() == "cow":
            self._itr = Iteration(
                current_trio_num="None",
                next_trio_num="None",
                current_genome_num=None,
                total_num_genomes=None,
                train_genome=None,
                eval_genome=None,
                env=None,
                logger=self.logger,
                args=self.args,
                default_region_file=Path(
                    f"{getcwd()}/region_files/{self._species.lower()}_autosomes_withX.bed"
                ),
            )
        else:
            self._itr = Iteration(
                current_trio_num="None",
                next_trio_num="None",
                current_genome_num=None,
                total_num_genomes=None,
                train_genome=None,
                eval_genome=None,
                env=None,
                logger=self.logger,
                args=self.args,
                default_region_file=None,
            )

    def find_output(self, index: int = 0) -> None:
        """
        Determine if output VCF already exists
        """
        output = Path(self._data_list[index]["OutPath"]) / f"{self._sampleID}.vcf.gz"

        testing_file = TestFile(str(output), self.logger)
        testing_file.check_existing(
            logger_msg=self._test_logger_msg, debug_mode=self.args.debug
        )

        if testing_file.file_exists:
            self._output_exists = True
            self.logger.info(
                f"{self._test_logger_msg}: existing file found | '{testing_file.file}'... SKIPPING AHEAD"
            )
            return
        else:
            self._output_exists = False
            if self._output_path != testing_file.path.parent:
                self._output_path = testing_file.path.parent
                self.logger.info(
                    f"{self._test_logger_msg}: output path has changed | '{self._output_path}'"
                )

            if self._output_name != testing_file.path.name:
                self._output_name = testing_file.path.name
                self.logger.info(
                    f"{self._test_logger_msg}: output name has changed | '{self._output_name}'"
                )

            if self._output_path is not None:
                self._itr.job_dir = self._output_path
                self._itr.log_dir = self._output_path

    def create_bindings(self) -> None:
        """
        Create the path bindings for Apptainer
        """
        bindings = ["/usr/lib/locale/:/usr/lib/locale/", f"{getcwd()}/:/run_dir/"]

        if self._output_path is not None:
            bindings.append(f"{self._output_path}/:/out_dir/")

        if self._ckpt_path is not None:
            bindings.append(f"{self._ckpt_path}/:/start_dir/")

        if self._ref_path is not None:
            bindings.append(f"{self._ref_path}/:/ref_dir/")

        if self._reads_path is not None:
            bindings.append(f"{self._reads_path}/:/bam_dir/")

        if self._pop_path is not None:
            bindings.append(f"{self._pop_path}/:/popVCF_dir/")

        if self._region_path is not None:
            bindings.append(f"{self._region_path}/:/region_dir/")
        elif (
            self._species.lower() == "cow" and self._itr.default_region_file is not None
        ):
            # NOTE: when using the new Cattle model, unable to genotype all unmapped contigs due to file num
            # Therefore, by default, only genotype the autosomes + X chromosome only using the default regions file created by the TrioTrain pipeline
            # NOTE: when scaling this up to 6k samples, split up jobs per chromsome, rather than entire genome, and "have the list of unmapped contig names in an array and do "interval" operations on chunks of say 50 contigs single threaded" like Bob does with GATK
            if self._itr.default_region_file.exists():
                bindings.append(f"{self._itr.default_region_file.parent}/:/region_dir/")
            else:
                self.logger.warning(
                    f"{self._test_logger_msg}: missing the default region file | {self._itr.default_region_file}... SKIPPING AHEAD"
                )
                return

        self._bindings = ",".join(bindings)

    def create_flags(self) -> None:
        """
        Create a list of flags to pass to 'run_deepvariant'
        """
        flags = [
            "--model_type=WGS",
            f"--intermediate_results_dir=/out_dir/tmp/{self._sampleID}",
            f"--num_shards={self._n_parts}",
            f"--sample_name={self._sampleID}",
        ]

        if self._output_name is not None:
            flags.append(f"--output_vcf=/out_dir/{self._output_name}")

        if self._ckpt_name is not None:
            flags.append(f"--customized_model=/start_dir/{self._ckpt_name}")

        if self._ref_name is not None:
            flags.append(f"--ref=/ref_dir/{self._ref_name}")

        if self._reads_name is not None:
            flags.append(f"--reads=/bam_dir/{self._reads_name}")

        if self._pop_name is not None:
            flags.append(
                f'--make_examples_extra_args="use_allele_frequency=true,population_vcfs=/popVCF_dir/{self._pop_name}"'
            )

        if self._region_name is not None:
            flags.append(f"--region_file=/region_dir/{self._region_name}")
        elif (
            self._species.lower() == "cow" and self._itr.default_region_file is not None
        ):
            # NOTE: when using the new Cattle model, unable to genotype all unmapped contigs due to file num
            # Therefore, by default, only genotype the autosomes + X chromosome only using the default regions file created by the TrioTrain pipeline
            # NOTE: when scaling this up to 6k samples, split up jobs per chromsome, rather than entire genome, and "have the list of unmapped contig names in an array and do "interval" operations on chunks of say 50 contigs single threaded" like Bob does with GATK
            if self._itr.default_region_file.exists():
                flags.append(
                    f"--regions=/region_dir/{self._itr.default_region_file.name}"
                )
            else:
                self.logger.warning(
                    f"{self._test_logger_msg}: missing the default region file | {self._itr.default_region_file}... SKIPPING AHEAD"
                )
                return

        self._flag = " ".join(flags)

    def build_command(self) -> None:
        """
        Combine container, bindings, and flags into a single Apptainer command.
        """
        self.create_bindings()
        self.create_flags()
        self._command_list = [
            f'echo "INFO: using {self._variant_caller} with {self._ckpt_name} to call variants from {self._species}|{self._label}|{self._sampleID}|{self._labID}"',
            f"time apptainer run -B {self._bindings} {self._container} /opt/deepvariant/bin/run_deepvariant {self._flag}",
        ]

    def make_job(self) -> Union[SBATCH, None]:
        """
        Defines the contents of the SLURM job for the call_variant phase outside of the TrioTrain pipeline.
        """
        # initialize a SBATCH Object
        self.build_command()
        self._job_name = f"{self._sampleID}_{self._variant_caller}"

        slurm_job = SBATCH(
            self._itr,
            self._job_name,
            None,
            None,
            self._test_logger_msg,
        )

        if slurm_job.check_sbatch_file():
            self._sbatch_exists = True
            self.logger.info(
                f"{self._test_logger_msg}: SLURM job file already exists... SKIPPING AHEAD"
            )
            return
        else:
            if self.args.debug:
                self.logger.debug(f"{self._test_logger_msg}: creating job file now... ")

        slurm_job.create_slurm_job(
            None,
            command_list=self._command_list,
            **self._resources,
        )

        return slurm_job

    def submit_job(self, index: int = 0, total_jobs: int = 1) -> None:
        """
        Submits a SLURM job to the queue.
        """
        self.find_output(index=index)

        if self._output_exists:
            self._skipped_counter += 1
            if self._job_nums:
                self._job_nums[index] = None
        else:
            slurm_job = self.make_job()

            if slurm_job is None:
                return
            elif slurm_job is not None:
                if slurm_job.check_sbatch_file() and self.overwrite is False:
                    return

                if self._itr.dryrun_mode:
                    slurm_job.display_job()
                else:
                    slurm_job.write_job()

            submit_slurm_job = SubmitSBATCH(
                self._itr.job_dir,
                f"{self._job_name}.sh",
                self._job_name,
                self.logger,
                self._test_logger_msg,
            )

            if self.args.debug:
                self.logger.debug(
                    f"{self._test_logger_msg}: submitting without a SLURM dependency"
                )
            submit_slurm_job.build_command(None)

            if self.args.dry_run:
                submit_slurm_job.display_command(
                    current_job=(index + 1),
                    total_jobs=total_jobs,
                    display_mode=self.args.dry_run,
                )
                if self._job_nums:
                    self._job_nums[index] = generate_job_id()
            else:
                submit_slurm_job.display_command(
                    current_job=(index + 1),
                    total_jobs=total_jobs,
                    debug_mode=self.args.debug,
                )
                submit_slurm_job.get_status(
                    current_job=(index + 1),
                    total_jobs=total_jobs,
                    debug_mode=self.args.debug,
                )
                if submit_slurm_job.status == 0:
                    self._job_nums[index] = str(submit_slurm_job.job_number)
                else:
                    self.logger.warning(
                        f"{self._test_logger_msg}: unable to submit SLURM job",
                    )
                    if self._job_nums:
                        self._job_nums[index] = None

    def process_samples(self) -> None:
        """
        Iterate through all lines in Metadata
        """
        if self.args.debug:
            self.load_variables()
            self.set_iteration()
            self.submit_job(total_jobs=self._total_lines)
        else:
            for i in range(0, self._total_lines):
                self.load_variables(index=i)
                self.set_iteration()
                self.submit_job(index=i, total_jobs=self._total_lines)

    def run(self) -> None:
        """
        Combine the entire steps into one command
        """
        self.set_container()
        if self.args.get_help:
            self.get_help()
            return
        self.load_slurm_resources()
        self.load_metadata()
        self.process_samples()


def __init__() -> None:
    from helpers.utils import get_logger
    from helpers.wrapper import Wrapper, timestamp

    # Collect command line arguments
    args = collect_args()

    # Collect start time
    Wrapper(__file__, "start").wrap_script(timestamp())

    # Create error log
    current_file = p.basename(__file__)
    module_name = p.splitext(current_file)[0]
    logger = get_logger(module_name)

    check_args(args=args, logger=logger)

    VariantCaller(args=args, logger=logger).run()

    Wrapper(__file__, "end").wrap_script(timestamp())


# Execute functions created
if __name__ == "__main__":
    __init__()
