#!/usr/bin/python
"""
description: 

usage:
    from run import Run
"""
import argparse
from logging import Logger
from os import environ
from os import path as p
from pathlib import Path
from sys import path

# Custom helper modules
abs_path = Path(__file__).resolve()
dv_path = Path(abs_path.parent.parent.parent)
module_path = str(dv_path / "triotrain")
path.append(module_path)


def collect_args() -> argparse.Namespace:
    """
    Process command line argument to execute script.
    """
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-M",
        "--metadata",
        dest="metadata",
        type=str,
        help="[REQUIRED]\ninput file (.csv)\ndescribes each sample to produce VCFs",
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
        "--get-help",
        dest="get_help",
        help="if True, display DV 'run_deepvariant' man page to the screen",
        action="store_true",
        default=False,
    )
    # parser.add_argument(
    #     "--metrics",
    #     dest="metrics",
    #     help=f"sets what metrics to return with hap.py\n(default: %(default)s)",
    #     choices=["all", "raw", "type"],
    #     default="all",
    # )
    # parser.add_argument(
    #     "--use-DT",
    #     dest="use_DT",
    #     help="if True, variant calling is assumed to be completed already and will be skipped",
    #     action="store_true",
    #     default=False,
    # )
    return parser.parse_args(
        [
            "-M",
            # "triotrain/variant_calling/data/metadata/240528_benchmarking_metadata.csv",
            # "triotrain/variant_calling/data/metadata/240715_benchmarking_metadata.csv",
            "triotrain/variant_calling/data/metadata/240805_benchmarking_metadata.csv",
            "-r",
            "triotrain/model_training/tutorial/resources_used_hellbender.json",
            "--dry-run",
        ]
    )
    # return parser.parse_args()


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

    if args.get_help is False:
        assert (
            args.metadata
        ), "Missing --metadata; Please provide the path to variant calling run parameters in CSV format"
        assert (
            args.resource_config
        ), "Missing --resources; Please designate a path to pipeline compute resources in JSON format"


def __init__() -> None:
    from helpers.utils import get_logger
    from helpers.wrapper import Wrapper, timestamp
    from call_DV import VariantCaller
    

    # Collect command line arguments
    args = collect_args()

    # Collect start time
    Wrapper(__file__, "start").wrap_script(timestamp())

    # Create error log
    current_file = p.basename(__file__)
    module_name = p.splitext(current_file)[0]
    logger = get_logger(module_name)

    check_args(args=args, logger=logger)

    run_DV = VariantCaller(args=args, logger=logger)
    run_DV.setup()
    run_DV.process_samples()   

    # current_itr = Iteration(
    #     current_trio_num=12,
    #     current_genome_num=0,
    #     total_num_tests=16,
    #     env=Env(args.env_file, logger, dryrun_mode=args.dry_run),
    #     logger=logger,
    #     args=args,
    # )

    # pipeline = Run(
    #     itr=current_itr,
    #     resource_file=args.resource_config,
    #     num_tests=1,
    #     train_mode=True,
    # )

    # pipeline.test_model_jobs(useDT=args.use_DT)

    Wrapper(__file__, "end").wrap_script(timestamp())


# Execute functions created
if __name__ == "__main__":
    __init__()
