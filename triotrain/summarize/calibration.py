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
from subprocess import run as run_sub
from typing import Union

abs_path = Path(__file__).resolve()
module_path = str(abs_path.parent.parent)
path.append(module_path)

from helpers.files import TestFile, WriteFiles
from helpers.outputs import check_if_output_exists


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
    # return parser.parse_args()
    return parser.parse_args(
        [
            "--input",
            "/storage/hpc/group/UMAG_test/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/230312_GIAB/DT1.4_default_human/Human.Trio1.PASS.MIE.vcf.gz",
            "--debug",
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

    _input_file = TestFile(file=args.vcf_input, logger=logger)
    _input_file.check_existing(logger_msg=_logger_msg, debug_mode=args.debug)
    assert (
        _input_file.file_exists
    ), f"non-existant file provided | '{_input_file.file}'\nPlease provide a valid MIE VCF."
    return _logger_msg


# def convert_to_tsv() -> None:
#     """
#     Run 'bcftools query' as a Python Subprocess, and write the output to an intermediate file.
#     """
#     bcftools_query = run_sub(
#         [
#             "bcftools",
#             "query",
#             "-f",
#             "%CHROM\t%POS[\t%BD\t%GT\t%BVT\t%BLT\t%BI]\n",
#             # str(self.happy_vcf_file_path),
#         ],  # type: ignore
#         capture_output=True,
#         text=True,
#         check=True,
#     )

#     if self.args.debug:
#         self.logger.debug(
#             f"{self._logger_msg}: writing TSV metrics file using | '{self.happy_vcf_file_path.name}'"
#         )

#     if not self.args.dry_run:
#         file = open(str(self.file_tsv), mode="w")
#         # Add custom header to the new TSV
#         file.write("\t".join(self._custom_header[0:]) + "\n")
#         file.close()
#         contents = open(str(self.file_tsv), mode="a")
#         contents.write(bcftools_query.stdout)
#         contents.close()
#     else:
#         self.tsv_format = bcftools_query.stdout.splitlines()

#     if self.args.debug:
#         self.logger.debug(f"{self._logger_msg}: done converting to TSV file")


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
        logger_msg = check_args(args, logger)
        logger.info(f"{logger_msg}: DO STUFF HERE!")
        # bcftools query -f '%CHROM\t%POS\t%REF\t%ALT\t%INFO/MCU\t%INFO/MCV[\t%GT\t%GQ]\n' Human.Trio1.PASS.MIE.vcf.gz
    except AssertionError as E:
        logger.error(E)

    Wrapper(__file__, "end").wrap_script(timestamp())


# Execute functions created
if __name__ == "__main__":
    __init__()
