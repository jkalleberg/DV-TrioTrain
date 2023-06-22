#!/bin/python3
"""
description: converts a hap.py VCF to an intermediate tab-separated values file.

example:
    from convert_hap.py import Convert
"""
# Load python libraries
import argparse
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import helpers as h
from regex import compile


@dataclass
class Convert:
    """
    Define what data to keep when converting & processing hap.py results.
    """

    # required values
    args: argparse.Namespace
    logger: h.Logger

    # internal, imutable values
    _phase: str = field(default="convert_happy", init=False, repr=False)
    _version: str = field(
        default=str(os.environ.get("BIN_VERSION_DV")), init=False, repr=False
    )

    def __post_init__(self) -> None:
        self.happy_vcf_file_path = Path(self.args.vcf_file)
        self._custom_header = [
            "chromosome",
            "position",
            "truth_label",
            "truth_genotype",
            "truth_variant_type",
            "truth_genotype_class",
            "truth_TiTv_label",
            "test_label",
            "test_genotype",
            "test_variant_type",
            "test_genotype_class",
            "truth_TiTv_label",
        ]

    def set_test_num(self) -> None:
        """
        Detects which test number is being run.
        """
        file = h.remove_suffixes(self.happy_vcf_file_path)
        file_name = Path(file).name
        digits_only = compile(r"\d+")
        match = digits_only.search(file_name)
        if match:
            self._test_num = match.group()
            self._test_name = f"Test{self._test_num}"
        else:
            self._test_num = None
            self._test_name = "Test"
            self.logger.warning(
                f"{self._logger_msg}: unable to find a valid test number"
            )
        self._test_msg = f"{self._test_name.lower()}"

    def set_genome(self) -> None:
        """
        Determines which genome's hap.py results to process.
        """
        # Extract labels from input vcf name
        # Example: '../TRIO_TRAINING_OUTPUTS/TriosRawNoPopBeam/Trio1RawNoPopBeam/compare_Father/happy1-no-flags.vcf.gz'
        self.set_test_num()

        if "variant_calling" in str(self.happy_vcf_file_path).lower():
            self._input_pattern = str(self.happy_vcf_file_path).lower()
            self._train_genome = None
            if "default" in self._input_pattern:
                self._test_vcf_name = f"test{self._test_num}.vcf.gz"
                self._custom_model = False
            else:
                self._test_vcf_name = f"test{self._test_num}.vcf.gz"
                self._custom_model = True
        else:
            self._input_pattern = self.happy_vcf_file_path.parent.stem
            if "Father" in self._input_pattern or "Mother" in self._input_pattern:
                self._train_genome = self._input_pattern.split("_")[1]
                self._test_vcf_name = (
                    f"test{self._test_num}-{self._train_genome}.vcf.gz"
                )
                self._custom_model = True
            else:
                self._train_genome = None
                self._test_vcf_name = f"test{self._test_num}.vcf.gz"
                self._custom_model = False

        ### --- Identify the Current Test Genome --- ###
        # Drop the file extension
        self._input_file = self.happy_vcf_file_path.stem.split(".")[0]
        input_file_list = self._input_file.split("-")
        self._current_comparision_name = input_file_list[0]

        # Grab the genome number only
        # split_nums = re.compile(r"([a-zA-Z]+)([0-9]+)")
        # match = split_nums.match(self._current_comparision_name)
        # if match is not None:
        #     self._test_num = match.groups()[1]

        # else:
        #     self._test_num = None
        #     self._test_name = "Test"

    def load_variables(self) -> None:
        """
        Load in variables from the env file, and define python variables.
        """
        self.env = h.Env(self.args.env_file, self.logger, dryrun_mode=self.args.dry_run)
        env_vars = [
            "RunName",
            "RunOrder",
            "CodePath",
            "ResultsDir",
            f"{self._test_name}TruthVCF_Path",
            f"{self._test_name}TruthVCF_File",
        ]

        if self._custom_model:
            if self._train_genome is None:
                extra_vars = ["RunDir", "RunDir"]
            else:
                extra_vars = [
                    f"{self._train_genome}TestDir",
                    f"{self._train_genome}CompareDir",
                ]
        else:
            extra_vars = ["BaselineModelResultsDir", "BaselineModelResultsDir"]

        var_list = env_vars + extra_vars

        (
            self._run_name,
            self._trio_num,
            code_path,
            self._results_dir,
            self._truth_dir,
            self._truth_file,
            self._test_dir,
            self._compare_dir,
        ) = self.env.load(*var_list)

        if self._custom_model:
            if self._train_genome is None:
                self._mode = "Benchmark"
                self._model_used = f"{self._run_name}"
            else:
                self._mode = f"Trio-{self._train_genome}{self._trio_num}"
                self._model_used = f"{self._run_name}-{self._train_genome}"
        else:
            self._mode = f"Baseline-v{self._version}"
            self._model_used = "default"

        self._test_vcf_file_path = Path(self._test_dir) / self._test_vcf_name
        self._logger_msg = f"[{self._mode}] - [{self._phase}] - [{self._test_msg}]"

        if self.args.species.lower() == "cow":
            self.CHR = list(map(str, range(1, 30))) + ["X", "Y"]
            self.CHR_Order = {k: v for v, k in enumerate(self.CHR)}
        elif self.args.species.lower() == "human":
            self.CHR = list(map(str, range(1, 22))) + ["X", "Y"]
            self.CHR_Order = {k: v for v, k in enumerate(self.CHR)}
        else:
            self.logger.error(
                f"{self._logger_msg}: ADD LOGIC FOR HANDELING DIFFERENT CHR NUMBERS"
            )
            exit(1)

        assert (
            os.getcwd() == code_path
        ), "Run the workflow in the deep-variant/ directory only!"

        if f"{self._train_genome}TestCkptName" in self.env.contents:
            self._checkpoint = self.env.contents[f"{self._train_genome}TestCkptName"]
        elif "BaselineTestCkptName" in self.env.contents:
            self._checkpoint = self.env.contents["BaselineTestCkptName"]
        elif "TestCkptName" in self.env.contents:
            self._checkpoint = self.env.contents["TestCkptName"]
        else:
            self._checkpoint = None

    def find_files(self) -> None:
        """
        Determine which intermediate files need to be made
        """
        # INPUT FILE | TRUTH VCF
        self.truth_vcf = Path(self._truth_dir) / self._truth_file
        assert (
            self.truth_vcf.exists()
        ), f"missing the TruthVCF file | '{self.truth_vcf.name}'"

        # OUTPUT FILE | HAP.PY METRICS IN TSV FORMAT
        self.file_tsv = (
            Path(self._compare_dir) / f"{self._test_name}.converted-metrics.tsv"
        )

        # OUTPUT FILE | INTERMEDIATE METRICS FILE IN CSV FORMAT
        self.interm_file_csv = (
            Path(self._compare_dir) / f"{self._test_name}.processed-metrics.csv"
        )

        self.final_output_file_csv = (
            Path(self._compare_dir) / f"{self._test_name}.total.metrics.csv"
        )

        if (
            self.file_tsv.exists()
            and self.interm_file_csv.exists()
            and self.final_output_file_csv.exists()
        ):
            self.missing_tsv = False
            self.missing_csv = False
            self.missing_output = False
            self.logger.info(
                f"{self._logger_msg}: all output files were created previously and can not be overwritten."
            )
        else:
            if self.file_tsv.exists() is False:
                self.missing_tsv = True
            else:
                self.missing_tsv = False

            if self.interm_file_csv.exists() is False:
                self.missing_csv = True
            else:
                self.missing_csv = False

            if self.final_output_file_csv.exists() is False:
                self.missing_output = True
            else:
                self.missing_output = True

    def convert_to_tsv(self) -> None:
        """
        Run 'bcftools query' as a Python Subprocess, and write the output to an intermediate file.
        """
        # Perform a bcftools query search for all loci within
        #   CALLABLE_REGIONS FILE
        #   Thus dropping all loci/positions which are NOT
        #   contained in the truth regions file
        bcftools_query = subprocess.run(
            [
                "bcftools",
                "query",
                "-f",
                "%CHROM\t%POS[\t%BD\t%GT\t%BVT\t%BLT\t%BI]\n",
                str(self.happy_vcf_file_path),
            ],  # type: ignore
            capture_output=True,
            text=True,
            check=True,
        )

        if self.args.debug:
            self.logger.debug(
                f"{self._logger_msg}: writing TSV metrics file using | '{self.happy_vcf_file_path.name}'"
            )

        if not self.args.dry_run:
            file = open(str(self.file_tsv), mode="w")
            # Add custom header to the new TSV
            file.write("\t".join(self._custom_header[0:]) + "\n")
            file.close()
            contents = open(str(self.file_tsv), mode="a")
            contents.write(bcftools_query.stdout)
            contents.close()
        else:
            self.tsv_format = bcftools_query.stdout.splitlines()

        if self.args.debug:
            self.logger.debug(f"{self._logger_msg}: done converting to TSV file")

    def run(self) -> None:
        """
        Combine all the steps required to proccess results from hap.py into one step.
        """
        self.set_genome()
        self.load_variables()
        self.find_files()

        # Covert the VCF output from Hap.py into a TSV text file
        if self.missing_tsv:
            self.convert_to_tsv()
        else:
            self.logger.info(
                f"{self._logger_msg}: existing intermediate TSV file detected | '{self.file_tsv.name}'... SKIPPING AHEAD"
            )
