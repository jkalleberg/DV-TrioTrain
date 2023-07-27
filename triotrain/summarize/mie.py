#!/bin/python3
"""
description: produce a Trio VCF, then give to 'rtg-tools mendelian' to calculate Mendelian Inheritance Error (MIE) Rate, saved in a log file.

example:
    python3 scripts/results/mie_rate.py                                                \\
        --metadata metadata/230515_mie_rate_inputs.csv                                 \\
        --output ../TRIO_TRAINING_OUTPUTS/final_results/230213_mendelian.csv           \\
        --resources resource_configs/221205_resources_used.json                        \\
        --dry-run
"""

import argparse
import sys
from dataclasses import dataclass, field
from json import load
from os import getcwd, path
from pathlib import Path
from re import sub
from typing import List, TextIO, Union

from regex import compile

sys.path.append(
    "/storage/hpc/group/UMAG_test/WORKING/jakth2/deep-variant/scripts/model_training"
)

import helpers as h
import helpers_logger
from iteration import Iteration
from results_stats import Stats, check_args
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
        "-m",
        "--metadata",
        dest="metadata",
        type=str,
        help="[REQUIRED]\ninput file (.csv)\nprovides the list of VCFs to find or produce summary stats",
        metavar="</path/file>",
    )
    parser.add_argument(
        "-o",
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
        "--all-variants",
        dest="all",
        help="if True, calculates errors for all variants, rather than just PASS variants",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--threshold",
        dest="threshold",
        help="trio concordance percentage required for consistent parentage",
        default=99.0,
        metavar="<float>",
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
    return parser.parse_args()


@dataclass
class MIE:
    """
    Define what data to keep when calculating Mendelian inheritance errors with TrioVCFs.
    """

    # required parameters
    args: argparse.Namespace
    logger: h.Logger

    # optional values
    run_iteractively: bool = False
    overwrite: bool = False

    # internal, imutable values
    _command_list: List = field(default_factory=list, repr=False, init=False)
    _job_nums: List = field(default_factory=list, repr=False, init=False)
    _num_processed: int = field(default=0, init=False, repr=False)
    _num_skipped: int = field(default=0, init=False, repr=False)
    _num_submitted: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        self._stats = Stats(self.args, self.logger)
        self._stats._phase = "mie_summary"

        with open(str(self.args.resource_config), mode="r") as file:
            self._slurm_resources = load(file)

    def set_threshold(self) -> None:
        if self.args.threshold != 99.0:
            self._alter_min_concordance = True
        else:
            self._alter_min_concordance = False

    def find_regions(self) -> None:
        regions_path = (
            Path(getcwd())
            / "region_files"
            / f"{self._stats._species.lower()}_autosomes_withX.bed"
        )
        self._regions_file = h.TestFile(regions_path, self.logger)
        self._regions_file.check_existing()
        if self._stats._species != "Mosquito":
            if self._regions_file.file_exists:
                return
            else:
                self.logger.error(
                    f"{self._stats._logger_msg}: missing a valid regions file | '{self._regions_file.file}'\nExiting..."
                )
                sys.exit(1)

    def find_trio_name(self, trio_input: str) -> Union[str, None]:
        """
        Identify the 'Trio##' pattern in an input string.
        """
        _trio_regex = compile(rf"Trio\d+")
        match = _trio_regex.search(trio_input)
        if match:
            if self.args.debug:
                self.logger.debug(
                    f"[{self._stats._phase}]: INPUT CLEAN_FILENAME | '{match.group()}'"
                )
            return match.group()

    def find_trio_num(self, trio_input: str) -> None:
        """
        Identify the run order '##' pattern from an input string.
        """
        match = self._stats._digits_only.search(trio_input)
        if match:
            self._trio_num = int(match.group())
            if self.args.debug:
                self.logger.debug(
                    f"[{self._stats._phase}]: INPUT NUMBER | '{self._trio_num}'"
                )

    def find_trios(self) -> bool:
        """
        Determine which lines in metadata file contain trios with pedigrees.
        """
        self._childID = self._stats._data["sampleID"]
        self._child_sex = self._stats._data["sex"]
        self._motherID = self._stats._data["maternalID"]
        self._fatherID = self._stats._data["paternalID"]
        self._output_label = self._stats._data["label"]
        self._filter = self._stats._data["filter"]
        self._stats._caller = self._stats._sample_metadata["variant_caller"]

        _trio_type = self._stats._data["type"]
        if "truth" in _trio_type.lower():
            self._trio_type = "TRUTH"
        else:
            self._trio_type = "RAW"

        self._stats._logger_msg = f"[{self._stats._phase}] - [{self._stats._species}] - [{self._stats._caller}]"

        if self._child_sex == "0":
            self.logger.info(
                f"{self._stats._logger_msg}: missing sex info for 'child | {self._childID}'... SKIPPING AHEAD"
            )
            self._num_skipped += 1
            return False
        elif self._motherID == "0" and self._fatherID == "0":
            if self.args.debug:
                self.logger.debug(
                    f"{self._stats._logger_msg}: trio parent line... SKIPPING AHEAD"
                )
            return False
        elif (
            len(self._child_sex) == 0
            and len(self._motherID) == 0
            and len(self._fatherID) == 0
        ):
            if self.args.debug:
                self.logger.debug(
                    f"{self._stats._logger_msg}: not a Trio... SKIPPING AHEAD"
                )
            return False
        else:
            self.logger.info(
                f"{self._stats._logger_msg}: currently processing || INDEX: {self._index} | CHILD: {self._childID} | CHILD_SEX: {self._child_sex} | FATHER: {self._fatherID} | MOTHER: {self._motherID}"
            )
            return True

    def find_input_file(self) -> None:
        """
        Determine what type (vcf vs. bcf) of input was provided.
        """
        # INPUT VCF/BCF provided via -M ----
        if self._stats._data_list[self._index]["trio_path"]:
            _input = Path(self._stats._data_list[self._index]["trio_path"])
            self._merge_inputs = False
        else:
            _input = Path(self._stats._data_list[self._index]["file_path"])
            self._merge_inputs = True

        _input_file = h.TestFile(file=_input, logger=self.logger)
        _input_file.check_missing(
            logger_msg=self._stats._logger_msg, debug_mode=self.args.debug
        )
        if _input_file.file_exists:
            self._input_path = _input.parent
            _file = h.remove_suffixes(_input, remove_all=False)
            self._input_filename = _file.name
            self._name = self.find_trio_name(self._input_filename)
            self._running_name = self.find_trio_name(self._output_label)
            if self._running_name:
                if self._name is None:
                    self._name = self._running_name
                self.find_trio_num(self._running_name)

            self._filetype = _file.suffix
            if self.args.debug:
                self.logger.debug(
                    f"[{self._stats._phase}]: INPUT_PATH | '{self._input_path}'"
                )
                self.logger.debug(
                    f"[{self._stats._phase}]: INPUT_FILENAME | '{self._input_filename}'"
                )
                self.logger.debug(
                    f"[{self._stats._phase}]: SEARCH1 RESULT | '{self._name}'"
                )
                self.logger.debug(
                    f"[{self._stats._phase}]: SEARCH2 RESULT | '{self._running_name}'"
                )
                self.logger.debug(
                    f"[{self._stats._phase}]: INPUT_FILETYPE | '{self._filetype}'"
                )
        else:
            return

        if self.args.debug:
            self.logger.debug(
                f"[{self._stats._phase}]: INPUT FILTER | '{self._filter}'"
            )
            self.logger.debug(f"[{self._stats._phase}]: OUTPUT LABEL | '{self._name}'")

        if self._filetype == ".bcf":
            self._stats._logger_msg = f"[{self._stats._phase}] - [{self._stats._species}] - [{self._stats._caller}] - [{self._running_name}:{self._trio_type}]"
            _label = f"{self._name}.{self._trio_type}"
            self._trio_vcf = h.TestFile(
                f"{self._input_path}/{_label}.vcf.gz", self.logger
            )
        else:
            self._stats._logger_msg = f"[{self._stats._phase}] - [{self._stats._species}] - [{self._stats._caller}] - [{self._running_name}]"
            if not self._merge_inputs and _input_file.file_exists:
                self._trio_vcf = _input_file
            else:
                if self._merge_inputs and self._filter == "test":
                    _label = f"{self._stats._species}.{self._name}"
                    self._trio_vcf = h.TestFile(
                        f"{self._input_path}/{_label}.vcf.gz", self.logger
                    )
                else:
                    raise FileNotFoundError

        self._trio_vcf.check_existing()
        if self.args.debug:
            self.logger.debug(
                f"[{self._stats._phase}]: TRIO VCF_FILE | '{self._trio_vcf.file}'"
            )

    def find_mie(self, pass_only: bool = True):
        """
        Determine if 'rtg-tools mendelian' needs to be run.
        """
        trio_filename = h.remove_suffixes(self._trio_vcf.path)

        if pass_only:
            mie_vcf_file = Path(f"{trio_filename}.PASS.MIE")
        else:
            mie_vcf_file = Path(f"{trio_filename}.ALL.MIE")

        self._mie_vcf = h.WriteFiles(
            path_to_file=str(mie_vcf_file.parent),
            file=f"{mie_vcf_file.name}.vcf.gz",
            logger=self.logger,
            logger_msg=self._stats._logger_msg,
            debug_mode=self.args.debug,
            dryrun_mode=self.args.dry_run,
        )
        self._mie_vcf.check_missing()

        if self._mie_vcf._file_exists:
            self.logger.info(
                f"{self._stats._logger_msg}: the MIE VCF already exists... SKIPPING AHEAD"
            )
            if self.args.dry_run:
                self.logger.info(
                    f"[DRY_RUN] - {self._stats._logger_msg}: rtg-tools MIE VCF | '{self._mie_vcf.file_path}'"
                )

            logging_dir = Path(trio_filename).parent / "logs"
            if logging_dir.is_dir():
                self._log_dir = logging_dir
            else:
                self._log_dir = Path(trio_filename).parent

            mie_regex = compile(rf"mie-{self._name}-{self._stats._caller}_\d+\.out")

            mie_metrics_file_exists, num_found, files_found = h.check_if_output_exists(
                match_pattern=mie_regex,
                file_type="the MIE log file",
                search_path=self._log_dir,
                label=self._stats._logger_msg,
                logger=self.logger,
                debug_mode=self.args.debug,
            )

            if mie_metrics_file_exists and num_found == 1:
                self._existing_metrics_log_file = mie_metrics_file_exists
                mie_metrics_file = self._log_dir / str(files_found[0])

                self._mie_metrics = h.WriteFiles(
                    path_to_file=str(mie_metrics_file.parent),
                    file=f"{mie_metrics_file.name}",
                    logger=self.logger,
                    logger_msg=self._stats._logger_msg,
                    debug_mode=self.args.debug,
                    dryrun_mode=self.args.dry_run,
                )
                self._mie_metrics.check_missing()
                if self.args.dry_run:
                    self.logger.info(
                        f"[DRY_RUN] - {self._stats._logger_msg}: MIE metrics log file | '{mie_metrics_file}'"
                    )
            else:
                self._existing_metrics_log_file = mie_metrics_file_exists
        else:
            self._existing_metrics_log_file = self._mie_vcf._file_exists

    def handle_mie_data(self, input: Union[list, TextIO]) -> None:
        """
        Parse out summary info from the string output.
        """
        variants_analyzed = None
        num_errors = None
        numerator = None
        denominator = None
        results_dict = {}

        if self.args.debug:
            self.logger.debug(
                f"{self._stats._logger_msg}: reading in a file | '{self._mie_metrics.file_path}'",
            )

        for row in input:
            if "violation of Mendelian constraints" in row:
                MIE = row.strip()
                MIE_parts = MIE.split(" ")[0].split("/")
                num_errors = int(MIE_parts[0])
                variants_analyzed = int(MIE_parts[1])

            if "concordance" in row.lower() and "incorrect pedigree" not in row.lower():
                self._concordance_msg = row.strip()
                concordance_parts = self._concordance_msg.split(" ")
                trio_concordance_messy = concordance_parts[-1]
                self._trio_concordance_clean = float(
                    sub(r"[()%]", "", trio_concordance_messy)
                )

                # sanity check
                trio_con_parts = concordance_parts[8].split("/")
                denominator = int(trio_con_parts[1])
                match = self._stats._digits_only.search(trio_con_parts[0])
                if match:
                    numerator = int(match.group())
                    trio_con = round(numerator / denominator * 100, ndigits=2)
                    if self._trio_concordance_clean == trio_con:
                        results_dict["trio_concordance"] = f"{trio_con:.2f}%"
                        if trio_con >= self.args.threshold and self.args.dry_run:
                            self.logger.info(
                                f"[DRY_RUN] - {self._stats._logger_msg}: Trio Concordance ({self._trio_concordance_clean}%) meets Threshold ({self.args.threshold:.2f}%)"
                            )
                    else:
                        self.logger.error(
                            f"{self._stats._logger_msg}: trio concordance math error | expected: {self._trio_concordance_clean}%, but got {trio_con}\nExiting..."
                        )
                        sys.exit(1)

            elif "incorrect pedigree" in row.lower():
                
                if self._stats._species.lower() == "human":
                    self.logger.error(
                        f"{self._stats._logger_msg}: {self._concordance_msg}"
                    )
                    self.logger.error(
                        f"{self._stats._logger_msg}: Trio Concordance ({self._trio_concordance_clean}%) does not meet Threshold ({self.args.threshold:.2f}%)"
                    )
                    # self.logger.error(
                    #     f"{self._stats._logger_msg}: {self._stats._species} samples are required to meet minimum concordance threshold ({self.args.threshold:.2f}%)"
                    # )
                    # self.logger.error(
                    #     f"{self._stats._logger_msg}: Check trio pedigree file and vcfs for correct sample names\nExiting..."
                    # )
                    # sys.exit(1)
                    continue
                else:
                    self.logger.warning(
                        f"{self._stats._logger_msg}: {self._concordance_msg}"
                    )
                    self.logger.warning(
                        f"{self._stats._logger_msg}: Trio Concordance ({self._trio_concordance_clean}%) does not meet Threshold ({self.args.threshold:.2f}%)"
                    )
                    continue

        if variants_analyzed is not None and num_errors is not None:
            results_dict["variants_analyzed"] = str(variants_analyzed)
            results_dict["num_mendelian_errors"] = str(num_errors)
            results_dict[
                "mendelian_error_rate"
            ] = f"{num_errors/variants_analyzed * 100:.2f}%"

        # merge the user-provided metadata with sample_stats
        self._stats._sample_stats = {**self._stats._sample_metadata, **results_dict}

        # save the merged data in a dict of dicts with _num_processed as the index
        self._num_processed += 1
        self._stats._output_lines[self._num_processed] = self._stats._sample_stats

        if self.args.dry_run:
            if self._index < 1:
                self.logger.info(
                    f"[DRY RUN] - {self._stats._logger_msg}: pretending to add header + row to a CSV | '{self.args.outpath}'"
                )
                print("---------------------------------------------")
                print(",".join(self._stats._sample_stats.keys()))
            else:
                self.logger.info(
                    f"[DRY RUN] - {self._stats._logger_msg}: pretending to add a row to a CSV | '{self.args.outpath}'"
                )
        self._stats._vcf_file = self._trio_vcf
        self._stats.write_output(unique_records_only=True)

    def rename(self, input: str, sampleID: str) -> str:
        """
        Add unique sampleIDs to GIAB vcf files.
        Returns the new file name, if reheader is being used.
        Otherwise, returnts the old file name.
        """
        # requiring re-naming to work correctly!
        giab_samples = {
            "NA24385": "HG002",
            "NA24149": "HG003",
            "NA24143": "HG004",
            "NA24631": "HG005",
            "NA24694": "HG006",
            "NA24695": "HG007",
        }

        if (
            giab_samples[sampleID] not in self._clean_filename.name
            and sampleID not in self._clean_filename.name
        ):
            self.logger.error(
                f"{self._stats._logger_msg}: unable to find '{giab_samples[sampleID]}' or '{sampleID}' in '{self._clean_filename.name}'"
            )
            self.logger.error(f"{self._stats._logger_msg}: re-naming error\nExiting...")
            sys.exit(1)

        if "giab" in self._stats._caller.lower():
            self.logger.info(
                f"{self._stats._logger_msg}: sample name will be updated | '{sampleID}'"
            )
            self.find_renaming_file(sample_name=sampleID)
            input_path = Path(input)
            stem = input_path.stem
            suffix = Path(stem).suffix
            output = f"{self._clean_filename}.renamed{suffix}.gz"
            new_vcf = h.TestFile(output, self.logger)
            new_vcf.check_existing(
                logger_msg=self._stats._logger_msg, debug_mode=self.args.debug
            )
            reheader_cmd = [
                "bcftools",
                "reheader",
                "--samples",
                f"{self._input_path}/{sampleID}.rename",
                "--output",
                output,
                input,
            ]

            if not new_vcf.file_exists:
                self._stats.execute(command_list=reheader_cmd, type="bcftools reheader")
            return output
        else:
            return input

    def convert(self, input: str, output: str, vcf_to_bcf: bool = True) -> None:
        """
        Speed up merging by converting any vcf inputs that are missing a bcf companion.
        """
        if vcf_to_bcf:
            output_type = "b"
            self.logger.info(
                f"{self._stats._logger_msg}: using 'bcftools convert' to create a BCF | '{output}'",
            )
        else:
            output_type = "z"
            self.logger.info(
                f"{self._stats._logger_msg}: using 'bcftools convert' to create a VCF | '{output}'",
            )

        convert_cmd = [
            "bcftools",
            "convert",
            "--output-type",
            output_type,
            "--output",
            output,
            input,
        ]

        self._stats.execute(command_list=convert_cmd, type="bcftools convert")

    def find_vcf(self) -> None:
        """
        Confirm that the Trio's VCF files in the metadata file exist.
        """
        if self._trio_vcf.file_exists:
            self._missing_merge_inputs = False
            self.logger.info(
                f"{self._stats._logger_msg}: the Trio VCF already exists... SKIPPING AHEAD"
            )
        else:
            # If we are creating a Family VCF from merging,
            if self._merge_inputs:
                self.logger.info(
                    f"{self._stats._logger_msg}: merging (3) existing BCFs into the Trio VCF | '{self._trio_vcf.file}'"
                )
                # Identify the individual VCFs required that will be merged.
                missing_files = []

                if (
                    self._stats._data_list[self._index]["file_path"]
                    and self._stats._data_list[self._index + 1]["file_path"]
                    and self._stats._data_list[self._index + 2]["file_path"]
                ):
                    # Child ---
                    self._child_vcf = h.TestFile(
                        self._stats._data_list[self._index]["file_path"], self.logger
                    )
                    self._child_vcf.check_existing(
                        logger_msg=self._stats._logger_msg, debug_mode=self.args.debug
                    )

                    # Father ---
                    self._father_vcf = h.TestFile(
                        self._stats._data_list[self._index + 1]["file_path"],
                        self.logger,
                    )
                    self._father_vcf.check_existing(
                        logger_msg=self._stats._logger_msg, debug_mode=self.args.debug
                    )

                    # Mother ---
                    self._mother_vcf = h.TestFile(
                        self._stats._data_list[self._index + 2]["file_path"],
                        self.logger,
                    )
                    self._mother_vcf.check_existing(
                        logger_msg=self._stats._logger_msg, debug_mode=self.args.debug
                    )

                    if (
                        self._child_vcf.file_exists
                        and self._mother_vcf.file_exists
                        and self._father_vcf.file_exists
                    ):
                        self._vcf_inputs = [
                            self._child_vcf,
                            self._father_vcf,
                            self._mother_vcf,
                        ]
                    else:
                        if not self._child_vcf.file_exists:
                            missing_files.append(self._child_vcf.file)

                        if not self._mother_vcf.file_exists:
                            missing_files.append(self._mother_vcf.file)

                        if not self._father_vcf.file_exists:
                            missing_files.append(self._father_vcf.file)

                    if missing_files:
                        self._missing_merge_inputs = True
                        self.logger.warning(
                            f"{self._stats._logger_msg}: missing the following [REQUIRED] input files |"
                        )
                        for i, f in enumerate(missing_files):
                            print(f"\t({i+1}) '{f}'")
                    else:
                        self._missing_merge_inputs = False

            # Determine if we need to convert the existing Family BCF to a VCF...
            else:
                self._missing_merge_inputs = False
                self.logger.info(f"{self._stats._logger_msg}: missing the Trio VCF...")
                self.convert(
                    input=str(self._trio_bcf.file),
                    output=str(self._trio_vcf.file),
                    vcf_to_bcf=False,
                )

    def find_renaming_file(self, sample_name: str) -> None:
        """
        Create a text output file to add a unique sampleID to a vcf, if it doesn't exist.
        """
        _lines = [f"{sample_name}"]

        renaming_file = h.WriteFiles(
            path_to_file=str(self._input_path),
            file=f"{sample_name}.rename",
            logger=self.logger,
            logger_msg=self._stats._logger_msg,
            debug_mode=self.args.debug,
            dryrun_mode=self.args.dry_run,
        )
        renaming_file.check_missing()
        if not renaming_file._file_exists:
            if self.args.dry_run:
                self.logger.info(
                    f"[DRY_RUN] - {self._stats._logger_msg}: missing the  'bcftools reheader' input file | '{sample_name}.rename'"
                )
            renaming_file.write_list(_lines)
        else:
            self.logger.info(
                f"{self._stats._logger_msg}: the 'bcftools reheader' file already exists... SKIPPING AHEAD"
            )

    def find_pedigree(self) -> None:
        """
        Create the .PED output file for Trio, if it doesn't exist.
        """
        pedigree_lines = [
            "# PED format pedigree for RTG-tools",
            "# NOTE: For Sex column, Female=2, Male=1, Unknown=0",
            "## FamilyID IndvID PaternalID MaternalID Sex Pheno",
            f"{self._name} {self._motherID} 0 0 2 0",
            f"{self._name} {self._fatherID} 0 0 1 0",
            f"{self._name} {self._childID} {self._fatherID} {self._motherID} {self._child_sex} 0",
        ]

        self._pedigree = h.WriteFiles(
            path_to_file=str(self._input_path),
            file=f"{self._name}.PED",
            logger=self.logger,
            logger_msg=self._stats._logger_msg,
            debug_mode=self.args.debug,
            dryrun_mode=self.args.dry_run,
        )
        self._pedigree.check_missing()
        if not self._pedigree._file_exists:
            if self.args.dry_run:
                self.logger.info(
                    f"[DRY_RUN] - {self._stats._logger_msg}: missing the Trio pedigree file..."
                )
            self._pedigree.write_list(pedigree_lines)
        else:
            self.logger.info(
                f"{self._stats._logger_msg}: the Trio pedigree file already exists... SKIPPING AHEAD"
            )

    def find_bcf(
        self, vcf_path: Union[Path, None] = None, index: Union[int, None] = None
    ) -> None:
        """
        Find any existing bcf files for the Trio, or create them.
        """
        # If a Family BCF is missing,
        if vcf_path is not None and index is not None and self._merge_inputs:
            # Determine if indvidual BCF files exist
            self._clean_filename = h.remove_suffixes(vcf_path)
            _bcf = h.TestFile(file=f"{self._clean_filename}.bcf.gz", logger=self.logger)
            _bcf.check_existing(
                logger_msg=self._stats._logger_msg, debug_mode=self.args.debug
            )

            if not _bcf.file_exists:
                self.convert(input=str(vcf_path), output=_bcf.file, vcf_to_bcf=True)
            else:
                self.logger.info(
                    f"{self._stats._logger_msg}: individual BCF '{_bcf.file}' already exists... SKIPPING AHEAD"
                )

            if index == 0:
                bcf_renamed = self.rename(input=_bcf.file, sampleID=self._childID)
                if bcf_renamed != _bcf.file:
                    _bcf = h.TestFile(file=bcf_renamed, logger=self.logger)
                    _bcf.check_existing(
                        logger_msg=self._stats._logger_msg, debug_mode=self.args.debug
                    )
                self.find_indexed_inputs(input=_bcf.file)
                self._child_bcf = _bcf
            elif index == 1:
                bcf_renamed = self.rename(input=_bcf.file, sampleID=self._fatherID)
                if bcf_renamed != _bcf.file:
                    _bcf = h.TestFile(file=bcf_renamed, logger=self.logger)
                    _bcf.check_existing(
                        logger_msg=self._stats._logger_msg, debug_mode=self.args.debug
                    )
                self.find_indexed_inputs(input=_bcf.file)
                self._father_bcf = _bcf
            elif index == 2:
                bcf_renamed = self.rename(input=_bcf.file, sampleID=self._motherID)
                if bcf_renamed != _bcf.file:
                    _bcf = h.TestFile(file=bcf_renamed, logger=self.logger)
                    _bcf.check_existing(
                        logger_msg=self._stats._logger_msg, debug_mode=self.args.debug
                    )
                self.find_indexed_inputs(input=_bcf.file)
                self._mother_bcf = _bcf

        # Confirm a Family BCF File already exists...
        else:
            self._trio_bcf = h.TestFile(
                f"{self._input_path}/{self._input_filename}", self.logger
            )
            self._trio_bcf.check_existing(
                logger_msg=self._stats._logger_msg, debug_mode=self.args.debug
            )

            if self._trio_bcf.file_exists:
                self.logger.info(
                    f"{self._stats._logger_msg}: the Trio BCF already exists... SKIPPING AHEAD"
                )
                self._merge_inputs = False
            else:
                self.logger.info(
                    f"{self._stats._logger_msg}: missing the Trio BCF | '{self._trio_bcf.file}'"
                )
                self._merge_inputs = True

    def index_bcf(self, bcf_input: Union[str, Path]) -> None:
        """
        Create the require TBI index file for 'bcftools merge'
        """
        if self.args.debug:
            self.logger.debug(
                f"{self._stats._logger_msg}: using 'bcftools index' to create .CSI index file | '{str(bcf_input)}.csi'",
            )

        index_cmd = [
            "bcftools",
            "index",
            str(bcf_input),
        ]
        self._stats.execute(command_list=index_cmd, type="bcftools index")

    def find_indexed_inputs(self, input: Union[None, str] = None) -> None:
        """
        Find any existing CSI files for the Trio, or create them.
        """
        if input is None:
            output = f"{self._clean_filename}.bcf.gz.csi"
        else:
            output = f"{input}.csi"

        _bcf_index = h.TestFile(file=output, logger=self.logger)
        _bcf_index.check_existing(
            logger_msg=self._stats._logger_msg, debug_mode=self.args.debug
        )
        if not _bcf_index.file_exists:
            output_path = Path(output)
            input_path = Path(output_path.parent)
            input_name = output_path.stem
            self.index_bcf(bcf_input=f"{input_path}/{input_name}")

    def merge_trio_bcfs(self) -> None:
        """
        Combine the child:father:mother bcfs into a TRIO.VCF.GZ file for RTG-tools.
        """
        if not self._trio_vcf.file_exists:
            if self.args.debug:
                self.logger.debug(
                    f"{self._stats._logger_msg}: using 'bcftools merge' to combine (3) BCFs into a Family VCF | '{self._trio_vcf.file}'",
                )
            merge_cmd = [
                "bcftools",
                "merge",
                "--output-type",
                "z",
                "--output",
                self._trio_vcf.file,
                self._child_bcf.file,
                self._father_bcf.file,
                self._mother_bcf.file
            ]

            if self._regions_file.file_exists:
                merge_cmd.extend(["--regions-file", self._regions_file.file])
                self.logger.info(
                    f"{self._stats._logger_msg}: calculations will only be peformed on autosomes and X chromosome"
                )

            self._stats.execute(command_list=merge_cmd, type="bcftools merge")
            self.find_indexed_inputs(input=self._trio_vcf.file)

    def calc_trio_errors(self, pass_only: bool = True) -> Union[List[str], None]:
        """
        Use the family VCF file to calculate the number of violations to Mendelian inheritance.
        """
        if "cow" in self._stats._species.lower():
            template = "rtg_tools/cattle_reference"
        elif "mosquito" in self._stats._species.lower():
            template = "rtg_tools/mosquito_reference"
        elif "human" in self._stats._species.lower():
            template = "rtg_tools/human_reference"
        else:
            self.logger.error(
                f"{self._stats._logger_msg}: unrecognized species provided, options include [cow, human, mosquito] | '{self._stats._species}'... SKIPPING AHEAD"
            )
            return

        mendelian_cmd = [
            "conda",
            "run",
            "--no-capture-output",
            "-p",
            "miniconda_envs/beam_v2.30",
            "rtg",
            "mendelian",
            "--input",
            self._trio_vcf.file,
            "--output",
            str(self._mie_vcf.file_path),
            "--template",
            template,
            "--pedigree",
            str(self._pedigree.file_path),
        ]

        if not pass_only:
            mendelian_cmd.append("--all-records")
            self._stats._sample_metadata["criteria"] = "PASS"
        else:
            self._stats._sample_metadata["criteria"] = "ALL"

        if self._alter_min_concordance:
            mendelian_cmd.append(f"--min-concordance={self.args.threshold}")

        if self.args.debug:
            self.logger.debug(
                f"{self._stats._logger_msg}: using 'rtg mendelian' to calculate mendelian errors within | '{self._trio_vcf.file}'",
            )
        self._stats.execute(
            command_list=mendelian_cmd, type="rtg mendelian", keep_output=True
        )

    def make_job(self) -> Union[SBATCH, None]:
        """
        Define the contents of the SLURM job for the rtg-mendelian phase for TrioTrain Pipeline.
        """
        # initialize a SBATCH Object
        self.job_name = f"mie-{self._name}-{self._stats._caller}"
        self.itr.job_dir = Path(self._trio_vcf.file).parent / "jobs"
        self.itr.log_dir = Path(self._trio_vcf.file).parent / "logs"
        if self.args.dry_run:
            self.logger.info(
                f"[DRY_RUN] - [{self._stats._phase}]: JOB DIR | '{self.itr.job_dir}'"
            )
            self.logger.info(
                f"[DRY_RUN] - [{self._stats._phase}]: LOG DIR | '{self.itr.log_dir}'"
            )

        slurm_job = SBATCH(
            self.itr,
            self.job_name,
            self._stats._caller,
            None,
            self._stats._logger_msg,
        )

        if slurm_job.check_sbatch_file():
            if self.overwrite:
                self.itr.logger.info(
                    f"{self._stats._logger_msg}: --overwrite=True, re-writing the existing SLURM job now..."
                )
            else:
                self.itr.logger.info(
                    f"{self._stats._logger_msg}: SLURM job file already exists... SKIPPING AHEAD"
                )
                self._num_skipped += 1
                return
        else:
            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"{self._stats._logger_msg}: creating file job now... "
                )

        slurm_job.create_slurm_job(
            None,
            command_list=self._stats._command_list,
            overwrite=self.overwrite,
            **self._slurm_resources[self._stats._phase],
        )
        return slurm_job

    def submit_job(self) -> None:
        """
        Submit SLURM jobs to queue.
        """
        slurm_job = self.make_job()

        # only submit a job if a new SLURM job file was created
        if slurm_job is None:
            return

        if self.itr.dryrun_mode:
            slurm_job.display_job()
        else:
            slurm_job.write_job()

        # submits the job to queue
        submit_slurm_job = SubmitSBATCH(
            self.itr.job_dir,
            f"{self.job_name}.sh",
            "None",
            self.logger,
            self._stats._logger_msg,
        )

        submit_slurm_job.build_command(
            prior_job_number=self.itr.current_genome_dependencies
        )
        submit_slurm_job.display_command(
            current_job=(self._num_submitted + 1),
            total_jobs=int(self._stats._total_lines / 3),
            display_mode=self.itr.dryrun_mode,
            debug_mode=self.itr.debug_mode,
        )

        if self.itr.dryrun_mode:
            self._job_nums.append(h.generate_job_id())
            self._num_submitted += 1
        else:
            submit_slurm_job.get_status(debug_mode=self.itr.debug_mode)

            if submit_slurm_job.status == 0:
                self._num_submitted += 1
                self._job_nums.append(submit_slurm_job.job_number)
            else:
                self.logger.error(
                    f"{self._stats._logger_msg}: unable to submit SLURM job",
                )
                self._job_nums.append(None)

    def check_submission(self) -> None:
        """
        Check if the SLURM job file was submitted to the SLURM queue successfully
        """
        if self._num_processed != 0 and self._num_skipped != 0:
            completed = self._num_processed + self._num_skipped
        elif self._num_processed != 0:
            completed = self._num_processed
        else:
            completed = self._num_skipped

        self._stats._logger_msg = f"[{self._stats._phase}]"
        # look at job number list to see if all items are 'None'
        _results = h.check_if_all_same(self._job_nums, None)
        if _results is False:
            self.logger.info(
                f"{self._stats._logger_msg}: submitted {self._num_submitted}-of-{int(self._stats._total_lines/3)} jobs"
            )
            if self.args.dry_run:
                print(
                    f"============ [DRY RUN] - {self._stats._logger_msg} Job Numbers - {self._job_nums} ============"
                )
            else:
                print(
                    f"============ {self._stats._logger_msg} Job Numbers - {self._job_nums} ============"
                )
        elif completed == int(self._stats._total_lines / 3):
            self.logger.info(
                f"{self._stats._logger_msg}: no SLURM jobs were submitted... SKIPPING AHEAD"
            )
        elif self.itr.debug_mode and completed == self._itr:
            self.logger.debug(
                f"{self._stats._logger_msg}: no SLURM jobs were submitted... SKIPPING AHEAD"
            )
        else:
            self.logger.warning(
                f"{self._stats._logger_msg}: expected SLURM jobs to be submitted, but they were not",
            )
            self.logger.warning(
                f"{self._stats._logger_msg}: fatal error encountered, unable to proceed further with pipeline.\nExiting... ",
            )
            exit(1)

        self.logger.info(
            f"[{self._stats._phase}]: processed {completed}-of-{int(self._stats._total_lines/3)} Trios from '{str(self._stats._metadata_input)}'"
        )

    def process_multiple_samples(self) -> None:
        """
        Iterate through multiple VCF files
        """
        itr = 0
        if self.args.debug:
            itr_list = self._stats._data_list[:4]
        else:
            itr_list = self._stats._data_list

        for i, item in enumerate(itr_list):
            self._stats._command_list.clear()
            self._stats._data = item
            self._index = i
            self._stats.save_metadata()
            process_line = self.find_trios()

            if process_line:
                self.find_regions()
                self.find_input_file()
                self.itr = Iteration(
                    current_trio_num=self._trio_num,
                    next_trio_num="None",
                    current_genome_num=None,
                    total_num_genomes=None,
                    train_genome=None,
                    eval_genome=None,
                    env=None,
                    logger=self.logger,
                    args=self.args,
                )

                self.find_mie()

                if self.args.all:
                    self.find_mie(pass_only=False)

                if self._existing_metrics_log_file:
                    if self._mie_metrics._file_exists:
                        with open(self._mie_metrics.file_path, "r") as data:
                            self.handle_mie_data(input=data)
                else:
                    if self.args.debug:
                        self.logger.debug(
                            f"[{self._stats._phase}]: SUFFIX | '{self._filetype}'"
                        )
                    if self._filetype == ".bcf":
                        self.find_bcf()
                    self.find_vcf()
                    self.find_pedigree()

                    if self._missing_merge_inputs:
                        self.logger.warning(
                            f"{self._stats._logger_msg}: input files must exist before a SLURM job can be submitted... SKIPPING AHEAD"
                        )
                        self._num_skipped += 1
                        continue
                    else:
                        if self._merge_inputs and not self._trio_vcf.file_exists:
                            
                            for index, indv in enumerate(self._vcf_inputs):
                                self.find_bcf(vcf_path=indv.path, index=index)
                                # self.find_indexed_inputs()
                            
                            self.merge_trio_bcfs()

                    self.calc_trio_errors()
                    if self.args.all:
                        self.calc_trio_errors(pass_only=False)

                    self.submit_job()
                    # breakpoint()

                    if self._num_submitted == 0:
                        completed = f"skipped {self._num_skipped}"
                    else:
                        completed = f"submitted {self._num_submitted}"

                    if (self._num_submitted % 5) == 0:
                        self.logger.info(
                            f"[{self._stats._phase}]: {completed}-of-{self._stats._total_lines} jobs"
                        )

                itr += 1
                self._itr = itr

                if self.args.dry_run:
                    print(f"[ITR{itr}] ==================================")

    def run(self) -> None:
        """
        Combine all the steps into a single command.
        """
        self._stats.load_variables()
        self._stats.load_metadata()
        self.set_threshold()
        self.process_multiple_samples()

        if self.args.debug:
            self.logger.debug(
                f"[{self._stats._phase}]: MIE SUBMITTED = {self._num_submitted}"
            )
            self.logger.debug(
                f"[{self._stats._phase}]: MIE SKIPPED = {self._num_skipped}"
            )
            self.logger.debug(
                f"[{self._stats._phase}]: MIE PROCESSED = {self._num_processed}"
            )
            self.logger.debug(
                f"[{self._stats._phase}]: STATS SUBMITTED = {self._stats._num_submitted}"
            )
            self.logger.debug(
                f"[{self._stats._phase}]: STATS SKIPPED = {self._stats._num_skipped}"
            )
            self.logger.debug(
                f"[{self._stats._phase}]: STATS PROCESSED = {self._stats._num_processed}"
            )
            self.logger.debug(
                f"[{self._stats._phase}]: MIE TOTAL = {self._stats._total_lines}"
            )

        self.check_submission()


def __init__():
    # Collect command line arguments
    args = collect_args()

    # Collect start time
    h.Wrapper(__file__, "start").wrap_script(h.timestamp())

    # Create error log
    current_file = path.basename(__file__)
    module_name = path.splitext(current_file)[0]
    logger = helpers_logger.get_logger(module_name)

    try:
        # Check command line args
        check_args(args, logger)
        MIE(args, logger).run()
    except AssertionError as E:
        logger.error(E)

    h.Wrapper(__file__, "end").wrap_script(h.timestamp())


# Execute functions created
if __name__ == "__main__":
    __init__()
