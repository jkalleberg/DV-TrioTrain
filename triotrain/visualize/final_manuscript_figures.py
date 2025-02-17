#!/usr/bin/python3
"""
NOTE: This file was run locally, not on HPC, for convenient plot review. Therefore, this script may not be fully reproducible in it's current state.
"""

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from matplotlib.patches import Patch
# from mpl_toolkits.mplot3d import Axes3D
# from matplotlib.colors import ListedColormap
from pandas.api.types import CategoricalDtype
from scipy.stats import friedmanchisquare

import seaborn as sns
import argparse
from logging import Logger
from dataclasses import dataclass, field
import pandas as pd
from pathlib import Path
from sys import path, exit
from os import path as p
from regex import compile
from typing import Union, List, Dict
from string import ascii_uppercase
from regex import search

abs_path = Path(__file__).resolve()
module_path = str(abs_path.parent.parent)
path.append(module_path)

from helpers.utils import get_logger
from helpers.files import File
from helpers.outputs import check_if_output_exists


def round_down(value: Union[int, float], digits: int = 3) -> int:
    """
    Calculate a lower limit boundary inclusive of a specific value.

    Parameters
    ----------
    value : int or float
        the minimum value to include
    digits : int, optional
        how many digits will lost during rounding, by default 3 (i.e. 1234 -> 1000)

    Returns
    -------
    int
        the lower limit
    """
    n = 10**digits
    if isinstance(value, float):
        _value = value * 100
        _rounded_val = int(_value // n * n)
        return float(_rounded_val / 100)
    else:
        return int(value // n * n)


def round_up(value: Union[int, float], digits: int = 3) -> int:
    """
    Calculate a upper limit boundary inclusive of a specific value.

    Parameters
    ----------
    value : int
        the maximum value to include
    digits : int, optional
        how many digits will lost during rounding, by default 3 (i.e. 1234 -> 2000)

    Returns
    -------
    int
        the upper limit
    """
    n = 10**digits
    if isinstance(value, float):
        _value = value * 100
        _rounded_val = int(_value if _value % n == 0 else _value + n - _value % n)
        return float(_rounded_val / 100)
    else:
        return int(value if value % n == 0 else value + n - value % n)


def sum1(l):
    from itertools import accumulate

    return list(accumulate(l))


def sum2(l):
    from numpy import cumsum

    return list(cumsum(l))


def collect_args(
    ) -> argparse.Namespace:
    """
    Process command line argument to execute script.
    """
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-O",
        "--output-path",
        dest="outpath",
        type=str,
        help="[REQUIRED]\noutput path\nwhere to save the resulting summary stats and JPEG files",
        metavar="</path/>",
    )
    parser.add_argument(
            "-I",
            "--input",
            dest="input",
            type=str,
            help="[REQUIRED]\ninput path\nwhere to find files containing data to plot.\nIf a directory is provided, multiple inputs will be identified.\nIf a file is provided, only that file will be used as input.",
            metavar="</path/to/file>",
        )
    parser.add_argument(
        "--overwrite",
        dest="overwrite",
        help="if True, enable re-writing files",
        default=False,
        action="store_true",
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

    return parser.parse_args(
        [
            "-O",
            "/Users/JAKTH2/Documents/UMAG/Research/deep-variant/images/v1.4/round2/",
            "-I",
            
            ## FIG 1 INPUTS
            # "/Users/JAKTH2/Documents/UMAG/Research/deep-variant/input_data/240724_CoverageData.csv",
            
            ## FIG 2/S3 INPUTS
            # "/Users/JAKTH2/Documents/UMAG/Research/deep-variant/results/v1.4.0/R_Visuals/data/",
            
            ## FIG S4-S5 INPUTS
            # "/Users/JAKTH2/Documents/UMAG/Research/deep-variant/input_data/250108_training_performance_metrics.csv",
            
            ## FIG 3/S6/S7 INPUTS
            "/Users/JAKTH2/Documents/UMAG/Research/deep-variant/results/v1.4.0/241008_manuscript/generalization",
            
            ## FIG 4AB/S16 INPUTS
            # "/Users/JAKTH2/Documents/UMAG/Research/deep-variant/results/v1.4.0/241008_manuscript/PR_ROC/data/NA24385",
            ## ORIGINAL INPUT FOR FIGURE 4CD
            # "/Users/JAKTH2/Documents/UMAG/Research/deep-variant/results/v1.4.0/241008_manuscript/PR_ROC/data/NA24385/annotated/DV1.4_WGS.AF_cattle4.SegDups.roc.all.csv.gz",
            # "/Users/JAKTH2/Documents/UMAG/Research/deep-variant/results/v1.4.0/241008_manuscript/PR_ROC/data/NA24385/annotated/",
             
            # "/Users/JAKTH2/Documents/UMAG/Research/deep-variant/results/v1.4.0/241008_manuscript/mie.csv/",
            # "/Users/JAKTH2/Documents/UMAG/Research/deep-variant/results/v1.4.0/241008_manuscript/241008_MIE_Ranking/NA24385",
            # "--dry-run",
            # "--debug",
            "--overwrite",
        ]
    )
    # return parser.parse_args()


def check_args(
    args: argparse.Namespace, logger: Logger) -> None:
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

    if args.dry_run:
        logger.info("[DRY_RUN]: output will display to screen and not write to a file")

    assert args.outpath, "missing --output; Please provide a file name to save results."

    assert (
            args.input
        ), "missing --input; Please provide either a directory location or an existing file containing metrics to plot."


@dataclass
class Plot:
    """
    """
    # optional parameters
    plot_type: str = "PR_ROC"
    # Set the desired font size
    fontsize: int = 10

    _num_variants: Dict[str,str] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self._custom_palette = ["#d95f02", "#7570b3", "#e7298b", "#67a61e", "#e6a902"]
        self._palette_dict = {
            "DT": "#1f77b4",
            "DV-AF": "#d62728",
            "DV": "#000000",
            "12": "#d95f02",
            "18": "#7570b3",
            "22": "#e7298b",
            "28": "#67a61e",
            "30": "#e6a902",
            "2": "#7f7f7f",
            "2B": "#bcbd22",
            "2C": "#17becf",
        }
        # GATK =
        self._train_test_pallette = sns.color_palette(palette="Set1")

        # Create error log
        current_file = p.basename(__file__)
        module_name = p.splitext(current_file)[0]
        self.logger = get_logger(module_name)

        # Collect command line arguments
        self.args = collect_args()
        check_args(args=self.args, logger=self.logger)

        if self.args.dry_run:
            self.logger_msg = f"[DRY_RUN] - [{self.plot_type}] - [visualize]"
        else:
            self.logger_msg = f"[{self.plot_type}] - [visualize]"

        self._output_path = Path(self.args.outpath)
        self._input_file = File(path_to_file=self.args.input,
                           logger=self.logger,
                           debug_mode=self.args.debug,
                           dryrun_mode=self.args.dry_run
                           )
        self._input_file.check_status(should_file_exist=True)

        if self.plot_type == "PR_ROC":
            if self._input_file.file_exists and self._input_file.path.is_file():
                _sample_prefix = self._input_file.path.parent.name
                # Determine if there is a file annotation
                # This says get the first word before '.roc.all.csv.gz' when it does NOT equal 'flags'
                # AKA whenever there's something between happy#-no-flags and file suffix!
                _annotation_pattern = r"\w+(?=\.roc\.all\.csv\.gz)(?<!flags)"

                match = search(_annotation_pattern, self._input_file.file_name)
                if match:
                    self._annotate = str(match.group())
                    _prefix = f"{_sample_prefix}.{self._annotate}"
                else:
                    self._annotate = None
                    _prefix = _sample_prefix
                self._suffix = f"{_prefix}.pr_roc_plot"
                self.summary_suffix = f"{_prefix}_summary.csv"
            elif self._input_file.path.is_dir():
                _prefix = self._input_file.path.name
                self._suffix = f"{_prefix}.AllModels.pr_roc_plot"
                self.summary_suffix = f"{_prefix}.AllModels.pr_roc_summary.csv"
                self._annotate = None
            else:
                self.logger.error(f"{self.logger_msg}: missing a required input file | '{self._input_file.path}'\nExiting...")
                exit(1)

        elif self.plot_type == "AVG_COV":
            self._suffix = "Kalleberg_279542_Fig1"
            self.summary_suffix = None
        elif self.plot_type == "TRAIN_F1":
            self._suffix = "Kalleberg_279542_Fig2"
            self.summary_suffix = "Fig2_summary.csv"
        elif self.plot_type == "IMPACTS":
            self._suffix = "Kalleberg_279542"
            self.summary_suffix = None
        elif self.plot_type == "TEST_F1":
            self._suffix = "Kalleberg_279542_Fig3"
            self.summary_suffix = None
        elif self.plot_type == "STATS_TEST":
            self._suffix = "Kalleberg_279542_FigS7"
            self.summary_suffix = "stats_testing_summary.csv"
        elif self.plot_type == "TOTAL_MIE":
            self._suffix = "Kalleberg_279542_Fig5_Top"
            self.summary_suffix = None
        elif self.plot_type == "CALIBRATION":
            self._suffix = "Kalleberg_279542_Fig5_Bottom"
            self.summary_suffix = None
        else:
            pass

    def mm2inch(self, *value: tuple) -> tuple:
        inch = 25.4
        if isinstance(value[0], tuple):
            return tuple(i/inch for i in value[0])
        else:
            return tuple(i/inch for i in value)

    def find_figure(self, supplemental_plot: bool = False, type: str = "pdf") -> None:
        """
        Confirms if creating plot is necessary.
        """
        if supplemental_plot:
            self._supplemental_plot = True
            _figure_file = self._output_path / f"supp_{self._suffix}.{type}"
        else:
            self._supplemental_plot = False
            _figure_file = self._output_path / f"{self._suffix}.{type}"
        self._plot = File(
            path_to_file=_figure_file,
            logger=self.logger,
            logger_msg=self.logger_msg,
            debug_mode=self.args.debug,
            dryrun_mode=self.args.dry_run,
        )
        if self.args.overwrite:
            self._plot.check_status(should_file_exist=True)
        else:
            self._plot.check_status()

        if self._plot.file_exists and self.args.overwrite is False:
            self.logger.error(
                f"unable to overwrite an existing file | '{self._plot.path_to_file}'\nPlease add the --overwrite flag to discard previous plot.\nExiting..."
            )
            exit(1)

    def update_dicts(self, list_of_dicts: List[Dict[str, str]], update_data: Dict[str, str]):
        for d in list_of_dicts:
            d.update(update_data)

    def find_data(self) -> None:
        """
        Load in results files from multiple analyses.
        """
        _alias = {
            "DT1.4_default_human": "DT",
            "DV1.4_WGS.AF_human": "DV-AF",
            "DV1.4_default_human": "DV",
            "DV1.4_WGS.AF_cattle1": "12",
            "DV1.4_WGS.AF_cattle2": "18",
            "DV1.4_WGS.AF_cattle3": "22",
            "DV1.4_WGS.AF_cattle4": "28",
            "DV1.4_WGS.AF_cattle5": "30",
            "DV1.4_WGS.AF_OneTrio": "2",
            "DV1.4_WGS.AF_OneTrio_AA_BR": "2B",
            "DV1.4_WGS.AF_OneTrio_YK_HI": "2C",
            }

        if self.plot_type == "PR_ROC" and self._input_file.path.is_dir():
            # the Precision-Recall results from Hap.py
            _regex = r".*roc.all.csv.gz"
            (
                inputs_exist,
                inputs_found,
                files,
            ) = check_if_output_exists(
                match_pattern=_regex,
                file_type="PR ROC files",
                search_path=self._input_file.path,
                msg=self.logger_msg,
                logger=self.logger,
                debug_mode=self.args.debug,
                dryrun_mode=self.args.dry_run,
            )
            if inputs_exist:
                _all_metrics = list()
                self.logger.info(
                    f"{self.logger_msg}: number of CSV ROC metrics files identified | '{inputs_found}'"
                )
                for file in files:
                    _csv_file = File(
                        path_to_file=self._input_file.path / file,
                        logger=self.logger,
                        logger_msg=self.logger_msg,
                        debug_mode=self.args.debug,
                        dryrun_mode=self.args.dry_run,
                    )
                    _csv_file.check_status(should_file_exist=True)
                    _csv_file.load_csv()

                    # Add a column for ModelName across multiple files
                    _name_list = file.split(".")

                    if "segdups" not in file.lower():
                        if len(_name_list) == 6:
                            _prefix = _name_list[0:2]
                        elif len(_name_list) == 7:
                            _prefix = _name_list[0:3]
                        else:
                            print("FIX ME!")
                            breakpoint()
                    else:
                        if len(_name_list) == 7:
                            _prefix = _name_list[0:2]
                        elif len(_name_list) == 8:
                            _prefix = _name_list[0:3]
                        else:
                            print("FIX ME! - SEG DUP")
                            breakpoint()

                    _model_name = ".".join(_prefix)
                    _add_alias = {"ModelName": _alias[_model_name]}
                    self.update_dicts(
                        list_of_dicts=_csv_file._existing_data,
                        update_data=_add_alias,
                    )

                    _all_metrics.extend(_csv_file._existing_data)

                # Convert to pd.DataFrame
                _df = pd.DataFrame.from_records(data=_all_metrics)
            else:
                self.logger.error(
                    f"{self.logger_msg}: missing JCSV ROC metrics files | '{self._input_file.path}'\nPlease update --input with a path to exisiting roc.all.csv.gz files.\nExiting..."
                )
                exit(1)

        elif self.plot_type == "TRAIN_F1":
            # the evaluation metrics produced during multiple successive rounds of TrioTrain
            _regex = r".*best_checkpoint.metrics"
            (
                inputs_exist,
                inputs_found,
                files,
            ) = check_if_output_exists(
                match_pattern=_regex,
                file_type="best checkpoint files",
                search_path=self._input_file.path,
                msg=self.logger_msg,
                logger=self.logger,
                debug_mode=self.args.debug,
                dryrun_mode=self.args.dry_run,
            )

            if inputs_exist:
                _all_metrics = list()
                self.logger.info(
                    f"{self.logger_msg}: number of JSON training metrics identified | '{inputs_found}'"
                )
                for file in files:
                    _ckpt_name = Path(Path(file).stem).stem
                    _metrics_dict = {"CheckpointUsed": _ckpt_name}
                    _json_file = File(
                        path_to_file=self._input_file.path / file,
                        logger=self.logger,
                        logger_msg=self.logger_msg,
                        debug_mode=self.args.debug,
                        dryrun_mode=self.args.dry_run,
                    )
                    _json_file.check_status(should_file_exist=True)
                    _json_file.load_json_file()
                    _metrics_dict.update(_json_file.file_dict)
                    _all_metrics.append(_metrics_dict)

                # Convert to pd.DataFrame
                self._df = pd.DataFrame.from_records(data=_all_metrics)
                self.clean_train_metrics_data()

            else:
                self.logger.error(
                    f"{self.logger_msg}: missing JSON training metric files | '{self._input_file.path}'\nPlease update --input with a path to exisiting best_checkpoint.metrics JSON files.\nExiting..."
                )
                exit(1)

            # The genotying summary metrics for each training iteration (parent & offspring)
            _csv_file = File(
                path_to_file=Path(
                    "/Users/JAKTH2/Documents/UMAG/Research/deep-variant/input_data"
                )
                / "250102_alt_figures.csv",
                logger=self.logger,
                logger_msg=self.logger_msg,
                debug_mode=self.args.debug,
                dryrun_mode=self.args.dry_run,
            )
            _csv_file.check_status(should_file_exist=True)
            _csv_file.load_csv()

            # Convert to pd.DataFrame
            _df2 = pd.DataFrame.from_records(data=_csv_file._existing_data)

            # Make new columns numerical format
            _numerical_columns = [
                "Train_Order",
                "Trio_Discordancy",
                "Parent_Mean_Coverage",
                "Offspring_Mean_Coverage",
                "Delta_Coverage",
                "Parent_Truth_N_Hets",
                "Offspring_Truth_N_Hets",
                "Delta_N_Hets",
                "Parent_Truth_N_HomAlts",
                "Offspring_Truth_N_HomAlts",
                "Delta_N_HomAlts",
                "Parent_Truth_Het_HomAlt",
                "Offspring_Truth_Het_HomAlt",
                "Delta_Het_Hom_Alt",
                "Parent_Truth_N_SNV",
                "Offspring_Truth_N_SNV",
                "Delta_SNV",
                "Parent_Truth_N_INDEL",
                "Offspring_Truth_N_INDEL",
                "Delta_INDEL",
                "Parent_SNV_INDEL",
                "Offspring_SNV_INDEL",
                "Delta_SNV_INDEL",
                ] 
            for c in _numerical_columns:
                _df2[[c]] = _df2[[c]].apply(pd.to_numeric)

            # Merge the descriptive metadata & training metrics DataFrames on the 'Train_Order' column
            merged_df = pd.merge(self._df, _df2, on="Train_Order")

            # Then, update internal variables temporarily
            _original_output_path = self._output_path
            self._output_path = _csv_file.path_only

            _original_df = self._df
            self._df = merged_df

            _original_output_suffix = self.summary_suffix
            self.summary_suffix = "250108_training_performance_metrics.csv"

            # Save the new input file required to create coverage | training perofrmance scatter plots
            self.save_cleaned_data()

            # Revert internal variables back to their original values
            self._output_path = _original_output_path
            self._df = _original_df
            self.summary_suffix = _original_output_suffix

            # Drop a duplicate column
            # "Phase" is phase name, while "Training_Phase" is phase number
            merged_df.drop('Training_Phase', axis=1, inplace=True)

            # Update the saved dataframe
            _df = merged_df

        elif self.plot_type == "TEST_F1" or self.plot_type == "STATS_TEST":
            if self.plot_type == "TEST_F1":
                _regex = r".*generalization.csv"
                _rows_to_keep = [f"Test{i}" for i in range(1,19)] + ["Trio"] 
            else:
                _regex = r".*stats_testing.csv"
                _rows_to_keep = [f"Test{i}" for i in range(1, 14)]
            (
                inputs_exist,
                inputs_found,
                files,
            ) = check_if_output_exists(
                match_pattern=_regex,
                file_type="generalization metrics",
                search_path=self._input_file.path,
                msg=self.logger_msg,
                logger=self.logger,
                debug_mode=self.args.debug,
                dryrun_mode=self.args.dry_run,
            )
            if inputs_exist:
                _all_metrics = list()
                self.logger.info(
                    f"{self.logger_msg}: number of CSV metrics files identified | '{inputs_found}'"
                )
                for file in files:
                    _csv_file = File(
                        path_to_file=self._input_file.path / file,
                        logger=self.logger,
                        logger_msg=self.logger_msg,
                        debug_mode=self.args.debug,
                        dryrun_mode=self.args.dry_run,
                    )
                    _csv_file.check_status(should_file_exist=True)
                    _csv_file.load_csv()

                    for row in _csv_file._existing_data:
                        _row_index = row["label"]
                        if any(substring in _row_index for substring in _rows_to_keep):
                            _all_metrics.append(row)

                # Convert to pd.DataFrame
                _df = pd.DataFrame.from_records(data=_all_metrics)

        elif self.plot_type == "CALIBRATION":
            _regex = r".*MIE.sorted.csv"
            (
                inputs_exist,
                inputs_found,
                files,
            ) = check_if_output_exists(
                match_pattern=_regex,
                file_type="sorted MIE files",
                search_path=self._input_file.path,
                msg=self.logger_msg,
                logger=self.logger,
                debug_mode=self.args.debug,
                dryrun_mode=self.args.dry_run,
            )
            if inputs_exist:
                self.logger.info(
                    f"{self.logger_msg}: number of CSV files identified | '{inputs_found}'"
                )

                _data_list = list()
                for file in files:
                    _file = self._input_file.path / file

                    # Load in the tsv file
                    _input_file = File(path_to_file=_file,
                                    logger=self.logger,
                                    logger_msg=self.logger_msg,
                                    debug_mode=self.args.debug,
                                    dryrun_mode=self.args.dry_run
                                    )
                    _input_file.check_status()
                    _input_file.load_csv()

                    # Convert to pd.DataFrame
                    _num_variants = len(_input_file._existing_data)

                    _revised_content = list()
                    for line in _input_file._existing_data:
                        _n_snv = int(line["Num_SNVs"])

                        if _n_snv == 1 or _n_snv % 10000 == 0 or _n_snv == _num_variants:
                            # Update Variant Caller to be the Alias
                            _original_variant_caller = line["Variant_Caller"]
                            _new_variant_caller = _alias[_original_variant_caller]
                            if _new_variant_caller not in self._num_variants.keys():
                                self._num_variants[_new_variant_caller] = _num_variants
                            line["Variant_Caller"] = _new_variant_caller
                            _revised_content.append(line)

                    _df = pd.DataFrame.from_records(_revised_content)
                    _df["Variant_Caller"] = _df["Variant_Caller"].astype("category")

                    _numerical_columns = ["Num_SNVs", "Cumulative_MIE%"] 
                    for c in _numerical_columns:
                        _df[[c]] = _df[[c]].apply(pd.to_numeric)

                    _sample_ID = self._input_file.path.name
                    _file_prefix = _file.stem.split(".")
                    _model_name = ".".join(_file_prefix[0:2])

                    self.logger.info(
                        f"{self.logger_msg}: processing '{_model_name}' | '{_sample_ID}' | #Variants = {_num_variants:,}"
                    )
                    _data_list.append(_df)
                self._df = pd.concat(_data_list)
                return
        else:
            if "csv" in self._input_file.path.name and self._input_file.file_exists:
                self._input_file.load_csv()
            else:
                self.logger.error(
                    f"unable to find input file | '{self._input_file.file_name}'\nPlease update --input to include an existing file or directory.\nExiting..."
                )
                exit(1)

            # Convert to pd.DataFrame
            _df = pd.DataFrame.from_records(data=self._input_file._existing_data)

        # apply strip() method to remove whitespace from all strings in DataFrame
        _df = _df.rename(columns=lambda x: x.strip())
        self._df = _df.map(lambda x: x.strip() if isinstance(x, str) else x)

    def clean_pr_roc_data(self) -> None:
        """
        Clean the data for Precision-Recall ROC from Hap.py.
        """
        if self._annotate is None:
            # Drop unecessary rows (keep PASS only)
            # Retains values for SNPs and INDEls!
            _filtered_df = self._df[
                (self._df["Subtype"] == "*")
                & (self._df["Subset"] == "*")
                & (self._df["Filter"] == "PASS")
            ]
        else:
            # Keep the SNPs/INDELs metrics for that stratification
            _subset = self._annotate.lower()
            _filtered_df = self._df[
                (self._df["Subtype"] == "*")
                & (self._df["Subset"].str.contains(_subset))
                & (self._df["Filter"] == "PASS")
            ]

        # Convert object values to categories or numeric values
        _clean_df = _filtered_df.copy()
        _clean_df["Type"] = _clean_df["Type"].astype("category")

        if "ModelName" in _clean_df.columns.to_list():
            _clean_df["ModelName"] = _clean_df["ModelName"].astype("category")

        _numerical_columns = ["METRIC.Recall", "METRIC.Precision"] 
        for c in _numerical_columns:
            _clean_df[[c]] = _clean_df[[c]].apply(pd.to_numeric)

        # Update the internal data frame
        if "ModelName" in _clean_df.columns.to_list() and self._annotate is None: 
            self._df = _clean_df[
                ["ModelName", "Type", "METRIC.Recall", "METRIC.Precision"]
                ]
        elif "ModelName" in _clean_df.columns.to_list() and self._annotate: 
            self._df = _clean_df[
                ["ModelName", "Type", "Subset", "METRIC.Recall", "METRIC.Precision"]
                ]
        elif self._annotate:
            _clean_df["Subset"] = _clean_df["Subset"].astype("category")
            self._df = _clean_df[
                ["Type", "Subset", "METRIC.Recall", "METRIC.Precision"]
            ]
        else:
            self._df = _clean_df[
                ["Type", "METRIC.Recall", "METRIC.Precision"]
            ]

    def clean_coverage_data(self, cattle_only: bool = False) -> None:
        """_summary_
        """
        # Convert object values to categories or numeric values
        _clean_df = self._df.copy()
        _clean_df["group"] = _clean_df["group"].astype("category")
        _numerical_columns = ["avg_coverage"]
        for c in _numerical_columns:
            _clean_df[[c]] = _clean_df[[c]].apply(pd.to_numeric)

        # Subset the data to be N=13 for 'Testing' group
        if cattle_only:
            _training_only = _clean_df[_clean_df["group"] == "Training"] 
            _testing_only = _clean_df[_clean_df["group"] == "Testing"]
            _bovine_to_exclude = [
                "UMCUSAM000000341496",
                "UMCUSAF000000341497",
                "UMCUSAM000000341713",
                "UMCUSAM000009341496",
                "UMCUSAF000009341497",
                "UMCUSAM000009341713",
            ]
            _testing_filtered = _testing_only[~_testing_only["international_id"].isin(_bovine_to_exclude)]
            _result = pd.concat([_testing_filtered, _training_only])
        else:
            _result = _clean_df

        # Update the internal data frame
        self._df = _result

    def create_label(self, ckpt_name: str) -> None:
        _digits_only = compile(r"\d+")
        iter, genome = ckpt_name.split(".")

        match = _digits_only.search(iter)
        if match:
            iter_num = match.group()
        else:
            raise KeyError(f"missing an iteration number in file name | '{ckpt_name}'")

        if "m" in genome[:1].lower():
            genome_abr = "M"
        elif "f" in genome[:1].lower():
            genome_abr = "P"
        else:
            raise KeyError(f"invalid label provided | '{genome[:1]}'")

        return f"T{iter_num} - {genome_abr}"

    def assign_phase(self, iter_num: str) -> str:
        """_summary_

        Args:
            iter_num (str): _description_

        Returns:
            _type_: _description_
        """
        if int(iter_num) <= 6:
            return "Phase 1"
        elif int(iter_num) >= 7 and int(iter_num) <= 9:
            return "Phase 2"
        elif int(iter_num) >= 10 and int(iter_num) <= 11:
            return "Phase 3"
        elif int(iter_num) >= 12 and int(iter_num) <= 14:
            return "Phase 4"
        elif int(iter_num) > 14:
            return "Phase 5"
        else:
            return

    def clean_train_metrics_data(self) -> None:
        """
        Revise the format of the 'metrics.json' files produced from multiple iterations of TrioTrain.
        """
        # Convert object values to categories or numeric values
        _clean_df = self._df.copy()

        for c in _clean_df.columns.values[1:]:
            _clean_df[[c]] = _clean_df[[c]].apply(pd.to_numeric)

        # Add values for F1-score for SNPs and INDELs
        _clean_df["F1/SNPs"] = (
            2 * _clean_df["Precision/SNPs"] * _clean_df["Recall/SNPs"]
        ) / (_clean_df["Precision/SNPs"] + _clean_df["Recall/SNPs"])

        _clean_df["F1/Indels"] = (
            2 * _clean_df["Precision/Indels"] * _clean_df["Recall/Indels"]
        ) / (_clean_df["Precision/Indels"] + _clean_df["Recall/Indels"])

        _clean_df["Train_Order"] = [ x for x in range(1, (len(_clean_df) + 1))]

        _clean_df["Plot_Label"] = _clean_df["CheckpointUsed"].apply(self.create_label)

        _clean_df[["Iteration", "Train_Genome"]] = _clean_df[
            "CheckpointUsed"
        ].str.split(".", n=1, expand=True).astype("category")

        _clean_df["Iteration_Num"] = _clean_df.Iteration.str.extract(r"(\d+)")

        _clean_df["Phase"] = (
            _clean_df["Iteration_Num"].apply(self.assign_phase).astype("category")
        )

        # Update the internal data frame
        self._df = _clean_df

    def clean_performance(self) -> None:
        # Drop unecessary rows (keep Training Metrics only)
        # Exclude SynDip Trio!
        _filtered_df = self._df[
            (self._df["Training_Phase"] != "5")
        ].copy()

        # Best checkpoint performance metrics
        # Grab only F1 score
        _training_metrics_columns = [col for col in _filtered_df.columns if "F1" in col or "Precision" in col or "Recall" in col]

        _cols_to_keep = ["Train_Order", "Training_Phase", "Parent_Sex", "Parent_Breed_Code", "Parent_Mean_Coverage", "Offspring_Breed_Code", "Offspring_Mean_Coverage", "Offspring_Sex"] + _training_metrics_columns

        # Drop unecessary columns
        _training_performance_df = _filtered_df.filter(regex="|".join(_cols_to_keep))

        # Convert object values to categories or numeric values
        _training_performance_df.loc[:, "Training_Phase"] = _training_performance_df["Training_Phase"].astype(
            "category"
        )
        _training_performance_df.loc[:, "Parent_Breed_Code"] = _training_performance_df["Parent_Breed_Code"].astype(
            "category"
        )
        _training_performance_df.loc[:, "Parent_Sex"] = _training_performance_df["Parent_Sex"].astype("category")

        _training_performance_df.loc[:, "Offspring_Breed_Code"] = _training_performance_df["Offspring_Breed_Code"].astype(
            "category"
        )
        _training_performance_df.loc[:, "Offspring_Sex"] = _training_performance_df["Offspring_Sex"].astype("category")

        _numerical_columns = [
            "Train_Order",
            "Parent_Mean_Coverage",
            "Offspring_Mean_Coverage",
        ] + _training_metrics_columns

        for c in _numerical_columns:
            _training_performance_df[[c]] = _training_performance_df[[c]].apply(
                pd.to_numeric
            )

        # Rename columns for legend titles
        _df = _training_performance_df.rename(
            # columns={"Training_Phase": "Phase", "Parent_Breed_Code": "Breed"}
            columns={"Training_Phase": "Phase", "Offspring_Breed_Code": "Breed"}
        )

        # Update the internal data frame
        self._df = _df

    def clean_generalization(self,
                             stats_testing: bool = False,
                             min_vals_only: bool = False,
                             subset_data: bool = False,
                             )-> None:

        if stats_testing:
            # Grab only Precision and Recall
            _cols_to_keep = [col for col in self._df.columns if "F1" not in col]
        else:
            # Grab only F1 score
            _cols_to_keep = [col for col in self._df.columns if "Precision" not in col and "Recall" not in col]

        _raw_metrics_data = self._df[_cols_to_keep]

        # Drop unecessary metadata columns
        # Filter columns based on substrings
        if stats_testing or min_vals_only:
            _cols_to_keep = [
                "model_name",
                "SNP",
                "INDEL",
                "HOMREF",
                "HET",
                "HOMALT",
                ]
        else:
            _cols_to_keep = [
                    "model_name",
                    "ancestry_info",
                    "ancestry_code",
                    "biosample_ID",
                    "SNP",
                    "INDEL",
                    "HOMREF",
                    "HET",
                    "HOMALT",
                ]
        filtered_df = _raw_metrics_data.filter(
            regex="|".join(_cols_to_keep))
        
        # print(filtered_df.head())
        # print("COLUMNS KEPT:", filtered_df.columns.values)

        if not stats_testing and not min_vals_only:
            filtered_df = filtered_df.replace({
                "model_name": {
                    "DT1.4_default_human": "DT",
                    "DV1.4_default_human": "DV",
                    "DV1.4_WGS.AF_human": "DV-AF",
                    "DV1.4_WGS.AF_OneTrio": "2",
                    "DV1.4_WGS.AF_OneTrio_AA_BR": "2B",
                    "DV1.4_WGS.AF_OneTrio_YK_HI": "2C",
                    "DV1.4_WGS.AF_cattle1": "12",
                    "DV1.4_WGS.AF_cattle2": "18",
                    "DV1.4_WGS.AF_cattle3": "22",
                    "DV1.4_WGS.AF_cattle4": "28",
                    "DV1.4_WGS.AF_cattle5": "30",
                },
                "ancestry_info": {
                    "YakHighlanderF1": "YKxHI",
                    "AngusBrahmanF1": "AAxBR",
                    "BisonSimmentalF1": "BIxSI",
                }
            }
            )

        if subset_data:
            ### ONE_TRIO ITERATIONS ONLY
            # Compare the last checkpoint of (3) OneTrio checkpoints against the
            # best benchmarked checkpoint (C28)
            _filtered_df1 = filtered_df[
                filtered_df["model_name"].isin(["DV", "1B", "2B", "1C", "2C", "2", "28"])
            ]
            iterations = _filtered_df1["model_name"].unique()
            _sorted_vals2 = ["DV", "1B", "2B", "1C", "2C", "2", "28"]
            _checkpoint_categories = CategoricalDtype(categories=_sorted_vals2, ordered=True)
        elif stats_testing:
            ### TRIO_TRAIN ITERATIONS ONLY:
            # Exclude rows for the 'extra' model checkpoints run with only one trio
            _filtered_df1 = filtered_df[
                ~filtered_df["model_name"].isin(["1B", "2B", "1C", "2C"])
            ]
            iterations = _filtered_df1["model_name"].unique()
            _sorted_vals1 = sorted(iterations, key=lambda x: (x.isalnum(), x.isnumeric()))
            _checkpoint_categories = CategoricalDtype(categories=_sorted_vals1, ordered=True)
        else:
            ### TRIO_TRAIN ITERATIONS ONLY:
            # Keep Rows for Main Comparision
            _filtered_df = filtered_df[
                filtered_df["model_name"].isin(["DT", "DV", "DV-AF", "2", "2B", "2C", "12", "18", "22", "28", "30"])
            ].copy()

            _filtered_df["species"] = [
                "human" if x in ["AJ", "HC"] else "bovine"
                for x in _filtered_df["ancestry_code"]
            ]
            
            # print(_filtered_df.groupby(["model_name"]).count())
            # breakpoint()

            _filtered_df.drop_duplicates(subset=["model_name", "ancestry_info", "ancestry_code", "biosample_ID"], inplace=True)

            _filtered_df1 = _filtered_df[
                ~_filtered_df["biosample_ID"].isin([
                    "SAMN08473804", "SAMN08473803", "SAMN12153485", "SAMN12153486", "SAMN16823422", "SAMN16825967"
                ])
            ]

            iterations = _filtered_df1["model_name"].unique()
            _sorted_vals1 = sorted(
                iterations, key=lambda x: (x.isalnum(), x.isnumeric())
            )
            _checkpoint_categories = CategoricalDtype(
                categories=_sorted_vals1, ordered=True
            )

        # Subset the data, and create categorical columns
        _clean_data = _filtered_df1.copy()
        _clean_data["model_name"] = _clean_data["model_name"].astype(_checkpoint_categories)

        # Define numerical columns
        if stats_testing:
            _numerical_columns = [
                "Precision_INDEL",
                "Precision_SNP",
                "Precision_HOMREF",
                "Precision_HET",
                "Precision_HOMALT",
                "Recall_INDEL",
                "Recall_SNP",
                "Recall_HOMREF",
                "Recall_HET",
                "Recall_HOMALT",
                ]
        else:
            _numerical_columns = [
                "F1_INDEL",
                "F1_SNP",
                "F1_HOMREF",
                "F1_HET",
                "F1_HOMALT",
            ]

        for c in _numerical_columns:
            _clean_data[[c]] = _clean_data[[c]].apply(pd.to_numeric)

        if (not subset_data and stats_testing) or min_vals_only:
            # Identify the minimum values of Precision/Recall for each model
            _grouping = _clean_data.groupby("model_name", observed=True)
            _min_vals = _grouping.min()

            # Calculate the amount of difference between 'defaults' and 'C28'
            _change_from_warmstart = _min_vals.loc[["DV", "28"]]

            _change_from_warmstart.loc["Diff"] = (
                _change_from_warmstart.loc["28"] - _change_from_warmstart.loc["DV"]
            )

            # Calculate the amount of difference between 'C1' and 'C28'
            _change_1_28 = _min_vals.loc[["1", "28"]]
            _change_1_28.loc["Diff"] = (
                _change_1_28.loc["28"] - _change_1_28.loc["1"]
            )
            # Concatenate along rows
            self._df = pd.concat([_change_from_warmstart, _change_1_28]).reindex()

            if min_vals_only:
                self.summary_suffix = "stats_testing.min_vals.csv"

            # Save to a new file
            self.save_cleaned_data()
        else:

            # Identify which checkpoint performs 'best' in each species
            # Where 'best' means has the highest minimum F1 score
            _grouping = _clean_data.groupby(["species", "model_name"], observed=True).agg({
                "model_name": "size",
                "F1_SNP": ["min", "mean", "median", "max"],
                "F1_INDEL": ["min", "mean", "median", "max"],
            })

            _grouping = _clean_data.groupby(["species", "model_name"], observed=True).agg(
                count=("F1_SNP", "count"),
                min=("F1_SNP", "min"),
                mean=("F1_SNP", "mean"),
                median=("F1_SNP", "median"),
                max=("F1_SNP", "max")
            ).reset_index()

            # _grouping = _clean_data.groupby(["species", "model_name"], observed=True).agg(
            #     count=("F1_INDEL", "count"),
            #     min=("F1_INDEL", "min"),
            #     mean=("F1_INDEL", "mean"),
            #     median=("F1_INDEL", "median"),
            #     max=("F1_INDEL", "max")
            # ).reset_index()

            # Filter out rows to exclude
            df_filtered = _grouping[~_grouping["model_name"].isin(["DT", "DV", "DV-AF"])]

            _max_rows = (
                df_filtered.groupby("species")["max"].idxmax()
            )
            _summary = df_filtered.loc[_max_rows]
            _summary.insert(1, "metric", ["F1_SNV", "F1_SNV"])
            _summary.insert(
                2,
                "description",
                [
                    "checkpoint with max maximum value",
                    "checkpoint with max maximum value",
                ],
            )
            # print(_summary)
            # breakpoint()

        if min_vals_only:
            _min_melted = _min_vals.reset_index().melt(id_vars=["model_name"], value_name="Minimum Value")
            _min_melted[["metric", "type"]] = _min_melted["variable"].str.split("_", expand=True)

            # Make the minimum values from a string to a number
            _min_melted["metric"] = _min_melted["metric"].astype("category")
            _min_melted["type"] = _min_melted["type"].astype("category")
            _min_melted[["Minimum Value"]] = _min_melted[["Minimum Value"]].apply(pd.to_numeric)
            self._df = _min_melted
        elif stats_testing:
            # Plot a line with 95% CI around values (N=13)
            _melted = _clean_data.melt(id_vars=["model_name"])
            _melted[["metric", "type"]] = _melted["variable"].str.split("_", expand=True)

            # Make the values from a string to a number
            _melted["metric"] = _melted["metric"].astype("category")
            _melted["type"] = _melted["type"].astype("category")
            _melted[["value"]] = _melted[["value"]].apply(pd.to_numeric)

            self._df = _melted
        else:
            _filtered_clean_data = _clean_data[["model_name", "species", "F1_INDEL", "F1_SNP", "F1_HET", "F1_HOMALT"]].copy()
            _melted = _filtered_clean_data.melt(id_vars=["model_name", "species"])

            _melted[["metric", "type"]] = _melted["variable"].str.split(
                "_", expand=True
            )
            _melted["species"] = _melted["species"].astype("category")
            _melted["model_name"] = _melted["model_name"].astype("category")
            _melted["type"] = _melted["type"].astype("category")
            _melted[["value"]] = _melted[["value"]].apply(pd.to_numeric)

            _nobs = _clean_data.groupby(["species", "model_name"], observed=True)["F1_INDEL"].count()
            self._nobs = [f"N=({x})" for x in _nobs.tolist()]
            self._df = _melted

    def grouped_significance(self, group_values: List[List[float]]):
        # print("GROUPED_VALUES:", group_values)
        result = friedmanchisquare(*group_values)
        return [result.statistic, result.pvalue]

    def estimate_generalization(self) -> None:
        _relevant_data = self._df[["model_name", "metric", "type", "value"]].copy()
        print(_relevant_data.shape)
        # _grouped_data = _relevant_data.groupby(["model_name", "metric", "type"], observed=False)
        # print("BOOTSTRAPPING NOW...")
        # _bootstrapped = _grouped_data.apply(sns.algorithms.bootstrap)
        # print("DONE BOOTSTRAPPING")
        # _result = _bootstrapped.reset_index(name="bootstrapped")
        # _summary = _result[["model_name", "metric", "type"]].copy()
        # _summary["count"] = pd.DataFrame(_result["bootstrapped"].values.tolist()).count(1)
        # _summary["min"] = pd.DataFrame(_result["bootstrapped"].values.tolist()).min(1)
        # _summary["max"] = pd.DataFrame(_result["bootstrapped"].values.tolist()).max(1)
        # _summary["mean"] = pd.DataFrame(_result["bootstrapped"].values.tolist()).mean(1)
        # print("CALCULATING 95% CI NOW...")
        # _95_ci = _bootstrapped.apply(sns.utils.ci).reset_index(name="95_ci")
        # print("DONE CALCULATING 95% CI.")
        # _summary[["95_ci_lower", "95_ci_upper"]] = pd.DataFrame(_95_ci["95_ci"].tolist(), index=_95_ci.index)
        # print(_summary.head())
        # breakpoint()

        _models_to_exclude = ["DV", "DV-AF", "23", "29", "30"]
        _filtered_data = _relevant_data[
            ~_relevant_data["model_name"].isin(_models_to_exclude)
        ].copy()
        _filtered_data["model_name"] = _filtered_data['model_name'].cat.remove_categories(_models_to_exclude)

        _grouped_data = _filtered_data.groupby(
            ["model_name", "metric", "type"], observed=False
        )
        _new_data = (_grouped_data["value"].apply(list).reset_index(name="values"))
        print(_new_data["model_name"].unique().tolist())

        _group_checkpoints = _new_data.groupby(["metric", "type"], observed=False)
        _summary_df = _group_checkpoints["values"].apply(list).reset_index(name="all_checkpoints")
        print("NUM METRICS:", len(_summary_df["all_checkpoints"]))
        print("NUM OF REPEATED SAMPLES (J):", len(_summary_df["all_checkpoints"][0][0]))
        print("NUM OF MODELS (K):", len(_summary_df["all_checkpoints"][0]))

        _summary_df["f_stat"], _summary_df["pvalue"] = zip(*_summary_df["all_checkpoints"].map(self.grouped_significance))
        print(_summary_df)
        breakpoint()
        pass

    def save_cleaned_data(self) -> None:
        """
        Save summary metrics to a new file.
        """
        if self.summary_suffix is None:
            self.logger.info(
                    f"{self.logger_msg}: skipping saving a summary CSV file"
                )
            return

        _summary_file = self._output_path / self.summary_suffix
        _clean_file = File(
            path_to_file=_summary_file,
            logger=self.logger,
            logger_msg=self.logger_msg,
            debug_mode=self.args.debug,
            dryrun_mode=self.args.dry_run,
        )
        if self.args.overwrite:
            _clean_file.check_status(should_file_exist=True)
        else:
            _clean_file.check_status()

        if not _clean_file.file_exists or self.args.overwrite:
            if not _clean_file.file_exists:
                self.logger.info(
                    f"{self.logger_msg}: saving summary data to a new file | '{str(_summary_file)}'"
                )
            elif self.args.overwrite:
                if self.args.dry_run:
                    self.logger.info(
                        f"{self.logger_msg}: --overwrite=True, pretending to replace previous file."
                    )
                else:
                    self.logger.info(
                        f"{self.logger_msg}: --overwrite=True, previous file will be replaced."
                    )
            _clean_file.write_dataframe(df=self._df)

    def build_pr_roc(self, supplement_plot: bool = False) -> None:
        """
        Create the Precision-Recall ROC figure.
        """
        self._description = "Precision-Recall ROC"

        # Single Model - Single Genome
        if "ModelName" not in self._df.columns.to_list():
            # Identify lower boundaries for X and Y axes
            _summary = self._df.describe()
            x_lower_bound = _summary["METRIC.Recall"]["25%"]
            y_lower_bound = _summary["METRIC.Precision"]["25%"]

            if self._annotate is None:
                # Create a basic seaborn plot
                plot = sns.relplot(
                    data=self._df,
                    x="METRIC.Recall",
                    y="METRIC.Precision",
                    kind="line",
                    markers=True,
                    hue="Type",
                    hue_order=["SNP", "INDEL"],
                    aspect=0.65,
                )
            else:
                # Create a basic seaborn plot
                # but stratified by certain truth classes
                # NOTE: ideally this should be automatic!
                # print(self._input_file.path.name)
                _unique_values = self._df["Subset"].unique()
                _stratification = self._annotate.lower()
                _not_stratification = [val for val in _unique_values if val != _stratification][0]
                plot = sns.relplot(
                    data=self._df,
                    x="METRIC.Recall",
                    y="METRIC.Precision",
                    kind="line",
                    markers=False,
                    hue="Type",
                    palette={"SNP": self._palette_dict["28"], "INDEL": self._palette_dict["28"]},
                    style="Type",
                    style_order=["SNP", "INDEL"],
                    col="Subset",
                    col_order=[_not_stratification, _stratification],
                    aspect=0.8,
                    height=4,
                )

            # Remove the unecessary Seaborn legend
            plot._legend.remove()

            # Define boundaries for axes
            plot.set(xlim=(x_lower_bound, 1), ylim=(y_lower_bound, 1))

            if self._annotate is None:
                # Format the axes labels
                for ax in plot.axes.flat:
                    ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1.0,
                                                                        decimals=2,
                                                                        ))
                    ax.xaxis.set_major_formatter(mtick.PercentFormatter(xmax=1.0,
                                                                        decimals=0,
                                                                        ))
                plot.set_titles(col_template="{col_name}")
                plt.legend(loc="lower left", title=None)

            elif "segdup" in self._annotate.lower():
                # Format the axes labels
                titles = ["HG002 | Outside SegDups", "HG002 | Within SegDups",]
                pad_list = [6.7, 7]
                for ax,title in zip(plot.axes.flat,enumerate(titles)):
                    n = title[0]
                    if n == 0:
                        _handles = plot._legend.legend_handles
                        _sub_handles = [
                            _handles[1], #SNV
                            _handles[0], #INDEL
                        ]
                        _legend = ax.legend(
                            handles=_sub_handles,
                            title="Checkpoint 28:",
                            labels=[
                                "SNV",
                                "INDEL",
                            ],
                            loc="lower left",
                            fancybox=False,
                        )
                        for line in _legend.get_lines():
                            line.set_linewidth(2)

                    # Add (C,D) plot labels
                    ax.text(
                        -0.09,
                        1.1,
                        ascii_uppercase[n+2],
                        transform=ax.transAxes,
                        size=12,
                        weight="bold",
                    )

                    # Add black title box
                    title_box = ax.set_title(
                        title[1],
                        fontsize=8,
                        weight="bold",
                        position=(0.5, 0.90),
                        y=0.99,
                        backgroundcolor="black",
                        color="white",
                        verticalalignment="bottom",
                        horizontalalignment="center",
                        )
                    title_box._bbox_patch._mutation_aspect = 0.03
                    title_box.get_bbox_patch().set_boxstyle("square", pad=pad_list[n])

                plot.set_axis_labels(x_var="Recall", y_var="Precision", fontsize=self.fontsize)

                # Manually adjust the legend to improve interpretation
                # children = plt.gca().get_children()

                # ax[0].legend(
                #     [children[0], children[2]],
                #     ["SNV", "INDEL"],
                #     loc="lower left",
                #     title=None,
                #     fancybox=False
                # )
            else:
                print("FIX ME!")
                breakpoint()

            plt.tight_layout()

        else:
            # Muliple Models - Single Genome
            if supplement_plot: 
                fig,axes = plt.subplots(
                    nrows=3,
                    ncols=2,
                    figsize=(8,8),
                    sharey=False,
                    sharex=True,
                    )
                _dims = [
                    axes[0,0],
                    axes[0,1],
                    ]
            else:
                # Original Figure Shape
                fig,axes = plt.subplots(
                    nrows=1,
                    ncols=2,
                    figsize=(8,4),
                    sharey=True,
                    sharex=False,
                )
                _dims=[
                    axes[0],
                    axes[1],
                ]

            # 1. Grab Species Comparision Data
            _compare_species = self._df[
                self._df['ModelName'].isin(
                    [
                        "DT",
                        "DV-AF",
                        "DV", 
                        "28",
                    ]
                )
            ]
            # Identify lower boundaries for X and Y axes
            _summary1 = _compare_species.groupby(by="ModelName", observed=False).describe()
            if supplement_plot:
                y_lower_bound1 = _summary1["METRIC.Precision"]["min"].max()
                y_upper_bound = 1.00005
            else:
                y_lower_bound1 = _summary1["METRIC.Precision"]["25%"].min()
                y_upper_bound = 1.00009

            if supplement_plot:
                # 2. Grab TrioTrain Phases Data
                _compare_trio_train_phases = self._df[
                    self._df["ModelName"].isin(
                        [
                            "DV",
                            "12",
                            "18",
                            "22",
                            "28",
                            "30",
                        ]
                    )
                ]
                # Identify lower boundaries for X and Y axes
                _summary2 = _compare_trio_train_phases.groupby(
                    by="ModelName", observed=False
                ).describe()
                # x_lower_bound2 = _summary2["METRIC.Recall"]["25%"].min()
                y_lower_bound2 = _summary2["METRIC.Precision"]["min"].max()

                # 3. Grab Shorter/Longer Training Length Data
                _compare_training_length = self._df[
                    self._df["ModelName"].isin(
                        [
                            "DV",
                            "2",
                            "2B",
                            "2C",
                            "28",
                        ]
                    )
                ]
                # Identify lower boundaries for X and Y axes
                _summary3 = _compare_trio_train_phases.groupby(
                    by="ModelName", observed=False
                ).describe()
                # x_lower_bound3 = _summary3["METRIC.Recall"]["25%"].min()
                y_lower_bound3 = _summary3["METRIC.Precision"]["min"].max()

            for n,ax in enumerate(axes.flat):
                # Add (A,B) plot labels
                ax.text(
                    -0.09,
                    1.1,
                    ascii_uppercase[n],
                    transform=ax.transAxes,
                    size=12,
                    weight="bold",
                )
                # Define axis limits (zoom in)
                if n < 2:
                    ax.set(xlim=(0.15, 1), ylim=(y_lower_bound1, y_upper_bound))
                elif n >= 2 and n < 4:
                    ax.set(xlim=(0.15, 1), ylim=(y_lower_bound2, y_upper_bound))
                elif n >= 4 and n < 6:
                    ax.set(xlim=(0.15, 1), ylim=(y_lower_bound3, y_upper_bound))
                else:
                    print("FIX AXIS LIMITS!")
                    breakpoint()

            # A. Build Species Comparision Plot | SNP Only
            if supplement_plot:
                add_legend = False
                _padding = 10.8
                _title = "SNV"
            else:
                add_legend = True
                _padding = 11.2
                _title = "HG002 | SNVs"

            _species_SNP_plot = sns.lineplot(
                _compare_species.loc[_compare_species["Type"] == "SNP"],
                ax=_dims[0],
                x="METRIC.Recall",
                y="METRIC.Precision",
                hue="ModelName",
                hue_order=list(self._palette_dict.keys()),
                palette=self._palette_dict,
                legend=add_legend,
            )
            _species_SNP_plot.set_ylabel("Precision", fontsize=self.fontsize)

            if supplement_plot:
                _species_SNP_plot.set_xlabel("", fontsize=self.fontsize)
            else:
                _species_SNP_plot.set_xlabel("Recall", fontsize=self.fontsize)

            title_box = _species_SNP_plot.set_title(
                label=_title,
                fontsize=8,
                weight="bold",
                position=(0.5, 0.90),
                y=0.98,
                backgroundcolor="black",
                color="white",
                verticalalignment="bottom",
                horizontalalignment="center",
            )
            title_box._bbox_patch._mutation_aspect = 0.02
            title_box.get_bbox_patch().set_boxstyle("square", pad=_padding)

            # B. Build Species Comparision Plot | INDEL Only
            if supplement_plot:
                add_legend=True
                _padding = 10.3
                _legend = _species_INDEL_plot.get_legend()
                _title = "Indels"
            else:
                add_legend=False
                _padding = 10.7
                _legend = _species_SNP_plot.get_legend()
                _title = "HG002 | Indels"

            _species_INDEL_plot = sns.lineplot(
                _compare_species.loc[_compare_species["Type"] == "INDEL"],
                ax=_dims[1],
                x="METRIC.Recall",
                y="METRIC.Precision",
                hue="ModelName",
                hue_order=list(self._palette_dict.keys()),
                palette=self._palette_dict,
                legend=add_legend,
            )

            _handles = _legend.legend_handles
            _sub_handles = [
                _handles[0], #DT
                _handles[2], #DV
                _handles[1], #DV-AF
                _handles[6], #C28
            ]
            if supplement_plot:
                _legend = _species_INDEL_plot.legend(
                    handles=_sub_handles,
                    labels=["DT", "DV", "DV-AF", "28"],
                    bbox_to_anchor=(1.05, 1.01),
                    borderaxespad=0,
                    fancybox=False,
                    frameon=False,
                )
            else:
                _legend = _species_SNP_plot.legend(
                    handles=_sub_handles,
                    title="Checkpoint:",
                    labels=["DT", "DV", "DV-AF", "28"],
                    loc="lower left",
                    # borderaxespad=0,
                    fancybox=False,
                    # frameon=False,
                )

            for line in _legend.get_lines():
                line.set_linewidth(2)

            _species_INDEL_plot.set_ylabel("", fontsize=self.fontsize)

            if supplement_plot:
                _species_INDEL_plot.set_xlabel("", fontsize=self.fontsize)
            else:
                _species_INDEL_plot.set_xlabel("Recall", fontsize=self.fontsize)

            title_box = _species_INDEL_plot.set_title(
                label=_title,
                fontsize=8,
                weight="bold",
                position=(0.5, 0.90),
                y=0.98,
                backgroundcolor="black",
                color="white",
                verticalalignment="bottom",
                horizontalalignment="center",
            )
            title_box._bbox_patch._mutation_aspect = 0.02
            title_box.get_bbox_patch().set_boxstyle("square", pad=_padding)

            if supplement_plot:
                # C. Build Species Comparision Plot | SNP Only
                _TrioTrain_SNP_plot = sns.lineplot(
                    _compare_trio_train_phases.loc[_compare_trio_train_phases["Type"] == "SNP"],
                    ax=axes[1,0],
                    x="METRIC.Recall",
                    y="METRIC.Precision",
                    hue="ModelName",
                    hue_order=list(self._palette_dict.keys()),
                    palette=self._palette_dict,
                    legend=False
                )
                _TrioTrain_SNP_plot.set_ylabel("Precision", fontsize=self.fontsize)
                _TrioTrain_SNP_plot.set_xlabel("", fontsize=8)

                title_box = _TrioTrain_SNP_plot.set_title(
                    "SNV",
                    fontsize=8,
                    weight="bold",
                    position=(0.5, 0.90),
                    y=0.99,
                    backgroundcolor="black",
                    color="white",
                    verticalalignment="bottom",
                    horizontalalignment="center",
                )
                title_box._bbox_patch._mutation_aspect = 0.02
                title_box.get_bbox_patch().set_boxstyle("square", pad=10.8)

                # D. Build Species Comparision Plot | INDEL Only
                _TrioTrain_INDEL_plot = sns.lineplot(
                    _compare_trio_train_phases.loc[_compare_trio_train_phases["Type"] == "INDEL"],
                    ax=axes[1,1],
                    x="METRIC.Recall",
                    y="METRIC.Precision",
                    hue="ModelName",
                    hue_order=list(self._palette_dict.keys()),
                    palette=self._palette_dict,
                )

                _sub_handles = [
                    _handles[2],  # DV
                    _handles[3],  # C12
                    _handles[4],  # C18
                    _handles[5],  # C22
                    _handles[6],  # C28 
                    _handles[7],  # C30
                ]
                _legend = _TrioTrain_INDEL_plot.legend(
                    handles=_sub_handles,
                    labels=["DV", "12", "18", "22", "28", "30"],
                    bbox_to_anchor=(1.05, 1.01),
                    borderaxespad=0,
                    fancybox=False,
                    frameon=False,
                )
                for line in _legend.get_lines():
                    line.set_linewidth(2)

                _TrioTrain_INDEL_plot.set_ylabel("", fontsize=8)
                _TrioTrain_INDEL_plot.set_xlabel("", fontsize=8)

                title_box = _TrioTrain_INDEL_plot.set_title(
                    "INDEL",
                    fontsize=8,
                    weight="bold",
                    position=(0.5, 0.90),
                    y=0.98,
                    backgroundcolor="black",
                    color="white",
                    verticalalignment="bottom",
                    horizontalalignment="center",
                )
                title_box._bbox_patch._mutation_aspect = 0.02
                title_box.get_bbox_patch().set_boxstyle("square", pad=10.3)

                # E. Build Training Length Comparision Plot | SNP Only
                _Train_Length_SNP_plot = sns.lineplot(
                    _compare_training_length.loc[_compare_training_length["Type"] == "SNP"],
                    ax=axes[2,0],
                    x="METRIC.Recall",
                    y="METRIC.Precision",
                    hue="ModelName",
                    hue_order=list(self._palette_dict.keys()),
                    palette=self._palette_dict,
                    legend=False
                )
                _Train_Length_SNP_plot.set_ylabel("Precision", fontsize=self.fontsize)
                _Train_Length_SNP_plot.set_xlabel("Recall", fontsize=self.fontsize)

                title_box = _Train_Length_SNP_plot.set_title(
                    "SNV",
                    fontsize=8,
                    weight="bold",
                    position=(0.5, 0.90),
                    y=0.99,
                    backgroundcolor="black",
                    color="white",
                    verticalalignment="bottom",
                    horizontalalignment="center",
                )
                title_box._bbox_patch._mutation_aspect = 0.02
                title_box.get_bbox_patch().set_boxstyle("square", pad=10.8)

                # F. Build Training Length Comparision Plot | INDEL Only
                _Train_Length_INDEL_plot = sns.lineplot(
                    _compare_training_length.loc[_compare_training_length["Type"] == "INDEL"],
                    ax=axes[2,1],
                    x="METRIC.Recall",
                    y="METRIC.Precision",
                    hue="ModelName",
                    hue_order=list(self._palette_dict.keys()),
                    palette=self._palette_dict,
                )

                _sub_handles = [
                    _handles[2],  # DV
                    _handles[8],  # 2
                    _handles[9],  # 2B
                    _handles[10], # 2C
                    _handles[6],  # 28
                ]
                _legend = _Train_Length_INDEL_plot.legend(
                    handles=_sub_handles,
                    labels=["DV", "2", "2B", "2C", "28"],
                    bbox_to_anchor=(1.05, 1.01),
                    borderaxespad=0,
                    fancybox=False,
                    frameon=False,
                )
                for line in _legend.get_lines():
                    line.set_linewidth(2)

                _Train_Length_INDEL_plot.set_ylabel("", fontsize=self.fontsize)
                _Train_Length_INDEL_plot.set_xlabel("Recall", fontsize=self.fontsize)

                title_box = _Train_Length_INDEL_plot.set_title(
                    "INDEL",
                    fontsize=8,
                    weight="bold",
                    position=(0.5, 0.90),
                    y=0.98,
                    backgroundcolor="black",
                    color="white",
                    verticalalignment="bottom",
                    horizontalalignment="center",
                )
                title_box._bbox_patch._mutation_aspect = 0.02
                title_box.get_bbox_patch().set_boxstyle("square", pad=10.3)

            plt.tight_layout(rect=(0.002, 0, 0.98, 1))

    def build_avg_cov(self) -> None:
        """
        Create (3) plots:
            1. Distribution of mean coverage for training samples
            2. Distribution of mean coverage for testing samples
            3. Normalized KDE for mean coverage to compare subsets
        """
        self._description = "mean coverage"
        sns.set_theme("paper", style="ticks")

        # Identify boundaries for X axis
        _summary = self._df.describe()
        _lower_bound = round_down(value=int(_summary["avg_coverage"]["min"]), digits=1)
        _upper_bound = round_up(value=int(_summary["avg_coverage"]["max"]), digits=1)
        ticks = list(range(_lower_bound, (_upper_bound + 10), 10))
        labels = [f"{x}×" for x in ticks]

        # Define subsets used for the first two histogram plots
        _train_data = self._df[self._df["group"] == "Training"]
        _train_mean = _train_data["avg_coverage"].mean()
        _train_n = len(_train_data)

        _test_data = self._df[self._df["group"] == "Testing"]
        _test_mean = _test_data["avg_coverage"].mean()
        _test_n = len(_test_data)

        # Define the color palette
        pallete = sns.color_palette(palette="Set1")

        # Initalize (3) plots within one figure
        fig, ax = plt.subplots(
            1,
            3,
            figsize=(8, 3),
        )

        # Add (A,B) plot labels
        for n, a in enumerate(ax):
            a.text(
                -0.15,
                1.05,
                # -0.1,
                # 1.1,
                ascii_uppercase[n],
                transform=a.transAxes,
                size=12,
                weight="bold",
            )

        # 1. Build Training Plot
        _train_plot = sns.histplot(
            _train_data,
            x="avg_coverage",
            ax=ax[0],
            color=pallete[0],
        )
        _train_plot.set(xticks=ticks, xticklabels=labels)
        _train_plot.set_ylabel("Sample Count", fontsize=self.fontsize)
        _train_plot.set_xlabel("Mean Coverage", fontsize=self.fontsize)
        _train_plot.set_ylim(0, 18.5)

        title_box = _train_plot.set_title(
            f"Train (N={_train_n})",
            fontsize=8,
            weight="bold",
            position=(0.5, 0.90),
            y=0.97,
            backgroundcolor="black",
            color="white",
            verticalalignment="bottom",
            horizontalalignment="center",
        )
        title_box._bbox_patch._mutation_aspect = 0.05
        title_box.get_bbox_patch().set_boxstyle("square", pad=5.45)

        # 2. Build Testing Plot
        _test_plot = sns.histplot(
            _test_data,
            x="avg_coverage",
            ax=ax[1],
            color=pallete[1],
        )
        _test_plot.set(xticks=ticks, xticklabels=labels)
        _test_plot.set_ylabel("Sample Count", fontsize=self.fontsize)
        _test_plot.set_xlabel("Mean Coverage", fontsize=self.fontsize)

        title_box = _test_plot.set_title(
            f"Test (N={_test_n})",
            fontsize=8,
            weight="bold",
            position=(0.5, 0.90),
            y=0.97,
            backgroundcolor="black",
            color="white",
            verticalalignment="bottom",
            horizontalalignment="center",
        )
        title_box._bbox_patch._mutation_aspect = 0.04
        title_box.get_bbox_patch().set_boxstyle("square", pad=5.65)

        # 3. Build normalized distribution (KDE, kernel density estimation)
        _both = sns.kdeplot(
            self._df,
            x="avg_coverage",
            ax=ax[2],
            bw_adjust=0.75,
            hue="group",
            hue_order=["Training", "Testing"],
            palette="Set1",
            cut=0,
        )
        _both.set(xticks=ticks, xticklabels=labels)
        _both.set_ylabel("Density", fontsize=self.fontsize)
        _both.set_xlabel("Mean Coverage", fontsize=self.fontsize)

        # Add vertical lines to highlight the mean across the entire subset
        _both.axvline(_train_mean, color=pallete[0], linestyle="--", alpha=0.5)
        _both.axvline(_test_mean, color=pallete[1], linestyle="--", alpha=0.5)

        title_box = _both.set_title(
            f"Comparison",
            fontsize=8,
            weight="bold",
            position=(0.5, 0.90),
            y=0.97,
            backgroundcolor="black",
            color="white",
            verticalalignment="bottom",
            horizontalalignment="center",
        )
        title_box._bbox_patch._mutation_aspect = 0.04
        title_box.get_bbox_patch().set_boxstyle("square", pad=5.4)

        _both.legend_.set_title(None)

        # Manually adjust the legend to improve interpretation
        children = plt.gca().get_children()
        plt.legend(
            [children[3], children[4],],
            [f"Train Mean\n(N={_train_n})", f"Test Mean\n(N={_test_n})"],
            frameon=False,
            fontsize=8,
        )
        plt.tight_layout()

    def build_fig2(self,
                   keep_synth: bool = True,
                   supplement_plot: bool = False
                   ) -> None:
        """
        Visualize performance at each checkpoint created with TrioTrain.
        """
        self._description = "Evaluation F1 Score"

        # Data for Figure 2A | SNPs vs INDELs -----------------
        # Extract metrics stratified by variant type:
        _type_data = self._df.loc[
            :,
            self._df.columns.str.contains(
                "SNPs|Indels|Train_Order|Plot_Label|Train_Genome|Phase"
            ),
        ]

        if keep_synth is False:
            filter = _type_data["Phase"].str.contains("5")
            _filtered_df = _type_data[~filter]
        else:
            _filtered_df = _type_data

        _max_x = len(_filtered_df)

        # Then, extract just F1-score values:
        _type_F1_only = _filtered_df.loc[
            :,
            _filtered_df.columns.str.contains(
                "F1|Train_Order|Plot_Label|Train_Genome|Phase"
            ),
        ].copy()
        _type_F1_only["Plot_Label"] = _type_F1_only["Plot_Label"].astype("category")

        # Next, convert wide data to long data:
        _type_melted_data = _type_F1_only.melt(
            ["Train_Order", "Plot_Label", "Phase", "Train_Genome"],
            var_name="variable",
            value_name="value",
        )

        _type_melted_data["variable"] = _type_melted_data["variable"].astype(
            "category"
        )

        _type_melted_data.sort_values("Train_Order", inplace=True)
        _type_melted_data.reset_index(drop=True, inplace=True)

        # _type_min_y = _type_melted_data["value"].min()
        _type_max_y = _type_melted_data["value"].max()

        # Data for Figure 2B | Het vs HomAlt -----------------
        # Extract metrics stratified by variant class
        _class_data = self._df.loc[
            :,
            self._df.columns.str.contains(
                "Het|HomVar|Train_Order|Plot_Label|Train_Genome|Phase"
            ),
        ]

        if keep_synth is False:
            filter = _class_data["Phase"].str.contains("5")
            _filtered_df = _class_data[~filter]
        else:
            _filtered_df = _class_data

        # Then, extract just F1-score values:
        _class_F1_only = _filtered_df.loc[
            :,
            _filtered_df.columns.str.contains(
                "F1|Train_Order|Plot_Label|Train_Genome|Phase"
            ),
        ].copy()
        _class_F1_only["Plot_Label"] = _class_F1_only["Plot_Label"].astype("category")

        # Next, convert wide data to long data:
        _class_melted_data = _class_F1_only.melt(
            ["Train_Order", "Plot_Label", "Phase", "Train_Genome"],
            var_name="variable",
            value_name="value",
        )
        _class_melted_data["variable"] = _class_melted_data[
            "variable"
        ].astype("category")
        _class_melted_data.sort_values("Train_Order", inplace=True)
        _class_melted_data.reset_index(drop=True, inplace=True)

        # _class_min_y = _class_melted_data["value"].min()
        _class_max_y = _class_melted_data["value"].max()

        # Define the maximum value for the Y axis in Fig 2A and Fig 2B
        _max_y = max(_type_max_y, _class_max_y)
        _upper_bound = round_up(_max_y, digits=1) + 0.005

        # Define the minimum values for the Y axis in Fig 2A and Fig 2B
        # _min_y = min(_type_min_y, _class_min_y)
        # _lower_bound = round_down(_min_y, digits=0)
        if keep_synth:
            _lower_bound = 0.84
        else:
            _lower_bound = 0.90

        # Data for Figure 2C | Descriptive Values Requested by R3 -----------------
        # Extract genome-wide genotype metrics stratified by Parent/Offspring
        _training_metadata = self._df.loc[
            :,
            self._df.columns.str.contains(
                "Truth_N_Hets|Truth_N_HomAlt|Truth_Het_HomAlt|Train_Order|Mean_Coverage|Train_Genome|Phase"
            ),
        ]

        if keep_synth is False:
            filter = _training_metadata["Phase"].str.contains("5")
            _filtered_df = _training_metadata[~filter]
        else:
            _filtered_df = _training_metadata

        # Next, convert wide data to long data:
        _training_metadata_melted = _training_metadata.melt(
            ["Train_Order", "Phase", "Train_Genome"],
            var_name="variable",
            value_name="value",
        )

        # Split the 'variable' column into two columns: 'Parent/Offspring' and 'variable_name'
        _training_metadata_melted[['subset', 'new_variable']] = _training_metadata_melted['variable'].str.split('_', n=1, expand=True)

        # Make new columns categorical
        _training_metadata_melted["new_variable"] = _training_metadata_melted["new_variable"].astype(
            "category"
        )
        _training_metadata_melted["subset"] = _training_metadata_melted["subset"].astype(
            "category"
        )
        _training_metadata_melted.sort_values("Train_Order", inplace=True)
        _training_metadata_melted.reset_index(drop=True, inplace=True)

        _metadata_subsets = [
            "Truth_Het_HomAlt",
            "Truth_N_Hets",
            "Truth_N_HomAlts",
            "Mean_Coverage",
        ]

        # Create a list of dataframes (one for each panel)
        _fig_data_2A_2B = [_type_melted_data, _class_melted_data]

        # Define the x-ticks for the first two dataframes
        _x_ticks = [
            _type_melted_data.Train_Order.values,
            _class_melted_data.Train_Order.values,
        ]

        # Define the y-axis values for the first two dataframes
        _all_max_y_values = [_upper_bound, 
                             _upper_bound,
                             ]
        _all_min_y_values = [_lower_bound,
                             _lower_bound,
        ]

        # Subset the 3rd dataframe into different metrics
        _filtered_data = []
        for variable_name in _metadata_subsets:
            # Filter rows where the 'new_variable' column contains each subset
            filtered_df = _training_metadata_melted[
                _training_metadata_melted["new_variable"].str.contains(variable_name)
            ]

            # Add the new dataframe to x-ticks
            _x_ticks.append(filtered_df.Train_Order.values)

            _filtered_data.append(filtered_df)
            _all_max_y_values.append(filtered_df["value"].max())
            _all_min_y_values.append(filtered_df["value"].min())

        _max_total_variants = max(_all_max_y_values[3], _all_max_y_values[4])
        _min_total_variants = max(_all_min_y_values[3], _all_min_y_values[4])
        _common_upper_limit = round_up(_max_total_variants, digits=8) + 1000000
        _common_lower_limit = round_down(_min_total_variants, digits=8) - 1000000
        _all_max_y_values[3:5] = [_common_upper_limit, _common_upper_limit]
        _all_min_y_values[3:5] = [_common_lower_limit, _common_lower_limit]

        # Define the number of panels
        if supplement_plot:
            _figure_data = _fig_data_2A_2B + _filtered_data
            _n_panels = len(_figure_data)
            _fig_length = (2 * 2) + (4 * 1) 
        else:
            _figure_data = _fig_data_2A_2B + [_filtered_data[0]] 
            _n_panels = len(_figure_data)
            _fig_length = 6

        # Define the parameters that differ between panels
        _y_axis_label = ["Offspring F1 Score", "Offspring F1 Score", "Het:HomAlt", "N Hets", "N HomAlts", "Mean Coverage"]
        _style_column = [
            "variable",
            "variable",
            "subset",
            "subset",
            "subset",
            "subset",
        ]
        _style_order_list = [
            ["F1/SNPs", "F1/Indels"],
            ["F1/HomVar", "F1/Het"],
            ["Parent", "Offspring"],
            ["Parent", "Offspring"],
            ["Parent", "Offspring"],
            ["Parent", "Offspring"],
        ]
        _legend_label_list = [
            ["SNVs", "Indels"],
            ["HomAlts", "Hets"],
            ["Parent", "Offspring"],
            ["Parent", "Offspring"],
            ["Parent", "Offspring"],
            ["Parent", "Offspring"],
        ]
        if supplement_plot:
            _height_ratio_list = [2, 2, 1, 1, 1, 1]
        else:
            _panel_title = [
                "Peformance During Training – Variant Type",
                "Performance During Training – Genotype Class",
                "Training Truth Label Contents",
            ]
            _panel_title_padding = [
                19.75,
                18.7,
                22.9,
            ]
            _height_ratio_list = [
                2,
                2,
                1,
            ]

        # Create three sub-plots ------------------------------
        fig, axes = plt.subplots(
            _n_panels,
            1,
            figsize=(8,_fig_length),
            # figsize=self.mm2inch(170, 95),
            gridspec_kw={'height_ratios': _height_ratio_list},
            sharex=True,
            sharey=False,
        )

        # Adjust figure size based on font size
        fig.set_size_inches(fig.get_size_inches() * self.fontsize / 10)

        for n,ax in enumerate(axes):
            # Keep figure proportional to text size
            ax.tick_params(axis='x', which='major', labelsize=self.fontsize)
            ax.tick_params(axis='y', which='major', labelsize=8) 

            # Add (A,B,C...) plot labels
            ax.text(
                -0.08,
                1.05,
                ascii_uppercase[n],
                transform=ax.transAxes,
                size=12,
                weight="bold",
            )

            # Define the y-axis limits
            if n == 2:
                _y_rounded_up = round_up(_all_max_y_values[n], digits = 2)
                _y_rounded_down = round_down(_all_min_y_values[n], digits = 2)

                _panel_upper_bound = _y_rounded_up + 1
                _panel_lower_bound = _y_rounded_down - 1

                yticks = range(int(_y_rounded_down), (int(_y_rounded_up)+3), 3)
                ax.set_yticks(yticks)

            elif n == 5:
                _y_rounded_up = round_up(_all_max_y_values[n], digits = 3)
                _y_rounded_down = round_down(_all_min_y_values[n], digits=3)

                _panel_upper_bound = _y_rounded_up + 5
                _panel_lower_bound = _y_rounded_down - 5

                yticks = range(int(_y_rounded_down), (int(_y_rounded_up) + 5), 10)
                ax.set_yticks(yticks) 
                ax.yaxis.set_major_formatter(
                    mtick.FuncFormatter(
                        lambda y, pos: "{:,.0f}".format(y) + "×"
                    )
                )
                ax.set(
                    xlim=(1, (_max_x + 0.24)),
                    ylim=(_panel_lower_bound, _panel_upper_bound),
                )
            else:
                _panel_upper_bound = _all_max_y_values[n] 
                _panel_lower_bound = _all_min_y_values[n]

                if n > 2 and n < 5:

                    # Format as Millions
                    # y / 1,000,000 -> M
                    yticks = range(
                        int(_all_min_y_values[n]),
                        (int(_all_max_y_values[n]) + 6000000),
                        6000000,
                    )
                    ax.set_yticks(yticks)
                    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda y, pos: 
                    '{:,.0f}'.format(y/1000000) + 'M'))
                    _panel_upper_bound += 1000000
                    _panel_lower_bound -= 1000000

            ax.set(xlim=(1, (_max_x + 0.24)), ylim=(_panel_lower_bound, _panel_upper_bound))

            # Fill in the background for each training phase
            ax.axvspan(xmin=1, xmax=12, facecolor=self._custom_palette[0], alpha=0.3)
            ax.axvspan(xmin=12, xmax=18, facecolor=self._custom_palette[1], alpha=0.3)
            ax.axvspan(xmin=18, xmax=22, facecolor=self._custom_palette[2], alpha=0.3)
            ax.axvspan(xmin=22, xmax=28, facecolor=self._custom_palette[3], alpha=0.3)

            if keep_synth is True:
                ax.axvspan(xmin=28, xmax=_max_x, facecolor=self._custom_palette[4], alpha=0.3)
                _custom_pallette = ["#7f7f7f"] + self._custom_palette
                # Create thick vertical bars highlighting certain checkpoints
                ax.vlines(
                    x=[2, 12, 18, 22, 28, _max_x],
                    ymin=_panel_lower_bound,
                    ymax=_panel_upper_bound,
                    color=_custom_pallette,
                    linewidth=10,
                )
            else:
                # Create thick vertical bars highlighting certain checkpoints
                ax.vlines(
                    x=[12, 18, 22, 28],
                    ymin=_panel_lower_bound,
                    ymax=_panel_upper_bound,
                    color=self._custom_palette[0:4],
                    linewidth=10,
                )

            # Create a separate line plot in each panel
            panel = sns.lineplot(
                data=_figure_data[n],
                x="Train_Order",
                y="value",
                ax=axes[n],
                color="black",
                style=_style_column[n],
                style_order=_style_order_list[n],
                sort=True,
            )
            panel.set(xlabel=None,
                    xticks=_x_ticks[n])

            if supplement_plot is False:
                panel.set_ylabel(_y_axis_label[n], fontsize=self.fontsize)
            else:
                panel.set_ylabel(_y_axis_label[n], fontsize=8)

            if supplement_plot is False and n < 3:
                # Create a black header box with white text
                title_box = panel.set_title(
                    _panel_title[n],
                    fontsize=8,
                    weight="bold",
                    position=(0.5, 0.99),
                    y=0.96,
                    backgroundcolor="black",
                    color="white",
                    verticalalignment="bottom",
                    horizontalalignment="center",
                )
                title_box._bbox_patch._mutation_aspect = 0.015
                title_box.get_bbox_patch().set_boxstyle("square", pad=_panel_title_padding[n])

            # Create a legend within each panel to label the lines
            _legend = panel.get_legend()
            _handles = _legend.legend_handles

            if n < 2:
                if keep_synth:
                    panel.legend(
                            handles=_handles,
                            loc="lower left",
                            labels=_legend_label_list[n],
                            fancybox=False,
                            bbox_to_anchor=(0.05,0),
                        )
                else:
                    panel.legend(
                        handles=_handles,
                        loc="lower right",
                        labels=_legend_label_list[n],
                        fancybox=False,
                        bbox_to_anchor=(0.05, 0),
                    )
            else:
                panel.legend(
                        handles=_handles,
                        loc="upper left",
                        labels=_legend_label_list[n],
                        fancybox=False,
                        bbox_to_anchor=(0.05,1),
                    )

            # Add the x-axis label to the last panel only
            if n == (_n_panels-1):
                panel.set_xlabel("Checkpoint", fontsize=self.fontsize)

        # Edit the entire figure -----------------
        plt.tight_layout(rect=(0.002, 0, 0.95, 1.005))

        if supplement_plot:
            plt.subplots_adjust(hspace=0.2)

        # Create a second legend for outside all panels
        # Labels the training phase colors for the background/vertical lines
        color_legend1 = [
            Patch(facecolor=self._custom_palette[0], alpha=0.3, label="1"),
            Patch(facecolor=self._custom_palette[1], alpha=0.3, label="2"),
            Patch(facecolor=self._custom_palette[2], alpha=0.3, label="3"),
            Patch(facecolor=self._custom_palette[3], alpha=0.3, label="4"),
        ]
        if keep_synth:
            color_legend1 = color_legend1 + [Patch(facecolor=self._custom_palette[4], alpha=0.3, label="5"),]

        legend2 = fig.legend(
            handles=color_legend1,
            title="Phase:",
            bbox_to_anchor=(0.995,0.6),
            borderaxespad=0,
            fancybox=False,
            frameon=False,
        )
        plt.gca().add_artist(legend2)

    def build_training_stratified(self, offspring_only: bool = False, subset: str = "type") -> None:
        """
        How does parental or offspring coverage impact offspring Precision and Recall during training?
        """
        self._description = "Training Precision and Recall"
        # Create four sub-plots ------------------------------
        if offspring_only:
            _x_axis_column = "Offspring_Mean_Coverage"
            _x_axis_label = "Offspring Mean Coverage" 
        else:
            _x_axis_column = "Parent_Mean_Coverage"
            _x_axis_label = "Parent Mean Coverage"

        if subset == "type":
            _title1 = "SNVs"
            if offspring_only:
                _pad1 = 7.75
            else:
                _pad1 = 7.31

            _precision1 = "Precision/SNPs"
            _recall1 = "Recall/SNPs"
            _f1_1 = "F1/SNPs"

            _title2 = "Indels"
            if offspring_only:
                _pad2 = 7.6
            else:
                _pad2 = 7.2
            _precision2 = "Precision/Indels"
            _recall2 = "Recall/Indels"
            _f1_2 = "F1/Indels"

        elif subset == "class":
            _title1 = "Hets"
            if offspring_only:
                _pad1 = 7.95
            else:
                _pad1 = 7.73
            _precision1 = "Precision/Het"
            _recall1 = "Recall/Het"
            _f1_1 = "F1/Het"

            _title2 = "HomAlts"
            if offspring_only:
                _pad2 = 6.95
            else:
                _pad2 = 6.75
            _precision2 = "Precision/HomVar"
            _recall2 = "Recall/HomVar"
            _f1_2 = "F1/HomVar"    

        _summary = self._df.describe()
        # Identify boundaries for Y axes
        # _min_precision = min(_summary["Precision/SNPs"]["min"], _summary["Precision/Indels"]["min"])
        # _max_precision = max(_summary["Precision/SNPs"]["max"], _summary["Precision/Indels"]["max"])

        # _min_recall = min(_summary["Recall/SNPs"]["min"], _summary["Recall/Indels"]["min"])
        # _max_recall = max(_summary["Recall/SNPs"]["max"], _summary["Recall/Indels"]["max"])

        # _y_lower_bound_p = round_down(value=_min_precision, digits = -2)
        # _y_upper_bound_p = round_up(value=_max_precision, digits=0)

        # _y_lower_bound_r = round_down(value=_min_recall, digits = 0)
        # _y_upper_bound_r = round_up(value=_max_recall, digits=-2)

        # print("PRECISION YMAX:", _y_upper_bound_p)
        # print("PRECISION YMIN:", _y_lower_bound_p)
        # print("RECALL YMAX:", _y_upper_bound_r)
        # print("RECALL YMIN:", _y_lower_bound_r)
        # breakpoint()

        # Identify boundaries for X axis
        _x_lower_bound = round_down(value=int(_summary[_x_axis_column]["min"]), digits=1)
        _x_upper_bound = round_up(value=int(_summary[_x_axis_column]["max"]), digits=1)
        xticks = list(range(_x_lower_bound, (_x_upper_bound + 10), 10))
        xlabels = [f"{x}×" for x in xticks]

        fig, axes = plt.subplots(
            3,
            2,
            figsize=(8, 8),
            sharex=True,
            sharey=False,
            layout="constrained",
        )

        axes = axes.flat

        # Original 2x2 grid plot
        # _column_list = [_precision1, _recall1, _precision2, _recall2]
        # _title_list = [_title1, _title1, _title2, _title2]
        # _pad_list = [_pad1, _pad1, _pad2, _pad2]
        # _y_label_list = ["Offspring Precision", "Offspring Recall", "Offspring Precision", "Offspring Recall",]

        # Updated 2x2 grid plot
        # _column_list = [_precision1, _precision2, _recall1, _recall2]
        # _title_list = [_title1, _title2, _title1, _title2]
        # _pad_list = [_pad1, _pad2, _pad1, _pad2]
        # _y_label_list = [
        #     "Offspring Precision",
        #     "Offspring Precision",
        #     "Offspring Recall",
        #     "Offspring Recall",
        # ]

        # New 3x3 grid plot
        _column_list = [_f1_1, _f1_2, _precision1, _precision2, _recall1, _recall2]
        _title_list = [_title1, _title2, _title1, _title2, _title1, _title2]
        _pad_list = [_pad1, _pad2, _pad1, _pad2, _pad1, _pad2]
        _y_label_list = [
            "Offspring F1 Score",
            "Offspring F1 Score",
            "Offspring Precision",
            "Offspring Precision",
            "Offspring Recall",
            "Offspring Recall",
        ]

        for n, ax in enumerate(axes):
            # Add (A,B) plot labels
            ax.text(
                -0.15,
                1.05,
                ascii_uppercase[n],
                transform=ax.transAxes,
                size=12,
                weight="bold",
            )
            # Increase font size for all subplots
            ax.tick_params(axis='both', which='major', labelsize=self.fontsize)

            _keep_legend = False 
            if n == 1:
                _keep_legend = True

            _fig = sns.scatterplot(
                data=self._df,
                ax=ax,
                x=_x_axis_column,
                y=_column_list[n],
                hue="Phase",
                palette=self._custom_palette,
                style="Breed",
                s=40,
                legend=_keep_legend,
            )
            if len(axes) > 4:
                if n == 1:
                    _legend = _fig.get_legend()
            else:
                _legend = _fig.legend(
                        # bbox_to_anchor=(1.05, 1.05),
                        borderaxespad=0,
                        fancybox=False,
                        frameon=False,
                    )
            _fig.set(xticks=xticks, xticklabels=xlabels)
            _fig.set_xlabel(_x_axis_label, fontsize=self.fontsize)

            _fig.set_ylabel(_y_label_list[n], fontsize=self.fontsize)
            title_box = _fig.set_title(
                _title_list[n],
                fontsize=self.fontsize,
                weight="bold",
                position=(0.5, 0.97),
                y=0.96,
                backgroundcolor="black",
                color="white",
                verticalalignment="bottom",
                horizontalalignment="center",
            )
            title_box._bbox_patch._mutation_aspect = 0.03
            title_box.get_bbox_patch().set_boxstyle("square", pad=_pad_list[n])

        axes[1].get_legend().remove()

        plt.tight_layout(rect=(0.002, 0, 0.85, 1))
        fig.legend(
            handles=_legend.legend_handles,
            loc="upper right",
            # bbox_to_anchor=(0.95, 0.95),
            bbox_to_anchor=(0.97, 0.90),
            # borderaxespad=0,
            fancybox=False,
            frameon=False,
            prop={'size': self.fontsize}
        )
        # plt.tight_layout()

    def build_generalization(self,
                             stats_testing: bool = False,
                             min_vals_only: bool = False,
                             subset_data: bool = False,
                             supplement_plot: bool = False,
                             ) -> None:
        """_summary_

        Args:
            min_vals_only (bool, optional): _description_. Defaults to False.
        """
        self._description = "Generalization"

        if stats_testing:
            if min_vals_only:
                _y_axis_limits = self._df.groupby("type", observed=True).describe().reindex(["SNP", "INDEL", "HET", "HOMALT", "HOMREF"]).reset_index()

                y_var = "Minimum Value"
                y_label = "Min. Value"
            else:
                y_var = "value"
                y_label = "Value"

            g = sns.relplot(
                data=self._df,
                x="model_name",
                y=y_var,
                row="type",
                row_order=["SNP", "INDEL", "HET", "HOMALT"],
                hue="metric",
                hue_order=["Precision", "Recall"],
                style="metric",
                kind="line",
                height=2,
                aspect=5,
                facet_kws={'sharey': False,},
            )

            pad_list = [43.35, 43.2, 43.5, 42.55]
            ordered_titlelist = [
                "SNVs",
                "Indels",
                "Hets",
                "HomAlts",
            ]
            _y=0.98
            box_aspect=0.01
        else:
            # _y=0.999
            _y = 0.98
            box_aspect=0.03

            if supplement_plot:
                _data_used = self._df
                pad_list = [
                    7.3,
                    7.1,
                    7.4,
                    6.45,
                    7.3,
                    7.1,
                    7.35,
                    6.5,
                ]
                ordered_titlelist = [
                    "Bovine SNVs",
                    "Bovine Indels",
                    "Bovine Hets",
                    "Bovine HomAlts",
                    "Human SNVs",
                    "Human Indels",
                    "Human Hets",
                    "Human HomAlts",
                ]
                _col_order = ["SNP", "INDEL", "HET", "HOMALT"]
            else:
                _data_used = self._df[self._df["type"].isin(["SNP", "INDEL"])]
                pad_list = [6.6, 6.5, 6.6, 6.5]
                ordered_titlelist = [
                    "Bovine SNVs",
                    "Bovine Indels",
                    "Human SNVs",
                    "Human Indels",
                ]
                _col_order = ["SNP", "INDEL"]

            g = sns.catplot(
                data=_data_used,
                x="value",
                y="model_name",
                row="species",
                col="type",
                col_order=_col_order,
                kind="box",
                hue="model_name",
                legend=False,
                palette=self._palette_dict,
                height=3,
            )

        for n, ax in enumerate(g.axes.flat):
            ax.tick_params(axis="both", labelsize=self.fontsize)

            # NOTE: Catplot is unable to use different axis limits for each sub-plot
            ax.set_xlim(0.75, 1)

            if min_vals_only:
                # Enable different axis limits for each plot
                _min = _y_axis_limits.loc[n, "Minimum Value"]["min"]
                _max = _y_axis_limits.loc[n, "Minimum Value"]["max"]
                _lower_limit = round_down(_min, digits=1)
                _upper_limit = round_up(_max, digits=1)
                g.axes[n, 0].set_ylim(_lower_limit, _upper_limit)

            # Add a legend to the first plot
            if n == 0 and stats_testing:
                ax.legend(["Mean Precision (N=13)", "95% CI", "Mean Recall (N=13)", "95% CI"], loc="lower left", title=None, fancybox=False, ncol=2)

            if stats_testing:
                # Add (A,B) plot labels
                ax.text(
                    -0.07,
                    # -0.1,
                    # 1.1,
                    1.05,
                    ascii_uppercase[n],
                    transform=ax.transAxes,
                    size=12,
                    weight="bold",
                )

                # Update the axis labels
                ax.set_xlabel("Checkpoint", fontsize=self.fontsize)
                ax.set_ylabel(y_label, fontsize=self.fontsize)
            else:        
                # Add (A,B) plot labels
                ax.text(
                    -0.1,
                    1.05,
                    # -0.07,
                    # 1.0,
                    ascii_uppercase[n],
                    transform=ax.transAxes,
                    size=12,
                    weight="bold",
                )

                # Update the axis labels
                ax.set_ylabel("Checkpoint", fontsize=self.fontsize)
                ax.set_xlabel("F1 Score", fontsize=self.fontsize)

            # Add sub-figure title boxes
            title_box = ax.set_title(
                label=ordered_titlelist[n],
                fontsize=8,
                weight="bold",
                position=(0.5, 0.99),
                y=_y,
                backgroundcolor="black",
                color="white",
                verticalalignment="bottom",
                horizontalalignment="center",
            )
            title_box._bbox_patch._mutation_aspect = box_aspect
            title_box.get_bbox_patch().set_boxstyle("square", pad=pad_list[n])

        if stats_testing:
            # Remove the unecessary Seaborn legend
            g._legend.remove()

        if subset_data:
            plt.tight_layout()
        else:
            if stats_testing:
                if self._supplemental_plot:
                    plt.xlim("DV-AF", "30")
                else:
                    plt.xlim("DV-AF", "28")

        # Adjust figure size based on font size
        # fig.set_size_inches(fig.get_size_inches() * self.fontsize / 10)
        plt.tight_layout()

    def build_fig4(self) -> None:
        self._description = "Stratified Precision-Recall Curves in HG002"
        # Save a copy of the DataFrame before cleaning
        _og_df = self._df.copy()

        # 1. Fig4 A & B: Create ROC curve without stratification
        self.clean_pr_roc_data()

        # Original Fig4 A/B only (no stratifications)
        # hg002_roc.build_pr_roc()
        # hg002_roc.generate_figure()

        # 2. Fig4: Grab P-R ROC Data For Specific Checkpoints
        _compare_all = self._df[
            self._df["ModelName"].isin(
                [
                    "DT",
                    "DV-AF",
                    "DV",
                    "28",
                ]
            )
        ].copy()

        # 3. Fig4 C,D,E,F: Create ROC curve with stratification
        self._df = _og_df.copy()
        self._annotate = "SegDups"
        self.clean_pr_roc_data()
        _compare_stratifications = self._df[
            self._df["ModelName"].isin(
                [
                    "DT",
                    "DV-AF",
                    "DV",
                    "28",
                ]
            )
        ]

        # Updated Fig4 -- plotting no stratifications & stratifications together
        fig,axes = plt.subplots(
            nrows=3,
            ncols=2,
            figsize=(6,8),
            sharey=False,
            sharex=True,
            )
        _dims = [axes[0, 0], axes[0, 1], axes[1, 0], axes[1,1], axes[2,0], axes[2,1]]

        # Identify lower boundaries for X and Y axes
        y_upper_bound1 = 1.0005
        y_upper_bound2 = 1.005 

        # Panels A & B & C & D
        _summary1 = _compare_all.groupby(by="ModelName", observed=False).describe()
        y_lower_bound1 = _summary1["METRIC.Precision"]["25%"].min()

        # Panels E & F
        _summary2 = _compare_stratifications.groupby(by=["ModelName", "Subset"], observed=False).describe()  
        y_lower_bound2 = _summary2["METRIC.Precision"]["mean"].min()

        # Define Black Box Titles and Padding
        _title_list = [
            "SNVs",
            "Indels",
            "SNVs – Outside SegDups",
            "Indels – Outside SegDups",
            "SNVs – Within SegDups",
            "Indels – Within SegDups",
        ]
        _padding_list = [
            7.4,
            7.2,
            2.65,
            2.45,
            3.0,
            2.85,
        ]
        _aspect_list = [0.05, 0.05, 0.15, 0.15, 0.15, 0.15]
        _legend_list = [True, False, False, False, False, False]
        _data_list = [
            _compare_all.loc[_compare_all["Type"] == "SNP"],
            _compare_all.loc[_compare_all["Type"] == "INDEL"],
            _compare_stratifications.loc[
                (_compare_stratifications["Type"] == "SNP")
                & (_compare_stratifications["Subset"] == "notinsegdups")
            ],
            _compare_stratifications.loc[
                (_compare_stratifications["Type"] == "INDEL")
                & (_compare_stratifications["Subset"] == "notinsegdups")
            ],
            _compare_stratifications.loc[
                (_compare_stratifications["Type"] == "SNP")
                & (_compare_stratifications["Subset"] == "segdups")
            ],
            _compare_stratifications.loc[
                (_compare_stratifications["Type"] == "INDEL")
                & (_compare_stratifications["Subset"] == "segdups")
            ],
        ]

        # Adjust figure size based on font size
        fig.set_size_inches(fig.get_size_inches() * self.fontsize / 10)

        # Add (A,B) plot labels
        for n,ax in enumerate(axes.flat):
            # Keep figure proportional to text size
            ax.tick_params(axis='x', which='major', labelsize=8)
            ax.tick_params(axis='y', which='major', labelsize=8)

            ax.text(
                -0.09,
                1.005,
                ascii_uppercase[n],
                transform=ax.transAxes,
                size=12,
                weight="bold",
            )
            # Define axis limits (zoom in)
            if n < 4:
                ax.set(xlim=(0.15, 1), ylim=(y_lower_bound1, y_upper_bound1))
            else:
                ax.set(xlim=(0.15, 1), ylim=(y_lower_bound2, y_upper_bound2))

            # Add black title box
            title_box = ax.set_title(
                f"HG002 {_title_list[n]}",
                fontsize=8,
                weight="bold",
                position=(0.5, 0.90),
                y=0.95,
                backgroundcolor="black",
                color="white",
                verticalalignment="bottom",
                horizontalalignment="center",
            )
            title_box._bbox_patch._mutation_aspect = _aspect_list[n]
            title_box.get_bbox_patch().set_boxstyle("square", pad=_padding_list[n])

            _panel = sns.lineplot(
                _data_list[n],
                ax=_dims[n],
                x="METRIC.Recall",
                y="METRIC.Precision",
                hue="ModelName",
                hue_order=list(self._palette_dict.keys()),
                palette=self._palette_dict,
                legend=_legend_list[n],
            )
            if n == 0:
                _legend = _panel.get_legend()
                _handles = _legend.legend_handles
                _sub_handles = [
                    _handles[0], #DT
                    _handles[2], #DV
                    _handles[1], #DV-AF
                    _handles[6], #C28
                    ]
                final_legend = _panel.legend(
                    handles=_sub_handles,
                    title="Checkpoint:",
                    labels=["DT", "DV", "DV-AF", "28"],
                    loc="lower left",
                    # borderaxespad=0,
                    fancybox=False,
                    # frameon=False,
                )
                for line in final_legend.get_lines():
                    line.set_linewidth(2)

            if n in [0, 2, 4]:
                # add a y-axis label for all left panels
                ax.set_ylabel("Precision", fontsize=self.fontsize)
            else:
                # remove y-axis abels for all right panels
                ax.set_ylabel("")
                ax.set_yticklabels([])
                # ax.set_yticks([])

            if n in [4, 5]:
                ax.set_xlabel("Recall", fontsize=self.fontsize)

        plt.tight_layout()

    def clean_mie_rate(self) -> None:
        self._df[["species", "ancestry"]] = self._df["info"].str.split("_", n=1, expand=True)
        self._df = self._df.replace(
            {
                "variant_caller": {
                    "DT1.4_default_human": "DT",
                    "DV1.4_default_human": "DV",
                    "DV1.4_WGS.AF_human": "DV-AF",
                    "DV1.4_WGS.AF_OneTrio": "2",
                    "DV1.4_WGS.AF_OneTrio_AA_BR": "2B",
                    "DV1.4_WGS.AF_OneTrio_YK_HI": "2C",
                    "DV1.4_WGS.AF_cattle1": "12",
                    "DV1.4_WGS.AF_cattle2": "18",
                    "DV1.4_WGS.AF_cattle3": "22",
                    "DV1.4_WGS.AF_cattle4": "28",
                    "DV1.4_WGS.AF_cattle5": "30",
                },
                "species": {"Cow": "Bovine"},
                "ancestry": {
                    "AngusBrahmanF1": "AAxBR",
                    "YakHighlanderF1": "YKxHI",
                    "BisonSimmentalF1": "BIxSI",
                    "Chinese": "HC",
                    "Ashkenazi": "AJ"
                    },
                "sampleID": {
                    "UMCUSAM000000341496": "SAMN08473802",
                    "UMCUSAF000000341497": "SAMN12153487",
                    "UMCUSAM000000341713": "SAMN16780309",
                    "NA24631": "HG005",
                    "NA24385": "HG002"
                    }
            }
            )

        # exclude single-trio checkpoints
        _clean_data = self._df[~self._df["variant_caller"].isin(["2", "2B", "2C"])].copy()
        _sorted_vals1 = ["DT", "DV-AF", "DV", "12", "18", "22", "28", "30"]
        _checkpoint_categories = CategoricalDtype(categories=_sorted_vals1, ordered=True)

        _clean_data["variant_caller"] = _clean_data[
            "variant_caller"
        ].astype(_checkpoint_categories)
        _clean_data["species"] = _clean_data[
            "species"
        ].astype("category")

        self._final_labels = list()
        _ancestry_labels = _clean_data["ancestry"].unique().tolist()
        _sample_labels = _clean_data["sampleID"].unique().tolist()
        for idx,item in enumerate(_ancestry_labels):
            _new_label = f"{_sample_labels[idx]}\n{item}"
            self._final_labels.append(_new_label)

        _clean_data["ancestry"] = _clean_data[
            "ancestry"
        ].astype("object")

        _clean_data["mendelian_error_rate"] = (
            _clean_data["mendelian_error_rate"].str.rstrip("%").astype(float) / 100
        )

        self._df = _clean_data.copy()

    def build_mie_rate(self)-> None:
        self._description = "SNV MIE Rate"
        _ancestry_counts = self._df.groupby("species", observed=True)["ancestry"].count()
        _total = _ancestry_counts.sum()
        xranges = (_ancestry_counts / _total) * 200
        xranges *= 1.1  # Account for default margins

        g = sns.catplot(
            data=self._df,
            kind="bar",
            col="species",
            col_order=["Bovine", "Human"],
            x="ancestry",
            y="mendelian_error_rate",
            hue="variant_caller",
            palette=self._palette_dict,
            sharex=False,
            height=3,
            aspect=1.25,
            facet_kws=dict(gridspec_kws=dict(width_ratios=xranges)),
        )
        g.set_ylabels("MIE Rate", fontsize=12)
        g._legend.remove()

        _titles = ["Bovine SNVs", "Human SNVs"]
        _pad_list = [15.8, 9.5]
        _aspect_list = [0.02, 0.04]
        _labels_list = [self._final_labels[0:3], self._final_labels[3:5]]

        for n, ax in enumerate(g.axes.flat):
            # Add (C) plot label
            ax.text(
                -0.08,
                1.09,
                ascii_uppercase[n],
                transform=ax.transAxes,
                size=12,
                weight="bold",)

            # Add black title box
            title_box = ax.set_title(
                label=_titles[n],
                fontsize=8,
                weight="bold",
                position=(0.5, 0.90),
                y=0.99,
                backgroundcolor="black",
                color="white",
                verticalalignment="bottom",
                horizontalalignment="center",
            )
            title_box._bbox_patch._mutation_aspect = _aspect_list[n]
            title_box.get_bbox_patch().set_boxstyle("square", pad=_pad_list[n])
            if n == 0:
                _handles = g._legend.legend_handles
                ax.legend(
                    handles=_handles,
                    loc="upper right",
                    title="Checkpoints:",
                    fancybox=False,
                    ncol=2,
                )

        for n, species in enumerate(g.axes_dict):
            g.axes_dict[species].set_xlabel("")
            g.axes_dict[species].yaxis.set_major_formatter(
                mtick.PercentFormatter(
                    xmax=1.0,
                    decimals=2,
                )
            )
            g.axes_dict[species].set_xticklabels(_labels_list[n])
        plt.tight_layout()

    def build_mie_calibration(self) -> None:
        self._description = "MIE Calibration"
        _max_num_variants = max(self._num_variants.values())
        _x_upper_limit = round_up(_max_num_variants, digits=6)

        # fig, ax = plt.subplots(figsize=(5, 5))
        _plot = sns.relplot(
            data=self._df,
            kind="line",
            x="Num_SNVs",
            y="Cumulative_MIE%",
            hue="Variant_Caller",
            hue_order=["DT", "DV", "DV-AF", "28"],
            palette=self._palette_dict,
            height=4,
            aspect=1.75,
        )

        # Remove the unecessary Seaborn legend
        _plot._legend.remove()

        # Format the axes labels
        for ax in _plot.axes.flat:
            ax.yaxis.set_major_formatter(
                mtick.PercentFormatter(
                    xmax=100.0,
                    decimals=2,
                )
            )
            # Manually Add a Legend
            _legend = ax.legend(
                title="Checkpoint:",
                loc="upper left",
                fancybox=False,
            )
            for line in _legend.get_lines():
                line.set_linewidth(2)

            # Add (C) plot label
            ax.text(
                -0.09,
                1.01,
                ascii_uppercase[2],
                transform=ax.transAxes,
                size=12,
                weight="bold",
            )

            # Add black title box
            title_box = ax.set_title(
                "HG002 Mendelian Inheritance Errors",
                fontsize=8,
                weight="bold",
                position=(0.5, 0.90),
                y=0.98,
                backgroundcolor="black",
                color="white",
                verticalalignment="bottom",
                horizontalalignment="center",
            )
            title_box._bbox_patch._mutation_aspect = 0.02
            title_box.get_bbox_patch().set_boxstyle("square", pad=22.4)

        # Format the axes labels
        _plot.set_axis_labels(
            x_var=f"Cumulative Variants\nhigh \u2192 low GQ",
            y_var="Cumulative MIE Rate",
            fontsize=self.fontsize,
        )
        _plot.set(
            xlim=(0, _x_upper_limit),
        )
        plt.tight_layout()

    def generate_figure(self) -> None:

        if not self._plot.file_exists or self.args.overwrite:
            if self.args.overwrite:
                if self.args.dry_run:
                    self.logger.info(
                        f"{self.logger_msg}: --overwrite=True, pretending to replace previous plot."
                    )
                else:
                    self.logger.info(
                        f"{self.logger_msg}: --overwrite=True, previous plot will be replaced."
                    )
        if self.args.dry_run:
            self.logger.info(
                f"{self.logger_msg}: pretending to create {self._description} plot | '{self._plot.path}'"
            )

            plt.show()
        else:
            self.logger.info(
                f"{self.logger_msg}: creating {self._description} plot | '{self._plot.path}'"
            )
            plt.savefig(str(self._plot.path_to_file), format="pdf")
            # plt.savefig(str(self._plot.path_to_file), format="tiff", dpi=1200)
            plt.show()


def __init__() -> None:
    from helpers.wrapper import Wrapper, timestamp

    # Collect start time
    Wrapper(__file__, "start").wrap_script(timestamp())

    sns.set_context("paper")
    sns.set_theme("paper", style="whitegrid", rc={"font.size":10,"axes.titlesize":10,"axes.labelsize":8})

    ## ----------------- ##
    ##   FINAL FIGURES   ##
    ## ----------------- ##
    # pr_plot = Plot()
    # pr_plot.find_figure()
    # pr_plot.find_data()
    # pr_plot.clean_pr_roc_data()
    # pr_plot.save_cleaned_data()
    # pr_plot.build_pr_roc()
    # pr_plot.generate_figure()

    # Main Figure
    # Figure 1 A,B,C ----------------------------
    # coverage_plot = Plot(plot_type="AVG_COV")
    # coverage_plot.find_figure()
    # coverage_plot.find_data()
    # coverage_plot.clean_coverage_data()
    # # coverage_plot.clean_coverage_data(cattle_only=True)
    # coverage_plot.build_avg_cov()
    # coverage_plot.generate_figure()

    # Depreciated Main Figure
    # Keep for using during presentations!
    # Phases 1 - 4 only -----------------------
    # fig2.find_figure()
    # fig2.build_fig2(keep_synth=False)
    # fig2.generate_figure()

    # Main Figure
    # Figure 2 A,B,C ----------------------------
    # Phase 1 - 5 ----------------------------
    # fig2 = Plot(plot_type="TRAIN_F1")
    # fig2.find_data()
    # # supplement_plot=False, adds (1) training metadata plots
    # fig2.find_figure()
    # fig2.build_fig2()
    # fig2.generate_figure()

    # Supplemental Plot
    # Figure S3: A,B,C,D,E,F ----------------------------
    # Phase 1 - 5 ----------------------------
    # fig2 = Plot(plot_type="TRAIN_F1")
    # fig2.find_data()
    # # supplement_plot=True, adds (3) training metadata plots
    # fig2.find_figure(supplemental_plot=True)
    # fig2.build_fig2(supplement_plot=True)
    # fig2.generate_figure()

    # Supplemental Plots S4/S5
    # model_behavior = Plot(plot_type="IMPACTS")
    # model_behavior.find_data()
    # model_behavior.clean_performance()
    # _original_suffix = model_behavior._suffix

    # # Figure S4: A,B,C,D ----------------------------
    # # Phases 1 - 4 only -----------------------
    # # NOTE: Input file created when cleaning data with Figure 2
    # # COVERAGE vs SNV|INDEL
    # model_behavior._suffix = f"{_original_suffix}_FigS4"
    # model_behavior.find_figure()
    # model_behavior.build_training_stratified(subset="type", offspring_only=False)
    # model_behavior.generate_figure()
    # breakpoint()

    # model_behavior._suffix = f"{_original_suffix}_FigS4_offspring"
    # model_behavior.find_figure()
    # model_behavior.build_training_stratified(subset="type", offspring_only=True)
    # model_behavior.generate_figure()
    # # breakpoint()

    # # Figure S5: A,B,C,D ----------------------------
    # # Phases 1 - 4 only -----------------------
    # # NOTE: Input file created when cleaning data with Figure 2
    # # COVERAGE vs. HET|HOMALT
    # model_behavior._suffix = f"{_original_suffix}_FigS5"
    # model_behavior.find_figure()
    # model_behavior.build_training_stratified(subset="class", offspring_only=False)
    # model_behavior.generate_figure()
    # # breakpoint()

    # model_behavior._suffix = f"{_original_suffix}_FigS5_offspring"
    # model_behavior.find_figure()
    # model_behavior.build_training_stratified(subset="class", offspring_only=True)
    # model_behavior.generate_figure()

    # Main Figure
    # Figure 3: A,B,C,D ----------------------------
    # Phase 1 - 5 ---------------------------
    # NOTE: N=19 for all boxes except DT (N=3) for bovine, and N=6 for all humans!-
    fig3 = Plot(plot_type="TEST_F1")
    fig3.find_figure()
    fig3.find_data()
    fig3.clean_generalization()
    fig3.build_generalization()
    fig3.generate_figure()

    # Supplemental Plot
    # Figure S6: A,B,C,D,E,F ----------------------------
    # Phase 1 - 5 ----------------------------
    # fig3.find_figure(supplemental_plot=True)
    # fig3.build_generalization(supplement_plot=True)
    # fig3.generate_figure()

    # Supplemental Plot
    # Figure S7: A,B,C,D ----------------------------
    # Phase 1 - 5 ----------------------------
    # stats_testing = Plot(plot_type="STATS_TEST")
    # stats_testing.find_figure(supplemental_plot=True)

    # # Create summary plot of all values (excludes OneTrio)
    # stats_testing.find_data()
    # stats_testing.clean_generalization(stats_testing=True)

    # # print(stats_testing._df.head())

    # # # Get statistical signficance of generalization
    # # stats_testing.estimate_generalization()
    # # breakpoint()
    # #
    # stats_testing.build_generalization(stats_testing=True)
    # stats_testing.generate_figure()

    # # Create a separate figure to check "minimum values" with generalization
    # # Supplemental Plot (Not Used)
    # # Figure S7_min_values: A,B,C,D ----------------------------
    # # Phase 1 - 5 ----------------------------
    # stats_testing = Plot(plot_type="STATS_TEST")
    # stats_testing.find_figure(supplemental_plot=True)

    # # Create summary plot of all values (excludes OneTrio)
    # stats_testing.find_data()
    # stats_testing.clean_generalization(stats_testing=True, min_vals_only=True)

    # # Update the figure file name to avoid replacing the supplemental plot used
    # _fig_name = stats_testing._plot.file_name.split(".")
    # _min_valus_only = f"{_fig_name[0]}_min_values.{_fig_name[1]}"
    # stats_testing._plot = File(path_to_file=stats_testing._output_path/ _min_valus_only,
    #                   logger=stats_testing.logger,
    #                   logger_msg=stats_testing.logger_msg,
    #                   debug_mode=stats_testing.args.debug,
    #                   dryrun_mode=stats_testing.args.dry_run)
    # stats_testing._plot.check_status()

    # if stats_testing.args.overwrite:
    #     stats_testing._plot.check_status(should_file_exist=True)
    # else:
    #     stats_testing._plot.check_status()

    # stats_testing.build_generalization(stats_testing=True, min_vals_only=True)
    # stats_testing.generate_figure()

    # # [NOTE: BROKEN CODE] Create a separate figure for the "alternative checkpoints" (OneTrio)
    # _fig_name = stats_testing._plot.file_name.split(".")
    # _one_trio_only = f"{_fig_name[0]}_alternative_checkpoints.{_fig_name[1]}"
    # stats_testing._plot = File(
    #     path_to_file=stats_testing._output_path / _one_trio_only,
    #     logger=stats_testing.logger,
    #     logger_msg=stats_testing.logger_msg,
    #     debug_mode=stats_testing.args.debug,
    #     dryrun_mode=stats_testing.args.dry_run,
    # )
    # stats_testing._plot.check_status()
    # if stats_testing.args.overwrite:
    #     stats_testing._plot.check_status(should_file_exist=True)
    # else:
    #     stats_testing._plot.check_status()
    # stats_testing.clean_generalization(min_vals_only=True, subset_data=True)
    # stats_testing.build_generalization(min_vals_only=True, subset_data=True)
    # stats_testing.generate_figure()

    # Main Figure
    # Figure 4: A,B ----------------------------
    # Phase 4 only ---------------------------
    # Main Fig4AB - PR ROC Curve with human-trained and C28 in HG002
    # Use directory to create plot

    # Main Fig4CD - PR ROC Curve with C28 in HG002, stratified by SegDups
    # Change input to "annotations/filename.roc.csv.gz" to produce additional panels
    # hg002_roc = Plot()
    # # hg002_roc.find_figure(type="tiff")
    # hg002_roc.find_figure()
    # hg002_roc.find_data()
    # hg002_roc.build_fig4()
    # hg002_roc.generate_figure()

    # Supplemental Plot PR ROC Curves in all models with HG002
    # hg002_roc = Plot()
    # hg002_roc.find_figure(supplemental_plot=True)
    # hg002_roc.find_data()
    # hg002_roc.clean_pr_roc_data()
    # hg002_roc.save_cleaned_data()
    # hg002_roc.build_pr_roc(supplement_plot=True)
    # hg002_roc.generate_figure()

    # Main Plot -
    # TOP: MIE Ranked Grouped Bar Chart
    # mie_bar_plot = Plot(plot_type="TOTAL_MIE")
    # mie_bar_plot.find_data()
    # mie_bar_plot.find_figure(type="tiff")
    # mie_bar_plot.clean_mie_rate()
    # mie_bar_plot.build_mie_rate()
    # mie_bar_plot.generate_figure()

    # BOTTOM: Cumualtive MIE in HG002
    # calibrate_MIE = Plot(plot_type="CALIBRATION")
    # calibrate_MIE.find_figure(type="tiff")
    # calibrate_MIE.find_data()
    # calibrate_MIE.build_mie_calibration()
    # calibrate_MIE.generate_figure()

    ## ----------------- ##
    ##    WIP FIGURES    ##
    ## ----------------- ##

    # Training PROC
    # sns.relplot(
    #     data=_filtered_df,
    #     x="Training_Recall_All",
    #     y="Training_Precision_All",
    #     # y="Training_F1_All",
    #     hue="Training_Phase",
    #     palette=TrainingComparision._custom_palette,
    #     style="Breed_Code",
    #     s=50,
    #     # alpha=0.7
    # )

    # # Illustrates "DV overestimating INDELs in HE trios"
    # sns.relplot(
    #     data=_filtered_df,
    #     x="Average_Coverage",
    #     # y="Training_Precision_All",
    #     # y="Training_F1_All",
    #     # y="Training_Precision_SNV",
    #     y="Training_Precision_INDELs",
    #     hue="Training_Phase",
    #     palette=TrainingComparision._custom_palette,
    #     style="Breed_Code",
    #     s=50,
    #     # alpha=0.7
    # )

    # sns.relplot(
    #     data=_filtered_df,
    #     x="Delta_Num_NonRef",
    #     # x="Truth_Prop_Het",
    #     # x="Truth_Prop_NonRef",
    #     # x="Truth_Prop_Singleton",
    #     # x="Truth_Num_NonRef",
    #     # x="Delta_Hets_HomAlts",
    #     # y="Training_F1_All",
    #     # y="Training_Precision_SNV",
    #     y="Training_Precision_Het",
    #     # y="Training_Recall_Het",
    #     hue="Training_Phase",
    #     palette=TrainingComparision._custom_palette,
    #     style="Breed_Code",
    #     s=50,
    #     # alpha=0.7,
    # )
    # sns.relplot(
    #     data=_filtered_df,
    #     x="Delta_Num_NonRef",
    #     # x="Truth_Num_NonRef",
    #     # x="Truth_Prop_Het",
    #     # x="Truth_Prop_NonRef",
    #     # x="Truth_Prop_Singleton",
    #     # x="Delta_Hets_HomAlts",
    #     # y="Training_F1_All",
    #     # y="Training_Precision_SNV",
    #     # y="Training_Precision_Het",
    #     y="Training_Recall_Het",
    #     hue="Training_Phase",
    #     palette=TrainingComparision._custom_palette,
    #     style="Breed_Code",
    #     s=50,
    #     # alpha=0.7,
    # )
    # sns.relplot(
    #     data=_filtered_df,
    #     x="Delta_Num_NonRef",
    #     # x="Truth_Num_NonRef",
    #     # x="Truth_Prop_Het",
    #     # x="Truth_Prop_NonRef",
    #     # x="Truth_Prop_Singleton",
    #     # x="Delta_Hets_HomAlts",
    #     y="Training_F1_Het",
    #     # y="Training_Precision_SNV",
    #     # y="Training_Precision_Het",
    #     # y="Training_Recall_Het",
    #     hue="Training_Phase",
    #     palette=TrainingComparision._custom_palette,
    #     style="Breed_Code",
    #     s=50,
    #     # alpha=0.7,
    # )

    # 3D Figure -----------------------------------
    # # axes instance
    # fig = plt.figure(figsize=(12,8))
    # ax = Axes3D(fig, auto_add_to_figure=False)
    # fig.add_axes(ax)

    # # get colormap from seaborn
    # # cmap = ListedColormap(sns.color_palette("husl", 256).as_hex())

    # # define custom colors
    # phase_names = _filtered_df["Training_Phase"].unique()

    # color_dict = dict()
    # for i,p in enumerate(list(phase_names)):
    #     color_dict[p] = TrainingComparision._custom_palette[i]

    # # plot each color separately to enable custom legend
    # for phase in phase_names:
    #     # extract data for each training phase
    #     embedding = _filtered_df.loc[_filtered_df["Training_Phase"] == phase]
    #     sc = ax.scatter(
    #         embedding.iloc[:, 5], # Average Coverage
    #         # embedding.iloc[:, 24],
    #         # embedding.iloc[:, 28], # Training_F1_All
    #         # embedding.iloc[:, 32], # Training_F1_INDELs
    #         embedding.iloc[:, 34],  # Training_Precision_All
    #         embedding.iloc[:, 24], # Het_HomAlt ratio
    #         s=40,
    #         c=[color_dict[i] for i in embedding["Training_Phase"]],
    #         marker="o",
    #         label=phase,
    #     )
    #     # legend
    #     plt.legend(loc=2, bbox_to_anchor=(1.05, 1))

    # ax.set_xlabel('Average Coverage')
    # # ax.set_ylabel('Het:HomAlt')
    # ax.set_ylabel("Precision.All")
    # # ax.set_zlabel("F1.All")
    # # ax.set_zlabel("F1.INDELs")
    # # ax.set_zlabel("Precision.All")
    # ax.set_zlabel("Het:HomAlt")
    # ---------------------------------------------------------

    # plt.show()

    Wrapper(__file__, "end").wrap_script(timestamp())

# Execute functions created
if __name__ == "__main__":
    __init__()
