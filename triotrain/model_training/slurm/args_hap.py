#!/bin/python3
"""
description: combines TRUTH and QUERY column values [FP/FP/FN/N/.] into unique 'TRUTH_QUERY' combinations (e.g. 'TP_TP'), count observations, and write values to comma-separated values output file.

example:
    python3 triotrain/model_training/slurm/process_hap.py   \\
        --env-file envs/demo.env                            \\
        --vcf-file /path/to/file.vcf.gz                     \\
        --dry-run
"""
# Load python libraries
import argparse
from logging import Logger
from pathlib import Path
from os import environ

# Parsing command line inputs function
def collect_args():
    """
    Process command line argument to execute script.
    """
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-e",
        "--env-file",
        dest="env_file",
        help="[REQUIRED]\ninput file (.env)\nprovides environment variables",
        type=str,
        metavar="</path/file>",
    )
    parser.add_argument(
        "-v",
        "--vcf-file",
        dest="vcf_file",
        help="[REQUIRED]\ninput file (.vcf)\ncontains comparision metrics created by hap.py",
        type=str,
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
        help="if True, display final hap.py metrics to the screen",
        action="store_true",
    )
    parser.add_argument(
        "-s",
        "--species",
        dest="species",
        choices=["cow", "human", "None"],
        help="sets the default autosomes + sex chromosomes to use for training\n(default: %(default)s)",
        type=str,
        default="cow",
    )

    return parser.parse_args()
    # return parser.parse_args(
    #     [
    #         "--env-file",
    #         "envs/220913_NewTrios-run1.env",
    #         "--vcf-file",
    #         "/storage/hpc/group/UMAG_test/WORKING/jakth2/TRIO_TRAINING_OUTPUTS/220913_NewTrios/PASS1/compare_Father/happy1-no-flags.vcf.gz",
    #         # "--debug",
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
        logger.debug(f"using DeepVariant version | {environ.get('BIN_VERSION_DV')}")

    assert (
        args.env_file
    ), "Missing --env-file; Please provide a file with environment variables for the current analysis"
    
    # Confirm data input is an existing file
    assert Path(
        args.vcf_file
    ).exists(), f"non-existant VCF provided | '{args.vcf_file}'"

    # Confirm input file is a compressed vcf
    assert (
        "vcf.gz" in args.vcf_file
    ), f"missing the '.vcf.gz' extension | '{args.vcf_file}'"