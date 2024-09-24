#!/bin/python3
"""
description: stratify 'extended.csv' files by genotype class and variant type

example:
    python3 triotrain/summarize/happy_performance.py                           \\
"""

import argparse
# from csv import DictReader
from logging import Logger
from os import path as p
from pathlib import Path
from sys import path, exit
import pandas as pd
from typing import Union, Dict
from dataclasses import dataclass, field
from regex import compile
from natsort import natsorted


abs_path = Path(__file__).resolve()
module_path = str(abs_path.parent.parent)
path.append(module_path)

from helpers.files import Files
from helpers.outputs import check_if_output_exists
# from model_training.slurm.suffix import remove_suffixes

def collect_args() -> argparse.Namespace:
    """
    Process command line argument to execute script.
    """
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
            "-I",
            "--input-path",
            dest="input",
            type=str,
            help="[REQUIRED]\ninput path\nparent directory containing per-sample directories with the extended metrics summary file from hap.py (.CSV)",
            metavar="</path/to/file>",
        )
    parser.add_argument(
        "-O",
        "--output-path",
        dest="outpath",
        type=str,
        help="[REQUIRED]\noutput path\nwhere to save the results",
        metavar="</path/>",
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
        help="if True, display commands to the screen",
        action="store_true",
    )
    # return parser.parse_args()
    return parser.parse_args(
        [
            "--input-path",
            "/mnt/pixstor/schnabelr-drii/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/240528_Benchmarking/",
            "--output-path",
            "/mnt/pixstor/schnabelr-drii/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/240528_Benchmarking/summary/",
            # "--debug",
            "--dry-run",
        ]
    )

def check_args(args: argparse.Namespace, logger: Logger) -> ModuleNotFoundError:
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
        logger.info(
            f"[DRY_RUN]: output will display to screen and not write to a file"
        )

    assert (
        args.input
    ), "missing --input; Please provide an 'extended' meterics file produced by 'hap.py'"
    
    assert args.outpath, "missing --output; Please provide an exisiting directory to save results."

def calculate_total_hom_ref(row: pd.Series, subset: str = "TRUTH") -> pd.Series:
    _total_non_ref = (row[f"{subset}.TOTAL.het"] + row[f"{subset}.TOTAL.homalt"])
    _total_hom_ref = (row[f"{subset}.TOTAL"] - _total_non_ref)
    return _total_hom_ref

def calculate_tp_hom_ref(row: pd.Series, subset: str = "TRUTH") -> pd.Series:
    _total_non_ref_tp = (row[f"{subset}.TP.het"] + row[f"{subset}.TP.homalt"])
    _total_tp = (row[f"{subset}.TP"] - _total_non_ref_tp)
    return _total_tp

def calculate_fn_hom_ref(row: pd.Series) -> pd.Series:
    _total_non_ref_fn = (row["TRUTH.FN.het"] + row["TRUTH.FN.homalt"])
    _total_hom_ref_fn = (row["TRUTH.FN"] - _total_non_ref_fn)
    return _total_hom_ref_fn

def calculate_fp_hom_ref(row: pd.Series) -> pd.Series:
    _total_non_ref_fp = (row["QUERY.FP.het"] + row["QUERY.FP.homalt"])
    _total_hom_ref_fp = (row["QUERY.FP"] - _total_non_ref_fp)
    return _total_hom_ref_fp

# def calculuate_unk_hom_ref(row: pd.Series) -> pd.Series:
#     _total_non_ref_unk = (row["QUERY.UNK.het"] + row["QUERY.UNK.homalt"])
#     _total_unk = row["QUERY.UNK"] - _total_non_ref_unk
#     return _total_unk

def calculate_precision(row: pd.Series) -> pd.Series:
    _denominator = (row["QUERY.TP"] + row["QUERY.FP"])
    return round((row["QUERY.TP"] / _denominator), ndigits=6)

def calculate_recall(row: pd.Series) -> pd.Series:
    _denominator = (row["TRUTH.TP"] + row["TRUTH.FN"])
    return round((row["TRUTH.TP"] / _denominator), ndigits=6)

def calculate_f1_score(row: pd.Series) -> pd.Series:
    _numerator = row["Precision"] * row["Recall"]
    _denominator = row["Precision"] + row["Recall"] 
    return round(2 * ((_numerator / _denominator)), ndigits=6)

# def calculate_frac_na(row: pd.Series, type: str = "het") -> pd.Series:
#     return ((row[f"QUERY.UNK.{type}"] / row[f"QUERY.TOTAL.{type}"]))

@dataclass
class Performance:
    """
    Summarize raw count metrics into precision, recall, and F1 score.
    """

    # required parameters
    csv_input: Union[str, Path]
    logger: Logger

    # optional values
    debug: bool = False
    dry_run: bool = False
    logger_msg: Union[str, None] = None
    
    # internal, imutable values
    _clean_data: Dict[str, Union[int,float]] = field(default_factory=dict, init=False, repr=False)
    _data: pd.DataFrame = field(default_factory=pd.DataFrame, init=False, repr=False)
    _metrics: Dict[str, Union[int,float]] = field(default_factory=dict, init=False, repr=False)
    
    def __post_init__(self) -> None:
        if self.logger_msg is None:
            self.logger_msg = ""
            self._internal_msg = ""
        else:
            self._internal_msg = f"{self.logger_msg}: "
        
        self._metric_names = ["F1_Score", "Precision", "Recall", "Frac_NA"]
        
        self._stratifications = ["SNP", "INDEL", "HomRef", "Het", "HomAlt"]
        for s in self._stratifications:
            for m in self._metric_names:
                _label = f"{m}.{s}"
                self._metrics[_label] = 0
        
        # load in metadata
        _sample_metadata_file = Files(path_to_file="/mnt/pixstor/schnabelr-drii/WORKING/jakth2/DV-TrioTrain/triotrain/summarize/data/benchmarking_metadata.json",
                                      logger=self.logger)
        _sample_metadata_file.check_status(should_file_exist=True)
        _sample_metadata_file.load_json_file()
        self._sample_metadta = _sample_metadata_file.file_dict
        
        _ckpt_metadata_file = Files(path_to_file="/mnt/pixstor/schnabelr-drii/WORKING/jakth2/DV-TrioTrain/triotrain/summarize/data/model_ckpt_metadata.json", logger=self.logger)
        _ckpt_metadata_file.check_status(should_file_exist=True)
        _ckpt_metadata_file.load_json_file()
        self._ckpt_metadata = _ckpt_metadata_file.file_dict
        
    def check_input(self) -> None:
        """
        Confirm the VCF input file exists.
        """
        self._input_file = Files(path_to_file=Path(self.csv_input), logger=self.logger)
        self._input_file.check_status(should_file_exist=True)
        assert (
            self._input_file.file_exists
        ), f"non-existant file provided | '{self._input_file.file_name}'\nPlease provide a valid CSV file."
            
        self._input_file.load_txt_file()
        
        _data_list = list()
        for i,line in enumerate(self._input_file._existing_data):
            if i == 0:
                _keys = line.split(",")
            else:
                _dict = dict()
                if line.startswith("SNP,*,*,PASS") or line.startswith("INDEL,*,*,PASS"):
                    _values = line.split(",")
                    for index,k in enumerate(_keys):
                        _dict[k] = _values[index]
                    _data_list.append(_dict)
                else:
                    continue
            
        _df = pd.DataFrame(_data_list)
        _numerical_columns = _df.columns[7:]
        
        for c in _numerical_columns:
            _df[[c]] = _df[[c]].apply(pd.to_numeric, errors='coerce')
        self._data = _df.copy()
        
        self._subset = self._data[["Type", "QUERY.TP", "QUERY.FP", "TRUTH.TP", "TRUTH.FN"]].copy()
    
    def find_metadata(self) -> None:
        _model_used = self._input_file.path.parent.parent.name
        _sample_id = self._input_file.path.parent.name
        
        _cols_to_keep = ["training_iteration_number", "training_phase", "checkpoint_name", "version"]
        if _model_used in self._ckpt_metadata.keys():
            for k,v in self._ckpt_metadata[_model_used].items():
                if k in _cols_to_keep:
                    self._clean_data[k] = v
        
        self._clean_data["model_name"] = _model_used
        
        if _sample_id in self._sample_metadta.keys():
            for k,v in self._sample_metadta[_sample_id].items():
                self._clean_data[k] = v
    
    def calculate_homref(self) -> None:
        self._data["TRUTH.TOTAL.homref"] = self._data.apply(calculate_total_hom_ref, subset="TRUTH", axis=1)
        self._data["TRUTH.TP.homref"] = self._data.apply(calculate_tp_hom_ref, subset="TRUTH", axis=1)
        self._data["TRUTH.FN.homref"] = self._data.apply(calculate_fn_hom_ref, axis=1)
        self._data["QUERY.TOTAL.homref"] = self._data.apply(calculate_total_hom_ref, subset="QUERY", axis=1)
        self._data["QUERY.TP.homref"] = self._data.apply(calculate_tp_hom_ref, subset="QUERY", axis=1)
        self._data["QUERY.FP.homref"] = self._data.apply(calculate_fp_hom_ref, axis=1)
        # self._data["QUERY.UNK.homref"] = self._data.apply(calculuate_unk_hom_ref, axis=1)
    
    def update_data(self) -> None:
        # Sum metrics across variant type [SNV and INDEL]
        _df = self._data[["Type", "TRUTH.TP.het", "TRUTH.TP.homalt", "TRUTH.TP.homref", "TRUTH.FN.het", "TRUTH.FN.homalt", "TRUTH.FN.homref", "QUERY.TP.het", "QUERY.TP.homalt", "QUERY.TP.homref", "QUERY.FP.het", "QUERY.FP.homalt", "QUERY.FP.homref"]].copy()
        _df.loc[_df.index.max()+1]=['TOTAL']+_df.sum().tolist()[1:]
        
        _total = _df.iloc[2:].copy()
        
        _varinat_types = ["homref", "het", "homalt"]
        
        for v in _varinat_types:
            _cols = [col for col in _total.columns if f"{v}" in col]
            _metrics = _total.loc[:, _cols].to_dict(orient="records")[0]
            _new_row = dict()
            for k,v in _metrics.items():
                _components = k.split(".")
                _metric_name = ".".join(_components[0:2])
                if "Type" not in _new_row.keys():
                    _new_row["Type"] = _components[2].upper()
                
                if _metric_name not in _new_row.keys():
                    _new_row[_metric_name] = int(v)
            
            # Add to previous dataframe
            self._subset.loc[len(self._subset)] = _new_row
            
        self._subset["Precision"] = self._subset.apply(calculate_precision, axis=1)
        self._subset["Recall"] = self._subset.apply(calculate_recall, axis=1)
        self._subset["F1"] = self._subset.apply(calculate_f1_score, axis=1)
            
        # Transpose long data into wide data
        _df = self._subset[["Type", "F1", "Precision", "Recall"]].copy().set_index(["Type"])
        _new_df = _df.unstack()
        _new_df.index = ["_".join(i) for i in _new_df.index]
        last_df = _new_df.to_frame().T
        self._clean_data.update(last_df.to_dict(orient="records")[0])
    
def __init__() -> None:
    from helpers.utils import get_logger
    from helpers.wrapper import Wrapper, timestamp
     
    # Create error log
    current_file = p.basename(__file__)
    module_name = p.splitext(current_file)[0]
    logger = get_logger(module_name)

    # Collect command line arguments
    args = collect_args()
    
    # Check command line args
    check_args(args=args, logger=logger)
    
    if args.dry_run:
        logger_msg = f"[DRY_RUN] - [performance_summary]"
    else:
        logger_msg = f"[performance_summay]"

    # Collect start time
    Wrapper(__file__, "start").wrap_script(timestamp())
    
    # Check for an existing output file:
    _output_csv = Files(path_to_file=f"{args.outpath}/240923_benchmarking_results.csv", logger=logger)
    _output_csv.check_status()
    
    if _output_csv.file_exists and not args.overwrite:
        logger.error(f"{logger_msg}: unable to replace an existing file | '{_output_csv.file_name}'\nPlease add --overwrite flag to continue.")
        exit(1)
    elif _output_csv.file_exists and args.overwrite:
        if args.dry_run:
            logger.info(f"{logger_msg}: --overwrite=True; pretending to overwrite an existing file | '{_output_csv.path_to_file}'")
        else:
            logger.info(f"{logger_msg}: --overwrite=True; replacing an exisiting file | '{_output_csv.path_to_file}'") 
    
    # Identify lots of files to process:
    _extended_metrics_files_list = list()
    _records = list()
    
    # First, confirm input search directory exists:
    _input_path = Path(args.input)
    if _input_path.is_dir():
        
        # Identify if multiple models have been benchmarked
        _model_name_dirs = _input_path.glob("*")
        
        for dir in _model_name_dirs:
            
            # Identify if multiple samples were benchmarked per model
            _sample_dirs = dir.glob("*")
            
            for sample in _sample_dirs:
                
                # Confirm hap.py output file is present
                # And collect full path
                extended_metrics_pattern = compile(f"happy.*extended.csv")

                # Confirm if files do not already exist
                (
                    _existing_happy_metrics_file,
                    _num_files_found,
                    _files_list,
                ) = check_if_output_exists(
                    extended_metrics_pattern,
                    "extended hap.py metrics file",
                    sample,
                    logger_msg,
                    logger,
                    debug_mode=args.debug,
                    dryrun_mode=args.dry_run,
                )
                
                if _existing_happy_metrics_file:
                    _extended_metrics_files_list.append(Path(sample) / _files_list[0] )

    _num_records = len(_extended_metrics_files_list)
    logger.info(f"{logger_msg}: number of metric files | {_num_records}")
    breakpoint()
    
    for itr,_input in enumerate(natsorted(_extended_metrics_files_list)):
        logger.info(f"{logger_msg}: processing input {itr+1}-of-{_num_records}")
        
        # Transform the Trio VCF output from RTG mendelian into a TSV file
        _summary = Performance(
            csv_input=_input,
            logger=logger,
            debug=args.debug,
            dry_run=args.dry_run,
            logger_msg=logger_msg,
        )
        _summary.check_input()
        _summary.find_metadata()
        _summary.calculate_homref()
        _summary.update_data()
        _records.append(_summary._clean_data)
    
    # Write output file:
    _output_csv.write_list_of_dicts(line_list=_records, delim=",")

    Wrapper(__file__, "end").wrap_script(timestamp())


# Execute functions created
if __name__ == "__main__":
    __init__()