#!/bin/python3
"""
description: call variants outside the TrioTrain pipeline with a DeepVariant model

example:
    python3 scripts/variant_calling/callDT.py                       \\
    --metadata metadata/230119_DTvariant_calling_metadata.csv       \\
    --resources resource_configs/230108_resources_used.json         \\
    --dry-run
"""
import argparse
import csv
import re
import sys
from dataclasses import dataclass, field
from json import load
from logging import Logger
from os import environ, getcwd, path
from pathlib import Path
from typing import List, Union

from spython.main import Client

sys.path.append(
    "/storage/hpc/group/UMAG_test/WORKING/jakth2/deep-variant/scripts/model_training"
)
import helpers as h
import helpers_logger
from iteration import Iteration
from sbatch import SBATCH, SubmitSBATCH


def collect_args():
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
        help="if True, display, total hap.py metrics to the screen",
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

    if not args.get_help:
        assert (
            args.metadata
        ), "Missing --metadata; Please provide the path to variant calling run parameters in CSV format"
        assert (
            args.resource_config
        ), "Missing --resources; Please designate a path to pipeline compute resources in JSON format"
        # assert args.outpath, "Missing --outpath; Please designate a path to write files"


@dataclass
class DTVariantCaller:
    """
    Define what data to keep when generating VCF summary stats
    """

    # required variables
    args: argparse.Namespace
    logger: h.Logger

    # optional variables
    use_gpu: bool = False
    overwrite: bool = False

    # imutable, interal variables
    _base_binding: str = field(
        default="/usr/lib/locale/:/usr/lib/locale/", init=False, repr=False
    )
    _job_nums: List[Union[str, None]] = field(
        default_factory=list, repr=False, init=False
    )
    _phase: str = "DT_call_variants"
    _ref_path: Union[Path, None] = None
    _ref_name: Union[str, None] = None
    _region_path: Union[Path, None] = None
    _region_name: Union[str, None] = None
    _skipped_counter: int = 0
    _trio: dict = field(default_factory=dict, init=False, repr=False)
    _version: str = field(
        default=str(environ.get("BIN_VERSION_DT")), init=False, repr=False
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
            self._container = f"deepvariant_deeptrio-{self._version}-gpu.sif"
        else:
            type = "CPU"
            self._container = f"deepvariant_deeptrio-{self._version}.sif"

        self.logger.info(
            f"{self._logger_msg}: using the {type} container | '{self._container}'"
        )

    def get_help(self) -> None:
        """
        disply the help page for the program within the container used (make_examples)
        """
        get_help = Client.execute(  # type: ignore
            self._container,
            ["/opt/deepvariant/bin/deeptrio/run_deeptrio", "--helpfull"],
            bind=[self._base_binding],
        )
        print(get_help["message"][0])

    def load_slurm_resources(self) -> None:
        """
        Collect the SBATCH resources from the config file provided
        """
        # Confirm data input is an existing file
        resources = h.TestFile(str(self._resource_input), self.logger)
        resources.check_existing(
            logger_msg=self._logger_msg, debug_mode=self.args.debug
        )
        if resources.file_exists:
            # read in the json file
            with open(str(self._resource_input), mode="r") as file:
                resource_dict = load(file)

            if self._phase in resource_dict:
                self._resources = resource_dict[self._phase]
                if self.args.dry_run:
                    self.logger.info(
                        f"[DRY_RUN] - {self._logger_msg}: SLURM resources provided | {self._resources}"
                    )
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
                sys.exit(1)
        else:
            self.logger.error(
                f"{self._logger_msg}: please update --resources an existing config file\nExiting..."
            )
            sys.exit(1)

    def load_metadata(self) -> None:
        """
        Read in and save the metadata file as a dictionary.
        """
        # Confirm data input is an existing file
        metadata = h.TestFile(str(self._metadata_input), self.logger)
        metadata.check_existing(logger_msg=self._logger_msg, debug_mode=self.args.debug)
        if metadata.file_exists:
            # read in the csv file
            with open(
                str(self._metadata_input), mode="r", encoding="utf-8-sig"
            ) as data:
                dict_reader = csv.DictReader(data)
                self._data_list = list(dict_reader)
                self._total_lines = len(self._data_list)
                self._total_trios = int(self._total_lines / 3)
            self.logger.info(
                f"{self._logger_msg}: metadata contains '{self._total_trios}' trios from '{self._total_lines}' input lines"
            )
            # if self.args.dry_run:
            #     self.logger.info(f"[DRY_RUN] - {self._logger_msg}: metatdata contents |")
            #     for i, line in enumerate(self._data_list):
            #         print(f"LINE{i}: {line}")
        else:
            self.logger.error(
                f"{self._logger_msg}: unable to load metadata file | '{self._metadata_input}'"
            )
            raise ValueError("Invalid Input File")

    def build_dict(self, list, key) -> dict:
        """
        Re-index dictionary in a list by a specific key
        """
        return dict((d[key], dict(d, index=index)) for (index, d) in enumerate(list))

    def load_variables(self, index: int = 0) -> None:
        """
        Define python variables.
        """
        self._variant_caller = self._data_list[index]["VariantCaller"]
        self._test_logger_msg = f"{self._logger_msg} - [{self._variant_caller}] - [{self._num_submitted+1}-of-{self._total_trios}]"
        self._species = self._data_list[index]["Species"]
        self._output_path = Path(self._data_list[index]["OutPath"])
        self.args.outpath = str(self._output_path)

        # Reference ---------------------------------------
        _reference = Path(self._data_list[index]["RefFASTA"])
        self._reference = h.TestFile(_reference, self.logger)
        self._reference.check_existing(
            logger_msg=self._test_logger_msg, debug_mode=self.args.debug
        )
        if not self._reference.file_exists:
            self.logger.error(
                f"{self._test_logger_msg}: missing the reference genome | '{self._reference.file}'... SKIPPING AHEAD"
            )
            return

        # Region File --------------------------------------

        if self._species.lower() == "cow":
            use_cow = True
            _regions = Path(f"{getcwd()}/region_files/cow_autosomes_withX.bed")
        else:
            use_cow = False
            if self._data_list[index]["RegionsFile"] != "NA":
                _regions = Path(self._data_list[0]["RegionsFile"])
            else:
                _regions = None

        if _regions is not None:
            self._regions = h.TestFile(_regions, self.logger)
            self._regions.check_existing(
                logger_msg=self._test_logger_msg, debug_mode=self.args.debug
            )
            if not self._regions.file_exists:
                self.logger.error(
                    f"{self._test_logger_msg}: missing the reference genome | '{self._regions.file}'... SKIPPING AHEAD"
                )
                return

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
                default_region_file=self._regions.path,
                # cow=use_cow
            )
        else:
            self._regions = None
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
                # cow=use_cow
            )

        # INITIALIZE Pedigree ------------------------------------
        pedigree = [
            "#PED format pedigree",
            "#fam-id/ind-id/pat-id/mat-id: 0=unknown",
            "#sex: 1=male; 2=female; 0=unknown",
            "#phenotype: -9=missing, 0=missing; 1=unaffected; 2=affected",
            "#fam-id ind-id pat-id mat-id sex phen",
        ]

        # Search across 3 input lines for Trio Name and Relationship
        trio_data = self._data_list[index : (index + 3)]

        for i, sample in enumerate(trio_data):
            sample_info = sample["Info"]
            trio_list = re.findall(r"trio\d+", sample_info, re.IGNORECASE)
            if not any(trio_list):
                self.logger.error(
                    f"{self._logger_msg}: unable to find a valid trio number; expected 'Trio#' in the Info column\nExiting..."
                )
                sys.exit(1)
            else:
                self._trio_name = trio_list[0]
                sample["TrioName"] = self._trio_name

            rel_list = re.findall(r"child|mother|father", sample_info, re.IGNORECASE)
            if not any(rel_list):
                self.logger.error(
                    f"{self._logger_msg}: unable to find a valid relationship; expected either 'child', 'mother' or 'father' in the Info column\nExiting..."
                )
                sys.exit(1)
            else:
                relationship = rel_list[0]
                sample["Relationship"] = relationship

            # update with new key:value pairs
            trio_data[i] = sample

        # Re-index sample dictionary by Relationship key
        samples_by_relationship = self.build_dict(trio_data, key="Relationship")

        # Child ----------------------------------------
        child_info = samples_by_relationship.get("Child")
        if child_info:
            self._child_sampleID = child_info["SampleID"]
            self._child_labID = child_info["LabID"]
            _child_BAM = Path(child_info["ReadsBAM"])
            self._child_BAM = h.TestFile(_child_BAM, self.logger)
            self._child_BAM.check_existing(
                logger_msg=self._test_logger_msg, debug_mode=self.args.debug
            )
            if self._child_BAM.file_exists:
                self._trio["Child"] = self._child_sampleID
            else:
                self.logger.error(
                    f"{self._test_logger_msg}: missing the child BAM | '{self._child_BAM}'... SKIPPING AHEAD"
                )
                return

            # ADD TO PEDIGREE:
            paternal, maternal, sex = (
                child_info["paternalID"],
                child_info["maternalID"],
                child_info["sex"],
            )
            pedigree.append(
                f"{self._trio_name} {self._child_sampleID} {paternal} {maternal} {sex} 0"
            )

        # Mother ---------------------------------------
        mother_info = samples_by_relationship.get("Mother")
        if mother_info:
            self._mother_sampleID = mother_info["SampleID"]
            self._mother_labID = mother_info["LabID"]
            _mother_BAM = Path(mother_info["ReadsBAM"])
            self._mother_BAM = h.TestFile(_mother_BAM, self.logger)
            self._mother_BAM.check_existing(
                logger_msg=self._test_logger_msg, debug_mode=self.args.debug
            )
            if self._mother_BAM.file_exists:
                self._trio["Mother"] = self._mother_sampleID
            else:
                self.logger.error(
                    f"{self._test_logger_msg}: missing the mother BAM | '{self._mother_BAM}'... SKIPPING AHEAD"
                )
                return

            # ADD TO PEDIGREE:
            paternal, maternal, sex = (
                mother_info["paternalID"],
                mother_info["maternalID"],
                mother_info["sex"],
            )
            pedigree.append(
                f"{self._trio_name} {self._mother_sampleID} {paternal} {maternal} {sex} 0"
            )

        # Father ------------------------------------------
        father_info = samples_by_relationship.get("Father")
        if father_info:
            self._father_sampleID = father_info["SampleID"]
            self._father_labID = father_info["LabID"]
            _father_BAM = Path(father_info["ReadsBAM"])
            self._father_BAM = h.TestFile(_father_BAM, self.logger)
            self._father_BAM.check_existing(
                logger_msg=self._test_logger_msg, debug_mode=self.args.debug
            )
            if self._father_BAM.file_exists:
                self._trio["Father"] = self._father_sampleID
            else:
                self.logger.error(
                    f"{self._test_logger_msg}: missing the father BAM | '{self._father_BAM}'... SKIPPING AHEAD"
                )
                return

            # ADD TO PEDIGREE:
            paternal, maternal, sex = (
                father_info["paternalID"],
                father_info["maternalID"],
                father_info["sex"],
            )
            pedigree.append(
                f"{self._trio_name} {self._father_sampleID} {paternal} {maternal} {sex} 0"
            )

        self._pedigree = h.WriteFiles(
            path_to_file=str(self._output_path),
            file=f"{self._trio_name}.PED",
            logger=self.logger,
            logger_msg=self._logger_msg,
            debug_mode=self.args.debug,
            dryrun_mode=self.args.dry_run,
        )
        self._pedigree.check_missing()
        if not self._pedigree.file_exists:
            if self.args.dry_run:
                self.logger.info(
                    f"[DRY_RUN] - {self._logger_msg}: missing the Trio pedigree file..."
                )
            self._pedigree.write_list(pedigree)
        else:
            self.logger.info(
                f"{self._logger_msg}: the Trio pedigree file already exists... SKIPPING AHEAD"
            )

    def find_output(self, sampleID: str, relationship: str = "Child") -> None:
        """
        Determine if output VCF already exists
        """
        output = self._output_path / f"{sampleID}.vcf.gz"

        if not output.parent.is_dir():
            self.logger.info(
                f"{self._test_logger_msg}: creating a new directory | '{output.parent}'\nExiting..."
            )
            output.parent.mkdir(parents=True)

        self._itr.job_dir = output.parent
        self._itr.log_dir = output.parent
        self._output_path = output.parent

        _output = h.TestFile(str(output), self.logger)
        _output.check_existing(
            logger_msg=self._test_logger_msg, debug_mode=self.args.debug
        )

        if _output.file_exists:
            if relationship == "Child":
                self._child_exists = True
            elif relationship == "Mother":
                self._mother_exists = True
            elif relationship == "Father":
                self._father_exists = True
            else:
                self.logger.error(
                    f"{self._test_logger_msg}: invalid relationship provided, expected ['Child', 'Mother' or 'Father'] | '{relationship}'\nExiting..."
                )
                sys.exit(1)

            self.logger.info(
                f"{self._test_logger_msg}: existing file found | '{_output.file}'... SKIPPING AHEAD"
            )
            return
        else:
            if relationship == "Child":
                self._child_exists = False
                self._child_name = _output.path.name
            elif relationship == "Mother":
                self._mother_exists = False
                self._mother_name = _output.path.name
            elif relationship == "Father":
                self._father_exists = False
                self._father_name = _output.path.name
            else:
                self.logger.warning(
                    f"{self._test_logger_msg}: invalid relationship provided, expected ['Child', 'Mother' or 'Father'] | '{relationship}'\nExiting..."
                )
                sys.exit(1)

    def create_bindings(self) -> None:
        """
        Create the path bindings for Apptainer
        """
        bindings = [
            self._base_binding,
            f"{getcwd()}/:/run_dir/",
            f"{self._reference.path.parent}/:/ref_dir/",
            f"{self._output_path}/:/out_dir/",
            f"{self._child_BAM.path.parent}/:/child_BAM/",
            f"{self._mother_BAM.path.parent}/:/mother_BAM/",
            f"{self._father_BAM.path.parent}/:/father_BAM/",
        ]
        if self._regions is not None:
            if self._regions.file_exists:
                bindings.append(f"{self._regions.path.parent}/:/region_dir/")
        self._bindings = ",".join(bindings)

    def create_flags(self) -> None:
        """
        Create a list of flags to pass to 'run_deepvariant'
        """
        flags = [
            f"--ref=/ref_dir/{self._reference.path.name}",
            "--model_type=WGS",
            f"--intermediate_results_dir=/out_dir/tmp/{self._trio_name}",
            f"--num_shards=$(nproc)",
            f"--sample_name_child={self._child_sampleID}",
            f"--reads_child=/child_BAM/{self._child_BAM.path.name}",
            f"--output_vcf_child=/out_dir/{self._child_name}",
            f"--output_gvcf_child=/out_dir/{self._child_sampleID}.g.vcf.gz",
            f"--sample_name_parent1={self._mother_sampleID}",
            f"--reads_parent1=/mother_BAM/{self._mother_BAM.path.name}",
            f"--output_vcf_parent1=/out_dir/{self._mother_name}",
            f"--output_gvcf_parent1=/out_dir/{self._mother_sampleID}.g.vcf.gz",
            f"--sample_name_parent2={self._father_sampleID}",
            f"--reads_parent2=/father_BAM/{self._father_BAM.path.name}",
            f"--output_vcf_parent2=/out_dir/{self._father_name}",
            f"--output_gvcf_parent2=/out_dir/{self._father_sampleID}.g.vcf.gz",
        ]
        if self._regions is not None:
            if self._regions.file_exists:
                flags.append(f"--regions=/region_dir/{self._regions.path.name}")
        self._flag = " ".join(flags)

    def build_command(self) -> None:
        """
        Combine container, bindings, and flags into a single Apptainer command.
        """
        self.create_bindings()
        self.create_flags()
        self._command_list = [
            f'echo "INFO: using {self._variant_caller} with to call variants from {self._species}|{self._trio_name}={self._child_labID}|{self._mother_labID}|{self._father_labID}"',
            f"time apptainer run -B {self._bindings} {self._container} /opt/deepvariant/bin/deeptrio/run_deeptrio {self._flag}",
        ]

    def make_job(self) -> Union[SBATCH, None]:
        """
        Defines the contents of the SLURM job for the call_variant phase outside of the TrioTrain pipeline.
        """
        # initialize a SBATCH Object
        self.build_command()
        self._job_name = f"{self._trio_name}_{self._variant_caller}"

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
        for k, v in self._trio.items():
            self.find_output(sampleID=v, relationship=k)

        if self._child_exists and self._mother_exists and self._father_exists:
            self._skipped_counter += 1
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

            submit_slurm_job.build_command(prior_job_number=None)

            if self.args.dry_run:
                submit_slurm_job.display_command(
                    current_job=(index + 1),
                    total_jobs=total_jobs,
                    display_mode=self.args.dry_run,
                )
                self._job_nums.insert(index, h.generate_job_id())
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
                    self._job_nums.insert(index, str(submit_slurm_job.job_number))
                else:
                    self.logger.warning(
                        f"{self._test_logger_msg}: unable to submit SLURM job",
                    )
                    self._job_nums.insert(index, None)

    def check_submissions(self) -> None:
        """
        Checks if the SLURM job file was submitted to the SLURM queue successfully.
        """
        if self.args.debug:
            self._total_trios = 1

        call_vars_results = h.check_if_all_same(self._job_nums, None)

        if call_vars_results is False:
            if self._job_nums and len(self._job_nums) == 1:
                if self.args.dry_run:
                    print(
                        f"============ [DRY_RUN] - {self._logger_msg} Job Number - {self._job_nums} ============"
                    )
                else:
                    print(
                        f"============ {self._logger_msg} Job Number - {self._job_nums} ============"
                    )
            else:
                if self.args.dry_run:
                    print(
                        f"============ [DRY_RUN] - {self._logger_msg} Job Numbers ============\n{self._job_nums}\n============================================================"
                    )

                else:
                    print(
                        f"============ {self._logger_msg} Job Numbers ============\n{self._job_nums}\n============================================================"
                    )
        elif self._skipped_counter != 0:
            if self._skipped_counter == self._total_trios:
                self.logger.info(
                    f"{self._logger_msg}: all VCFs made previously... SKIPPING AHEAD"
                )
            else:
                self.logger.info(
                    f"{self._logger_msg}: found existing VCFs for {self._skipped_counter} trios"
                )

            self._job_nums = [None]
        else:
            self.logger.error(
                f"{self._logger_msg}: expected SLURM jobs to be submitted, but they were not",
            )
            self._job_nums = [None]
            self.logger.warning(
                f"[{self._logger_msg}: fatal error encountered, unable to proceed further with pipeline.\nExiting... ",
            )
            sys.exit(1)

    def process_samples(self) -> None:
        """
        Iterate through all lines in Metadata
        """
        self._num_submitted = 0
        if self.args.debug:
            self.load_variables()
            self.submit_job(total_jobs=self._total_trios)
        else:
            for i in range(0, self._total_lines):
                if i % 3 == 0:
                    self.load_variables(index=i)
                    self.submit_job(
                        index=self._num_submitted, total_jobs=self._total_trios
                    )
                    self._num_submitted += 1
        self.check_submissions()

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


def __init__():
    # Collect command line arguments
    args = collect_args()

    # Collect start time
    Wrapper(__file__, "start").wrap_script(h.timestamp())

    # Create error log
    current_file = path.basename(__file__)
    module_name = path.splitext(current_file)[0]
    logger = helpers_logger.get_logger(module_name)

    check_args(args=args, logger=logger)

    DTVariantCaller(args=args, logger=logger).run()

    Wrapper(__file__, "end").wrap_script(h.timestamp())


# Execute functions created
if __name__ == "__main__":
    __init__()
