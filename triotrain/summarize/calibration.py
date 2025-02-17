#!/bin/python3
"""
description: transform MIE VCF into summary metrics to calibrate DV model

example:
    python3 triotrain/summarize/calibration.py                           \\
"""

import argparse
from csv import DictReader
from logging import Logger
from os import path as p
from pathlib import Path
from sys import path
import pandas as pd
from typing import List

abs_path = Path(__file__).resolve()
module_path = str(abs_path.parent.parent)
path.append(module_path)

from helpers.files import TestFile, Files
from helpers.vcf_to_tsv import Convert_VCF


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
            "--input",
            dest="input",
            type=str,
            help="[REQUIRED]\ninput path\noutput file from rtg-tools mendelian (.VCF)",
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
            "--input",
            "/mnt/pixstor/schnabelr-drii/WORKING/jakth2/TRIOS_220704/TRIO_RAW/Trio14.RAW.sorted.PASS.MIE.exclude_mis.vcf.gz", 
            # "/mnt/pixstor/schnabelr-drii/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/240528_Benchmarking/DV1.4_default_human/TRIOS/Trio14.PASS.MIE.vcf.gz",
            # "/mnt/pixstor/schnabelr-drii/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/240528_Benchmarking/DT1.4_default_human/TRIOS/Trio14.PASS.MIE.vcf.gz",
            # "/mnt/pixstor/schnabelr-drii/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/240528_Benchmarking/DV1.4_WGS.AF_human/TRIOS/Trio14.PASS.MIE.vcf.gz",
            # "/mnt/pixstor/schnabelr-drii/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/240528_Benchmarking/DV1.4_WGS.AF_cattle1/TRIOS/Trio14.PASS.MIE.vcf.gz",
            # "/mnt/pixstor/schnabelr-drii/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/240528_Benchmarking/DV1.4_WGS.AF_OneTrio/TRIOS/Trio14.PASS.MIE.vcf.gz",
            # "/mnt/pixstor/schnabelr-drii/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/240528_Benchmarking/DV1.4_WGS.AF_OneTrio_AA_BR/TRIOS/Trio14.PASS.MIE.vcf.gz",
            # "/mnt/pixstor/schnabelr-drii/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/240528_Benchmarking/DV1.4_WGS.AF_OneTrio_YK_HI/TRIOS/Trio14.PASS.MIE.vcf.gz",
            "--output-path",
            "/mnt/pixstor/schnabelr-drii/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/240528_Benchmarking/summary/MIE_Ranked/UMCUSAM000000341713",
            "--debug",
            # "--dry-run",
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
    ), "missing --input; Please provide a Trio VCF file produced by 'rtg-tools mendelian'"
    
    assert args.outpath, "missing --output; Please provide an exisiting directory to save results."


def sum2(l: List[int]) -> List[int]:
    from numpy import cumsum

    return list(cumsum(l))

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
        logger_msg = f"[DRY_RUN] - [calibrate_mie]"
    else:
        logger_msg = f"[calibrate_mie]"

    # Collect start time
    Wrapper(__file__, "start").wrap_script(timestamp())
    
    _input_path = Path(args.input)
    _labels = _input_path.name.split(".")
    _tsv_path = _input_path.parent
    _trio_name = _labels[0]
    _model_name = _input_path.parent.parent.name
    if "dv" not in _model_name.lower() and "dt" not in _model_name.lower():
        _model_name = "GATK4_PostVQSR_UMAGv1"

    try:
        # Transform the Trio VCF output from RTG mendelian into a TSV file
        mie_vcf = Convert_VCF(
            vcf_input=args.input,
            tsv_output=_tsv_path,
            logger=logger,
            debug=args.debug,
            dry_run=args.dry_run,
            logger_msg=logger_msg,
        )
        mie_vcf.check_files()
    except AssertionError as E:
        logger.error(E)

    # Check for exisiting output
    # _processed_file = TestFile(file=f"{args.outpath}/{mie_vcf._prefix_name}.SNPs.sorted.csv", logger=logger)
    _processed_file = TestFile(file=f"{args.outpath}/{_model_name}.{mie_vcf._prefix_name}.sorted.csv", logger=logger)
    _processed_file.check_missing(logger_msg=logger_msg, debug_mode=args.debug)

    if _processed_file.file_exists:
        logger.info(
            f"{logger_msg}: loading in processed CSV | '{_processed_file.path}'"
        )
        
        with open(_processed_file.file, mode="r", encoding="utf-8-sig") as data:
            dict_reader = DictReader(data, delimiter="\t")
            _tsv_dict_array = list(dict_reader)

        # Sort the GQ from smallest to largest
        # USING THE CHILD'S GQ VALUE!
        print("FIX ME!")
        breakpoint()
        sorted_dict_array = sorted(
            _variable_within_trio, key=lambda x: int(x[f"GQ_{_offspring}"]), reverse=True
        )
        logger.info(
            f"{logger_msg}: done loading in processed CSV | '{_processed_file.path.name}'"
        )
    else:
        # Process MIE TSV into usable format
        mie_vcf.run()
        
        _offspring = mie_vcf._samples[0]
        
        logger.info(f"{logger_msg}: --------------- processing {_model_name} | {_trio_name} | {_offspring} ---------------")       
        
        _num_Non_Ref_Family_Records = 0
        # NOTE: This number (^) should match the value in the RTG-mendelian log file for
        #       the number of sites "checked for Mendelian constraints"

        _num_MissingRef_Records = 0
        _uncalled_in_offspring = []
        _non_variable_within_trio = []
        _ignored_by_rtg_tools = []
        _variable_within_trio = []
        
        for itr, row in enumerate(mie_vcf._tsv_dict_array):
            if args.debug and itr % 5000 == 0:
                logger.debug(f"{logger_msg}: processing row {itr}")

            gt_values = [val for key, val in row.items() if key.startswith("GT")]

            # First, skip uncalled in offspring
            # For the GATK (UMAGv1) VCF, did the following manually:
            # bcftools view -e 'GT[0]="mis"' Trio14.RAW.sorted.PASS.MIE.vcf.gz | bcftools view -e 'GT[1]="mis" && GT[2]="miss"' -o Trio14.RAW.sorted.PASS.MIE.exclude_mis.vcf.gz -O z 
            if gt_values[0] == "./.":
                _num_MissingRef_Records += 1
                _uncalled_in_offspring.append(row)
                continue

            # Remove sites where complete trio is either "./." or "0/0"
            else:
                contains_gt = [s for s in gt_values if "." not in s and "0/0" not in s]
                if len(contains_gt) == 0:
                    _num_MissingRef_Records += 1
                    _non_variable_within_trio.append(row)
                    continue
                else:
                    _num_Non_Ref_Family_Records += 1
            
            if row["INFO/MCU"] != ".":
                _ignored_by_rtg_tools.insert(itr, row)
                continue
            
            # Calculate minimum GQ value per site for all samples
            _row_copy = row.copy()
            
            gq_values = [
                None if val == "." else int(val)
                for key, val in row.items()
                if key.startswith("GQ")
            ]
            min_gq = (
                min(filter(lambda x: x is not None, gq_values))
                if any(gq_values)
                else None
            )
            _row_copy["INFO/MIN_GQ"] = min_gq

            # Transform Mendelian Violations to boolean for efficient counting
            if row["INFO/MCV"] != ".":
                _row_copy["IS_MIE"] = 1
            else:
                _row_copy["IS_MIE"] = 0

            # Save transformations to the copy made
            _variable_within_trio.insert(itr, _row_copy)

        # Sort the Min. GQ from largest to smallest
        # USING THE CHILD'S GQ VALUE!
        sorted_dict_array = sorted(
            _variable_within_trio, key=lambda x: int(x[f"GQ_{_offspring}"]), reverse=True
        )
        
        # Calculate a cumulative sum for the 'IS_MIE' column
        # Convert to pd.DataFrame
        _df = pd.DataFrame.from_records(data=sorted_dict_array)

        # Subset the dataframe for plotting
        _mie_only = _df["IS_MIE"].astype(int)
        _offspring_gq_values = _df[f"GQ_{_offspring}"].astype(int)

        num_variants = len(_mie_only)
        
        logger.info(f"{logger_msg}: ------------- done processing {_model_name} | {_trio_name} | {_offspring} -------------") 
        logger.info(f"{logger_msg}: {_offspring} | Number of Variants: {num_variants:,}")

        logger.info(
            f"{logger_msg}: saving contents from TSV -> CSV\t| '{_processed_file.path}'"
        )

        # Create an index value of variants from largest GQ to smallest GQ score
        idx = list(range(1, (num_variants+1)))

        # Add metaddata
        sample_used = [_offspring] * num_variants
        hue_val = [_model_name] * num_variants

        # Calculate cumulative error rate
        cumulative_n_mie = sum2(_mie_only)
        prop_mie = [(100 * x/num_variants) for x in cumulative_n_mie]

        # Save data
        data = {"Num_SNVs": idx,
                "Sample_ID": sample_used,
                "Variant_Caller": hue_val,
                "GQ_value": _offspring_gq_values,
                "Cumulative_MIE": cumulative_n_mie,
                "Cumulative_MIE%": prop_mie
                }      
        _df = pd.DataFrame.from_dict(data=data)
        
        # Write output to disk
        results = Files(
            path_to_file=_processed_file.path.parent / _processed_file.path.name,
            logger=logger,
            logger_msg=logger_msg,
            dryrun_mode=args.dry_run,
        )
        results.check_status()
        results.write_dataframe(df=_df)

        logger.info(
            f"{logger_msg}: done saving contents from TSV -> CSV | '{_processed_file.path}'"
        )
    
    Wrapper(__file__, "end").wrap_script(timestamp())


# Execute functions created
if __name__ == "__main__":
    __init__()
