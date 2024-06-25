#!/bin/python
"""
description: process the command line arguments for run_trio_train

usage:
    from pipeline_args import collect_args, check_args
"""
import argparse
import importlib
import json
from logging import Logger
from pathlib import Path
from sys import exit
from typing import Text

from helpers.typos import check_typos


# use the doc string from __main__
def get_docstring(script_name, script_path) -> Text:
    spec = importlib.util.spec_from_file_location(script_name, script_path)
    foo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(foo)
    return foo.__doc__


def collect_args() -> argparse.ArgumentParser:
    """
    process the command line arguments to execute script.
    """
    # get the relative path to the triotrain/ dir
    h_path = Path(__file__).parent.parent.parent
    doc = get_docstring(
        script_name="run_trio_train.py", script_path=str(h_path / "run_trio_train.py")
    )
    parser = argparse.ArgumentParser(
        description=doc,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version="%(prog)s version 0.8",
        help="show program's version number and exit",
    )
    parser.add_argument(
        "-g",
        "--first-genome",
        dest="first_genome",
        choices=["Mother", "Father", "None"],
        help="[REQUIRED]\nsets the initial training genome",
        type=str,
    )
    parser.add_argument(
        "--ignore",
        dest="ignore",
        help="comma-separated list of prefixes; used to exclude regions during training (e.g., unmapped contigs or low-quality sex chrs)\nNOTE: requires partial match to @SQ tag from reference genome\nDefault based on ARS-UCD1.2_Btau5.0.1Y\n(default: %(default)s)",
        type=str,
        metavar="<str>",
        default="NKLS,Y",
    )
    parser.add_argument(
        "-m",
        "--metadata",
        dest="metadata",
        help="[REQUIRED]\ninput file (.csv)\ndescribes each trio to analyze and sets the training order",
        type=str,
        metavar="</path/file>",
    )
    parser.add_argument(
        "--modules",
        dest="modules",
        help="[REQUIRED]\ninput file (.sh)\nhelper script which loads the local software packages\n(default: %(default)s)",
        default="./scripts/setup/modules.sh",
        type=str,
        metavar="</path/file>",
    )
    parser.add_argument(
        "-n",
        "--name",
        dest="name",
        help="[REQUIRED]\nlabel for all iterations",
        type=str,
        metavar="<str>",
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
        "-t",
        "--num-tests",
        dest="num_tests",
        help="[REQUIRED]\nthe number of test genomes in metadata.csv file\n(default: %(default)s)",
        type=int,
        default=13,
        metavar="<int>",
    )
    parser.add_argument(
        "-d",
        "--debug",
        dest="debug",
        help="print debug logger messages",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        help="display executed commands to the screen",
        action="store_true",
    )
    parser.add_argument(
        "--est-examples",
        dest="est_examples",
        help="estimated examples created per variant\n(default: %(default)s)",
        default=1.5,
        type=float,
        metavar="<float>",
    )
    parser.add_argument(
        "--max-examples",
        dest="max_examples",
        help="maximum examples include per regions file\n(default: %(default)s)",
        default=200000,
        type=int,
        metavar="<int>",
    )
    parser.add_argument(
        "-B",
        "--batch-size",
        dest="batch_size",
        help="sets how many training example images to use per step\n(default: %(default)s)",
        type=int,
        default=32,
        metavar="<int>",
    )
    parser.add_argument(
        "-L",
        "--learning-rate",
        dest="learning_rate",
        help="defines how much to adjust model weights between batches\ncontrols the speed the model will approach convergence.\n(default: %(default)s)",
        type=float,
        default=0.005,
        metavar="<float>",
    )
    parser.add_argument(
        "-E",
        "--epochs",
        dest="num_epochs",
        help="defines training time\n[(# training examples/ batch_size) * # epochs] = number of total steps\n(default: %(default)s)",
        type=int,
        default=1,
        metavar="<int>",
    )
    parser.add_argument(
        "--keep-jobids",
        dest="benchmark",
        help="if True, save SLURM job numbers for calculating resource usage",
        action="store_true",
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output",
        help="directory path\nre-direct where to save TrioTrain results\n(default: %(default)s)",
        default="../TRIO_TRAINING_OUTPUTS",
        type=str,
        metavar="</path/dir>",
    )
    parser.add_argument(
        "--use-gpu",
        dest="use_gpu",
        help=f"if True, use the GPU container to accelerate variant calling\n\tNOTE: NOT RECOMMENDED; requires running with GPU partition/resources from SLURM\n(default: %(default)s)",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--use-regions-shuffle",
        dest="use_regions_shuffle",
        help="if True, split genomes into smaller, genome-wide chunks that fit 'in_memory' for Apache Beam Shuffling\nif False, return to shuffling all examples made\n(default: %(default)s)",
        action="store_true",
        default=True,
    )
    # parser.add_argument(
    #     "--use-DT",
    #     dest="use_deeptrio",
    #     help="[WIP] if True, call_variants and benchmarking will expect trios",
    #     action="store_true",
    # )
    # hidden argument
    parser.add_argument(
        "--phases",
        dest="_phases",
        help=argparse.SUPPRESS,
        default=[
            "make_examples",
            "beam_shuffle",
            "re_shuffle",
            "train_eval",
            "select_ckpt",
            "call_variants",
            "compare_happy",
            "convert_happy",
            "show_examples",
        ],
        required=False,
    )

    demo = parser.add_argument_group("pipeline demo")
    demo.add_argument(
        "--demo-mode",
        dest="demo_mode",
        help="if True, run a single chromosome for the first genome only\n(default: %(default)s)",
        default=False,
        action="store_true",
    )
    demo.add_argument(
        "--demo-chr",
        dest="demo_chr",
        help="sets which chromosome to use for demo mode\n(default: %(default)s)",
        default="29",
        metavar="<str>",
    )
    demo.add_argument(
        "--show-regions",
        dest="show_regions",
        help="[BETA]\nif True, create PNG images of the multi-channel tensor vector(s)\n(default: %(default)s)",
        default=False,
        action="store_true",
    )
    demo.add_argument(
        "--show-regions-file",
        dest="show_regions_file",
        help="[BETA]\ninput file (.bed or .txt)\ncontains location(s) to visualize\n==== .bed format ====\nCHROM\tSTART\tSTOP\n=====================\n==== .txt format ====\nCHROM:START-STOP\n=====================",
        type=str,
        metavar="</path/to/regions_file>",
    )
    restart = parser.add_argument_group("re-start the pipeline")

    _phases_string = ",\n\t".join(parser.get_default("_phases"))
    restart.add_argument(
        "--restart-jobs",
        dest="restart_jobs",
        help=f"provide a JSON dictionary containing phase names as keys, and either:\n- a list of indexs to re-run, or\n- a list of running SLURM job numbers to use as dependencies\nVALID PHASES:\n\t{_phases_string}\n(default: %(default)s)",
        type=json.loads,
        default=None,
        metavar='{"phase": [jobid1, jobid2, jobid3]}',
    )
    restart.add_argument(
        "--overwrite",
        dest="overwrite",
        help="if True, re-write the SLURM job files and output files\n(default: %(default)s)",
        default=False,
        action="store_true",
    )
    restart.add_argument(
        "--start-itr",
        dest="begin",
        help="start a pipeline at a specified genome iteration.\nEXAMPLE: to start @ Trio2-Parent1, set --start-itr=3",
        type=int,
        metavar="<int>",
    )
    restart.add_argument(
        "--stop-itr",
        dest="terminate",
        help="end a pipeline at a specified genome iteration.\nEXAMPLE: to end @ Trio2-Parent2, set --end-itr=4",
        type=int,
        metavar="<int>",
    )
    restart.add_argument(
        "--trio-dependencies",
        dest="trio_dependencies",
        help=f"comma-delimited list of (4) SLURM job numbers to use as job dependencies\nuse 'None' as place holders\n\ttrio_dependencies[0] = training genome re-shuffle job number\n\ttrio_dependencies[1] = evaluation genome re-shuffle job number\n\ttrio_dependencies[2] = prior itereation select-ckpt job number\n\ttrio_dependencies[3] = current iteration select-ckpt job number",
        type=str,
        metavar="<'None,None,24485783,None'>",
    )
    restart.add_argument(
        "-u",
        "--update",
        dest="update",
        help="if True, update an existing .env file with new variables (e.g. updating file paths)",
        action="store_true",
    )

    customize = parser.add_argument_group(
        "customize model weights with a non-default model"
    )
    customize.add_argument(
        "--custom-checkpoint",
        dest="custom_ckpt",
        help="input file (model.ckpt)\nprovides model weights to use as the warm-starting point",
    )
    customize.add_argument(
        "--channel-info",
        dest="channel_info",
        help="input file (.json) or JSON-format string\ncontaines 'channels' as a key, with a list of channel numbers as values\n(default: %(default)s)",
        default='{"channels": [1, 2, 3, 4, 5, 6, 19]}',
        metavar="JSON data or file",
    )
    return parser


def get_defaults(parser: argparse.ArgumentParser, arg_name: str) -> str:
    """
    Provide the default values for a pipeline argument
    """
    return parser.get_default(arg_name)


def get_args(parser: argparse.ArgumentParser) -> argparse.Namespace:
    """
    Return the key=value arguments from the command line
    """
    manual_args_list = [
        "-m",
        # "triotrain/model_training/metadata/240429_DeepVariantTriosTRUTH_UMAG1_noPopVCF.csv",
        "triotrain/model_training/metadata/240429_DeepVariantTriosTRUTH_UMAG1_noPopVCF_hellbender.csv",
        # "triotrain/model_training/metadata/230313_benchmarking.csv",
        # "triotrain/model_training/metadata/230307_PASS.csv",
        "--first-genome",
        "Father",
        # "Mother",
        # "None",
        "--name",
        "240429_NoPopVCF",
        # "230313_GIAB",
        # "220913_NewTrios",
        # "221118_NewTrios",
        # "221214_MotherFirst",
        "-r",
        "triotrain/model_training/tutorial/resources_used_hellbender.json",
        # "--demo-mode",
        # "--show-regions-file",
        # "region_files/DEMO_PASS1.show_regions.bed",
        "--num-tests",
        "19",
        # "6",
        "--start-itr",
        "17",
        "--stop-itr",
        "18",
        # "17",
        # "30",
        # "--dry-run",
        # "--ignore",
        # "NKLS,MSY",
        # "--debug",
        # "--update",
        # "--custom-checkpoint",
        # "/storage/hpc/group/UMAG_test/WORKING/jakth2/deep-variant/pretrained_models/DV1.4_WGS.AF_cattle2/model.ckpt-120844",
        # "/storage/hpc/group/UMAG_test/WORKING/jakth2/deep-variant/pretrained_models/DV1.4_WGS.AF_cattle3/model.ckpt-935368",
        # "/storage/hpc/group/UMAG_test/WORKING/jakth2/deep-variant/pretrained_models/DV1.4_WGS.AF_cattle4/model.ckpt-282383",
        # "/storage/hpc/group/UMAG_test/WORKING/jakth2/deep-variant/pretrained_models/DV1.4_WGS.AF_cattle5/model.ckpt-336710",
        # "/storage/hpc/group/UMAG_test/WORKING/jakth2/deep-variant/pretrained_models/v1.4.0-withIS-noPop/model.ckpt",
        # "/storage/hpc/group/UMAG_test/WORKING/jakth2/deep-variant/pretrained_models/v1.4.0-withIS-withPop/wgs_af.model.ckpt",
        # "pretrained_models/v1.4.0-withIS-withPop/wgs_af.model.ckpt",
        # "--channel-info",
        # '{"channels": [1, 2, 3, 4, 5, 6, 8, 19]}',
        # "/storage/hpc/group/UMAG_test/WORKING/jakth2/TRIO_TRAINING_OUTPUTS/220913_NewTrios/PASS11/examples/Mother.example_info.json",
        # "--use-gpu",
        # "--benchmark",
        # "--trio-dependencies",
        # "None,None,28935490,None",
        # "--overwrite",
        # "--restart-jobs",
        # '{"train_eval": [1]}',
        # '{"re_shuffle:Father": [1]}',
        # '{"call_variants": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19]}',
        # '{"convert_happy": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19]}',
        # '{"convert_happy": [2, 3, 4, 5, 6]}',
    ]
    return parser.parse_args(manual_args_list)
    # return parser.parse_args()


def check_args(args: argparse.Namespace, logger: Logger, default_channels: str) -> None:
    """
    with "--debug", display command line args provided.

    with "--dry-run", display a msg.

    check to make sure all required flags are provided.
    """
    if args.debug:
        str_args = "COMMAND LINE ARGS USED: "
        for key, val in vars(args).items():
            str_args += f"{key}={val} | "

        logger.debug(str_args)

    if args.dry_run:
        logger.info("option --dry-run set; display commands without running them")

    try:
        assert (
            args.name
        ), "missing option --name; Please provide a label for the current analysis"
        assert (
            args.metadata
        ), "missing option --metadata; Please provide the path to pipeline run parameters in CSV format"
        assert (
            args.first_genome
        ), "missing option --first-genome; Please designate which genome to use to start training for each iteration"
        # Convert the string value from arguments to a 'None' value
        if args.first_genome == "None":
            args.first_genome = None

        assert (
            args.resource_config
        ), "missing option --resources; Please designate a path to pipeline compute resources in JSON format"

        assert Path(
            args.modules
        ).is_file, f"unable to find the modules file | '{args.modules}'"

        if args.demo_mode and args.show_regions:
            assert (
                args.show_regions_file
            ), "missing option --show-regions-file; Please designate a path to show_examples subset region in either BED or text format"

        if args.overwrite:
            assert (
                args.restart_jobs
            ), f"option --overwrite is set, but missing --restart-jobs.\nPlease provide a JSON dictionary with the following format:\n{{'phase': ['jobid', 'jobid', 'None', 'jobid']}}.\n\t- 'phase' determines which parts of the pipeline to re-run completely\n\t- any jobid = 'None' will be have the SLURM job file and any existing results overwritten"

            if args.demo_mode is False:
                if args.begin is None:
                    args.begin = 0

                if args.terminate is None:
                    logger.warning(
                        "missing option --stop-itr; however only one iteration will be overwritten at a time"
                    )
                    args.terminate = args.begin + 1

                num_runs_to_overwrite = int(args.terminate) - int(args.begin)
                assert (
                    num_runs_to_overwrite == 1
                ), f"option --overwrite is set, but attempting to run {num_runs_to_overwrite} iterations.\nPlease adjust either --start-itr or --stop-itr flags so that only one iteration will be overwritten at a time"

        if "," in args.ignore:
            ignore_list = args.ignore.split(",")
            args.ignore = ignore_list

        # warn the user against phase name typos
        if args.restart_jobs:
            phase_dict = dict()
            for k in args.restart_jobs.keys():
                # ignore genome when checking for typos
                if ":" in k:
                    k = k.split(":")[0]

                close_matches = list()
                if k not in args._phases:
                    for p in args._phases:
                        match_found = check_typos(p, k)
                        if match_found:
                            close_matches.append(match_found[0])
                    phase_dict[k] = close_matches

            if phase_dict:
                for k, l in phase_dict.items():
                    if isinstance(l, list):
                        options_str = "', or '".join(l)
                        logger.info(
                            f"invalid phase entered: '{k}', did you mean to enter '{options_str}'?\nExiting..."
                        )
                        exit(1)

        if args.channel_info == default_channels:
            use_default_channels = True
        else:
            use_default_channels = False

        if args.custom_ckpt:
            logger.info("option --custom-ckpt is set")
            if "wgs_af" in args.custom_ckpt and use_default_channels:
                logger.info(
                    f"option --channel-info is missing, defaults will identified soon..."
                )
            elif "pretrained_models" in args.custom_ckpt:
                args.channel_info = f"{args.custom_ckpt}.example_info.json"
                logger.info("option --channel-info is set; using an existing json file")
            else:
                assert (
                    use_default_channels is False
                ), "--custom-ckpt is a non-default model so --channel-info must be set"
                if Path(args.channel_info).is_file():
                    assert (
                        "json" in args.channel_info.lower()
                    ), "expected a '.json' file input."
                    logger.info("option --channel-info is set; json file provided")
                else:
                    logger.info(
                        f"option --channel-info is set; using custom channels: {args.channel_info}"
                    )

    except AssertionError as error:
        logger.error(f"{error}.\nExiting... ")
        exit(1)
