#!/bin/python3
"""
description: produce a Trio VCF, then give to 'rtg-tools mendelian' to calculate Mendelian Inheritance Error (MIE) Rate, saved in a log file.

example:
    python3 triotrain/summarize/mie.py                           \\
        --metadata metadata/230515_mie_rate_inputs.csv           \\
        --output ../TRIO_TRAINING_OUTPUTS/final_results/230213_mendelian.csv           \\
        --resources resource_configs/221205_resources_used.json                        \\
        --dry-run
"""

import argparse
from dataclasses import dataclass, field
from json import load
from logging import Logger
from os import path as p
from pathlib import Path
from re import sub
from subprocess import CalledProcessError
from subprocess import run as run_sub
from sys import exit, path
from typing import Dict, List, TextIO, Union

from regex import compile

abs_path = Path(__file__).resolve()
module_path = str(abs_path.parent.parent)
path.append(module_path)

from _args import check_args, collect_args
from helpers.files import TestFile, WriteFiles
from helpers.iteration import Iteration
from helpers.outputs import check_if_output_exists
from helpers.utils import check_if_all_same, generate_job_id
from model_training.slurm.sbatch import SBATCH, SubmitSBATCH
from model_training.slurm.suffix import remove_suffixes
from stats import Summary


@dataclass
class MIE:
    """
    Define what data to keep when calculating Mendelian inheritance errors with TrioVCFs.
    """

    # required parameters
    args: argparse.Namespace
    logger: Logger

    # optional values
    run_iteractively: bool = False
    overwrite: bool = False

    # internal, imutable values
    _job_nums: List = field(default_factory=list, repr=False, init=False)
    _num_processed: int = field(default=0, init=False, repr=False)
    _num_skipped: int = field(default=0, init=False, repr=False)
    _num_submitted: int = field(default=0, init=False, repr=False)
    _total_lines: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        self._summary = Summary(self.args, self.logger)
        self._summary._phase = "summary"
        # if self.args.post_process is False:
        with open(str(self.args.resource_config), mode="r") as file:
            self._slurm_resources = load(file)

    def set_threshold(self) -> None:
        if self.args.threshold != 99.0:
            self._alter_min_concordance = True
        else:
            self._alter_min_concordance = False

    def find_default_region_file(self) -> None:
        self._ref_path = Path(self.args.reference).resolve()
        _ref_prefix = self._ref_path.stem
        _regions_path = self._ref_path.parent / f"{_ref_prefix}_autosomes_withX.bed"
        self._regions_file = TestFile(_regions_path, self.logger)
        self._regions_file.check_existing()
        if self._regions_file.file_exists:
            self.logger.info(
                f"[{self._summary._phase}]: MIE metrics will be constrained by the default region file | '{self._regions_file.file}'"
            )
            return
        else:
            self.logger.error(
                f"[{self._summary._phase}]: missing a valid regions file | '{self._regions_file.file}'\nExiting..."
            )
            exit(1)

    def find_reference_SDF(self) -> None:
        """
        Determine if SDF is missing, and if so, attempt to create it.

        Then, determine if

        Raises
        ------
        ChildProcessError
            Indicates that 'rtg format' was unable to be executed as a subprocess.
        """
        # First, confirm if FASTA has been converted to SDF
        self._rtg_tools_path = Path(self._ref_path.parent) / "rtg_tools"
        _sdf_summary_path = self._rtg_tools_path / "summary.txt"
        _sdf_summary_file = TestFile(file=f"{_sdf_summary_path}", logger=self.logger)
        _sdf_summary_file.check_existing()

        if not _sdf_summary_file.file_exists:
            # when run interactively as a sub-process, don't include conda
            rtg_format_cmd = [
                "rtg",
                "format",
                "-o",
                f"{self._rtg_tools_path}",
                f"{self._ref_path}",
            ]
            command_str = " ".join(rtg_format_cmd)
            try:
                result = run_sub(
                    rtg_format_cmd,
                    check=True,
                )
                if result.returncode != 0:
                    self.logger.error(
                        f"[{self._summary._phase}]: command used | '{command_str}'"
                    )
                    self.logger.error(f"[{self._summary._phase}]: {result.stdout}")
                    raise ChildProcessError(f"unable to complete 'rtg format'")
            except CalledProcessError or ChildProcessError as e:
                self.logger.error(
                    f"[{self._summary._phase}]: command used | '{command_str}'"
                )
                self.logger.error(f"[{self._summary._phase}]: {e}")
                self.logger.error(
                    f"[{self._summary._phase}]: unable to format the .FASTA into SDF required by rtg tools.\nExiting..."
                )

        else:
            self.logger.info(
                f"[{self._summary._phase}]: found existing SDF for 'rtg mendelian'  | '{_sdf_summary_file.file}'"
            )

        # rtg tools requires a "reference.txt" file to exists AFTER formatting the FASTA into SDF
        _rtg_ref_path = self._rtg_tools_path / "reference.txt"
        _rtg_reference_file = TestFile(file=f"{_rtg_ref_path}", logger=self.logger)
        _rtg_reference_file.check_existing()

        if self.args.par is not None:
            if _rtg_reference_file.file_exists:
                self.logger.info(
                    f"[{self._summary._phase}]: found existing 'reference.txt' for 'rtg mendelian'  | '{_rtg_reference_file.file}'"
                )
                self.logger.warning(
                    f"[{self._summary._phase}]: therefore, user input file will be ignored | '{self.args.par}'"
                )
            elif not _rtg_reference_file.file_exists:
                _input_rtg_reference_file = TestFile(
                    file=self.args.par, logger=self.logger
                )
                _input_rtg_reference_file.check_existing()
                if _input_rtg_reference_file.file_exists:
                    self.logger.info(
                        f"[{self._summary._phase}]: creating a copy of 'reference.txt' for 'rtg mendelian'  | '{_rtg_reference_file.file}'"
                    )
                    source = Path(_input_rtg_reference_file.file)
                    destination = Path(_rtg_reference_file.file)
                    destination.write_text(source.read_text())
                else:
                    self.logger.error(
                        f"[{self._summary._phase}]: missing an input file for 'rtg mendelian'  | '{_input_rtg_reference_file.file}'\nExiting..."
                    )
                    exit(1)

        else:
            if not _rtg_reference_file.file_exists:
                self.logger.warning(
                    f"[{self._summary._phase}]: missing a required input file | '{_rtg_reference_file.file}'"
                )
                self.logger.warning(
                    f"[{self._summary._phase}]: for non-human reference genomes, this file must be created MANUALLY.\nSee RTG Documentation for details.\nTrioTrain includes a template from GRCh38 here | './triotrain/variant_calling/data/GIAB/reference/rtg_tools/reference.txt'"
                )
                exit(1)

    def find_input_file(self) -> None:
        """
        Determine what type (vcf vs. bcf) of input was provided.
        """
        if self._filetype == ".bcf":
            self._trio_vcf = TestFile(
                f"{self._input_path}/{self._trio_name}.vcf.gz", self.logger
            )
        else:
            if not self._merge_inputs and _input_file.file_exists:
                self._trio_vcf = _input_file
            else:
                if self._merge_inputs:
                    self._trio_vcf = TestFile(
                        f"{self._input_path}/{self._trio_namel}.vcf.gz", self.logger
                    )
                else:
                    raise FileNotFoundError

        self._trio_vcf.check_existing()
        if self.args.debug:
            self.logger.debug(
                f"[{self._summary._phase}]: TRIO VCF_FILE | '{self._trio_vcf.file}'"
            )

    def find_mie_outputs(self, pass_only: bool = True) -> None:
        """
        Determine if 'rtg-tools mendelian' needs to be run.
        """
        trio_filename = remove_suffixes(self._trio_vcf.path)

        if pass_only:
            mie_vcf_file = Path(f"{trio_filename}.PASS.MIE")
        else:
            mie_vcf_file = Path(f"{trio_filename}.ALL.MIE")

        self._mie_vcf = WriteFiles(
            path_to_file=str(mie_vcf_file.parent),
            file=f"{mie_vcf_file.name}.vcf.gz",
            logger=self.logger,
            logger_msg=self._summary._logger_msg,
            debug_mode=self.args.debug,
            dryrun_mode=self.args.dry_run,
        )
        self._mie_vcf.check_missing()

        if self._mie_vcf.file_exists:
            self.logger.info(
                f"{self._summary._logger_msg}: the MIE VCF already exists... SKIPPING AHEAD"
            )
            if self.args.dry_run:
                self.logger.info(
                    f"[DRY_RUN] - {self._summary._logger_msg}: rtg-tools MIE VCF | '{self._mie_vcf.file_path}'"
                )

            logging_dir = Path(trio_filename).parent / "logs"
            if logging_dir.is_dir():
                self._log_dir = logging_dir
            else:
                self._log_dir = Path(trio_filename).parent

            # mie_regex = compile(
            #     rf"mie-{self._trio_name}-{self._summary._caller}_\d+\.out"
            # )
            mie_regex = compile(rf"mie-{self._trio_name}.log")

            mie_metrics_file_exists, num_found, files_found = check_if_output_exists(
                match_pattern=mie_regex,
                file_type="the MIE log file",
                search_path=self._log_dir,
                label=self._summary._logger_msg,
                logger=self.logger,
                debug_mode=self.args.debug,
            )

            if mie_metrics_file_exists and num_found == 1:
                self._existing_metrics_log_file = mie_metrics_file_exists
                mie_metrics_file = self._log_dir / str(files_found[0])

                self._mie_metrics = WriteFiles(
                    path_to_file=str(mie_metrics_file.parent),
                    file=f"{mie_metrics_file.name}",
                    logger=self.logger,
                    logger_msg=self._summary._logger_msg,
                    debug_mode=self.args.debug,
                    dryrun_mode=self.args.dry_run,
                )
                self._mie_metrics.check_missing()
                if self.args.dry_run:
                    self.logger.info(
                        f"[DRY_RUN] - {self._summary._logger_msg}: MIE metrics log file | '{mie_metrics_file}'"
                    )
            else:
                self._existing_metrics_log_file = mie_metrics_file_exists
        else:
            self._existing_metrics_log_file = self._mie_vcf.file_exists

    def find_pedigree_file(self) -> None:
        """
        Create the .PED output file for Trio, if it doesn't exist.
        """
        pedigree_lines = [
            "# PED format pedigree for RTG-tools",
            "# NOTE: For Sex column, Female=2, Male=1, Unknown=0",
            "## FamilyID IndvID PaternalID MaternalID Sex Pheno",
            f"{self._trio_name} {self._motherID} 0 0 2 0",
            f"{self._trio_name} {self._fatherID} 0 0 1 0",
            f"{self._trio_name} {self._childID} {self._fatherID} {self._motherID} {self._child_sex} 0",
        ]

        self._pedigree = WriteFiles(
            path_to_file=str(self._input_path),
            file=f"{self._trio_name}.PED",
            logger=self.logger,
            logger_msg=self._summary._logger_msg,
            debug_mode=self.args.debug,
            dryrun_mode=self.args.dry_run,
        )
        self._pedigree.check_missing()
        if not self._pedigree.file_exists:
            if self.args.dry_run:
                self.logger.info(
                    f"[DRY_RUN] - {self._summary._logger_msg}: missing the Trio pedigree file..."
                )
            self._pedigree.write_list(pedigree_lines)
        else:
            self.logger.info(
                f"{self._summary._logger_msg}: the Trio pedigree file already exists... SKIPPING AHEAD"
            )

    def convert(self, input: str, output: str, vcf_to_bcf: bool = True) -> None:
        """
        Speed up merging by converting any vcf inputs that are missing a bcf companion.
        """
        if vcf_to_bcf:
            output_type = "b"
            self.logger.info(
                f"{self._summary._logger_msg}: using 'bcftools convert' to create a BCF | '{output}'",
            )
        else:
            output_type = "z"
            self.logger.info(
                f"{self._summary._logger_msg}: using 'bcftools convert' to create a VCF | '{output}'",
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

        cmd_string = " ".join(convert_cmd)
        self._summary._command_list.append(cmd_string)

    def find_input_vcfs(self) -> None:
        """
        Confirm that the Trio's VCF files in the metadata file exist.
        """
        if self._trio_vcf.file_exists:
            self._missing_merge_inputs = False
            self.logger.info(
                f"{self._summary._logger_msg}: the merged Trio VCF already exists... SKIPPING AHEAD"
            )
        else:
            # If we are creating a Family VCF from merging,
            if self._merge_inputs:
                self.logger.info(
                    f"{self._summary._logger_msg}: merging (3) individual files into the Trio VCF | '{self._trio_vcf.file}'"
                )
                # Identify the individual VCFs required that will be merged.
                missing_files = []

                if (
                    self._summary._data_list[self._summary._index]["file_path"]
                    and self._summary._data_list[self._summary._index + 1]["file_path"]
                    and self._summary._data_list[self._summary._index + 2]["file_path"]
                ):
                    # Child ---
                    self._child_vcf = TestFile(
                        self._summary._data_list[self._summary._index]["file_path"],
                        self.logger,
                    )
                    self._child_vcf.check_existing(
                        logger_msg=self._summary._logger_msg, debug_mode=self.args.debug
                    )

                    # Father ---
                    self._father_vcf = TestFile(
                        self._summary._data_list[self._summary._index + 1]["file_path"],
                        self.logger,
                    )
                    self._father_vcf.check_existing(
                        logger_msg=self._summary._logger_msg, debug_mode=self.args.debug
                    )

                    # Mother ---
                    self._mother_vcf = TestFile(
                        self._summary._data_list[self._summary._index + 2]["file_path"],
                        self.logger,
                    )
                    self._mother_vcf.check_existing(
                        logger_msg=self._summary._logger_msg, debug_mode=self.args.debug
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
                            f"{self._summary._logger_msg}: missing the following [REQUIRED] input files |"
                        )
                        for i, f in enumerate(missing_files):
                            print(f"\t({i+1}) '{f}'")

                        # NOTE: Errors are handled in process_sample()
                    else:
                        self._missing_merge_inputs = False

            # Determine if we need to convert the existing Family BCF to a VCF...
            else:
                self._missing_merge_inputs = False
                self.logger.info(
                    f"{self._summary._logger_msg}: missing the Trio VCF..."
                )
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

        renaming_file = WriteFiles(
            path_to_file=str(self._input_path),
            file=f"{sample_name}.rename",
            logger=self.logger,
            logger_msg=self._summary._logger_msg,
            debug_mode=self.args.debug,
            dryrun_mode=self.args.dry_run,
        )
        renaming_file.check_missing()
        if not renaming_file._file_exists:
            if self.args.dry_run:
                self.logger.info(
                    f"[DRY_RUN] - {self._summary._logger_msg}: missing the  'bcftools reheader' input file | '{sample_name}.rename'"
                )
            renaming_file.write_list(_lines)
        else:
            self.logger.info(
                f"{self._summary._logger_msg}: the 'bcftools reheader' file already exists... SKIPPING AHEAD"
            )

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

        if sampleID not in giab_samples.keys():
            return input

        if (
            giab_samples[sampleID] not in self._clean_filename.name
            and sampleID not in self._clean_filename.name
        ):
            self.logger.error(
                f"{self._summary._logger_msg}: unable to find '{giab_samples[sampleID]}' or '{sampleID}' in '{self._clean_filename.name}'"
            )
            self.logger.error(
                f"{self._summary._logger_msg}: re-naming error\nExiting..."
            )
            exit(1)

        if "giab" in self._summary._caller.lower():
            self.logger.info(
                f"{self._summary._logger_msg}: sample name will be updated | '{sampleID}'"
            )
            self.find_renaming_file(sample_name=sampleID)
            input_path = Path(input)
            stem = input_path.stem
            suffix = Path(stem).suffix
            output = f"{self._clean_filename}.renamed{suffix}.gz"
            new_vcf = TestFile(output, self.logger)
            new_vcf.check_existing(
                logger_msg=self._summary._logger_msg, debug_mode=self.args.debug
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
                cmd_string = " ".join(reheader_cmd)
                self._summary._command_list.append(cmd_string)
            return output
        else:
            return input

    def find_indexed_inputs(self, input: Union[None, str] = None) -> None:
        """
        Find any existing CSI files for the Trio, or create them.
        """
        if input is None:
            output = f"{self._clean_filename}.bcf.gz.csi"
        else:
            output = f"{input}.csi"

        _bcf_index = TestFile(file=output, logger=self.logger)
        _bcf_index.check_existing(
            logger_msg=self._summary._logger_msg, debug_mode=self.args.debug
        )
        if not _bcf_index.file_exists:
            output_path = Path(output)
            input_path = Path(output_path.parent)
            input_name = output_path.stem
            self.logger.info(
                f"{self._summary._logger_msg}: using 'bcftools index' to create .CSI index file | '{input_path}/{input_name}.csi'",
            )

            index_cmd = [
                "bcftools",
                "index",
                f"{input_path}/{input_name}",
            ]
            cmd_string = " ".join(index_cmd)
            self._summary._command_list.append(cmd_string)

    def find_input_bcfs(
        self, vcf_path: Union[Path, None] = None, index: Union[int, None] = None
    ) -> None:
        """
        Find any existing BCF files for the Trio, or create them.
        """
        # If a Family BCF is missing,
        if vcf_path is not None and index is not None and self._merge_inputs:
            # Determine if indvidual BCF files exist
            self._clean_filename = remove_suffixes(vcf_path)
            _bcf = TestFile(file=f"{self._clean_filename}.bcf.gz", logger=self.logger)
            _bcf.check_existing(
                logger_msg=self._summary._logger_msg, debug_mode=self.args.debug
            )

            if not _bcf.file_exists:
                self.convert(input=str(vcf_path), output=_bcf.file, vcf_to_bcf=True)
            else:
                self.logger.info(
                    f"{self._summary._logger_msg}: individual BCF '{_bcf.file}' already exists... SKIPPING AHEAD"
                )

            if index == 0:
                bcf_renamed = self.rename(input=_bcf.file, sampleID=self._childID)
                if bcf_renamed != _bcf.file:
                    _bcf = TestFile(file=bcf_renamed, logger=self.logger)
                    _bcf.check_existing(
                        logger_msg=self._summary._logger_msg, debug_mode=self.args.debug
                    )
                self.find_indexed_inputs(input=_bcf.file)
                self._child_bcf = _bcf
            elif index == 1:
                bcf_renamed = self.rename(input=_bcf.file, sampleID=self._fatherID)
                if bcf_renamed != _bcf.file:
                    _bcf = TestFile(file=bcf_renamed, logger=self.logger)
                    _bcf.check_existing(
                        logger_msg=self._summary._logger_msg, debug_mode=self.args.debug
                    )
                self.find_indexed_inputs(input=_bcf.file)
                self._father_bcf = _bcf
            elif index == 2:
                bcf_renamed = self.rename(input=_bcf.file, sampleID=self._motherID)
                if bcf_renamed != _bcf.file:
                    _bcf = TestFile(file=bcf_renamed, logger=self.logger)
                    _bcf.check_existing(
                        logger_msg=self._summary._logger_msg, debug_mode=self.args.debug
                    )
                self.find_indexed_inputs(input=_bcf.file)
                self._mother_bcf = _bcf

        # Confirm a Family BCF File already exists...
        else:
            self._trio_bcf = TestFile(
                f"{self._input_path}/{self._input_filename}", self.logger
            )
            self._trio_bcf.check_existing(
                logger_msg=self._summary._logger_msg, debug_mode=self.args.debug
            )

            if self._trio_bcf.file_exists:
                self.logger.info(
                    f"{self._summary._logger_msg}: the Trio BCF already exists... SKIPPING AHEAD"
                )
                self._merge_inputs = False
            else:
                self.logger.info(
                    f"{self._summary._logger_msg}: missing the Trio BCF | '{self._trio_bcf.file}'"
                )
                self._merge_inputs = True

    def merge_trio_bcfs(self) -> None:
        """
        Combine the child:father:mother bcfs into a TRIO.VCF.GZ file for RTG-tools.
        """
        if not self._trio_vcf.file_exists:
            self.logger.info(
                f"{self._summary._logger_msg}: using 'bcftools merge' to combine (3) BCFs into a Family VCF | '{self._trio_vcf.file}'",
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
                self._mother_bcf.file,
            ]

            if self._regions_file.file_exists:
                merge_cmd.extend(["--regions-file", self._regions_file.file])
                self.logger.info(
                    f"{self._summary._logger_msg}: using 'bcftools merge' to restrict the Family VCF to the autosomes and X chromosome only | '{self._regions_file.file}'"
                )

            cmd_string = " ".join(merge_cmd)
            self._summary._command_list.append(cmd_string)
            self.find_indexed_inputs(input=self._trio_vcf.file)

    def run_mendelian_errors(self, pass_only: bool = True) -> Union[List[str], None]:
        """
        Use the family VCF file to calculate the number of violations to Mendelian inheritance.
        """

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
            str(self._rtg_tools_path),
            "--pedigree",
            str(self._pedigree.file_path),
        ]

        if not pass_only:
            mendelian_cmd.append("--all-records")

        if self._alter_min_concordance:
            mendelian_cmd.append(f"--min-concordance={self.args.threshold}")

        self.logger.info(
            f"{self._summary._logger_msg}: using 'rtg mendelian' to calculate mendelian errors within | '{self._trio_vcf.file}'",
        )
        cmd_string = " ".join(mendelian_cmd)
        self._summary._command_list.append(cmd_string)

    def make_job(self) -> Union[SBATCH, None]:
        """
        Define the contents of the SLURM job for the rtg-mendelian phase for TrioTrain Pipeline.
        """
        # initialize a SBATCH Object
        self.job_name = f"mie-{self._trio_name}-{self._summary._caller}"
        self.itr.job_dir = Path(self._trio_vcf.file).parent / "jobs"
        self.itr.log_dir = Path(self._trio_vcf.file).parent / "logs"
        if self.args.dry_run:
            self.logger.info(
                f"[DRY_RUN] - [{self._summary._phase}]: JOB DIR | '{self.itr.job_dir}'"
            )
            self.logger.info(
                f"[DRY_RUN] - [{self._summary._phase}]: LOG DIR | '{self.itr.log_dir}'"
            )

        slurm_job = SBATCH(
            self.itr,
            self.job_name,
            self._summary._caller,
            None,
            self._summary._logger_msg,
        )

        if slurm_job.check_sbatch_file():
            if self.overwrite:
                self.itr.logger.info(
                    f"{self._summary._logger_msg}: --overwrite=True, re-writing the existing SLURM job now..."
                )
            else:
                self.itr.logger.info(
                    f"{self._summary._logger_msg}: SLURM job file already exists... SKIPPING AHEAD"
                )
                self._num_skipped += 1
                return
        else:
            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"{self._summary._logger_msg}: creating file job now... "
                )

        slurm_job.create_slurm_job(
            None,
            command_list=self._summary._command_list,
            overwrite=self.overwrite,
            **self._slurm_resources[self._summary._phase],
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
            self._summary._logger_msg,
        )

        submit_slurm_job.build_command(
            prior_job_number=self.itr.current_genome_dependencies
        )
        submit_slurm_job.display_command(
            current_job=(self._num_submitted + 1),
            total_jobs=int(self._total_lines / 3),
            display_mode=self.itr.dryrun_mode,
            debug_mode=self.itr.debug_mode,
        )

        if self.itr.dryrun_mode:
            self._job_nums.append(generate_job_id())
            self._num_submitted += 1
        else:
            submit_slurm_job.get_status(debug_mode=self.itr.debug_mode)

            if submit_slurm_job.status == 0:
                self._num_submitted += 1
                self._job_nums.append(submit_slurm_job.job_number)
            else:
                self.logger.error(
                    f"{self._summary._logger_msg}: unable to submit SLURM job",
                )
                self._job_nums.append(None)

    # def check_submission(self) -> None:
    #     """
    #     Check if the SLURM job file was submitted to the SLURM queue successfully
    #     """
    #     if self._num_processed != 0 and self._num_skipped != 0:
    #         completed = self._num_processed + self._num_skipped
    #     elif self._num_processed != 0:
    #         completed = self._num_processed
    #     else:
    #         completed = self._num_skipped

    #     self._summary._logger_msg = f"[{self._summary._phase}]"
    #     # look at job number list to see if all items are 'None'
    #     _results = check_if_all_same(self._job_nums, None)
    #     if _results is False:
    #         self.logger.info(
    #             f"{self._summary._logger_msg}: submitted {self._num_submitted}-of-{int(self._total_lines/3)} jobs"
    #         )
    #         if self.args.dry_run:
    #             print(
    #                 f"============ [DRY RUN] - {self._summary._logger_msg} Job Numbers - {self._job_nums} ============"
    #             )
    #         else:
    #             print(
    #                 f"============ {self._summary._logger_msg} Job Numbers - {self._job_nums} ============"
    #             )
    #     elif completed == int(self._total_lines / 3):
    #         self.logger.info(
    #             f"{self._summary._logger_msg}: no SLURM jobs were submitted... SKIPPING AHEAD"
    #         )
    #     elif self.itr.debug_mode and completed == self._itr:
    #         self.logger.debug(
    #             f"{self._summary._logger_msg}: no SLURM jobs were submitted... SKIPPING AHEAD"
    #         )
    #     else:
    #         self.logger.warning(
    #             f"{self._summary._logger_msg}: expected SLURM jobs to be submitted, but they were not",
    #         )
    #         self.logger.warning(
    #             f"{self._summary._logger_msg}: fatal error encountered, unable to proceed further with pipeline.\nExiting... ",
    #         )
    #         exit(1)

    #     self.logger.info(
    #         f"[{self._summary._phase}]: processed {completed}-of-{int(self._total_lines/3)} Trios from '{str(self._summary._metadata_input)}'"
    #     )

    # def handle_mie_data(self, input: Union[list, TextIO]) -> None:
    #     """
    #     Parse out summary info from the string output.
    #     """
    #     variants_analyzed = None
    #     num_errors = None
    #     numerator = None
    #     denominator = None
    #     results_dict = {}

    #     if self.args.debug:
    #         self.logger.debug(
    #             f"{self._summary._logger_msg}: reading in a file | '{self._mie_metrics.file_path}'",
    #         )

    #     for row in input:
    #         if "violation of Mendelian constraints" in row:
    #             MIE = row.strip()
    #             MIE_parts = MIE.split(" ")[0].split("/")
    #             num_errors = int(MIE_parts[0])
    #             variants_analyzed = int(MIE_parts[1])

    #         if "concordance" in row.lower() and "incorrect pedigree" not in row.lower():
    #             self._concordance_msg = row.strip()
    #             concordance_parts = self._concordance_msg.split(" ")
    #             trio_concordance_messy = concordance_parts[-1]
    #             self._trio_concordance_clean = float(
    #                 sub(r"[()%]", "", trio_concordance_messy)
    #             )

    #             # sanity check
    #             trio_con_parts = concordance_parts[8].split("/")
    #             denominator = int(trio_con_parts[1])
    #             match = self._summary._digits_only.search(trio_con_parts[0])
    #             if match:
    #                 numerator = int(match.group())
    #                 trio_con = round(numerator / denominator * 100, ndigits=2)
    #                 if self._trio_concordance_clean == trio_con:
    #                     results_dict["trio_concordance"] = f"{trio_con:.2f}%"
    #                     if trio_con >= self.args.threshold and self.args.dry_run:
    #                         self.logger.info(
    #                             f"[DRY_RUN] - {self._summary._logger_msg}: Trio Concordance ({self._trio_concordance_clean}%) meets Threshold ({self.args.threshold:.2f}%)"
    #                         )
    #                 else:
    #                     self.logger.error(
    #                         f"{self._summary._logger_msg}: trio concordance math error | expected: {self._trio_concordance_clean}%, but got {trio_con}\nExiting..."
    #                     )
    #                     exit(1)

    #         elif "incorrect pedigree" in row.lower():
    #             self.logger.warning(
    #                 f"{self._summary._logger_msg}: {self._concordance_msg}"
    #             )
    #             self.logger.warning(
    #                 f"{self._summary._logger_msg}: Trio Concordance ({self._trio_concordance_clean}%) does not meet Threshold ({self.args.threshold:.2f}%)"
    #             )
    #             continue

    #     if variants_analyzed is not None and num_errors is not None:
    #         results_dict["variants_analyzed"] = str(variants_analyzed)
    #         results_dict["num_mendelian_errors"] = str(num_errors)
    #         results_dict["mendelian_error_rate"] = (
    #             f"{num_errors/variants_analyzed * 100:.2f}%"
    #         )

    #     # merge the user-provided metadata with sample_stats
    #     self._summary._sample_stats = {
    #         **self._summary._pickled_data.sample_metadata,
    #         **results_dict,
    #     }

    #     # save the merged data in a dict of dicts with _num_processed as the index
    #     self._num_processed += 1
    #     self._summary._output_lines[self._num_processed] = self._summary._sample_stats

    #     if self.args.dry_run:
    #         if self._index < 1:
    #             self.logger.info(
    #                 f"[DRY RUN] - {self._summary._logger_msg}: pretending to add header + row to a CSV | '{self.args.outpath}'"
    #             )
    #             print("---------------------------------------------")
    #             print(",".join(self._summary._sample_stats.keys()))
    #         else:
    #             self.logger.info(
    #                 f"[DRY RUN] - {self._summary._logger_msg}: pretending to add a row to a CSV | '{self.args.outpath}'"
    #             )
    #     self._summary._vcf_file = self._trio_vcf
    #     self._summary.write_output(unique_records_only=True)

    def process_sample(self, itr: int, row_data: Dict[str, str]) -> None:
        """ """
        if self._summary._command_list:
            self._summary._command_list.clear()

        self._summary._index = itr
        self._summary._data = row_data
        self._summary._get_sample_stats = False

        found_trio_vcf = self._summary.find_trio_vcf()

        if found_trio_vcf:
            self._merge_inputs = False
        else:
            self._merge_inputs = True

        if self._summary._missing_pedigree_data:
            print("SKIPPING DUE TO LACK OF PEDIGREE")
            return
        else:
            valid_trio = self.define_trio()
            if not valid_trio:
                return

            self.find_input_file()
            self.find_trio_num(self._trio_name)

            self.logger.info(
                f"{self._summary._logger_msg}: ========== INDEX: {self._summary._index} | CHILD: {self._childID} | FATHER: {self._fatherID} | MOTHER: {self._motherID} =========="
            )

            self.itr = Iteration(
                current_trio_num=self._trio_num,
                logger=self.logger,
                args=self.args,
            )

            self.find_mie_outputs()

            if self.args.all:
                self.find_mie_outputs(pass_only=False)

            if self._existing_metrics_log_file:
                if self._mie_metrics._file_exists:
                    with open(self._mie_metrics.file_path, "r") as data:
                        self.handle_mie_data(input=data)
            else:
                if self.args.debug:
                    self.logger.debug(
                        f"[{self._summary._phase}]: SUFFIX | '{self._filetype}'"
                    )

                self.find_pedigree_file()

                if self._filetype == ".bcf":
                    self.find_input_bcfs()

                self.find_input_vcfs()

                if self._missing_merge_inputs:
                    self.logger.warning(
                        f"{self._summary._logger_msg}: input files must exist before a SLURM job can be submitted... SKIPPING AHEAD"
                    )
                    self._num_skipped += 1
                    return
                else:
                    if self._merge_inputs and not self._trio_vcf.file_exists:
                        for index, indv in enumerate(self._vcf_inputs):
                            self.find_input_bcfs(vcf_path=indv.path, index=index)

                        self.merge_trio_bcfs()

                    self.run_mendelian_errors()
                    if self.args.all:
                        self.run_mendelian_errors(pass_only=False)

                    # self.submit_job()

    def process_multiple_samples(self) -> None:
        """
        Iterate through multiple VCF files
        """
        itr = 0
        if self.args.debug:
            itr_list = self._summary._data_list[:4]
        else:
            itr_list = self._summary._data_list

        self._total_lines = len(itr_list)

        for i, item in enumerate(itr_list):
            # Do an initial search to identify trio inputs
            self._summary._get_sample_stats = False
            self._summary._index = i
            _stop = self._summary._index + 3
            self._summary._data = self._summary._data_list[self._summary._index:_stop]

            self._summary.process_sample()
            print("TOTAL SAMPLES:", self._summary._pickled_data._total_samples)
            breakpoint()

            self.process_sample(itr=i, row_data=item)
            print("STOPPING NOW!")
            breakpoint()

        if self._num_submitted == 0:
            completed = f"skipped {self._num_skipped}"
        else:
            completed = f"submitted {self._num_submitted}"

        if (self._num_submitted % 5) == 0:
            self.logger.info(
                f"[{self._summary._phase}]: {completed}-of-{self._total_lines} jobs"
            )

            itr += 1
            self._itr = itr

            if self.args.dry_run:
                print(f"[ITR{itr}] ==================================")

        if self.args.debug:
            self.logger.debug(
                f"[{self._summary._phase}]: MIE SUBMITTED = {self._num_submitted}"
            )
            self.logger.debug(
                f"[{self._summary._phase}]: MIE SKIPPED = {self._num_skipped}"
            )
            self.logger.debug(
                f"[{self._summary._phase}]: MIE PROCESSED = {self._num_processed}"
            )
            self.logger.debug(
                f"[{self._summary._phase}]: STATS SUBMITTED = {self._summary._num_submitted}"
            )
            self.logger.debug(
                f"[{self._summary._phase}]: STATS SKIPPED = {self._summary._num_skipped}"
            )
            self.logger.debug(
                f"[{self._summary._phase}]: STATS PROCESSED = {self._summary._num_processed}"
            )
            self.logger.debug(
                f"[{self._summary._phase}]: MIE TOTAL = {self._total_lines}"
            )

        self.check_submission()

    def run(self) -> None:
        """
        Combine all the steps into a single command.
        """
        self._summary.load_variables()
        self._summary.load_metadata()

        # if self.args.post_process:
        # self.process_sample()
        # else:
        self.set_threshold()
        self.find_default_region_file()
        self.find_reference_SDF()
        self.process_multiple_samples()


def __init__() -> None:
    from helpers.utils import get_logger
    from helpers.wrapper import Wrapper, timestamp

    # Collect command line arguments
    args = collect_args(use_mie=True)

    # Collect start time
    Wrapper(__file__, "start").wrap_script(timestamp())

    # Create error log
    current_file = p.basename(__file__)
    module_name = p.splitext(current_file)[0]
    logger = get_logger(module_name)

    try:
        # Check command line args
        check_args(args, logger, use_mie=True)
        MIE(args, logger).run()
    except AssertionError as E:
        logger.error(E)

    Wrapper(__file__, "end").wrap_script(timestamp())


# Execute functions created
if __name__ == "__main__":
    __init__()
