#!/usr/bin/python
"""
description: 

usage:
    from run import Run
"""
import argparse
import sys
from logging import Logger
from os import environ, path

# Custom helper modules
sys.path.append(
    "/storage/hpc/group/UMAG_test/WORKING/jakth2/deep-variant/scripts/model_training"
)
import helpers as h
import helpers_logger
from iteration import Iteration
from pipeline_run import Run


def collect_args():
    """
    Process command line argument to execute script.
    """
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-r",
        "--resources",
        dest="resource_config",
        help="[REQUIRED]\ninput file (.json)\ndefines HPC cluster resources for SLURM",
        type=str,
        metavar="</path/file>",
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
        help="if True, display, commands to the screen",
        action="store_true",
    )
    parser.add_argument(
        "--metrics",
        dest="metrics",
        help=f"sets what metrics to return with hap.py\n(default: %(default)s)",
        choices=["all", "raw", "type"],
        default="all",
    )
    parser.add_argument(
        "--use-DT",
        dest="use_DT",
        help="if True, display, variant calling is assumed to be completed already and will be skipped",
        action="store_true",
        default=False,
    )
    return parser.parse_args()


def check_args(args: argparse.Namespace, logger: Logger) -> None:
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
    assert (
        args.resource_config
    ), "Missing --resources; Please designate a path to pipeline compute resources in JSON format"


def __init__():
    # Collect command line arguments
    args = collect_args()

    # Collect start time
    h.Wrapper(__file__, "start").wrap_script(h.timestamp())

    # Create error log
    current_file = path.basename(__file__)
    module_name = path.splitext(current_file)[0]
    logger = helpers_logger.get_logger(module_name)

    check_args(args=args, logger=logger)
    current_itr = Iteration(
        current_trio_num=12,
        next_trio_num="None",
        current_genome_num=0,
        total_num_genomes=None,
        total_num_tests=16,
        train_genome=None,
        eval_genome=None,
        env=h.Env(args.env_file, logger, dryrun_mode=args.dry_run),
        logger=logger,
        args=args,
    )

    pipeline = Run(
        itr=current_itr,
        resource_file=args.resource_config,
        num_tests=1,
        train_mode=True,
    )

    pipeline.test_model_jobs(useDT=args.use_DT)

    h.Wrapper(__file__, "end").wrap_script(h.timestamp())


# Execute functions created
if __name__ == "__main__":
    __init__()
