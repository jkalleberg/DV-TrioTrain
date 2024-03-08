#!/bin/python3
"""
description: transform MIE VCF into summary metrics to calibrate DV model

example:
    python3 triotrain/summarize/calibration.py                           \\
"""

import argparse
from csv import DictReader
from logging import Logger
from os import environ
from os import path as p
from pathlib import Path
from sys import path
from typing import Union

import pandas as pd

abs_path = Path(__file__).resolve()
module_path = str(abs_path.parent.parent)
path.append(module_path)

from helpers.collections import Bins
from helpers.files import TestFile, WriteFiles
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
        "-i",
        "--input",
        dest="vcf_input",
        type=str,
        help="[REQUIRED]\ninput file (.VCF)",
        metavar="</path/file>",
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
    parser.add_argument(
        "-o",
        "--output",
        dest="output",
        type=str,
        help="output path prefix; directory will be created if necessary",
        metavar="</path/prefix>",
    )
    # return parser.parse_args()
    return parser.parse_args(
        [
            "--input",
            "/storage/hpc/group/UMAG_test/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/230313_GIAB/DT1.4_default_human/Human.Trio1.PASS.MIE.vcf.gzQ",
            # "/storage/hpc/group/UMAG_test/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/230313_GIAB/DV1.4_default_human/Human.Trio1.PASS.MIE.vcf.gz",
            # "/storage/hpc/group/UMAG_test/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/230313_GIAB/DV1.4_WGS.AF_cattle4/Human.Trio1.PASS.MIE.vcf.gz",
            # "/storage/hpc/group/UMAG_test/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/230313_GIAB/DT1.4_default_human/Cow.Trio12.PASS.MIE.vcf.gz",
            # "/storage/hpc/group/UMAG_test/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/230313_GIAB/DV1.4_WGS.AF_cattle4/Cow.Trio12.PASS.MIE.vcf.gz",
            # "/storage/hpc/group/UMAG_test/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/230313_GIAB/DV1.4_default_human/Cow.Trio12.PASS.MIE.vcf.gz",
            # "/storage/hpc/group/UMAG_test/WORKING/jakth2/TRIOS_220704/TRIO_CLEAN/Trio12.TRUTH.PASS.MIE.vcf.gz",
            # "--debug",
            "--dry-run",
        ]
    )


def check_args(args: argparse.Namespace, logger: Logger) -> Union[str, None]:
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
        _version = environ.get("BIN_VERSION_DV")
        logger.debug(f"using DeepVariant version | {_version}")

    if args.dry_run:
        _logger_msg = f"[DRY_RUN]"
        logger.info(
            f"{_logger_msg}: output will display to screen and not write to a file"
        )
    else:
        _logger_msg = None

    assert (
        args.vcf_input
    ), "missing --input; Please provide a Trio VCF file produced by rtg-mendelian."

    return _logger_msg


def __init__() -> None:
    from helpers.utils import get_logger
    from helpers.wrapper import Wrapper, timestamp

    # Collect command line arguments
    args = collect_args()

    # Collect start time
    Wrapper(__file__, "start").wrap_script(timestamp())

    # Create error log
    current_file = p.basename(__file__)
    module_name = p.splitext(current_file)[0]
    logger = get_logger(module_name)

    try:
        # Check command line args
        _log_msg = check_args(args, logger)
        if _log_msg is None:
            _logger_msg = ""
            _internal_msg = ""
        else:
            _logger_msg = _log_msg
            _internal_msg = f"{_log_msg}: "

        # Transform the Trio VCF output from RTG mendelian into a TSV file
        mie_vcf = Convert_VCF(
            vcf_input=args.vcf_input,
            tsv_output=args.output,
            logger=logger,
            debug=args.debug,
            dry_run=args.dry_run,
            logger_msg=_logger_msg,
        )
        mie_vcf.check_files()
    except AssertionError as E:
        logger.error(E)

    # Check for exisiting output
    _processed_file = TestFile(file=f"{mie_vcf._prefix_path}.sorted.tsv", logger=logger)
    _processed_file.check_missing(logger_msg=_logger_msg, debug_mode=args.debug)

    if _processed_file.file_exists:
        logger.info(
            f"{_internal_msg}loading in processed TSV | '{_processed_file.path.name}'"
        )
        
        # print("STOPPING HERE!")
        # breakpoint()
        with open(str(_processed_file.path), mode="r", encoding="utf-8-sig") as data:
            dict_reader = DictReader(data, delimiter="\t")
            _tsv_dict_array = list(dict_reader)

        # Sort the Min. GQ from smallest to largest
        sorted_dict_array = sorted(_tsv_dict_array, key=lambda x: x["INFO/MIN_GQ"])
        logger.info(
            f"{_internal_msg}done loading in processed TSV | '{_processed_file.path.name}'"
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
            f"{_internal_msg}processing contents from VCF -> TSV | '{mie_vcf._output_file.path.name}'"
        )

        _edited_tsv_dict_array = []
        _num_Non_Ref_Family_Records = 0
        # NOTE: This number (^) should match the value in the RTG-mendelian log file for
        #       the number of sites "checked for Mendelian constraints"

        _num_MissingRef_Records = 0
        for itr, row in enumerate(mie_vcf._tsv_dict_array):
            print(f"ROW {itr} | {row}")
            breakpoint()
            if args.debug and itr % 5000 == 0:
                logger.debug(f"{_internal_msg}processing row {itr}")

            gt_values = [val for key, val in row.items() if key.startswith("GT")]

            # First, skip uncalled in offspring
            if gt_values[0] == "./.":
                _num_MissingRef_Records += 1
                continue

            # Remove sites where complete trio is either "./." or "0/0"
            else:
                contains_gt = [s for s in gt_values if "." not in s and "0/0" not in s]
                if len(contains_gt) == 0:
                    _num_MissingRef_Records += 1
                    continue
                else:
                    _num_Non_Ref_Family_Records += 1

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
            _edited_tsv_dict_array.insert(itr, _row_copy)

        # Sort the Min. GQ from smallest to largest
        sorted_dict_array = sorted(
            _edited_tsv_dict_array, key=lambda x: x["INFO/MIN_GQ"]
        )

        logger.info(
            f"{_internal_msg}done processing contents from VCF -> TSV | '{mie_vcf._output_file.path.name}'"
        )

        # Save output to disk
        results = WriteFiles(
            path_to_file=_processed_file.path.parent,
            file=_processed_file.path.name,
            logger=logger,
            logger_msg=_log_msg,
            dryrun_mode=args.dry_run,
        )
        results.check_missing()
        results.write_list_of_dicts(line_list=sorted_dict_array, delim="\t")

    # Create bins without having to read the (very large)
    #   processed TSV in as a pd.DataFrame
    _bins = tuple(range(0, 105, 5))
    _counts = Bins(_bins)
    _counts.create_bins()
    # print(f"COUNTS BINS: {_counts._sdict}")
    # breakpoint()

    _num_mie = Bins(_bins)
    _num_mie.create_bins()
    # print(f"NUM MIE BINS: {_num_mie._sdict}")

    for itr, row in enumerate(sorted_dict_array):
        _min_gq_value = int(row["INFO/MIN_GQ"])
        _mie_value = int(row["IS_MIE"])
        _counts[_min_gq_value] += 1
        _num_mie[_min_gq_value] += _mie_value
        # print(f"COUNTS BINS {itr}: {_counts._sdict}")
        # print(f"NUM MIE BINS {itr}: {_num_mie._sdict}")
        # breakpoint()

    # Transform the two summary dicts into a pd.DataFrame
    summary_data = {
        "MIN_GQ_BIN": list(_counts._sdict.keys()),
        "NUM_SITES": list(_counts._sdict.values()),
        "NUM_MIE": list(_num_mie._sdict.values()),
    }
    # print("SUMMARY DF")
    # print(summary_data)
    # breakpoint()
    summary_df = pd.DataFrame(summary_data)
    # print("SUMMARY DF")
    # print(summary_df)
    # breakpoint()
    _sum_sites = summary_df["NUM_SITES"].sum()
    _sum_mie = summary_df["NUM_MIE"].sum()

    summary_df["%NUM_SITES"] = (summary_df["NUM_SITES"] / _sum_sites) * 100
    summary_df["%MIE"] = (summary_df["NUM_MIE"] / _sum_mie) * 100
    summary_df["%MIE_Rate"] = (summary_df["NUM_MIE"] / _sum_sites) * 100

    # Define the summary output CSV file to be created
    summary_file = WriteFiles(
        str(_processed_file.path.parent),
        f"{_processed_file.path.stem}.calibration.csv",
        logger,
    )
    summary_file.check_missing()

    if args.dry_run:
        logger.info(
            f"{_internal_msg}pretending to write calibration CSV | '{summary_file.file_path.name}'"
        )
        print(summary_df)
    else:
        if summary_file.file_exists:
            logger.info(
                f"{_internal_msg}found exisiting calibration CSV | '{summary_file.file_path.name}'"
            )
        else:
            logger.info(
                f"{_internal_msg}writing calibration CSV | '{summary_file.file_path.name}'"
            )
            summary_df.to_csv(summary_file.file_path, index=False)
            if args.debug:
                summary_file.check_missing()
                if summary_file.file_exists:
                    logger.debug(
                        f"{_internal_msg}{summary_file.file_path.name} written"
                    )

    logger.info(
        f"{_internal_msg}total number of Mendelian Inheritance Errors (MIE): {_sum_mie:,}"
    )
    logger.info(f"{_internal_msg}total number of variants analyzed: {_sum_sites:,}")

    Wrapper(__file__, "end").wrap_script(timestamp())


# Execute functions created
if __name__ == "__main__":
    __init__()
