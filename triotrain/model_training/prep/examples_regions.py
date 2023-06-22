# /usr/bin/python3
"""
description: creates region BED-format files containing bp-length chromosome samples proportional to the bp-length of each chromosome contained in the reference fasta.

usage:
    from regions_make import MakeRegions
"""
# Load python libraries
import argparse
import os
import subprocess
import sys
from dataclasses import dataclass, field, fields, replace
from logging import Logger
from pathlib import Path
from typing import Dict, List, Union

import pandas as pd
from natsort import natsorted

# get the relative path to the triotrain/ dir
h_path = str(Path(__file__).parent.parent.parent)
sys.path.append(h_path)
import helpers


def collect_args():
    """
    Process the command line arguments
    """
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-e",
        "--env-file",
        dest="env_file",
        help="[REQUIRED]\ninput file (.env)\nprovides environmental variables",
        type=str,
        metavar="</path/file>",
    )
    parser.add_argument(
        "--start-itr",
        dest="restart",
        help="[REQUIRED]\nstart a pipeline at a specified genome iteration.\nExample: to start @ Trio2-Parent1, set --start-itr=3",
        type=int,
        metavar="<int>",
    )
    parser.add_argument(
        "-g",
        "--genome",
        dest="genome",
        choices=["Father", "Mother", "Child"],
        help="the genome to make_regions",
        default="Mother",
        type=str,
    )
    parser.add_argument(
        "--est-examples",
        dest="est_examples",
        help="estimated examples created per variant\n(default: %(default)s)",
        default=1.5,
        type=float,
    )
    parser.add_argument(
        "--max-examples",
        dest="max_examples",
        help="maximum examples include per regions file\n(default: %(default)s)",
        default=200000,
        type=int,
    )

    parser.add_argument(
        "-d",
        "--debug",
        dest="debug",
        help="print debug info",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--demo-mode",
        dest="demo_mode",
        help="if True, indicates that re-shuffling will use a demo chromosome",
        action="store_true",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        help="display region file contents to the screen",
        action="store_true",
    )
    return parser.parse_args()
    # return parser.parse_args(
    #     [
    #         "--debug",
    #         "--env-file",
    #         "envs/20220912_NewTrios-run1.env",
    #         "--genome",
    #         "Father",
    #         "--dry-run",
    #     ]
    # )


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
        logger.debug(f"using DeepVariant version | {os.environ.get('BIN_VERSION_DV')}")

    if args.dry_run:
        logger.info("[DRY_RUN]: output will display to screen and not write to a file")

    assert (
        args.env_file
    ), "Missing --env-file; Please provide a file with environment variables for the current analysis"
    assert (
        args.restart
    ), "Missing --start-itr; Please designate the iteration number you'd like to make_region files for Beam shuffling."


@dataclass
class MakeRegions:
    # required values
    itr: helpers.Iteration

    # optional values
    ex_per_file: List[int] = field(default_factory=list)
    ex_per_var: List[float] = field(default_factory=list)
    train_mode: bool = True

    # internal, imutable values
    _bed_files_created: int = field(default=0, init=False, repr=False)
    _chr_regions_dict: Dict[int, List] = field(
        default_factory=dict, init=False, repr=False
    )
    _chrs_skipped: dict = field(default_factory=dict, init=False, repr=False)
    _debug_max_files: int = field(default=5, init=False, repr=False)
    _input: Union[Path, None] = field(default=None, init=False, repr=False)
    _input_exists: Union[helpers.h.TestFile, bool, None] = field(
        default=None, init=False, repr=False
    )
    _line_list: List = field(default_factory=list, init=False, repr=False)
    _num_outputs: int = field(default=0, init=False, repr=False)
    _phase: str = field(default="region_shuffling", init=False, repr=False)
    _regions: Dict[str, List] = field(default_factory=dict, init=False, repr=False)
    _total_pass_variants: int = field(default=8000000, init=False, repr=False)
    _total_ref_variants: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.train_mode:
            self._expected_regions = self.itr.train_num_regions
            self._genome = self.itr.train_genome
            self._parameter_name = "train_num_regions"
        else:
            self._expected_regions = self.itr.eval_num_regions
            self._genome = self.itr.eval_genome
            self._parameter_name = "eval_num_regions"

    def check_inputs(self) -> None:
        """
        Load input files and confirm they exist before proceeding
        """
        if self.itr.env is None:
            return
        # Env File Variables
        var_list = ["RefFASTA_Path", "RefFASTA_File"]

        if self._genome is not None:
            var_list.extend(
                [
                    "ExamplesDir",
                    f"{self._genome}TruthVCF_Path",
                    f"{self._genome}TruthVCF_File",
                ]
            )
            (
                ref_fasta_path,
                ref_fasta_file,
                self._examples_dir,
                truth_path,
                truth_file,
            ) = self.itr.env.load(*var_list)
        else:
            (
                ref_fasta_path,
                ref_fasta_file,
            ) = self.itr.env.load(*var_list)
            truth_path = None
            truth_file = None

        # Load Input Files
        reference = Path(ref_fasta_path) / ref_fasta_file
        input_filename = reference.stem + ".dict"
        input_file = Path(ref_fasta_path) / input_filename

        if truth_path is not None and truth_file is not None:
            self._truth_vcf_path = Path(truth_path) / truth_file
        else:
            self._truth_vcf_path = None

        # Confirm Input Files Exist
        ref_genome_exists = helpers.h.TestFile(reference, self.itr.logger)
        ref_genome_exists.check_existing()
        ref_dict_exists = helpers.h.TestFile(input_file, self.itr.logger)
        ref_dict_exists.check_existing()
        if self._truth_vcf_path is not None:
            truth_exists = helpers.h.TestFile(self._truth_vcf_path, self.itr.logger)
            truth_exists.check_existing()

        if ref_genome_exists:
            if not ref_dict_exists.file_exists:
                try:
                    self.itr.logger.info(
                        f"[{self.itr._mode_string}] - [{self._phase}]: missing the reference .dict file; creating one now...",
                    )
                    # Creating a .dict file with Picard
                    picard = subprocess.run(
                        [
                            "picard",
                            "CreateSequenceDictionary",
                            "--REFERENCE",
                            f"{ref_genome_exists.file}",
                        ],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                except subprocess.CalledProcessError as err:
                    self.itr.logger.error(
                        f"unable to create a reference .dict file",
                    )
                    self.itr.logger.error(f"{err}\n{err.stderr}\nExiting... ")
                    sys.exit(err.returncode)

                ref_dict_exists.check_existing()
                if ref_dict_exists.file_exists:
                    self._input = input_file
                    self._input_exists = ref_dict_exists
                else:
                    raise FileNotFoundError(
                        f"[{self.itr._mode_string}] - [{self._phase}]: unable to find a dictionary file [{ref_dict_exists.file}] for the reference genome"
                    )
            else:
                self._input = input_file
                self._input_exists = ref_dict_exists
        else:
            self._input_exists = False
            raise FileNotFoundError(
                f"[{self.itr._mode_string}] - [{self._phase}]: unable to find the reference genome [{ref_genome_exists.file}]"
            )

    def check_output(self) -> None:
        """
        Create output path to store region BED files,
        if it doesn't already exist
        """
        if self._genome is not None:
            self._region_dir = Path(self._examples_dir) / "regions"
        else:
            self._region_dir = Path(os.getcwd()) / "region_files"

        if self._region_dir.is_dir():
            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"[{self.itr._mode_string}] - [{self._phase}]: directory [{self._region_dir}] already exists"
                )
        else:
            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"[{self.itr._mode_string}] - [{self._phase}]: creating a new directory for region files"
                )

            if self.itr.dryrun_mode:
                return
            else:
                self._region_dir.mkdir(parents=True, exist_ok=True)
                assert (
                    self._region_dir.is_dir()
                ), f"[{self.itr._mode_string}] - [{self._phase}]: output directory does not exist yet"

    def transform_dictionary(self) -> None:
        """
        Transform the reference genome's .dict file
        into a pandas dataframe for easier manipulations.
        """
        if isinstance(self._input_exists, helpers.h.TestFile):
            input_data = pd.read_csv(
                self._input_exists.file,
                sep="\t",
                skipinitialspace=True,
                skiprows=1,
                header=None,
                usecols=[1, 2],
            )
            chromosome_names = input_data[1].str.split(":", n=1, expand=True)[1]

            if self.itr.args.species == "cow":
                chr_to_exclude = ["Y", "MT"]
            elif self.itr.args.species == "human":
                chr_to_exclude = ["chrY", "chrM", "chrEBV"]
            else:
                print("ADD LOGIC HERE FOR OTHER SPECIES!")
                sys.exit(1)

            chr_names = [
                chr
                for chr in chromosome_names
                if chr.isalnum() and chr not in chr_to_exclude
            ]
            num_valid_chrs = len(chr_names)

            chrs_length = pd.to_numeric(
                input_data[2].str.split(":", n=1, expand=True)[1]
            )

            filtered_chrs_length = chrs_length[:num_valid_chrs]
            start_pos = [0] * num_valid_chrs

            # create a default regions file with only the autosomes
            # and the X chr for use with model testing
            self._autosome_BED_data = pd.concat(
                {
                    "chromosome": pd.Series(chr_names),
                    "start": pd.Series(start_pos),
                    "stop": filtered_chrs_length,
                },
                axis=1,
            )

            # create cleanded data as input for making
            # the regions shuffling BED files
            self._clean_data = pd.concat(
                {
                    "chromosome": pd.Series(chr_names),
                    "length_in_bp": filtered_chrs_length,
                },
                axis=1,
            )
        else:
            self._clean_data = None

    def write_autosomes_withX_regions(
        self,
        output_file_path: str = f"{os.getcwd()}/region_files/",
        output_file_name: str = "cow_autosomes_withX.bed",
    ) -> None:
        """
        Produces the autosomes + X chr only regions file to be used with --regions flag for training and calling variants
        """
        self.check_inputs()
        self.check_output()
        self.transform_dictionary()

        if self.itr.default_region_file is not None:
            output_file_path = str(self.itr.default_region_file.parent)
            output_file_name = str(self.itr.default_region_file.name)

        output_file = helpers.h.WriteFiles(
            output_file_path,
            output_file_name,
            self.itr.logger,
            logger_msg=f"[{self.itr._mode_string}] - [{self._phase}]: default call_variants",
        )
        output_file.check_missing()

        if not output_file.file_exists:
            self._autosome_BED_data.to_csv(
                output_file.path / output_file.file, sep="\t", index=False, header=False
            )

    def set_genome(
        self,
    ) -> None:
        """
        Handler for either the training genome or the evaluation genome.
        """
        if self.train_mode:
            self._genome = self.itr.train_genome
        else:
            self._genome = self.itr.eval_genome

    def set_region(self, current_region: Union[int, str, None] = None) -> None:
        """
        Define the current region
        """
        if current_region is None or self._existing_regions is None:
            self._prefix = self._genome
            self._logger_msg = (
                f"[{self.itr._mode_string}] - [{self._phase}] - [{self._genome}]"
            )
        else:
            self._prefix = f"{self._genome}-region{current_region}"
            self._logger_msg = f"[{self.itr._mode_string}] - [{self._phase}] - [{self._genome}] - [region{current_region}]"

    def update_iteration(self, add_to_env: bool = False) -> None:
        """
        Updates Iteration() and env-file with the Total Number of Regions for the current genome.
        """
        if self.itr.debug_mode:
            new_parameters = {self._parameter_name: self._debug_max_files}
        else:
            new_parameters = {self._parameter_name: self._num_outputs}

        # Add num output files created to Iteration()
        if self._expected_regions != self._num_outputs:
            self.itr.logger.info(
                f"{self._logger_msg}: updating Iteration() '{self._parameter_name}={new_parameters[self._parameter_name]}'"
            )
            self.itr = replace(self.itr, **new_parameters)

        # Add num output files created to env file
        if (
            self.itr.env is not None
            and add_to_env
            and f"{self._genome}_NumRegionFiles" not in self.itr.env.contents
        ):
            self.itr.env.add_to(
                f"{self._genome}_NumRegionFiles",
                str(self._num_outputs),
                dryrun_mode=self.itr.dryrun_mode,
            )

            self.itr.logger.info(
                f"[{self.itr._mode_string}] - [{self._phase}] - [{self._genome}]: adding '{self._genome}_NumRegionFiles={new_parameters[self._parameter_name]}' to env file"
            )

    def find_regions(self) -> None:
        """
        Check the current env file for regions variables containing the number of regions made for each dataset.

        If variable is missing, see if a regions file was provided in the metadata.csv file.

        If neither of those are found, the proceed to make regions.
        """
        # determine if a region_to_include file was provided
        # in the metadata.csv file
        if self.itr.env is not None and all(
            key in self.itr.env.contents
            for key in ("RegionsFile_Path", "RegionsFile_File")
        ):
            self.itr.logger.info(
                f"{self._logger_msg}: region file variables are present in [{str(self.itr.env.env_path.name)}]"
            )
            self.region_file = Path(
                str(self.itr.env.contents["RegionsFile_Path"])
            ) / str(self.itr.env.contents["RegionsFile_File"])

            if (
                self.itr.default_region_file is not None
                and self.itr.default_region_file.exists()
            ):
                self.itr.logger.info(
                    f"{self._logger_msg}: valid regions file provided",
                )
            else:
                self.itr.logger.warning(
                    f"{self._logger_msg}: region file provided in metadata.csv does not exist",
                )
                raise FileNotFoundError(
                    f"{self._logger_msg}: missing 'RegionFile_Path','RegionFile_File' from {self.itr.env.env_path.name}"
                )
        else:
            self.itr.logger.info(
                f"{self._logger_msg}: using the default call_variants regions file"
            )

        # Determine if number of regions has already been set
        if (
            self.itr.env is not None
            and f"{self._genome}_NumRegionFiles" in self.itr.env.contents
            and self.itr.env.contents[f"{self._genome}_NumRegionFiles"] is not None
        ):
            self._num_outputs = int(
                str(self.itr.env.contents[f"{self._genome}_NumRegionFiles"])
            )
        else:
            self._num_outputs = 0

        # Define the regrex pattern of expected output
        region_file_pattern = rf"{self._genome}-region\d+.bed"

        # Confirm region#'s config does not already exist
        (
            self._existing_regions,
            regions_found,
            region_files,
        ) = helpers.h.check_if_output_exists(
            region_file_pattern,
            "region shuffling BED files",
            self.itr.examples_dir / "regions",
            self._logger_msg,
            self.itr.logger,
            debug_mode=self.itr.debug_mode,
            dryrun_mode=self.itr.dryrun_mode,
        )

        if self.itr.demo_mode:
            expected_num_outputs = 1
            regions_found = 0
            self._existing_regions = False
        elif self.itr.debug_mode and self.itr.demo_mode is False:
            expected_num_outputs = self._debug_max_files
        else:
            expected_num_outputs = self._num_outputs

        if self._existing_regions:
            self.missing_regions_files = helpers.h.check_expected_outputs(
                regions_found,
                expected_num_outputs,
                self._logger_msg,
                "region shuffling BED files",
                self.itr.logger,
            )
        else:
            self.missing_regions_files = True

    def check_truth_vcf(self) -> None:
        """
        Count the total number of REF/REF variants, which should be 0.

        And count the total number of PASS variants, which will be used to define the number of region files to make for a training genome.
        """
        if self.itr.env is None:
            return
        if (
            self.itr.env is not None
            and f"{self._genome}_TotalTruth" in self.itr.env.contents
        ):
            value = self.itr.env.contents[f"{self._genome}_TotalTruth"]
            if value is not None:
                self._total_pass_variants = int(value)
            return

        self.itr.logger.info(
            f"{self._logger_msg}: identifying the number of REF/REF and PASS variants in '{str(self._truth_vcf_path)}' now..."
        )

        if self._truth_vcf_path is not None:
            variants_found = helpers.h.count_variants(
                self._truth_vcf_path,
                logger_msg=self._logger_msg,
                logger=self.itr.logger,
                count_pass=True,
                count_ref=True,
            )
        else:
            variants_found = None
            self.itr.logger.error(
                f"{self._logger_msg}: unable to count_variants() due to missing _truth_vcf_path"
            )

        if isinstance(variants_found, dict):
            self._total_pass = variants_found["pass"]
            self._total_ref = variants_found["ref/ref"]
            self._total_pass_variants = int(self._total_pass)

            self.itr.logger.info(
                f"{self._logger_msg}: there are [{int(self._total_ref):,}] REF/REF variants in the {self._genome}TruthVCF"
            )

            assert (
                self._total_ref == 0
            ), f"{self._logger_msg}: REF/REF variants were found in a TruthVCF.\nPlease remove them from [{str(self._truth_vcf_path)}], or update the path in metadata.csv with a corrected TruthVCF.\nExiting..."

            self.itr.logger.info(
                f"{self._logger_msg}: there are [{int(self._total_pass):,}] PASS variants in the {self._genome}TruthVCF"
            )
            assert (
                self._total_pass_variants != 0
            ), f"{self._logger_msg}: missing PASS variants in a TruthVCF.\nPlease include them [{str(self._truth_vcf_path)}], or update the path in metadata.csv with a corrected TruthVCF.\nExiting..."

            self.itr.env.add_to(
                f"{self._genome}_TotalTruth",
                str(self._total_pass_variants),
                dryrun_mode=self.itr.dryrun_mode,
            )
            self.itr.logger.info(
                f"[{self.itr._mode_string}] - [{self._phase}] - [{self._genome}]: adding '{self._genome}_TotalTruth={self._total_pass_variants}' to env file"
            )
        else:
            self.itr.logger.error(
                f"{self._logger_msg}: helpers.h.count_variants() failed.\nExiting..."
            )
            sys.exit(1)

    def create_samples(self) -> None:
        """
        Manipulate the transformed df to calculate the
        proportional length (in bp) needed from each
        chromosome in, for every regions BED file, given:
            1. an estimate number of variants for the individual genome.
            2. an estimate of examples created per variant
            3. a maximum number of examples to include in each regions file
        """
        if isinstance(self._clean_data, pd.DataFrame):
            # calculate how much of the genome each chr represents
            total_len_bp = self._clean_data["length_in_bp"].sum()
            self._clean_data["prop_len_in_bp"] = (
                self._clean_data["length_in_bp"] / total_len_bp
            )

            assert (
                self._clean_data["prop_len_in_bp"].sum() == 1
            ), "Region proportions do not add up to 1"

            # estimate the number of variants per chr
            self._clean_data["est_variants_per_chr"] = (
                self._clean_data["prop_len_in_bp"] * self._total_pass_variants
            )

            # make the estimate var per chr proportional to
            # chr length in bp
            self._clean_data["est_variants_per_bp"] = (
                self._clean_data["est_variants_per_chr"]
                / self._clean_data["length_in_bp"]
            )

            # determine how many examples are needed from each
            # chromosome so that a region file is
            # representative of the entire genome
            self._clean_data["examples_needed"] = (
                self._clean_data["prop_len_in_bp"] * self.ex_per_file
            )
            # calculate how many variants are needed to produce
            # a set number of examples
            self._clean_data["variants_needed"] = (
                self._clean_data["examples_needed"] / self.ex_per_var
            )

            # calculate region length that will produce a
            # specific number of variants
            self._clean_data["bp_needed"] = (
                self._clean_data["variants_needed"]
                / self._clean_data["est_variants_per_bp"]
            )

            # determine how many region files to make to
            # cover the complete genome
            self._clean_data["num_regions_files"] = (
                self._clean_data["length_in_bp"] / self._clean_data["bp_needed"]
            ) + 1

            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"{self._logger_msg}: clean data contents --------------"
                )
                print(self._clean_data)
                print("-------------- end of clean data --------------")

            # extract relevant calculations for further use
            self._chr_names = self._clean_data["chromosome"]
            self._sample_length_list = self._clean_data["bp_needed"].astype("int")
            self._chr_length_list = self._clean_data["length_in_bp"]

            outputs = self._clean_data["num_regions_files"].values[0]
            if outputs is not None:
                self._num_outputs = outputs.astype("int")
            else:
                raise ValueError("The number of regions to create is not valid")

    def test_sampling(self) -> None:
        """
        if default values are used to calculate how many
        region files to create, confirm output matches expectations (i.e. 61 regions files are created).
        """
        default_vars = ["total_variants", "ex_per_var", "ex_per_file"]
        for f in fields(self):
            if f.name in default_vars:
                val = getattr(self, f.name)
                if val == f.default:
                    assert (
                        int(self._num_outputs) == 61
                    ), f"{self._logger_msg}: did you change the default values to calculate how many region files to make?"

        # confirm samples were processed correctly
        assert (
            len(self._chr_names)
            == len(self._sample_length_list)
            == len(self._chr_length_list)
        ), f"{self._logger_msg}: indexing error due to different data slice sizes!"

    def create_chr_specific_regions(
        self,
        start: int = 0,
    ) -> None:
        """
        Create lists which divide each chromosome into ___ number of regions
        """
        self._expected_num_lines = 0
        for index, chrom in enumerate(self._chr_names):
            self._expected_num_lines += 1
            step = self._sample_length_list.values[index]
            end = self._chr_length_list.values[index]

            if end is not None and step is not None:
                regions_in_chr = list(range(int(start), int(end), int(step)))
                remainder_bp = int(end) - int(regions_in_chr[-1])

                # handle when the chrom is divided perfectly
                if int(remainder_bp) == int(step):
                    remainder_bp = 0

                regions_in_chr.append(end)

                # confirm you made the correct number of regions per chromosome
                regions_made = len(regions_in_chr) - 1
                if regions_made == self._num_outputs:
                    self.itr.logger.info(
                        f"[{self.itr._mode_string}] - [{self._phase}] - [{self._genome}] - [Chromosome {chrom}]: divided into {self._num_outputs} regions, with {int(remainder_bp):,} bp in the final region"
                    )
                else:
                    self.itr.logger.info(
                        f"[{self.itr._mode_string}] - [{self._phase}] - [{self._genome}] - [Chromosome {chrom}]: divided into {regions_made}-of-{self._num_outputs} regions, with {int(remainder_bp):,} bp in the final region"
                    )

                    regions_missing_chr = self._num_outputs - regions_made

                    if regions_missing_chr == 1:
                        self.itr.logger.info(
                            f"[{self.itr._mode_string}] - [{self._phase}] - [{self._genome}] - [Chromosome {chrom}]: final region file will lack variants from this chromosome, with {int(remainder_bp):,} bp in the final region"
                        )

                    elif regions_missing_chr > 0:
                        self.itr.logger.warning(
                            f"[{self.itr._mode_string}] - [{self._phase}] - [{self._genome}] - [Chromosome {chrom}]: contains fewer variants than expected"
                        )

                    elif regions_missing_chr < 0:
                        self.itr.logger.warning(
                            f"[{self.itr._mode_string}] - [{self._phase}] - [{self._genome}] - [Chromosome {chrom}]: contains more variants than expected"
                        )
                        self.itr.logger.error(
                            f"[{self.itr._mode_string}] - [{self._phase}] - [{self._genome}] - [Chromosome {chrom}]: {abs(regions_missing_chr)} additional region file(s) are needed. Exiting... "
                        )
                        sys.exit(1)

            else:
                regions_in_chr = None

            # save the chr-specific regions to a
            # dictionary of lists, where the
            # index is the chromosome name
            self._chr_regions_dict.update({chrom: regions_in_chr})

    def create_output_dictionary(self, region_index: int = 0) -> None:
        """
        Create a dictionary of non-overlapping base-pair
        regions from each chromosome

        Used with the make_examples step of pipeline.
        """
        chr_skipped_counter = 0
        for chr, regions_list in self._chr_regions_dict.items():
            # handle whenever a chrom is divided perfectly
            indexing_errors = int(len(regions_list)) - int(region_index)
            if regions_list is not None:
                if indexing_errors >= 2:
                    # NOTE: BED format does not include the last
                    # position of chromEND, so the regions can overlap
                    # ex: start=0, end=100 is bases num 0-99
                    region_start = regions_list[region_index]
                    region_end = regions_list[region_index + 1]
                    self._regions.update({str(chr): [region_start, region_end]})
                elif indexing_errors <= 1:
                    self.itr.logger.info(
                        f"{self._logger_msg}: skipping region in chromosome {chr}"
                    )
                    chr_skipped_counter += 1
                    # ensure that prior regions file's range isn't carried over
                    del self._regions[str(chr)]
            else:
                raise ValueError("An empty regions_list was provided")

            # keep track of any deviations from the number of lines
            # output bed file
            self._chrs_skipped[region_index] = chr_skipped_counter

        if self.itr.debug_mode:
            self.itr.logger.debug(f"{self._logger_msg}: processing a new region")

    def write_region_file(self) -> None:
        """
        Given a dictionary object, write the items in the dictionary to tab-delimited BED format text files.
        """
        self._line_list.clear()
        self._bed_filename = f"{self._prefix}.bed"
        for index, (key, value) in enumerate(self._regions.items()):
            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"{self._logger_msg}: line{index+1} | {key}\t{value[0]}\t{value[1]}"
                )
            self._line_list.insert(index, f"{key}\t{value[0]}\t{value[1]}")

        if self.itr.dryrun_mode:
            self.itr.logger.info(
                f"[DRY_RUN] - {self._logger_msg}: region file contents:"
            )
            print(f"------------- start of [{self._bed_filename}] -------------")
            print(*self._line_list, sep="\n")
            print(f"-------------- end of [{self._bed_filename}] --------------")
        else:
            outpath = self._region_dir / self._bed_filename
            if outpath.is_file():
                self.itr.logger.info(
                    f"{self._logger_msg}: can not overwrite existing files... SKIPPING AHEAD"
                )
            else:
                with open(outpath, mode="w+", encoding="UTF-8") as outfile:
                    outfile.writelines(f"{line}\n" for line in self._line_list)
                assert (
                    outpath.is_file()
                ), f"{self._logger_msg}: output file {self._bed_filename} was not written"

    def test_outputs(self, dryrun_max_chr: int = 10) -> None:
        """
        If writing output files (i.e. not under dry_run mode),
        then confirm all region files were created correctly.
        """
        # reset counter back to 0 to iterate through
        # both train and eval genomes
        self._bed_files_created = 0

        if self.itr.dryrun_mode:
            # IF YOU GET AN ERROR WHERE FILES EXIST, BUT EXPECTED 0,
            # DELETE THE EXISTING BED FILES BEFORE RUNNING DRY_RUN
            expected_num_outputs = 0
            self._expected_num_lines = dryrun_max_chr
        elif self.itr.debug_mode:
            expected_num_outputs = self._debug_max_files
        else:
            expected_num_outputs = self._num_outputs

        if self.itr.dryrun_mode is False:
            try:
                index = 0
                # Confirm that correct number of bed files are created
                for file in natsorted(self._region_dir.iterdir(), key=str):
                    # using filter and lambda
                    # to remove numeric digits from string
                    genome_prefix = "".join(
                        filter(lambda x: not x.isdigit(), str(self._prefix))
                    )

                    if genome_prefix in file.name:
                        self._bed_files_created += 1
                        num_skipped_lines = self._chrs_skipped[index]
                        if num_skipped_lines != 0:
                            total_lines = self._expected_num_lines - num_skipped_lines
                        else:
                            total_lines = self._expected_num_lines
                        # then confirm each file has the correct number of lines written
                        with open(file, mode="r") as testfile:
                            self._num_chr_found = len(testfile.readlines())

                            assert (
                                self._num_chr_found == total_lines
                            ), f"{self._logger_msg}: there sould be {total_lines} lines in this BED file, but {self._num_chr_found} were found"
                        index += 1

                assert (
                    self._bed_files_created == expected_num_outputs
                ), f"{self._logger_msg}: there should be {expected_num_outputs} BED files, but {self._bed_files_created} were found"

            except AssertionError as error_msg:
                self.itr.logger.error(f"{error_msg}\nExiting... ")
                sys.exit(1)

    def run(self) -> Union[helpers.Iteration, None]:
        """
        Combine all the steps for making region files into one step
        """
        self.set_genome()
        self.set_region(current_region=None)
        self.check_inputs()
        self.check_output()
        self.transform_dictionary()

        if (
            self.itr.current_genome_num is not None
            and self.itr.total_num_genomes is not None
        ):
            if 0 < self.itr.current_genome_num <= self.itr.total_num_genomes:
                self.find_regions()
                self.update_iteration()

                if self.missing_regions_files:
                    self.check_truth_vcf()
                    self.create_samples()
                    self.test_sampling()
                    self.update_iteration(add_to_env=True)

                    if self.itr.debug_mode:
                        regions_iterator = 5
                    else:
                        regions_iterator = self._num_outputs

                    self.create_chr_specific_regions()

                    for r in range(regions_iterator):
                        # THIS HAS TO BE +1 to avoid starting with a region0
                        region_num = r + 1
                        self.set_genome()
                        self.set_region(current_region=region_num)
                        self.create_output_dictionary(region_index=r)
                        self.write_region_file()

                    self.set_region()
                    self.test_outputs()
                    self.itr.logger.info(
                        f"{self._logger_msg}: found {self._bed_files_created} BED files",
                    )

                return self.itr


# Create regions files function
def __init__():
    """
    An example of how to use the module
    """
    # Collect command line arguments
    args = collect_args()

    # Collect start time
    helpers.h.Wrapper(__file__, "start").wrap_script(helpers.h.timestamp())

    # Create error log
    current_file = os.path.basename(__file__)
    module_name = os.path.splitext(current_file)[0]
    logger = helpers.log.get_logger(module_name)

    # Check command line args
    check_args(args, logger)

    env = helpers.h.Env(args.env_file, logger)
    trio_num = str(env.contents["RunOrder"])

    if args.genome != "Child":
        current_itr = helpers.Iteration(
            current_trio_num=trio_num,
            next_trio_num="None",
            current_genome_num=args.restart,
            total_num_genomes=(args.restart + 1),
            total_num_tests=19,
            train_genome=args.genome,
            eval_genome=None,
            env=env,
            logger=logger,
            args=args,
        )
        updated_itr = MakeRegions(
            current_itr,
            args.max_examples,
            args.est_examples,
        ).run()
    else:
        current_itr = helpers.Iteration(
            current_trio_num=trio_num,
            next_trio_num="None",
            current_genome_num=args.restart,
            total_num_genomes=(args.restart + 1),
            total_num_tests=19,
            train_genome=None,
            eval_genome="Child",
            env=env,
            logger=logger,
            args=args,
        )
        updated_itr = MakeRegions(
            current_itr, args.max_examples, args.est_examples, train_mode=False
        ).run()

    print(updated_itr)

    helpers.h.Wrapper(__file__, "end").wrap_script(helpers.h.timestamp())


# Execute all functions created
if __name__ == "__main__":
    __init__()
