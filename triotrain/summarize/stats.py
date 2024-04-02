#!/bin/python3
"""
description: 

example:
    python3 scripts/model_training/results_stats.py                                     \\
        --metadata metadata/230112_summary_stats_inputs.csv                             \\
        --output ../TRIO_TRAINING_OUTPUTS/final_results/230112_summary_stats.csv        \\
        -r resource_configs/221205_resources_used.json  \\
        --dry-run
"""

import argparse
import subprocess
from csv import DictReader
from dataclasses import dataclass, field
from json import load
from logging import Logger
from os import environ
from os import path as p
from pathlib import Path
from sys import path
from typing import List, TextIO, Union

from regex import compile

abs_path = Path(__file__).resolve()
module_path = str(abs_path.parent.parent)
path.append(module_path)

from helpers.files import TestFile, WriteFiles
from helpers.iteration import Iteration
from helpers.utils import check_if_all_same, generate_job_id
from model_training.prep.count import count_variants
from model_training.slurm.sbatch import SBATCH, SubmitSBATCH
from model_training.slurm.suffix import remove_suffixes


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
        help="[REQUIRED]\ninput file (.csv)\nprovides the list of VCFs to find or produce summary stats",
        metavar="</path/file>",
    )
    parser.add_argument(
        "-O",
        "--output",
        dest="outpath",
        type=str,
        help="[REQUIRED]\noutput file (.csv)\nwhere to save the resulting summary stats",
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
        help="if True, display +smpl-stats metrics to the screen",
        action="store_true",
    )
    parser.add_argument(
        "--filter-GQ",
        dest="filter_GQ",
        help="if True, subset +smpl-stats metrics by the following GQ values: [10, 13, 20, 30]",
        action="store_true",
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
        logger.info("[DRY RUN]: output will display to screen and not write to a file")

    assert (
        args.metadata
    ), "missing --metadata; Please provide a file with descriptive data for test samples."

    assert (
        args.resource_config
    ), "Missing --resources; Please designate a path to pipeline compute resources in JSON format"

    # if not args.dry_run:
    assert args.outpath, "missing --output; Please provide a file name to save results."


@dataclass
class Stats:
    """
    Define what data to keep when generating VCF summary stats
    """

    # required parameters
    args: argparse.Namespace
    logger: Logger

    # optional values
    run_iteractively: bool = False
    overwrite: bool = False

    # imutable, internal parameters
    _command_list: List = field(default_factory=list, repr=False, init=False)
    _digits_only = compile(r"\d+")
    _filter_applied: Union[str, None] = field(default=None, init=False, repr=False)
    _job_nums: List = field(default_factory=list, repr=False, init=False)
    _num_processed: int = field(default=0, init=False, repr=False)
    _num_skipped: int = field(default=0, init=False, repr=False)
    _num_submitted: int = field(default=0, init=False, repr=False)
    _output_lines: dict = field(default_factory=dict, init=False, repr=False)
    _phase: str = "summary_stats"
    _sample_stats: dict = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        with open(str(self.args.resource_config), mode="r") as file:
            self._slurm_resources = load(file)

    def load_variables(self) -> None:
        """
        Define python variables.
        """
        self._metadata_input = Path(self.args.metadata)
        self._logger_msg = f"[{self._phase}]"
        output = Path(self.args.outpath)
        self._output_path = str(output.parent)
        self._output_name = output.name

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

    def save_metadata(self) -> None:
        """ """
        # identify important information to keep
        metadata_cols = [
            "sort",
            "type",
            "filter",
            "label",
            "info",
            "average_coverage",
            "variant_caller",
            "sampleID",
            "labID",
            "sex",
        ]
        self._sample_metadata = {
            k.strip(): v.strip() for k, v in self._data.items() if k in metadata_cols
        }
        self._sampleID = self._sample_metadata["sampleID"]
        self._caller = self._sample_metadata["variant_caller"]
        info = self._sample_metadata["info"]
        if info:
            if "_" in info:
                self._species, self._description = info.split("_")
            else:
                self._species = info
                self._description = None
        self._logger_msg = (
            f"[{self._phase}] - [{self._caller}] - [{self._sample_metadata['label']}]"
        )

    def find_vcf_input(self) -> None:
        """
        Confirm that the VCF file in the metadata file exists.
        """
        self._vcf_file = TestFile(self._data["file_path"], self.logger)
        self._vcf_file.check_existing(
            logger_msg=self._logger_msg, debug_mode=self.args.debug
        )
        self._clean_filename = remove_suffixes(self._vcf_file.path)

    def execute(self, command_list: list, type: str, keep_output: bool = False) -> None:
        """
        Run a command line subprocess and check the output.
        """
        command_str = " ".join(command_list)
        if not self.run_iteractively:
            self._command_list.append(command_str)
            if self.args.dry_run:
                self.logger.info(
                    f"[DRY_RUN] - {self._logger_msg}: pretending to add the following line(s) to a SLURM job file |\n'{command_str}'"
                )
            return
        elif self.args.dry_run:
            self.logger.info(
                f"[DRY RUN] - {self._logger_msg}: pretending to execute the following | '{command_str}'"
            )
            breakpoint()
            return
        else:
            if keep_output:
                result = subprocess.run(
                    command_list,
                    check=True,
                    capture_output=True,
                    text=True,
                )
            else:
                result = subprocess.run(
                    command_list,
                    check=True,
                )

            if self.args.debug:
                self.logger.debug(f"{self._logger_msg}: done with '{type}'")

            if result.returncode != 0:
                self.logger.error(f"{self._logger_msg}: command used | '{command_str}'")
                self.logger.error(f"{self._logger_msg}: {result.stdout}")
                raise ChildProcessError(f"unable to complete '{type}'")
            elif keep_output and result.returncode == 0:
                output_file_contents = str(result.stdout).split("\n")
                # self._mie_metrics.write_list(output_file_contents)
                # self.handle_mie_data(input=output_file_contents)

    def filter(self, filter_flag: str, input: str, output: str) -> None:
        """
        Filter the contents of a VCF and create a new VCF file
        """
        # Determine if filtered VCF files exist
        _vcf = TestFile(file=output, logger=self.logger)
        _vcf.check_existing(logger_msg=self._logger_msg, debug_mode=self.args.debug)
        if _vcf.file_exists:
            if self.args.debug:
                self.logger.debug(
                    f"{self._logger_msg}: filtered VCF '{_vcf.file}' already exists... SKIPPING AHEAD"
                )
        else:
            self.logger.info(
                f"{self._logger_msg}: using 'bcftools view' to create a filtered VCF | '{output}'",
            )

            convert_cmd = [
                "bcftools",
                "view",
                "--threads",
                "2",
                filter_flag,
                "--output-type",
                "z",
                "--output",
                output,
                input,
            ]

            self.execute(command_list=convert_cmd, type="bcftools view")

    def index_vcf(self, vcf_input: Union[str, Path]) -> None:
        """
        Create the required TABIX index file for 'bcftools +smpl-stats'
        """
        # Determine if indexed VCF files exist
        _tbi = TestFile(file=f"{vcf_input}.tbi", logger=self.logger)
        _tbi.check_existing(logger_msg=self._logger_msg, debug_mode=self.args.debug)
        if _tbi.file_exists:
            if self.args.debug:
                self.logger.debug(
                    f"{self._logger_msg}: tabix-indexed VCF '{_tbi.file}' already exists... SKIPPING AHEAD"
                )
        else:
            self.logger.info(
                f"{self._logger_msg}: using 'tabix index' to create .TBI index file | '{str(vcf_input)}.tbi'",
            )

            index_cmd = [
                "tabix",
                "-p",
                "vcf",
                str(vcf_input),
            ]
            self.execute(command_list=index_cmd, type="tabix index")

    def find_filter(self, file_input: str) -> Union[str, None]:
        """
        Identify the 'GQ##' pattern in an input string.
        """
        _gq_regex = compile(rf"GQ\d+")
        match = _gq_regex.search(file_input)
        if match:
            if self.args.debug:
                self.logger.debug(
                    f"{self._logger_msg}: INPUT CLEAN_FILENAME | '{match.group()}'"
                )
            return match.group()

    def stats(self, input: str, create_job: bool) -> None:
        """
        Produce bcftools +smpl-stats for each sample in metadata file, if missing the .STATS file.
        """
        _filename = remove_suffixes(Path(input))
        stats_output = f"{_filename}.STATS"
        if self.args.filter_GQ and "GQ" in stats_output:
            self._filter_applied = self.find_filter(stats_output)
            if self.args.debug:
                self.logger.debug(
                    f"{self._logger_msg}: FILTER | '{self._filter_applied}'"
                )

        self._stats_file = TestFile(stats_output, self.logger)
        self._stats_file.check_existing(
            logger_msg=self._logger_msg, debug_mode=self.args.debug
        )

        if self._stats_file.file_exists:
            with open(self._stats_file.file, "r") as data:
                self.handle_stats(input=data)
            self.write_output(unique_records_only=True)
            return
        else:
            self._stats_file.check_missing(
                logger_msg=self._logger_msg, debug_mode=self.args.debug
            )

            if create_job:
                stats_cmd = [
                    "bcftools",
                    "+smpl-stats",
                    "--output",
                    str(stats_output),
                    input,
                ]
                self.execute(command_list=stats_cmd, type="bcftools +smpl-stats")
                return
            else:
                if self.args.debug:
                    self.logger.debug(
                        f"{self._logger_msg}: using 'bcftools +smpl-stats' to create STATS file | '{stats_output}'",
                    )

                bcftools_smpl_stats_output = count_variants(
                    self._vcf_file.path,
                    self._logger_msg,
                    logger=self.logger,
                    count_pass=False,
                    count_ref=False,
                )

                self.handle_stats(input=bcftools_smpl_stats_output)  # type: ignore
                self._output_lines[self._num_processed] = self._sample_stats

                if not self.args.dry_run:
                    output_path = str(Path(stats_output).parent)
                    output_name = Path(stats_output).name
                    stats_file = WriteFiles(
                        path_to_file=output_path,
                        file=output_name,
                        logger=self.logger,
                        logger_msg=self._logger_msg,
                        dryrun_mode=self.args.dry_run,
                        debug_mode=self.args.debug,
                    )
                    stats_file.check_missing()
                    stats_file.write_list(bcftools_smpl_stats_output)  # type: ignore

            if self._num_processed < 2:
                if self.args.dry_run:
                    self.logger.info(
                        f"[DRY RUN] - {self._logger_msg}: pretending to add rows to a CSV | '{self.args.outpath}'"
                    )
                    print("---------------------------------------------")
                    print(",".join(self._sample_stats.keys()))
            self.write_output(unique_records_only=True)

    def handle_stats(self, input: Union[list, TextIO]) -> None:
        """
        Search for the .STATS file and save only the FLT0 line values as a dictionary.
        """
        self._header_keys = [
            "sampleID",
            "num_pass_filter",
            "num_non_ref",
            "num_hom_ref",
            "num_hom_alt",
            "num_het",
            "num_hemi",
            "num_snv",
            "num_indel",
            "num_singleton",
            "num_missing",
            "num_transitions",
            "num_transversions",
            "ts_tv",
        ]
        input_line_dict = {}

        for line in input:
            if line.startswith("FLT"):
                line_values = line.split()[1:]  # Excludes the FLT0 field
                for i, v in enumerate(line_values):
                    input_line_dict[self._header_keys[i]] = v
            else:
                pass

        # make sure no sampleID values are 'default'
        if input_line_dict["sampleID"] == "default":
            input_line_dict["sampleID"] = self._sample_metadata["sampleID"]

        if int(input_line_dict["num_hom_alt"]) == 0:
            input_line_dict["hets_homalts"] = ""
        else:
            het_homalt_ratio = int(input_line_dict["num_het"]) / int(
                input_line_dict["num_hom_alt"]
            )
            input_line_dict["hets_homalts"] = f"{het_homalt_ratio:.2f}"

        if int(input_line_dict["num_indel"]) == 0:
            input_line_dict["snvs_indels"] = ""
        else:
            snv_indel_ratio = int(input_line_dict["num_snv"]) / int(
                input_line_dict["num_indel"]
            )
            input_line_dict["snvs_indels"] = f"{snv_indel_ratio:.2f}"

        # merge the user-provided metadata with sample_stats
        self._sample_stats = {**self._sample_metadata, **input_line_dict}

        # Include the GQ filter if applicable
        if self._filter_applied is not None:
            label = self._sample_stats["label"]
            new_label = f"{label}.{self._filter_applied}"
            self._sample_stats["label"] = new_label
            self._filter_applied = None

    def make_job(self) -> Union[SBATCH, None]:
        """
        Define the contents of the SLURM job for the rtg-mendelian phase for TrioTrain Pipeline.
        """
        # initialize a SBATCH Object
        vcf_name = Path(self._clean_filename).name
        if self._sampleID not in vcf_name:
            self.logger.warning(
                f"{self._logger_msg}: discrepancy between sampleID '{self._sampleID}' and file name '{vcf_name}'"
            )
            # if "-" in vcf_name:
            #     self.logger.info(f"{self._logger_msg}: job name will use vcf_name | '{vcf_name}'")
            #     self.job_name = f"stats.{vcf_name}.{self._caller}"
            # else:
            self.logger.info(
                f"{self._logger_msg}: job name will use sampleID | '{self._sampleID}'"
            )
            self.job_name = f"stats.{self._sampleID}.{self._caller}"
        else:
            self.job_name = f"stats.{vcf_name}.{self._caller}"

        self.itr.job_dir = Path(self._clean_filename).parent
        self.itr.log_dir = Path(self._clean_filename).parent

        slurm_job = SBATCH(
            self.itr,
            self.job_name,
            self._caller,
            None,
            self._logger_msg,
        )

        if slurm_job.check_sbatch_file():
            if self.overwrite:
                self.itr.logger.info(
                    f"{self._logger_msg}: --overwrite=True, re-writing the existing SLURM job now..."
                )
            else:
                self.itr.logger.info(
                    f"{self._logger_msg}: SLURM job file already exists... SKIPPING AHEAD"
                )
                self._num_skipped += 1
                return
        else:
            if self.itr.debug_mode:
                self.itr.logger.debug(f"{self._logger_msg}: creating file job now... ")

        slurm_job.create_slurm_job(
            None,
            command_list=self._command_list,
            overwrite=self.overwrite,
            **self._slurm_resources[self._phase],
        )
        return slurm_job

    def submit_job(self, index: int = 0) -> None:
        """
        Submit SLURM jobs to queue.
        """
        # only submit a job if a new SLURM job file was created
        if self._slurm_job is None:
            return

        if self.itr.dryrun_mode:
            self._slurm_job.display_job()
        else:
            self._slurm_job.write_job()

        # submit the training eval job to queue
        submit_slurm_job = SubmitSBATCH(
            self.itr.job_dir,
            f"{self.job_name}.sh",
            "None",
            self.logger,
            self._logger_msg,
        )

        submit_slurm_job.build_command(
            prior_job_number=self.itr.current_genome_dependencies
        )
        submit_slurm_job.display_command(
            current_job=(index + 1),
            total_jobs=self._total_lines,
            display_mode=self.itr.dryrun_mode,
            debug_mode=self.itr.debug_mode,
        )

        if self.itr.dryrun_mode:
            self._job_nums.append(generate_job_id())
            self._num_submitted += 1
        else:
            submit_slurm_job.get_status(
                debug_mode=self.itr.debug_mode,
                current_job=(index + 1),
                total_jobs=self._total_lines,
            )

            if submit_slurm_job.status == 0:
                self._num_submitted += 1
                self._job_nums.append(submit_slurm_job.job_number)
            else:
                self.logger.error(
                    f"{self._logger_msg}: unable to submit SLURM job",
                )
                self._job_nums.append(None)

    def write_output(self, unique_records_only: bool = False) -> None:
        """
        Save the combined metrics to a new CSV output, or display to screen.
        """
        results = WriteFiles(
            path_to_file=self._output_path,
            file=self._output_name,
            logger=self.logger,
            logger_msg=self._logger_msg,
            dryrun_mode=self.args.dry_run,
            # debug_mode=self.args.debug,
        )
        results.check_missing()
        if unique_records_only and results._file_exists:
            with open(str(results.file_path), "r") as file:
                dict_reader = DictReader(file)
                current_records = list(dict_reader)
            for r in current_records:
                if self._sample_stats == r:
                    if self.args.debug:
                        self.logger.debug(
                            f"{self._logger_msg}: skipping a previously processed file | '{self._vcf_file.file}'"
                        )
                    self.logger.info(
                        f"{self._logger_msg}: data has been written previously... SKIPPING AHEAD"
                    )
                    return
                else:
                    continue

        # ensure that output doesn't have duplicat sampleID column
        col_names = list(self._sample_stats.keys())
        results.add_rows(col_names=col_names, data_dict=self._sample_stats)
        self._num_processed += 1

    def check_submission(self) -> None:
        """
        Check if the SLURM job file was submitted to the SLURM queue successfully
        """
        # look at job number list to see if all items are 'None'
        _results = check_if_all_same(self._job_nums, None)
        if _results is False:
            if self.args.dry_run:
                print(
                    f"============ [DRY RUN] - [{self._phase}] Job Numbers - {self._job_nums} ============"
                )
            else:
                print(
                    f"============ [{self._phase}] Job Numbers - {self._job_nums} ============"
                )
        elif self._num_skipped == self._total_lines:
            self.logger.info(
                f"{self._logger_msg}: no SLURM jobs were submitted... SKIPPING AHEAD"
            )
        else:
            self.logger.warning(
                f"{self._logger_msg}: expected SLURM jobs to be submitted, but they were not",
            )
            self.logger.warning(
                f"{self._logger_msg}: fatal error encountered, unable to proceed further with pipeline.\nExiting... ",
            )
            exit(1)

    def process_multiple_samples(self) -> None:
        """
        Iterate through multiple VCF files
        """
        if self.args.debug:
            itr = self._data_list[0:3]
        else:
            itr = self._data_list

        for i, item in enumerate(itr):
            self._data = item
            self.itr = Iteration(
                logger=self.logger,
                args=self.args,
            )

            self.save_metadata()
            self.find_vcf_input()

            # Raw genotypes ALL loci
            if self._vcf_file.file_exists:
                self.stats(input=str(self._vcf_file.file), create_job=True)
            else:
                self.logger.warning(
                    f"{self._logger_msg}: missing the input VCF file | '{self._vcf_file.file}'... SKIPPING AHEAD"
                )

            # Exclude based on GQ
            if self.args.filter_GQ:
                GQ_scores = [10, 13, 20, 30]
                for g in GQ_scores:
                    label = f"{self._clean_filename}.GQ{g}.vcf.gz"

                    _gq_vcf = TestFile(label, self.logger)
                    _gq_vcf.check_existing(
                        logger_msg=self._logger_msg, debug_mode=self.args.debug
                    )
                    if _gq_vcf.file_exists:
                        if self.args.debug:
                            self.logger.debug(
                                f"{self._logger_msg}: GQ.VCF file '{_gq_vcf.file}' already exists... SKIPPING AHEAD"
                            )
                        self.stats(label, create_job=False)
                        continue
                    else:
                        self.logger.info(
                            f"{self._logger_msg}: missing GQ.VCF file | '{_gq_vcf.file}'"
                        )
                        self.filter(f"--exclude 'GQ<{g}'", self._vcf_file.file, label)
                        self.index_vcf(label)
                        self.stats(label, create_job=True)

                self._slurm_job = self.make_job()
                self.submit_job(index=i)
                self._command_list.clear()

                if self._num_processed == 0:
                    completed = f"skipped {self._num_skipped}"
                else:
                    completed = f"processed {self._num_processed}"

                if (self._num_processed % 5) == 0:
                    self.logger.info(
                        f"{self._logger_msg}: {completed}-of-{self._total_lines} records"
                    )
            else:
                # print("HERE!")
                self._slurm_job = self.make_job()
                self.submit_job(index=i)
                self._command_list.clear()

                if self._num_processed == 0:
                    completed = f"skipped {self._num_skipped}"
                else:
                    completed = f"processed {self._num_processed}"

                if (self._num_processed % 5) == 0:
                    self.logger.info(
                        f"{self._logger_msg}: {completed}-of-{self._total_lines} records"
                    )

        if self.args.dry_run:
            print("---------------------------------------------")

    def run(self) -> None:
        """
        Combine all the steps into a single command.
        """
        self.load_variables()
        self.load_metadata()
        self.process_multiple_samples()
        self.check_submission()
        if self._num_processed != 0:
            completed = self._num_processed
        else:
            completed = self._num_skipped
        self.logger.info(
            f"[{self._phase}]: processed {completed}-of-{self._total_lines} VCFs from '{str(self._metadata_input)}'"
        )


def __init__():
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

    try:
        # Check command line args
        check_args(args, logger)
        Stats(args, logger).run()
    except AssertionError as E:
        logger.error(E)

    Wrapper(__file__, "end").wrap_script(timestamp())


# Execute functions created
if __name__ == "__main__":
    __init__()
