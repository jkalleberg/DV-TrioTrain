#!/usr/bin/python3
"""_summary_

Returns:
    _type_: _description_
"""

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import seaborn as sns
import argparse
from logging import Logger
from dataclasses import dataclass, field
import pandas as pd
from pathlib import Path
from sys import path
from os import path as p
from typing import Union
from regex import search


abs_path = Path(__file__).resolve()
module_path = str(abs_path.parent.parent)
path.append(module_path)

from helpers.utils import get_logger
from helpers.files import Files
from helpers.round import round_up, round_down
from helpers.outputs import check_if_output_exists, check_expected_outputs

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
        help="[REQUIRED]\noutput path\nwhere to save the resulting summary stats and PNG files",
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
            "/mnt/pixstor/schnabelr-drii/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/240528_Benchmarking/summary",
            "-I",
            # "/mnt/pixstor/schnabelr-drii/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/240528_Benchmarking/DV1.4_default_human/UMCUSAM000000341496",
            "/mnt/pixstor/schnabelr-drii/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/240528_Benchmarking/summary/MIE_Ranked/NA24385",
            "--dry-run",
            # "--debug",
            # "--overwrite",
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

    assert args.outpath, "missing --output; Please provide an exisiting directory to save results."
    
    assert (
            args.input
        ), "missing --input; Please provide either a directory location or an existing file containing metrics to plot."


@dataclass
class Plot:
    """
    Check for an exisiting file, before saving/opening multiple types of file formats..

    Attributes:
        path -- a Path object for the file
        file -- a string pairs naming pattern
        logger -- a Logger object
    """
    # optional parameters
    plot_type: str = "PR_ROC"
    
    # internal parameters 
    _annotate: Union[str, None] = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self._custom_palette = ["#d95f02", "#7570b3", "#e7298b", "#67a61e", "#e6a902"]

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
        self._input_file = Files(path_to_file=self.args.input,
                           logger=self.logger,
                           logger_msg=self.logger_msg,
                           debug_mode=self.args.debug,
                           dryrun_mode=self.args.dry_run
                           )
        self._input_file.check_status(should_file_exist=True)

        if self.plot_type == "PR_ROC":
            if self._input_file.file_exists and self._input_file.path.is_file:
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
                    _prefix = _sample_prefix
            else:
                _roc_pattern = r".*roc.all.csv.gz"
                _input_exists, _n_found, _input_name = check_if_output_exists(
                    match_pattern=_roc_pattern,
                    file_type="hap.py ROC file",
                    search_path=self._input_file.path,
                    msg="visualize",
                    logger=self.logger,
                    debug_mode=self.args.debug,
                    dryrun_mode=self.args.dry_run,
                )
                if _input_exists:
                    _missing_input_file = check_expected_outputs(
                        outputs_found=_n_found,
                        outputs_expected=1,
                        msg=self.logger_msg,
                        file_type="hap.py ROC metrics",
                        logger=self.logger,
                    )
                    if not _missing_input_file:
                        _prefix = self._input_file.path.name
                        _new_input = self._input_file.path / _input_name[0]
                        self._input_file = Files(path_to_file=_new_input,
                           logger=self.logger,
                           logger_msg=self.logger_msg,
                           debug_mode=self.args.debug,
                           dryrun_mode=self.args.dry_run
                           )
                        self._input_file.check_status(should_file_exist=True)
                    else:
                        self.logger.error(f"{self.logger_msg}: missing an existing roc.all.csv.gz file from hap.py at input path | '{self._input_file.path_str}'\nPlease re-run after hap.py successfully completes.\nExiting...")
                        exit(1)
            self.png_suffix = f"{_prefix}.pr_roc_plot"
            self.summary_suffix = f"{_prefix}_summary.csv"
        elif self.plot_type == "AVG_COV":
            self.png_suffix = "Kalleberg_Fig1"
            self.summary_suffix = None
        elif self.plot_type == "TRAIN_F1":
            self.png_suffix = "Kalleberg_Fig2"
            self.summary_suffix = "training_metrics_summary.csv"
        elif self.plot_type == "IMPACTS":
            self._suffix = "Kalleberg_Fig3"
            self.summary_suffix = None
        elif self.plot_type == "CALIBRATION":
            self._suffix = "Kalleberg_Fig5"
            self.summary_suffix = None
        else:
            pass

    def find_figure(self) -> None:
        """
        Confirms if creating plot is necessary.
        """
        _png_file = self._output_path / f"{self.png_suffix}.png"

        self._plot = Files(
            path_to_file=_png_file,
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
                f"{self.logger_msg}: unable to overwrite an existing file | '{self._plot.path_str}'\nPlease add the --overwrite flag to discard previous plot.\nExiting..."
            )
            exit(1)

    def find_data(self) -> None:
        """
        Load in the Precision-Recall results from Hap.py.
        """
        if self.plot_type == "TRAIN_F1":
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
                    _json_file = Files(
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
                _df = pd.DataFrame.from_records(data=_all_metrics)

            else:
                self.logger.error(
                    f"{self.logger_msg}: missing JSON training metric files | '{self._input_file.path}'\nPlease update --input with a path to exisiting best_checkpoint.metrics JSON files.\nExiting..."
                )
                exit(1)
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
                self._data_list = list()
                for i,file in enumerate(files):
                    _file = self._input_file.path / file

                    # Load in the csv file
                    _input_file = Files(path_to_file=_file,
                                    logger=self.logger,
                                    logger_msg=self.logger_msg,
                                    debug_mode=self.args.debug,
                                    dryrun_mode=self.args.dry_run
                                    )
                    _input_file.check_status()
                    self.logger.info(
                        f"{self.logger_msg}: loading in {i+1}-of-{inputs_found} CSV files..."
                    )
                    _input_file.load_csv()

                    # Convert to pd.DataFrame
                    _df = pd.DataFrame.from_records(data=_input_file._existing_data)
                    
                    # Make the 'variant_Caller' column a categorical variable
                    _df["Variant_Caller"] = _df["Variant_Caller"].astype("category")
                    self._data_list.append(_df)
                
                # Concatinate all DataFrames...
                self.logger.info(
                        f"{self.logger_msg}: concatinating {inputs_found} CSV files..."
                    )
                self._df = pd.concat(self._data_list, ignore_index=True)
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
        Clean the Precision-Recall results from Hap.py.
        """
        if self._annotate is None:
            # Drop unecessary rows (keep PASS only)
            # Retains values for SNPs and INDEls!
            _filtered_df = self._df[
                (self._df["Subtype"] == "*") & (self._df["Subset"] == "*") & (self._df["Filter"] == "PASS")
            ]
        else:
            # Keep the SNPs/INDELs metrics for that stratification
            _subset = self._annotate.lower()
            _filtered_df = self._df[
                (self._df["Subtype"] == "*") & (self._df["Subset"].str.contains(_subset)) & (self._df["Filter"] == "PASS")
            ]

        # Convert object values to categories or numeric values
        _clean_df = _filtered_df.copy()
        _clean_df["Type"] = _clean_df["Type"].astype("category")
        _clean_df["Subset"] = _clean_df["Subset"].astype("category") 
        _numerical_columns = ["METRIC.Recall", "METRIC.Precision"] 
        for c in _numerical_columns:
            _clean_df[[c]] = _clean_df[[c]].apply(pd.to_numeric)

        # Update the internal data frame
        self._df = _clean_df

    def clean_coverage_data(self) -> None:
        """_summary_
        """
        # Convert object values to categories or numeric values
        _clean_df = self._df.copy()
        _clean_df["group"] = _clean_df["group"].astype("category")
        _numerical_columns = ["avg_coverage"]
        for c in _numerical_columns:
            _clean_df[[c]] = _clean_df[[c]].apply(pd.to_numeric)

        # Update the internal data frame
        self._df = _clean_df

    def save_cleaned_data(self) -> None:
        """
        Save summary metrics to a new file.
        """
        if self.summary_suffix is None:
            self.logger.info(
                    f"{self.logger_msg}: skipping saving a summary CSV file"
                )
            return

        _clean_file = Files(
            path_to_file=self._output_path / self.summary_suffix,
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
                    f"{self.logger_msg}: saving summary data to a new file | '{_clean_file.path_str}'"
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

    def build_pr_roc(self) -> None:
        """
        Create the Precision-Recall ROC figure.
        """
        self._description = "Precision-Recall ROC"
        sns.set_theme("paper", style="whitegrid")

        # Identify lower boundaries for X and Y axes
        _summary = self._df.describe()
        x_lower_bound = _summary["METRIC.Recall"]["25%"]
        y_lower_bound = _summary["METRIC.Precision"]["25%"]

        if self._annotate is None:
            # Create a seaborn plot
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
            _unique_values = self._df["Subset"].unique()
            _stratification = self._annotate.lower()
            _not_stratification = [val for val in _unique_values if val != _stratification][0]
                    
            plot = sns.relplot(
                data=self._df,
                x="METRIC.Recall",
                y="METRIC.Precision",
                kind="line",
                markers=True,
                hue="Type",
                hue_order=["SNP", "INDEL"],
                col="Subset",
                col_order=[_stratification, _not_stratification],
                aspect=0.65,
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
            titles = ["Within SegDups", "Outside SegDups"]
            for ax,title in zip(plot.axes.flat,titles):
                ax.set_title(title)
                ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1.0,
                                                                    decimals=2,
                                                                    ))
                ax.xaxis.set_major_formatter(mtick.PercentFormatter(xmax=1.0,
                                                                    decimals=0,
                                                                    ))
            plot.set_axis_labels(x_var="Recall", y_var="Precision")
            
            # Manually adjust the legend to improve interpretation
            children = plt.gca().get_children()
            
            plt.legend(
                [children[0], children[2]],
                ["SNV", "INDEL"],
                loc="lower left", 
                title=None,
            )
        else:
            print("FIX ME!")
            breakpoint()

        # Edit the matplotlib figure
        plt.tight_layout()

    def build_avg_cov(self) -> None:
        """
        Create (3) plots:
            1. Distribution of mean coverage for training samples
            2. Distribution of mean coverage for testing samples
            3. Normalized KDE for mean coverage to compare subsets
        """
        self._description = "mean coverage"

        # Identify boundaries for X axis
        _summary = self._df.describe()
        _lower_bound = round_down(value=_summary["avg_coverage"]["min"], digits=1)
        _upper_bound = round_up(value=_summary["avg_coverage"]["max"], digits=1)
        ticks = list(range(_lower_bound, _upper_bound, 10))
        labels = [f"{x}x" for x in ticks]

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
            figsize=(15, 4),
        )

        # 1. Build Training Plot
        _train_plot = sns.histplot(
            _train_data,
            x="avg_coverage",
            ax=ax[0],
            color=pallete[0],
        )
        _train_plot.set(
            ylabel="Count", xlabel="Mean Coverage", xticks=ticks, xticklabels=labels
        )

        # 2. Build Testing Plot
        _test_plot = sns.histplot(
            _test_data,
            x="avg_coverage",
            ax=ax[1],
            color=pallete[1],
        )
        _test_plot.set(
            ylabel="Count", xlabel="Mean Coverage", xticks=ticks, xticklabels=labels
        )

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
        _both.legend_.set_title(None)
        _both.set(xlabel="Mean Coverage", xticks=ticks, xticklabels=labels)

        # Add vertical lines to highlight the mean across the entire subset
        _both.axvline(_train_mean, color=pallete[0], linestyle="--", alpha=0.5)
        _both.axvline(_test_mean, color=pallete[1], linestyle="--", alpha=0.5)

        # Manually adjust the legend to improve interpretation
        children = plt.gca().get_children()
        _hidden_line = _both.axvline(10, color="black", linestyle="--", alpha=0.5)
        _both.legend(
            [children[0], children[1], _hidden_line],
            [f"Train (N={_train_n})", f"Test (N={_test_n})", "Subset Mean"],
            frameon=False,
        )
        _hidden_line.remove()

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
                f"{self.logger_msg}: pretending to {self._description} plot | '{self._plot.path_str}'"
            )
            plt.show()
        else:
            self.logger.info(
                f"{self.logger_msg}: creating {self._description} plot | '{self._plot.path_str}'"
            )
            plt.savefig(self._plot.path_str)
            plt.show()


def __init__() -> None:
    from helpers.wrapper import Wrapper, timestamp

    # Collect start time
    Wrapper(__file__, "start").wrap_script(timestamp())

    # pr_plot = Plot()
    # pr_plot.find_figure()
    # pr_plot.find_data()
    # pr_plot.clean_pr_roc_data()
    # pr_plot.save_cleaned_data()
    # pr_plot.build_pr_roc()
    # pr_plot.generate_figure()
    
    # print(sns.color_palette("tab10").as_hex())
    # breakpoint()
    
    calibrate_MIE = Plot(plot_type="CALIBRATION")
    calibrate_MIE.find_data()
    calibrate_MIE.find_figure()
    
    # GATK = 
    _palette = {
        "DT1.4_default_human": "#1f77b4",
        "DV1.4_WGS.AF_human": "#d62728",
        "DV1.4_default_human": "#2ca02c",
        "DV1.4_WGS.AF_cattle1": "#d95f02",
        "DV1.4_WGS.AF_cattle2": "#7570b3",
        "DV1.4_WGS.AF_cattle3": "#e7298b",
        "DV1.4_WGS.AF_cattle4": "#67a61e",
        "DV1.4_WGS.AF_cattle5": "#e6a902",
        "DV1.4_WGS.AF_OneTrio": "#7f7f7f",
        "DV1.4_WGS.AF_OneTrio_AA_BR": "#bcbd22",
        "DV1.4_WGS.AF_OneTrio_YK_HI": "#17becf",
        }

    print("CREATE PLOT")
    fig, ax = plt.subplots(figsize=(5, 5))
    _plot = sns.lineplot(data=calibrate_MIE._df,
                 x="Num_Variants",
                 y="Cumulative_MIE%",
                 hue="Variant_Caller"
                 )
    print("GENERATE FIGURE!")
    calibrate_MIE.generate_figure()
    
    Wrapper(__file__, "end").wrap_script(timestamp())

# Execute functions created
if __name__ == "__main__":
    __init__()
