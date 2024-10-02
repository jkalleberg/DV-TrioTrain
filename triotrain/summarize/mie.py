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
from helpers.files import TestFile, Files
from helpers.iteration import Iteration
from helpers.outputs import check_if_output_exists
from model_training.slurm.suffix import remove_suffixes
from summarize.summary import Summary


@dataclass
class MIE:
    """
    Define what data to keep when calculating Mendelian inheritance errors with TrioVCFs.
    """

    # Required parameters
    args: argparse.Namespace
    logger: Logger

    # Optional values
    run_iteractively: bool = False

    # Internal, imutable values
    _job_nums: List = field(default_factory=list, repr=False, init=False)
    _num_processed: int = field(default=0, init=False, repr=False)
    _num_skipped: int = field(default=0, init=False, repr=False)
    _num_submitted: int = field(default=0, init=False, repr=False)
    _total_lines: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        self._summary = Summary(self.args, self.logger)
        self._summary._phase = "mie"

        if self.args.dry_run:
            self._status = "pretending to use"
        else:
            self._status = "using"

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
                f"{self._summary._logger_msg}: MIE metrics will be constrained by the default region file | '{self._regions_file.file}'"
            )
            return
        else:
            self.logger.error(
                f"{self._summary._logger_msg}: missing a valid regions file | '{self._regions_file.file}'\nExiting..."
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
            # When run interactively as a sub-process, don't include conda
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
                        f"{self._summary._logger_msg}: command used | '{command_str}'"
                    )
                    self.logger.error(f"{self._summary._logger_msg}: {result.stdout}")
                    raise ChildProcessError(f"unable to complete 'rtg format'")
            except CalledProcessError or ChildProcessError as e:
                self.logger.error(
                    f"{self._summary._logger_msg}: command used | '{command_str}'"
                )
                self.logger.error(f"{self._summary._logger_msg}: {e}")
                self.logger.error(
                    f"{self._summary._logger_msg}: unable to format the .FASTA into SDF required by rtg tools.\nExiting..."
                )

        else:
            self.logger.info(
                f"{self._summary._logger_msg}: found existing SDF for 'rtg mendelian'  | '{_sdf_summary_file.file}'"
            )

        # Rtg tools requires a "reference.txt" file to exists AFTER formatting the FASTA into SDF
        _rtg_ref_path = self._rtg_tools_path / "reference.txt"
        _rtg_reference_file = TestFile(file=f"{_rtg_ref_path}", logger=self.logger)
        _rtg_reference_file.check_existing()

        if self.args.par is not None:
            if _rtg_reference_file.file_exists:
                self.logger.info(
                    f"{self._summary._logger_msg}: found existing 'reference.txt' for 'rtg mendelian'  | '{_rtg_reference_file.file}'"
                )
                self.logger.warning(
                    f"{self._summary._logger_msg}: therefore, user input file will be ignored | '{self.args.par}'"
                )
            elif not _rtg_reference_file.file_exists:
                _input_rtg_reference_file = TestFile(
                    file=self.args.par, logger=self.logger
                )
                _input_rtg_reference_file.check_existing()
                if _input_rtg_reference_file.file_exists:
                    self.logger.info(
                        f"{self._summary._logger_msg}: creating a copy of 'reference.txt' for 'rtg mendelian'  | '{_rtg_reference_file.file}'"
                    )
                    source = Path(_input_rtg_reference_file.file)
                    destination = Path(_rtg_reference_file.file)
                    destination.write_text(source.read_text())
                else:
                    self.logger.error(
                        f"{self._summary._logger_msg}: missing an input file for 'rtg mendelian'  | '{_input_rtg_reference_file.file}'\nExiting..."
                    )
                    exit(1)

        else:
            if not _rtg_reference_file.file_exists:
                self.logger.warning(
                    f"{self._summary._logger_msg}: missing a required input file | '{_rtg_reference_file.file}'"
                )
                self.logger.warning(
                    f"{self._summary._logger_msg}: for non-human reference genomes, this file must be created MANUALLY.\nSee RTG Documentation for details.\nTrioTrain includes a template from GRCh38 here | './triotrain/variant_calling/data/GIAB/reference/rtg_tools/reference.txt'"
                )
                exit(1)

    def find_merged_file(self) -> None:
        """
        Identify the Family VCF, and confirm it exists.
        """
        self._trio_path = (
            Path(self._summary._pickled_data._input_file.path.parent.parent) / "TRIOS"
        )
        if not self._trio_path.exists():
            if self.args.dry_run:
                self.logger.info(
                    f"{self._summary._logger_msg}: pretending to create a new directory | '{self._trio_path}'"
                )
            else:
                self.logger.info(
                    f"{self._summary._logger_msg}: creating a new directory | '{self._trio_path}'"
                )
                self._trio_path.mkdir(parents=True)
        
        self._trio_vcf = TestFile(
            f"{self._trio_path}/{self._summary._pickled_data._ID}.vcf.gz",
            self.logger,
        )
        self._trio_vcf.check_existing()
        if self.args.debug:
            self.logger.debug(
                f"{self._summary._logger_msg}: TRIO VCF_FILE | '{self._trio_vcf.file}'"
            )

    def find_mie_outputs(self, pass_only: bool = True) -> None:
        """
        Determine if 'rtg-tools mendelian' needs to be run.
        """
        trio_filename = remove_suffixes(self._trio_vcf.path)
        self._log_dir = self._trio_path / "logs"

        if not self._log_dir.exists():
            if self.args.dry_run:
                self.logger.info(
                    f"{self._summary._logger_msg}: pretending to create a new directory | '{self._log_dir}'"
                )
            else:
                self.logger.info(
                    f"{self._summary._logger_msg}: creating a new directory | '{self._log_dir}'"
                )
                self._log_dir.mkdir(parents=True)

        if pass_only:
            mie_vcf_file = Path(f"{trio_filename}.PASS.MIE")
        else:
            mie_vcf_file = Path(f"{trio_filename}.ALL.MIE")

        self._mie_vcf = Files(
            path_to_file=mie_vcf_file.parent / f"{mie_vcf_file.name}.vcf.gz",
            logger=self.logger,
            logger_msg=self._summary._logger_msg,
            debug_mode=self.args.debug,
            dryrun_mode=self.args.dry_run,
        )
        self._mie_vcf.check_status()

        if self._mie_vcf.file_exists:
            self.logger.info(
                f"{self._summary._logger_msg}: the MIE VCF already exists... SKIPPING AHEAD"
            )
            if self.args.debug:
                self.logger.debug(
                    f"{self._summary._logger_msg}: rtg-tools MIE VCF | '{self._mie_vcf.path_str}'"
                )

            mie_regex = compile(rf"mie-{self._summary._pickled_data._ID}.log")

            mie_metrics_file_exists, num_found, files_found = check_if_output_exists(
                match_pattern=mie_regex,
                file_type="a MIE log file",
                search_path=self._log_dir,
                msg=self._summary._logger_msg,
                logger=self.logger,
                debug_mode=self.args.debug,
            )

            if mie_metrics_file_exists and num_found == 1:
                self._existing_metrics_log_file = mie_metrics_file_exists
                mie_metrics_file = self._log_dir / str(files_found[0])

                self._mie_metrics = Files(
                    path_to_file=mie_metrics_file.parent / mie_metrics_file.name,
                    logger=self.logger,
                    logger_msg=self._summary._logger_msg,
                    debug_mode=self.args.debug,
                    dryrun_mode=self.args.dry_run,
                )
                self._mie_metrics.check_status()
                if self._mie_metrics.file_exists:
                    self.logger.info(
                        f"{self._summary._logger_msg}: the MIE log file already exists... SKIPPING AHEAD"
                    )
                if self.args.debug:
                    self.logger.debug(
                        f"{self._summary._logger_msg}: MIE metrics log file | '{mie_metrics_file}'"
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
            f"{self._summary._pickled_data._ID} {self._summary._pickled_data._motherID} 0 0 2 0",
            f"{self._summary._pickled_data._ID} {self._summary._pickled_data._fatherID} 0 0 1 0",
            f"{self._summary._pickled_data._ID} {self._summary._pickled_data._childID} {self._summary._pickled_data._fatherID} {self._summary._pickled_data._motherID} {self._summary._pickled_data._child_sex} 0",
        ]

        self._pedigree = Files(
            path_to_file=self._trio_path / f"{self._summary._pickled_data._ID}.PED",
            logger=self.logger,
            logger_msg=self._summary._logger_msg,
            debug_mode=self.args.debug,
            dryrun_mode=self.args.dry_run,
        )
        self._pedigree.check_status()
        if not self._pedigree.file_exists:
            if self.args.dry_run:
                self.logger.info(
                    f"{self._summary._logger_msg}: missing the Trio pedigree file..."
                )
            self._pedigree.write_list(pedigree_lines)
        else:
            self.logger.info(
                f"{self._summary._logger_msg}: the Trio pedigree file already exists... SKIPPING AHEAD"
            )

    def convert(
        self, input: Union[str, Path], output: Union[str, Path], vcf_to_bcf: bool = True
    ) -> None:
        """
        Speed up merging by converting any vcf inputs that are missing a bcf companion.
        """
        if vcf_to_bcf:
            status = "VCF -> BCF"
            output_type = "b"
            self.logger.info(
                f"{self._summary._logger_msg}: {self._status} 'bcftools convert' to create a BCF | '{output}'",
            )
        else:
            status = "BCF -> VCF"
            output_type = "z"
            self.logger.info(
                f"{self._summary._logger_msg}: {self._status} 'bcftools convert' to create a VCF | '{output}'",
            )

        convert_cmd = [
            "bcftools",
            "convert",
            "--output-type",
            output_type,
            "--output",
            str(output),
            str(input),
        ]

        cmd_string = " ".join(convert_cmd)
        self._summary._command_list.append(
            f'echo $(date) "- [INFO]: converting {status} | {Path(output).name}"'
        )
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
                    input=self._trio_bcf.file,
                    output=self._trio_vcf.file,
                    vcf_to_bcf=False,
                )

    def find_renaming_file(self, sample_name: str) -> None:
        """
        Create a text output file to add a unique sampleID to a vcf, if it doesn't exist.
        """
        _lines = [f"{sample_name}"]

        renaming_file = Files(
            path_to_file=self._trio_path / f"{sample_name}.rename",
            logger=self.logger,
            logger_msg=self._summary._logger_msg,
            debug_mode=self.args.debug,
            dryrun_mode=self.args.dry_run,
        )
        renaming_file.check_status()
        if not renaming_file._file_exists:
            if self.args.dry_run:
                self.logger.info(
                    f"{self._summary._logger_msg}: missing the  'bcftools reheader' input file | '{renaming_file.file_name}'"
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
        # Requiring re-naming to work correctly!
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

        if "giab" in self._summary._pickled_data._caller.lower():
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
                f"{self._trio_path}/{sampleID}.rename",
                "--output",
                output,
                input,
            ]

            if not new_vcf.file_exists:
                cmd_string = " ".join(reheader_cmd)
                self._summary._command_list.append(
                    f'echo $(date)" - [INFO]: updating sample name | {sampleID}={giab_samples[sampleID]}"'
                )
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
                f"{self._summary._logger_msg}: {self._status} 'bcftools index' to create .CSI index file | '{input_path}/{input_name}.csi'",
            )

            index_cmd = [
                "bcftools",
                "index",
                f"{input_path}/{input_name}",
            ]
            cmd_string = " ".join(index_cmd)
            self._summary._command_list.append(
                f'echo $(date)" - [INFO]: creating index | {input_name}.csi"'
            )
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
                    f"{self._summary._logger_msg}: individual BCF '{_bcf.path}' already exists... SKIPPING AHEAD"
                )

            if index == 0:
                bcf_renamed = self.rename(
                    input=_bcf.file, sampleID=self._summary._pickled_data._childID
                )
                if bcf_renamed != _bcf.file:
                    _bcf = TestFile(file=bcf_renamed, logger=self.logger)
                    _bcf.check_existing(
                        logger_msg=self._summary._logger_msg, debug_mode=self.args.debug
                    )
                self.find_indexed_inputs(input=_bcf.file)
                self._child_bcf = _bcf
            elif index == 1:
                bcf_renamed = self.rename(
                    input=_bcf.file, sampleID=self._summary._pickled_data._fatherID
                )
                if bcf_renamed != _bcf.file:
                    _bcf = TestFile(file=bcf_renamed, logger=self.logger)
                    _bcf.check_existing(
                        logger_msg=self._summary._logger_msg, debug_mode=self.args.debug
                    )
                self.find_indexed_inputs(input=_bcf.file)
                self._father_bcf = _bcf
            elif index == 2:
                bcf_renamed = self.rename(
                    input=_bcf.file, sampleID=self._summary._pickled_data._motherID
                )
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
                f"{self._trio_path}/{self._input_filename}",
                self.logger,
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
        Use BCFtools to combine the child:father:mother bcfs into a TRIO.VCF.GZ file for RTG-tools.
        
        Not using GLNexus because it adds yet another docker container, and also a 'CaptureBED' file?
        """
        if not self._trio_vcf.file_exists:
            self.logger.info(
                f"{self._summary._logger_msg}: {self._status} 'bcftools merge' to combine (3) BCFs into a Family VCF | '{self._trio_vcf.file}'",
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
                    f"{self._summary._logger_msg}: {self._status} 'bcftools merge' to restrict the Family VCF to the autosomes and X chromosome only | '{self._regions_file.file}'"
                )

            cmd_string = " ".join(merge_cmd)
            self._summary._command_list.append(
                f'echo $(date)" - [INFO]: merging individual VCFs into Family VCF | {self._trio_vcf.path.name}"'
            )
            self._summary._command_list.append(cmd_string)
            self.find_indexed_inputs(input=self._trio_vcf.file)

    def run_mendelian_errors(self, pass_only: bool = True) -> Union[List[str], None]:
        """
        Use the family VCF file to calculate the number of violations to Mendelian inheritance.
        
        Per the manual: 'By default, only VCF records with the FILTER field set to PASS or missing are processed. 
                        All variant records can be examined by specifying the --all-records parameter.'
        """
        mendelian_cmd = [
            "rtg",
            "mendelian",
            "--input",
            self._trio_vcf.file,
            "--output",
            self._mie_vcf.path_str,
            "--template",
            str(self._rtg_tools_path),
            "--pedigree",
            self._pedigree.path_str,
        ]

        if not pass_only:
            mendelian_cmd.append("--all-records")

        if self._alter_min_concordance:
            mendelian_cmd.append(f"--min-concordance={self.args.threshold}")

        # Save command line output to a separate file
        _mie_output = self._log_dir / f"mie-{self._summary._pickled_data._ID}.log"
        mendelian_cmd.append(f"> {str(_mie_output)}")

        self.logger.info(
            f"{self._summary._logger_msg}: {self._status} 'rtg mendelian' to calculate mendelian errors within | '{self._trio_vcf.path.name}'",
        )
        cmd_string = " ".join(mendelian_cmd)
        self._summary._command_list.append(
            f"echo $(date)\" - [INFO]: calculating mendelian errors with 'rtg-tools' | {self._trio_vcf.path.name}\""
        )
        self._summary._command_list.append(cmd_string)

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
                f"{self._summary._logger_msg}: reading in a file | '{self._mie_metrics.file_path}'",
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

                # Sanity check
                trio_con_parts = concordance_parts[8].split("/")
                denominator = int(trio_con_parts[1])
                if denominator == 0:
                    self.logger.info(
                        f"{self._summary._logger_msg}: unable to calculate Trio Concordance, error occurred during 'rtg-mendelian'\nExiting..."
                    )
                    exit(1)
                match = self._summary._pickled_data._digits_only.search(
                    trio_con_parts[0]
                )
                if match:
                    numerator = int(match.group())
                    trio_con = round(numerator / denominator * 100, ndigits=2)
                    if self._trio_concordance_clean == trio_con:
                        results_dict["trio_concordance"] = f"{trio_con:.2f}%"
                        if trio_con >= self.args.threshold:
                            self.logger.info(
                                f"{self._summary._logger_msg}: Trio Concordance ({self._trio_concordance_clean}%) meets Threshold ({self.args.threshold:.2f}%)"
                            )
                    else:
                        self.logger.error(
                            f"{self._summary._logger_msg}: trio concordance math error | expected: {self._trio_concordance_clean}%, but got {trio_con}\nExiting..."
                        )
                        exit(1)

            elif "incorrect pedigree" in row.lower():
                self.logger.warning(
                    f"{self._summary._logger_msg}: {self._concordance_msg}"
                )
                self.logger.warning(
                    f"{self._summary._logger_msg}: Trio Concordance ({self._trio_concordance_clean}%) does not meet Threshold ({self.args.threshold:.2f}%)"
                )
                continue

        if variants_analyzed is not None and num_errors is not None:
            results_dict["variants_analyzed"] = str(variants_analyzed)
            results_dict["num_mendelian_errors"] = str(num_errors)
            results_dict["mendelian_error_rate"] = (
                f"{num_errors/variants_analyzed * 100:.2f}%"
            )

        _mie_metrics = [results_dict]
        # Merge the user-provided metadata with sample_stats
        self._summary._pickled_data.add_metadata(messy_metrics=_mie_metrics)

        # Save the merged data in a dict of dicts with _num_processed as the index
        self._num_processed += 1
        self._summary._vcf_file = self._trio_vcf
        self._summary._pickled_data.output_file.logger_msg = self._summary._logger_msg
        self._summary._pickled_data.write_output(
            unique_records_only=True, data_type="mie"
        )

    def process_trio(
        self, itr: Union[int, None] = None, row_data: Union[Dict[str, str], None] = None
    ) -> None:
        """
        add a description!
        """
        if self._summary._command_list:
            self._summary._command_list.clear()

        if itr is not None:
            self._summary._index = itr

        if row_data is not None:
            self._summary._data = row_data
        else:
            self._summary._data = self._summary._pickled_data.sample_metadata
        
        if self._summary._pickled_data._total_samples < 3:
            self.logger.info(
                f"{self._summary._logger_msg}: not a trio... SKIPPING AHEAD"
            )
            return

        if self._summary._pickled_data._missing_merged_vcf:
            self._merge_inputs = True
        else:
            self._merge_inputs = False

        if self._summary._pickled_data._missing_pedigree_data:
            self.logger.info(
                f"{self._summary._logger_msg}: missing pedigree... SKIPPING AHEAD"
            )
            return
        else:
            if not self._summary._pickled_data._contains_valid_trio:
                return

            self.logger.info(
                f"{self._summary._logger_msg}: ========== INDEX: {self._summary._index} | {self._summary._pickled_data._ID} = CHILD: {self._summary._pickled_data._childID} | MOTHER: {self._summary._pickled_data._motherID} | FATHER: {self._summary._pickled_data._fatherID} =========="
            )

            self.find_merged_file()
            self.itr = Iteration(
                current_trio_num=self._summary._pickled_data._trio_num,
                logger=self.logger,
                args=self.args,
            )
            self.find_mie_outputs()

            if "all" in self.args and self.args.all:
                self.find_mie_outputs(pass_only=False)

            if self._existing_metrics_log_file:
                if self._mie_metrics.file_exists:
                    with open(self._mie_metrics.file_path, "r") as data:
                        self.handle_mie_data(input=data)
            else:
                self.find_pedigree_file()
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
                    if "all" in self.args and self.args.all:
                        self.run_mendelian_errors(pass_only=False)

    def process_multiple_samples(self) -> None:
        """
        Iterate through multiple VCF files
        """
        if self.args.debug:
            itr_list = self._summary._data_list[:4]
            self._summary._data_list = itr_list
        else:
            itr_list = self._summary._data_list

        _total_lines = len(itr_list)

        _counter = 0
        for i, item in enumerate(itr_list):
            self._summary._index = i
            _stop = self._summary._index + 3

            # Handle last item in metadata
            if i == (len(itr_list) - 1):
                self._summary._data = self._summary._data_list[self._summary._index]
            # Handle second-to-last item in metadata
            elif _stop > len(itr_list):
                self._summary._data = self._summary._data_list[
                    self._summary._index : -1
                ]
            else:
                self._summary._data = self._summary._data_list[
                    self._summary._index : _stop
                ]

            self._summary.check_sample()
            
            _counter += int(self._summary._pickled_data._contains_valid_trio)
            
            # print("COUNTER:", _counter)

            if self._summary._pickled_data._trio_num is not None:
                _trio_name = f"Trio{self._summary._pickled_data._trio_num}"

            if _counter == 1:
                self.process_trio(itr=i, row_data=item)
                self._job_name = _trio_name

                # Add bcftools +smpl-stats after preparing the TrioVCF
                self._summary.process_sample(pkl_suffix=_trio_name, store_data=True)
                _counter += 1
            else:
                # Add bcftools +smpl-stats for parent samples within a trio
                self._summary.process_sample(pkl_suffix=_trio_name, store_data=True)
                _counter += 1

            
            # Submit to SLURM after all 3 samples processed
            if _counter == 4:
                _counter = 0

                if (
                    self._existing_metrics_log_file
                    and not self.args.overwrite
                    and len(self._summary._command_list) == 0
                ):
                    continue
                else:
                    if self._existing_metrics_log_file and self.args.overwrite:
                        self.logger.info(
                            f"{self._summary._logger_msg}: --overwrite=True; re-submitting SLURM job"
                        )

                    self._summary._slurm_job = self._summary.make_job(
                        job_name=f"post_process.{self._job_name}"
                    )
                    self._summary.submit_job(
                        index=int(self._summary._index / 3), total=int(_total_lines / 3)
                    )
                    self._summary._command_list.clear()
                    self._num_submitted += 1
            elif _counter == 0:
                # Add bcftools +smpl-stats for individual samples
                self._summary.process_sample(store_data=True)
                self._summary._slurm_job = self._summary.make_job(
                    job_name=f"post_process.{self._summary._pickled_data._ID}"
                )
                self._summary.submit_job(index=self._summary._index, total=_total_lines)
                self._summary._command_list.clear()
                self._num_submitted += 1
            else:
                # Don't submit jobs while iterating through a trio
                continue
            print("-------------------------------------------------")
            if self.args.dry_run:
                self.logger.info(f"{self._summary._logger_msg}: pausing for manual review. Press (c) to continue to the next trio.")
                breakpoint()

        self._summary.check_submission()

    def run(self) -> None:
        """
        Combine all the steps into a single command.
        """
        self._summary.load_variables()
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
