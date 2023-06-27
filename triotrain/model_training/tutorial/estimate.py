import argparse
from logging import Logger
from os import path as p, environ
from sys import exit, path
from pathlib import Path

# get the absolute path to the triotrain/ dir
abs_path = Path(__file__).resolve()
module_path = str(abs_path.parent.parent.parent)
path.append(module_path)

from helpers.environment import Env
from helpers.utils import get_logger
from helpers.wrapper import Wrapper, timestamp
from model_training.prep.count import count_variants
from helpers.files import TestFile

def collect_args() -> argparse.Namespace:
    """
    Process the command line arguments
    """
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-e",
        "--env-file",
        dest="env_file",
        help="[REQUIRED]\ninput file (.env)\nprovides environmental variables",
        type=str,
        metavar="</path/file>",
    )
    parser.add_argument(
        "--vcf-file",
        dest="vcf_file",
        help="[REQUIRED]\ninput file (.vcf.gz)\nthe output from running DeepVariant 'call_variants'",
        type=str,
        metavar="</path/file>",
    )
    parser.add_argument(
        "-g",
        "--genome",
        dest="genome",
        choices=["Father", "Mother", "Child"],
        help="[REQUIRED]\nthe genome to count_variants for",
        default="Mother",
        type=str,
    )
    parser.add_argument(
        "-d",
        "--debug",
        dest="debug",
        help="print debug info",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--demo-mode",
        dest="demo_mode",
        help="if True, indicates using a demo chromosome",
        action="store_true",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        help="display region file contents to the screen",
        action="store_true",
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
        logger.debug(f"using DeepVariant version | {environ.get('BIN_VERSION_DV')}")

    if args.dry_run:
        logger.info("[DRY_RUN]: output will display to screen and not write to a file")

    assert (
        args.env_file
    ), "Missing --env-file; Please provide a file with environment variables for the current analysis"
    assert (
        args.vcf_file
    ), "Missing --vcf-file; Please provide a VCF file from DeepVariant"
    assert (
        args.genome
        ), "Missing --genome; Please designate which genome we are counting variants for"

def __init__() -> None:
    # Collect command line arguments
    args = collect_args()

    # Collect start time
    Wrapper(__file__, "start").wrap_script(timestamp())

    # Create error log
    current_file = p.basename(__file__)
    module_name = p.splitext(current_file)[0]
    logger = get_logger(module_name)

    # Check command line args
    check_args(args, logger)

    env = Env(args.env_file, logger, args.dry_run)
    trio_num = str(env.contents["RunOrder"])
    num_examples = int(env.contents[f"{args.genome}_Examples"])

    vcf_file = TestFile(args.vcf_file, logger)
    vcf_file.check_existing()

    if args.demo_mode:
        logger_msg = f"[DEMO] - [TRIO{trio_num}] - [count_variants] - [{args.genome}]"
    else:
        logger_msg = f"[TRIO{trio_num}] - [count_variants] - [{args.genome}]"

    variants_found = count_variants(
        vcf_file.path,
        logger_msg,
        logger=logger,
        count_pass=True,
        count_ref=True,
    )

    if isinstance(variants_found, dict):
        total_pass = variants_found["pass"]
        total_ref = variants_found["ref/ref"]
        total_pass_variants = int(total_pass)

        logger.info(
            f"{logger_msg}: number of REF/REF variants found | {int(total_ref):,}"
        )

        logger.info(
            f"{logger_msg}: number of PASS variants found | {int(total_pass):,}"
        )
        assert (
            total_pass_variants != 0
        ), f"{logger_msg}: missing PASS variants in a TruthVCF.\nPlease include them [{str(vcf_file.path)}], or update the path in metadata.csv with a corrected TruthVCF.\nExiting..."

        # import TrioTrain default args
        from model_training.pipeline.args import collect_args as tt_args, get_defaults

        parser = tt_args()
        default_max_examples = int(get_defaults(parser, "max_examples"))
        default_ex_per_var = float(get_defaults(parser, "est_examples"))

        logger.info(
            f"{logger_msg}: default maximum examples per region | {default_max_examples:,}"
        )

        if default_max_examples > total_pass_variants:
            logger.info(f"{logger_msg}: default value for --max-examples is appropriate")
        else:
            logger.info(f"{logger_msg}: when running TrioTrain outside of this tutorial, please use --max-examples={total_pass_variants}"
        )

        env.add_to(
        f"Demo_TotalVariants",
                    str(total_pass_variants),
                    dryrun_mode=args.dry_run,
                )
        logger.info(
            f"{logger_msg}: added 'Demo_TotalVariants={total_pass_variants}' to env file"
        )

        logger.info(
            f"{logger_msg}: number of examples made | {int(num_examples):,}"
        )
        examples_per_variant = int(num_examples) / total_pass
        
        logger.info(
            f"{logger_msg}: calculated examples per variant | {round(examples_per_variant, ndigits=3):,}"
        )
        
        logger.info(
            f"{logger_msg}: default examples per variant | {default_ex_per_var:,}"
        )

        _delta = default_ex_per_var - examples_per_variant

        logger.info(
            f"{logger_msg}: difference between default and calculated examples per variant | {round(_delta, ndigits=3):,}"
        )

        if abs(_delta) > 0.5:
            logger.info(f"{logger_msg}: when running TrioTrain outside of this tutorial, please use --est-examples={round(examples_per_variant, ndigits=2)}"
        )
        else:
            logger.info(f"{logger_msg}: default value for --est-examples is appropriate"
        )

        env.add_to(
            f"Est_Examples",
            str(round(examples_per_variant, ndigits=2)),
            dryrun_mode=args.dry_run,
            )
        logger.info(
            f"{logger_msg}: added 'Est_Examples={round(examples_per_variant, ndigits=2)}' to env file"
        )
        
    else:
        logger.error(f"{logger_msg}: count_variants() failed.\nExiting...")
        exit(1)

    # Collect end time
    Wrapper(__file__, "end").wrap_script(timestamp())

# Execute all functions created
if __name__ == "__main__":
    __init__()
