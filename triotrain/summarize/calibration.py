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
from typing import Union

import pandas as pd

abs_path = Path(__file__).resolve()
module_path = str(abs_path.parent.parent)
path.append(module_path)

from helpers.collections import Bins
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
            # "/mnt/pixstor/schnabelr-drii/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/230313_GIAB/DT1.4_default_human/Human.Trio1.PASS.MIE.vcf.gz",
            # "/mnt/pixstor/schnabelr-drii/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/230313_GIAB/DV1.4_WGS.AF_human/Human.Trio1.PASS.MIE.vcf.gz",
            # "/mnt/pixstor/schnabelr-drii/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/230313_GIAB/DV1.4_default_human/Human.Trio1.PASS.MIE.vcf.gz",
            # "/mnt/pixstor/schnabelr-drii/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/230313_GIAB/DV1.4_WGS.AF_cattle1/Human.Trio1.PASS.MIE.vcf.gz",
            # "/mnt/pixstor/schnabelr-drii/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/230313_GIAB/DV1.4_WGS.AF_cattle2/Human.Trio1.PASS.MIE.vcf.gz",
            # "/mnt/pixstor/schnabelr-drii/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/230313_GIAB/DV1.4_WGS.AF_cattle3/Human.Trio1.PASS.MIE.vcf.gz",
            # "/mnt/pixstor/schnabelr-drii/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/230313_GIAB/DV1.4_WGS.AF_cattle4/Human.Trio1.PASS.MIE.vcf.gz",
            "/mnt/pixstor/schnabelr-drii/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/230313_GIAB/DV1.4_WGS.AF_cattle5/Human.Trio1.PASS.MIE.vcf.gz",
            # "/mnt/pixstor/schnabelr-drii/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/230313_GIAB/DT1.4_default_human/Cow.Trio12.PASS.MIE.vcf.gz",
            # "/mnt/pixstor/schnabelr-drii/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/230313_GIAB/DV1.4_WGS.AF_cattle4/Cow.Trio12.PASS.MIE.vcf.gz",
            # "/mnt/pixstor/schnabelr-drii/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/230313_GIAB/DV1.4_default_human/Cow.Trio12.PASS.MIE.vcf.gz",
            # "/storage/hpc/group/UMAG_test/WORKING/jakth2/TRIOS_220704/TRIO_CLEAN/Trio12.TRUTH.PASS.MIE.vcf.gz",
            "--output-path",
            "/mnt/pixstor/schnabelr-drii/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/230313_GIAB/summary/",
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
    ), "missing --input; Please provide a Trio VCF file produced by 'rtg-tools mendelian'"
    
    assert args.outpath, "missing --output; Please provide an exisiting directory to save results."


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

    try:
        # Transform the Trio VCF output from RTG mendelian into a TSV file
        mie_vcf = Convert_VCF(
            vcf_input=args.input,
            tsv_output=args.outpath,
            logger=logger,
            debug=args.debug,
            dry_run=args.dry_run,
            logger_msg=logger_msg,
        )
        mie_vcf.check_files()
    except AssertionError as E:
        logger.error(E)

    # Check for exisiting output
    _processed_file = TestFile(file=f"{args.outpath}/{mie_vcf._prefix_name}.sorted.tsv", logger=logger)
    _processed_file.check_missing(logger_msg=logger_msg, debug_mode=args.debug)

    if _processed_file.file_exists:
        logger.info(
            f"{logger_msg}: loading in processed TSV | '{_processed_file.path.name}'"
        )
        
        with open(_processed_file.file, mode="r", encoding="utf-8-sig") as data:
            dict_reader = DictReader(data, delimiter="\t")
            _tsv_dict_array = list(dict_reader)

        # Sort the Min. GQ from smallest to largest
        sorted_dict_array = sorted(_tsv_dict_array, key=lambda x: x["INFO/MIN_GQ"])
        logger.info(
            f"{logger_msg}: done loading in processed TSV | '{_processed_file.path.name}'"
        )
    else:
        # Process MIE TSV into usable format
        mie_vcf.run()

        # for itr, row in enumerate(mie_vcf._tsv_dict_array):
        #     # print(f"ROW {itr}: {row}")
        #     for key, value in row.items():
        #         print(f"ROW #{itr} | KEY:{key}=VALUE:{value}")
        #         breakpoint()

        logger.info(
            f"{logger_msg}: processing contents from VCF -> TSV | '{mie_vcf._output_file.path.name}'"
        )

        _num_Non_Ref_Family_Records = 0
        # NOTE: This number (^) should match the value in the RTG-mendelian log file for
        #       the number of sites "checked for Mendelian constraints"

        _num_MissingRef_Records = 0
        _uncalled_in_offspring = []
        _non_variable_within_trio = []
        _ignored_by_rtg_tools = []
        _variable_within_trio = []
        
        for itr, row in enumerate(mie_vcf._tsv_dict_array):
            # print(f"ROW {itr} | {row}")
            # breakpoint()
            if args.debug and itr % 5000 == 0:
                logger.debug(f"{logger_msg}: processing row {itr}")

            gt_values = [val for key, val in row.items() if key.startswith("GT")]

            # First, skip uncalled in offspring
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
        _offspring = mie_vcf._samples[0]
        
        sorted_dict_array = sorted(
            _variable_within_trio, key=lambda x: int(x[f"GQ_{_offspring}"]), reverse=True
        )

        logger.info(
            f"{logger_msg}: done processing contents from VCF -> TSV | '{mie_vcf._output_file.path.name}'"
        )

        # Save output to disk
        results = Files(
            path_to_file=_processed_file.path.parent / _processed_file.path.name,
            logger=logger,
            logger_msg=logger_msg,
            dryrun_mode=args.dry_run,
        )
        results.check_status()
        results.write_list_of_dicts(line_list=sorted_dict_array, delim="\t")

    Wrapper(__file__, "end").wrap_script(timestamp())


# Execute functions created
if __name__ == "__main__":
    __init__()
