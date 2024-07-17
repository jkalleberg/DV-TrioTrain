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
from typing import Dict, List, Union

from spython.main import Client

abs_path = Path(__file__).resolve()
dv_path = Path(abs_path.parent.parent.parent)
module_path = str(dv_path / "triotrain")
path.append(module_path)

from helpers.environment import Env
from helpers.files import TestFile
from helpers.iteration import Iteration
from helpers.utils import generate_job_id, create_deps, check_if_all_same
from model_training.prep.examples_regions import MakeRegions
from model_training.slurm.sbatch import SBATCH, SubmitSBATCH
from compare import CompareHappy

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
    _env_vars: Dict[str, str] = field(default_factory=dict, init=False, repr=False)
    _reads_path: Union[Path, None] = field(default=None, init=False, repr=False)
    _reads_name: Union[str, None] = field(default=None, init=False, repr=False)
    _base_binding: str = field(
        default="/usr/lib/locale/:/usr/lib/locale/", init=False, repr=False
    )
    _bed_path: Union[Path, None] = field(default=None, init=False, repr=False)
    _bed_name: Union[Path, None] = field(default=None, init=False, repr=False)
    _ckpt_path: Union[Path, None] = field(default=None, init=False, repr=False)
    _ckpt_name: Union[str, None] = field(default=None, init=False, repr=False)
    _job_nums: Union[List[Union[str, None]], None] = field(
        default_factory=list, repr=False, init=False
    )
    _output_path: Union[Path, None] = field(default=None, init=False, repr=False)
    _output_name: Union[str, None] = field(default=None, init=False, repr=False)
    _phase: str = "call_variants"
    _pop_path: Union[Path, None] = field(default=None, init=False, repr=False)
    _pop_name: Union[str, None] = field(default=None, init=False, repr=False)
    _ref_path: Union[Path, None] = field(default=None, init=False, repr=False)
    _ref_name: Union[str, None] = field(default=None, init=False, repr=False)
    _region_path: Union[Path, None] = field(default=None, init=False, repr=False)
    _truth_vcf_path: Union[Path, None] = field(default=None, init=False, repr=False)
    _truth_vcf_name: Union[Path, None] = field(default=None, init=False, repr=False)
    _skipped_counter: int = 0
    _region_name: Union[str, None] = field(default=None, init=False, repr=False)
    _version: str = field(
        default=str(environ.get("BIN_VERSION_DV")), init=False, repr=False
    )

    def __post_init__(self) -> None:
        if not self.args.get_help:
            self._metadata_input = Path(self.args.metadata)
            self._resource_input = Path(self.args.resource_config)
        
        if self.args.dry_run:
            self._logger_msg = f"[DRY_RUN] - [{self._phase}]"
        else:
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
                self._resource_dict = load(file)

            if self._phase in self._resource_dict:
                self._resources = self._resource_dict[self._phase]
                self._n_parts = self._resources["ntasks"]
            else:
                self.logger.error(
                    f"{self._logger_msg}: unable to load SLURM resources as the current phase '{self._phase}' is not a key in '{self._resource_input}'"
                )
                self.logger.error(
                    f"{self._logger_msg}: contents include | {self._resource_dict.keys()}"
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
                f"{self._logger_msg}: unable to load metadata file | '{self._metadata_input}'\nExiting..."
            )
            exit(1)

    def create_environment(self, sample_num: int = 0) -> None:
        _env_file = f"{self._output_path}/run{sample_num}.env"
        self.logger.info(
            f"{self._logger_msg}: creating a new environment file | '{_env_file}'"
        )
        self._env = Env(
            _env_file,
            self.logger,
            logger_msg=self._logger_msg,
            dryrun_mode=self.args.dry_run,
        )

    def load_variables(self, index: int = 0) -> None:
        """
        Define python variables.
        """
        self._test_logger_msg = (
            f"{self._logger_msg} - [{index+1}-of-{self._total_lines}]"
        )
        self._output_path = self._data_list[index]["OutPath"]
        self.create_environment(sample_num=(index + 1))
        self._env.add_to(
            key="RunOrder",
            value=f"{index + 1}",
            dryrun_mode=self.args.dry_run,
            msg=self._test_logger_msg,
        )
        self._env.add_to(
            key="RunName",
            value=f"Run{index + 1}",
            dryrun_mode=self.args.dry_run,
            msg=self._test_logger_msg,
        )
        self._env.add_to(
            key="CodePath",
            value=f"{getcwd()}",
            dryrun_mode=self.args.dry_run,
            msg=self._test_logger_msg,
        )
        self._env.add_to(
            key="OutPath",
            value=self._output_path,
            dryrun_mode=self.args.dry_run,
            msg=self._test_logger_msg,
        )
        self._env.add_to(
            key="RunDir",
            value=self._output_path,
            dryrun_mode=self.args.dry_run,
            msg=self._test_logger_msg,
        )
        self._env.add_to(
            key="ResultsDir",
            value=self._output_path,
            dryrun_mode=self.args.dry_run,
            msg=self._test_logger_msg,
        )
        self._env.add_to(
            key="JobDir",
            value=self._output_path,
            dryrun_mode=self.args.dry_run,
            msg=self._test_logger_msg,
        )
        self._env.add_to(
            key="LogDir",
            value=self._output_path,
            dryrun_mode=self.args.dry_run,
            msg=self._test_logger_msg,
        )

        self._variant_caller = self._data_list[index]["VariantCaller"]
        self._sampleID = self._data_list[index]["SampleID"]
        self._env.add_to(
            key="SampleID",
            value=self._sampleID,
            dryrun_mode=self.args.dry_run,
            msg=self._test_logger_msg,
        )
        self._labID = self._data_list[index]["LabID"]
        self._env.add_to(
            key="LabID",
            value=self._labID,
            dryrun_mode=self.args.dry_run,
            msg=self._test_logger_msg,
        )
        self._species = self._data_list[index]["Species"]
        self._env.add_to(
            key="Species",
            value=self._species,
            dryrun_mode=self.args.dry_run,
            msg=self._test_logger_msg,
        )
        self._label = self._data_list[index]["Info"]
        self._env.add_to(
            key="Info",
            value=self._label,
            dryrun_mode=self.args.dry_run,
            msg=self._test_logger_msg,
        )

        if "TruthVCF" in self._data_list[index].keys():
            self._run_happy = True
            self._truth_VCF = self._data_list[index]["TruthVCF"]
            self._truth_BED = self._data_list[index]["CallableBED"]
            input_paths = [
                "RefFASTA",
                "PopVCF",
                "RegionsFile",
                "ReadsBAM",
                "ModelCkpt",
                "TruthVCF",
                "CallableBED",
            ]
        else:
            self._run_happy = False
            self._truth_VCF = "NA"
            self._truth_BED = "NA"
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

                            if self._ref_name != testing_file.path.name:
                                self._ref_name = testing_file.path.name

                            self._env.add_to(
                                key="RefFASTA_Path",
                                value=self._ref_path,
                                dryrun_mode=self.args.dry_run,
                                msg=self._test_logger_msg,
                            )
                            self._env.add_to(
                                key="RefFASTA_File",
                                value=self._ref_name,
                                dryrun_mode=self.args.dry_run,
                                msg=self._test_logger_msg,
                            )

                        elif k == "PopVCF":
                            if self._pop_path != testing_file.path.parent:
                                self._pop_path = testing_file.path.parent

                            if self._pop_name != testing_file.path.name:
                                self._pop_name = testing_file.path.name

                            self._env.add_to(
                                key="PopVCF_Path",
                                value=self._pop_path,
                                dryrun_mode=self.args.dry_run,
                                msg=self._test_logger_msg,
                            )

                            self._env.add_to(
                                key="PopVCF_File",
                                value=self._ref_path,
                                dryrun_mode=self.args.dry_run,
                                msg=self._test_logger_msg,
                            )

                        elif k == "RegionsFile":
                            if self._region_path != testing_file.path.parent:
                                self._region_path = testing_file.path.parent

                            if self._region_name != testing_file.path.name:
                                self._region_name = testing_file.path.name

                            self._env.add_to(
                                key="RegionsFile_Path",
                                value=self._region_path,
                                dryrun_mode=self.args.dry_run,
                                msg=self._test_logger_msg,
                            )
                            self._env.add_to(
                                key="RegionsFile_File",
                                value=self._ref_path,
                                dryrun_mode=self.args.dry_run,
                                msg=self._test_logger_msg,
                            )

                        elif k == "ReadsBAM":
                            if self._reads_path != testing_file.path.parent:
                                self._reads_path = testing_file.path.parent
                            self._env.add_to(
                                key=f"Test{index+1}ReadsBAM_Path",
                                value=self._reads_path,
                                dryrun_mode=self.args.dry_run,
                                msg=self._test_logger_msg,
                            )

                            if self._reads_name != testing_file.path.name:
                                self._reads_name = testing_file.path.name
                            self._env.add_to(
                                key=f"Test{index+1}ReadsBAM_File",
                                value=self._reads_name,
                                dryrun_mode=self.args.dry_run,
                                msg=self._test_logger_msg,
                            )

                        elif k == "TruthVCF":
                            if self._truth_vcf_path != testing_file.path.parent:
                                self._truth_vcf_path = testing_file.path.parent
                            self._env.add_to(
                                key=f"Test{index+1}TruthVCF_Path",
                                value=self._truth_vcf_path,
                                dryrun_mode=self.args.dry_run,
                                msg=self._test_logger_msg,
                            )

                            if self._truth_vcf_name != testing_file.path.name:
                                self._truth_vcf_name = testing_file.path.name
                            self._env.add_to(
                                key=f"Test{index+1}TruthVCF_File",
                                value=self._truth_vcf_name,
                                dryrun_mode=self.args.dry_run,
                                msg=self._test_logger_msg,
                            )

                        elif k == "CallableBED":
                            if self._bed_path != testing_file.path.parent:
                                self._bed_path = testing_file.path.parent
                            self._env.add_to(
                                key=f"Test{index+1}CallableBED_Path",
                                value=self._bed_path,
                                dryrun_mode=self.args.dry_run,
                                msg=self._test_logger_msg,
                            )

                            if self._bed_name != testing_file.path.name:
                                self._bed_name = testing_file.path.name
                            self._env.add_to(
                                key=f"Test{index+1}CallableBED_File",
                                value=self._bed_name,
                                dryrun_mode=self.args.dry_run,
                                msg=self._test_logger_msg,
                            )

                        else:
                            if self._ckpt_path != testing_file.path.parent:
                                self._ckpt_path = testing_file.path.parent
                            self._env.add_to(
                                key="Ckpt_Path",
                                value=self._ckpt_path,
                                dryrun_mode=self.args.dry_run,
                                msg=self._test_logger_msg,
                            )

                            if self._ckpt_name != testing_file.path.stem:
                                self._ckpt_name = testing_file.path.stem
                            self._env.add_to(
                                key="Ckpt_File",
                                value=self._ckpt_name,
                                dryrun_mode=self.args.dry_run,
                                msg=self._test_logger_msg,
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
                        self._env.add_to(
                            key="PopVCF",
                            value="None",
                            dryrun_mode=self.args.dry_run,
                            msg=self._test_logger_msg,
                        )
                    elif k == "RegionsFile":
                        self._region_path = None
                        self._region_name = None

                        self._env.add_to(
                            key="RegionsFile_Path",
                            value="None",
                            dryrun_mode=self.args.dry_run,
                            msg=self._test_logger_msg,
                        )
                        self._env.add_to(
                            key="RegionsFile_File",
                            value="None",
                            dryrun_mode=self.args.dry_run,
                            msg=self._test_logger_msg,
                        )
                    else:
                        self.logger.warning(
                            f"{self._test_logger_msg}: missing a required item in metadata file | '{k}'... SKIPPING AHEAD"
                        )
                        return

    def set_iteration(self) -> None:
        """
        Create an iteration object for downstream modules
        """
        _prefix = Path(self._ref_name).stem
        default_region_file = Path(f"{self._ref_path}/{_prefix}_autosomes_withX.bed")

        if default_region_file.is_file():
            self.logger.info(
                f"{self._test_logger_msg}: using the default region file | '{default_region_file}'"
            )
            self._env.add_to(
                key="RegionsFile_Path",
                value=self._ref_path,
                dryrun_mode=self.args.dry_run,
                msg=self._test_logger_msg,
                update=True,
            )
            self._env.add_to(
                key="RegionsFile_File",
                value=f"{_prefix}_autosomes_withX.bed",
                dryrun_mode=self.args.dry_run,
                msg=self._test_logger_msg,
                update=True,
            )
            self._itr = Iteration(
                logger=self.logger,
                args=self.args,
                default_region_file=default_region_file,
                env=self._env,
                total_num_tests=self._total_lines,
            )
        else:
            self.logger.warning(
                f"{self._test_logger_msg}: missing a default region file located here | '{self._ref_path}'"
            )

            self._itr = Iteration(
                logger=self.logger,
                args=self.args,
                env=self._env,
                total_num_tests=self._total_lines,
            )

            # --- Create Shuffling Regions for Non-Baseline Runs --- ##
            self.regions = MakeRegions(
                self._itr,
                ex_per_file=200000,
                ex_per_var=1.5,
                train_mode=False,
            )
            self.regions._reference = self._ref_path / self._ref_name

            # create the default regions_file for testing, if necessary
            if (
                self._itr.default_region_file is None
                or not self._itr.default_region_file.is_file()
            ):
                try:
                    self.regions.write_autosomes_withX_regions(
                        output_file_name=f"{_prefix}_autosomes_withX.bed"
                    )
                    self.logger.info(
                        f"{self._test_logger_msg}: updating Iteration() with the created default region file | '{default_region_file}'"
                    )
                    self._itr = Iteration(
                        logger=self.logger,
                        args=self.args,
                        default_region_file=default_region_file,
                        
                    )
                except Exception as ex:
                    self.logger.error(
                        f"{self._test_logger_msg} - [create_default_region]: unable to create a BED file from the reference Picard .dict file..."
                    )
                    self.logger.error(
                        f"{self._test_logger_msg} - [create_default_region]: an exception occured | Type='{type(ex).__name__}'\nMessage='{ex}'\nExiting..."
                    )
                    exit(1)

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
                if not self._output_path.is_dir():
                    self._output_path.mkdir(parents=True)

            if self._output_name != testing_file.path.name:
                self._output_name = testing_file.path.name

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
        elif self._itr.default_region_file is not None:
            # NOTE: when using the new Cattle model, unable to genotype all unmapped contigs due to file num
            # Therefore, by default, only genotype the autosomes + X chromosome only using the default regions file created by the TrioTrain pipeline
            # NOTE: when scaling this up to 6k samples, split up jobs per chromsome, rather than entire genome, and "have the list of unmapped contig names in an array and do "interval" operations on chunks of say 50 contigs single threaded" like Bob does with GATK
            if self._itr.default_region_file.exists():
                bindings.append(f"{self._itr.default_region_file.parent}/:/region_dir/")
            else:
                self.logger.error(
                    f"{self._test_logger_msg}: missing the default BED file | {self._itr.default_region_file}.\nExiting..."
                )
                exit(1)

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
        elif self._itr.default_region_file is not None:
            # NOTE: when using the new Cattle model, unable to genotype all unmapped contigs due to file num
            # Therefore, by default, only genotype the autosomes + X chromosome only using the default regions file created by the TrioTrain pipeline
            # NOTE: when scaling this up to 6k samples, split up jobs per chromsome, rather than entire genome, and "have the list of unmapped contig names in an array and do "interval" operations on chunks of say 50 contigs single threaded" like Bob does with GATK
            if self._itr.default_region_file.exists():
                flags.append(
                    f"--regions=/region_dir/{self._itr.default_region_file.name}"
                )
            else:
                self.logger.warning(
                    f"{self._test_logger_msg}: missing the default BED file | {self._itr.default_region_file}... SKIPPING AHEAD"
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
                self._job_nums.insert(index, None)
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

            self._slurm_job = SubmitSBATCH(
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
            self._slurm_job.build_command(None)

            if self.args.dry_run:
                self._slurm_job.display_command(
                    current_job=(index + 1),
                    total_jobs=total_jobs,
                    display_mode=self.args.dry_run,
                )
                if self._job_nums:
                    self._job_nums.insert(index, generate_job_id())
            else:
                self._slurm_job.display_command(
                    current_job=(index + 1),
                    total_jobs=total_jobs,
                    debug_mode=self.args.debug,
                )
                self._slurm_job.get_status(
                    current_job=(index + 1),
                    total_jobs=total_jobs,
                    debug_mode=self.args.debug,
                )
                if self._slurm_job.status == 0:
                    self._job_nums.insert(index, str(self._slurm_job.job_number))
                else:
                    self.logger.warning(
                        f"{self._test_logger_msg}: unable to submit SLURM job",
                    )
                    if self._job_nums:
                        self._job_nums.insert(index, None)

    def process_samples(self) -> None:
        """
        Iterate through all lines in Metadata
        """
        if self.args.debug:
            self.load_variables()
            self.set_iteration()
            self.submit_job(total_jobs=self._total_lines)
        else:
            self._job_nums = create_deps(self._total_lines)
            _run_happy_jobs = create_deps(self._total_lines)
            _convert_happy_jobs = create_deps(self._total_lines)
            for i in range(0, self._total_lines):
                self.load_variables(index=i)
                self.set_iteration()
                self.submit_job(index=i, total_jobs=self._total_lines)
                
                if self._run_happy is False:
                    continue

                if self._job_nums:
                    benchmark = CompareHappy(
                        itr=self._itr,
                        slurm_resources=self._resource_dict,
                        model_label=self._variant_caller,
                        call_variants_jobs=self._job_nums,
                    )
                else:
                    benchmark = CompareHappy(
                        itr=self._itr,
                        slurm_resources=self._resource_dict,
                        model_label=self._variant_caller,
                    )

                benchmark.set_genome()
                benchmark.job_num = i + 1
                # THIS HAS TO BE +1 to avoid labeling files Test0

                benchmark.set_test_genome(current_test_num=(i+1))
                benchmark.find_outputs()
                benchmark.submit_job(
                    dependency_index=i,
                    total_jobs=int(self._total_lines),
                )
                _run_happy_jobs[i] = benchmark._slurm_job.job_number
                
                #--------- PROCESS HAP.PY RESULTS ----------------------#
                benchmark.converting.job_num = i + 1
                benchmark.converting.set_test_genome(current_test_num=(i+1))
                benchmark.converting.find_outputs()
                benchmark.converting.compare_happy_jobs = benchmark._convert_happy_dependencies
                benchmark.converting.submit_job(
                    dependency_index=i,
                    total_jobs=int(self._total_lines))
                _convert_happy_jobs[i] = benchmark.converting._slurm_job.job_number

                if (i + 1) == self._total_lines:
                    _skip_DV = check_if_all_same(self._job_nums, None)
                    if not _skip_DV:
                        if len(self._job_nums) == 1:
                            print(
                                f"============ {self._logger_msg} - Job Number - {self._job_nums} ============"
                            )
                        else:
                            print(
                                f"============ {self._logger_msg} - Job Numbers ============\n{self._job_nums}\n============================================================"
                            )
                    benchmark._convert_happy_dependencies = _run_happy_jobs
                    benchmark.check_submissions()
                    benchmark.converting._final_jobs = _convert_happy_jobs
                    benchmark.converting.check_submissions()

    def setup(self) -> None:
        """
        Combine the entire steps into one command
        """
        self.set_container()
        if self.args.get_help:
            self.get_help()
            return
        self.load_slurm_resources()
        self.load_metadata()
        # self.process_samples()


def __init__() -> None:
    from helpers.utils import get_logger
    from helpers.wrapper import Wrapper, timestamp

    # Collect command line arguments
    # args = collect_args()
    # Collect start time
    Wrapper(__file__, "start").wrap_script(timestamp())

    # Create error log
    current_file = p.basename(__file__)
    module_name = p.splitext(current_file)[0]
    logger = get_logger(module_name)

    # check_args(args=args, logger=logger)

    # VariantCaller(args=args, logger=logger).setup()

    Wrapper(__file__, "end").wrap_script(timestamp())


# Execute functions created
if __name__ == "__main__":
    __init__()
