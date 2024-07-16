#!/bin/python3
"""
description: 

example:
"""

import argparse
from logging import Logger
from os import environ


def collect_args(
    use_mie: bool = False, postprocess: bool = False
) -> argparse.Namespace:
    """
    Process command line argument to execute script.
    """
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawTextHelpFormatter,
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

    if postprocess:
        parser.add_argument(
            "-P",
            "--pickle-file",
            dest="pickle_file",
            type=str,
            help="[REQUIRED]\ninput file (.pkl)\ncontains necessary data to process results as a pickled SummarizeResults() object.",
            metavar="</path/file>",
        )
        # return parser.parse_args(
        #     [
        #         "-P",
        #         "/mnt/pixstor/schnabelr-drii/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/240528_Benchmarking/DV1.4_cattle1/UMCUSAF000000341497.pkl",
        #         "--dry-run",
        #     ]
        # )
    else:
        parser.add_argument(
            "-M",
            "--metadata",
            dest="metadata",
            type=str,
            help="[REQUIRED]\ninput file (.csv)\nprovides the list of VCFs to summarize",
            metavar="</path/file>",
        )
        parser.add_argument(
            "-O",
            "--output",
            dest="outpath",
            type=str,
            help="[REQUIRED]\noutput file (.csv)\nwhere to save the resulting CSV output(s)",
            metavar="</path/file>",
        )
        parser.add_argument(
            "-r",
            "--resources",
            dest="resource_config",
            help="[REQUIRED]\ninput file (.json)\ndefines HPC cluster resources for SLURM",
            type=str,
            metavar="</path/file>",
        )

    if use_mie:
        parser.add_argument(
            "-R",
            "--reference",
            dest="reference",
            type=str,
            help="[REQUIRED]\ninput file (.fasta)\nwill be converted to SDF for rtg-tools",
            metavar="</path/file>",
        )
        parser.add_argument(
            "-P",
            "--pseudo-autosomal",
            dest="par",
            type=str,
            help="input file (reference.txt)\nif provided, activates sex-aware processing with rtg-tools",
            metavar="</path/file>",
        )
        parser.add_argument(
            "--all-variants",
            dest="all",
            help="if True, calculates errors for all variants, rather than just PASS variants",
            default=False,
            action="store_true",
        )
        parser.add_argument(
            "--threshold",
            dest="threshold",
            help="trio concordance percentage required for consistent parentage",
            default=99.0,
            metavar="<float>",
        )
        return parser.parse_args(
            [
                "-M",
                "triotrain/summarize/data/240627_mie_rate_inputs_noPop_cattle.csv",
                # "triotrain/summarize/data/240627_mie_rate_inputs_noPop_human.csv",
                "-O",
                "../VARIANT_CALLING_OUTPUTS/240528_Benchmarking/summary",
                "-r",
                "triotrain/model_training/tutorial/resources_used_hellbender.json",
                "-R",
                # "../REF_GENOME_COPY/ARS-UCD1.2_Btau5.0.1Y.fa",
                "triotrain/variant_calling/data/GIAB/reference/GRCh38_no_alt_analysis_set.fasta",
                # "-P",
                # "triotrain/summarize/data/ARS-UCD1.2_Btau5.0.1Y_reference.txt",
                # "--dry-run",
                # "--debug",
            ]
        )

    return parser.parse_args()


def check_args(
    args: argparse.Namespace,
    logger: Logger,
    use_mie: bool = False,
    postprocess: bool = False,
) -> None:
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
        logger.info("[DRY_RUN]: output will display to screen and not write to a file")

    if not postprocess:
        assert (
            args.metadata
        ), "missing --metadata; Please provide a file with descriptive data for test samples."

        assert (
            args.resource_config
        ), "Missing --resources; Please designate a path to pipeline compute resources in JSON format"

        assert (
            args.outpath
        ), "missing --output; Please provide a file name to save results."
    else:
        assert (
            args.pickle_file
        ), "missing --pickle-file; Please provide a path to a pickled SummarizeResults object."

    if use_mie:
        assert (
            args.reference
        ), "missing --reference; Please provide the path for a FASTA file compatible with the VCF(s) provided by --metadata"
