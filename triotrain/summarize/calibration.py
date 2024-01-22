#!/bin/python3
"""
description: transform MIE VCF into summary metrics to calibrate DV model

example:
    python3 triotrain/summarize/calibration.py                           \\
"""

import argparse
from logging import Logger
from os import environ
from os import path as p
from pathlib import Path
from sys import path
from typing import Union

abs_path = Path(__file__).resolve()
module_path = str(abs_path.parent.parent)
path.append(module_path)

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
            "/storage/hpc/group/UMAG_test/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/230313_GIAB/DT1.4_default_human/Human.Trio1.PASS.MIE.vcf.gz",
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
        _logger_msg = check_args(args, logger)
        mie_vcf = Convert_VCF(
            vcf_input=args.vcf_input,
            tsv_output=args.output,
            logger=logger,
            debug=args.debug,
            dry_run=args.dry_run,
            logger_msg=_logger_msg,
        )
        mie_vcf.run()

        _edited_tsv_dict_array = []
        _num_Non_Ref_Family_Records = 0
        _num_MissingRef_Records = 0
        for itr, row in enumerate(mie_vcf._tsv_dict_array):
            # print(f"ROW#{itr}: {row}")
            
            # Identify when all samples are either "./." or "0/0"
            gt_values = [val for key, val in row.items() if key.startswith("GT")]
            if gt_values[0] == "./.":
                _num_MissingRef_Records += 1
                continue
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
            _edited_tsv_dict_array.insert(itr, _row_copy)

        print("NUM NON REF FAMILY RECORDS:", _num_Non_Ref_Family_Records)
        print("NUM MISSING / REF ONLY RECORDS:", _num_MissingRef_Records)
        print("NUM MIN GQ RECORDS:", len(_edited_tsv_dict_array))
        breakpoint()
        # Sort by Min. GQ
        sorted_dict_array = sorted(
            _edited_tsv_dict_array, key=lambda x: x["INFO/MIN_GQ"]
        )
        for itr, row in enumerate(sorted_dict_array):
            if itr < 5:
                print(f"ROW{itr}: {row}")
            else:
                return

    except AssertionError as E:
        logger.error(E)

    Wrapper(__file__, "end").wrap_script(timestamp())


# Execute functions created
if __name__ == "__main__":
    __init__()
