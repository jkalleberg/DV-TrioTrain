#!/usr/bin/python3
"""
description: executes the TrioTrain pipeline

1) initializes environment config files (.env). 
2) writes SBATCH job files for each phase of the pipeline.
3) submits jobs to the SLURM queue to produce outputs. 

example:
    python3 triotrain/run_trio_train.py                                         \\
        -g Father                                                               \\
        -m triotrain/model_training/tutorial/GIAB.Human_tutorial_metadata.csv   \\
        -n test                                                                 \\
        -r triotrain/model_training/tutorial/resources_used.json
"""

### --- PYTHON LIBRARIES ---- ###
from os import path
from sys import exit

from helpers.files import WriteFiles
from helpers.iteration import Iteration
from helpers.utils import check_if_all_same, create_deps, get_logger
from helpers.wrapper import Wrapper, timestamp
from model_training.pipeline.args import (
    check_args,
    collect_args,
    get_args,
    get_defaults,
)
from model_training.pipeline.initialize import initalize_weights
from model_training.pipeline.run import RunTrioTrain
from model_training.pipeline.setup import Setup


def run_trio_train(eval_genome="Child") -> None:
    """
    Complete an Iteration of the TrioTrain pipeline.

    An Iteration is either:
        1. testing a baseline model checkpoint
        2. re-training with a parent-child duo within a trio
    """
    # Collect command line arguments
    parser = collect_args()
    channel_defaults = get_defaults(parser, "channel_info")
    args = get_args(parser=parser)

    # Collect start time
    Wrapper(__file__, "start").wrap_script(timestamp())

    # Create error log
    current_file = path.basename(__file__)
    module_name = path.splitext(current_file)[0]
    logger = get_logger(module_name)

    # Check command line args
    check_args(args=args, logger=logger, default_channels=channel_defaults)

    # Process any trio dependencies in args
    convert = lambda i: None if i == "None" else str(i)
    if args.trio_dependencies:
        current_genome_deps = [
            convert(dep) for dep in args.trio_dependencies.split(",")
        ]
        if current_genome_deps[3] is not None:
            next_genome_deps = [None, None, current_genome_deps[3], None]
        else:
            next_genome_deps = create_deps()
    else:
        current_genome_deps = create_deps()
        next_genome_deps = create_deps()

    pipeline = Setup(
        logger,
        args,
        eval_genome,
        current_genome_deps=current_genome_deps,
        next_genome_deps=next_genome_deps,
        demo_mode=args.demo_mode,
    )

    # Process any running jobs
    if pipeline.args.restart_jobs:
        num_running_phases = 0
        print("--------- running jobs were provided ---------")
        for k, v in pipeline.args.restart_jobs.items():
            num_running_phases += 1
            num_jobs = len(v)
            print(
                f"phase{num_running_phases}: you provided [{num_jobs}] jobs | '{k}'={v}"
            )
        print("----------------------------------------------")

    if pipeline.args.begin is not None:
        begining = pipeline.args.begin
    elif pipeline.args.demo_mode:
        begining = 1
        if pipeline.args.show_regions:
            # Determine if show_regions file is valid
            pipeline.find_show_regions_file()
    else:
        begining = 0

    if pipeline.args.terminate:
        if pipeline.args.terminate < begining:
            logger.error(
                f"The value for --stop-itr must be greater than or equal to '{begining}'.\nExiting... "
            )
            exit(1)
        else:
            end = pipeline.args.terminate
    else:
        end = begining + 1

    # Define the baseline environment
    new_env = pipeline.process_env(begining)

    if (
        not pipeline.args.demo_mode
        and end != pipeline.meta.num_of_iterations
        and pipeline.args.terminate is None
    ):
        end = pipeline.meta.num_of_iterations

    number_completed_itrs = 0
    for itr in range(begining, end):
        # do not re-create the first env,
        # or when running the second iteration for each trio

        if pipeline.args.demo_mode:
            if itr != begining and itr % 2 != 0:
                new_env = pipeline.process_env(itr_num=itr)
        else:
            if itr != begining:
                new_env = pipeline.process_env(itr_num=itr)

        pipeline.start_iteration(
            current_deps=pipeline.current_genome_deps,
            next_deps=pipeline.next_genome_deps,
        )

        number_completed_itrs += 1
        new_env = pipeline.meta.env

        if pipeline.args.first_genome is None:
            current_itr = Iteration(
                current_trio_num=None,
                next_trio_num=pipeline.next_trio_num,
                current_genome_num=pipeline.meta.itr_num,
                total_num_genomes=None,
                total_num_tests=pipeline.meta.num_tests,
                train_genome=None,
                eval_genome=None,
                env=new_env,
                logger=logger,
                args=pipeline.args,
                current_genome_dependencies=pipeline.current_genome_deps,
                next_genome_dependencies=pipeline.next_genome_deps,
                next_genome=pipeline.next_genome,
            )

        elif pipeline.meta.itr_num == 0:
            current_itr = Iteration(
                current_trio_num=pipeline.meta.itr_num,
                next_trio_num=pipeline.next_trio_num,
                current_genome_num=pipeline.meta.itr_num,
                total_num_genomes=pipeline.meta.num_of_iterations,
                total_num_tests=pipeline.meta.num_tests,
                train_genome=None,
                eval_genome=None,
                env=new_env,
                logger=logger,
                args=pipeline.args,
                current_genome_dependencies=pipeline.current_genome_deps,
                next_genome_dependencies=pipeline.next_genome_deps,
                next_genome=pipeline.next_genome,
            )
        else:
            current_itr = Iteration(
                current_trio_num=int(pipeline.current_trio_num),
                next_trio_num=pipeline.next_trio_num,
                current_genome_num=pipeline.meta.itr_num,
                total_num_genomes=pipeline.meta.num_of_iterations,
                total_num_tests=pipeline.meta.num_tests,
                train_genome=pipeline.current_genome,
                eval_genome=pipeline.eval_genome,
                env=new_env,
                logger=logger,
                args=pipeline.args,
                prior_genome=pipeline.prior_genome,
                current_genome_dependencies=pipeline.current_genome_deps,
                next_genome_dependencies=pipeline.next_genome_deps,
                next_genome=pipeline.next_genome,
            )

        logging_msg = f"[{current_itr._mode_string}] - [setup]"

        if current_itr.env is None:
            return
        # Add the number of test genomes to the envfile
        current_itr.env.add_to(
            "TotalTests",
            str(pipeline.meta.num_tests),
            dryrun_mode=pipeline.args.dry_run,
            msg=logging_msg,
        )

        current_itr.check_working_dir()

        # --- Notify which default_model is being used --- ##:
        if all(
            key in current_itr.env.contents for key in ("PopVCF_Path", "PopVCF_File")
        ) and (pipeline.meta._version == "1.4.0"):
            logger.info(
                f"{logging_msg}: population VCF variables found in environment file | '{current_itr.env.env_file}'"
            )
            if itr == 0 and pipeline.meta.checkpoint_name is None:
                logger.info(
                    f"{logging_msg}: however, the default model includes only the {pipeline.meta.additional_channels} channel"
                )
                logger.info(
                    f"{logging_msg}: therefore, ignoring the PopVCF_File + PopVCF_Path variables..."
                )
        else:
            logger.info(
                f"{logging_msg}: population VCF variables are NOT present in '{current_itr.env.env_file}'",
            )

        if itr > 1:
            logger.info(
                f"{logging_msg}: building a new model with {pipeline.meta.additional_channels} channels"
            )
        else:
            logger.info(
                f"{logging_msg}: model includes the {pipeline.meta.additional_channels} channel(s)"
            )

        # If tracking resources used from SLURM jobs,
        # inialize a file to store metrics
        if pipeline.args.benchmark:
            output_file = WriteFiles(
                path_to_file=str(current_itr.results_dir),
                file=f"{current_itr.model_label}.SLURM.job_numbers.csv",
                logger=logger,
                logger_msg=f"{logging_msg}",
                debug_mode=pipeline.args.debug,
                dryrun_mode=pipeline.args.dry_run,
            )
        else:
            output_file = None

        initalize_weights(setup=pipeline, itr=current_itr)

        ### Create GIAB Benchmarkinging Runs --------------------------###
        if current_itr.args.first_genome is None:
            RunTrioTrain(
                itr=current_itr,
                resource_file=pipeline.args.resource_config,
                num_tests=pipeline.meta.num_tests,
                overwrite=pipeline.args.overwrite,
                restart_jobs=pipeline.args.restart_jobs,
                train_mode=True,
                use_gpu=pipeline.args.use_gpu,
                use_regions_shuffle=False,
                track_resources=pipeline.args.benchmark,
                benchmarking_file=output_file,
            ).run()

        ### Create Training Runs --------------------------------------###
        elif (
            not current_itr.demo_mode
            and current_itr.current_genome_num is not None
            and current_itr.current_genome_num >= 1
        ):
            RunTrioTrain(
                itr=current_itr,
                resource_file=pipeline.args.resource_config,
                est_examples=pipeline.args.est_examples,
                max_examples=pipeline.args.max_examples,
                next_genome=pipeline.next_genome,
                num_tests=pipeline.meta.num_tests,
                overwrite=pipeline.args.overwrite,
                prior_genome=pipeline.prior_genome,
                restart_jobs=pipeline.args.restart_jobs,
                train_mode=True,
                use_gpu=pipeline.args.use_gpu,
                use_regions_shuffle=pipeline.args.use_regions_shuffle,
                track_resources=pipeline.args.benchmark,
                benchmarking_file=output_file,
            ).run()

            # --- switch the dependencies so that prior becomes current before the next iteration starts ---#
            # no_prior_jobs_run = check_if_all_same(pipeline.next_genome_deps, None)
            pipeline.end_iteration()
            pipeline.current_genome_deps = pipeline.next_genome_deps
            pipeline.next_genome_deps = create_deps()

        ### Create Demo Runs ------------------------------------------###
        elif current_itr.demo_mode:
            current_itr.logger.info(f"{logging_msg}: --demo_mode is active")
            RunTrioTrain(
                itr=current_itr,
                resource_file=args.resource_config,
                est_examples=pipeline.args.est_examples,
                max_examples=pipeline.args.max_examples,
                num_tests=pipeline.meta.num_tests,
                overwrite=pipeline.args.overwrite,
                restart_jobs=pipeline.args.restart_jobs,
                show_regions_file=pipeline.args.show_regions_file,
                train_mode=True,
                use_regions_shuffle=False,
                track_resources=pipeline.args.benchmark,
                benchmarking_file=output_file,
            ).run()

        ### Create Baseline Runs --------------------------------------###
        elif current_itr.current_trio_num == 0:
            RunTrioTrain(
                itr=current_itr,
                resource_file=pipeline.args.resource_config,
                next_genome=pipeline.next_genome,
                num_tests=pipeline.meta.num_tests,
                overwrite=pipeline.args.overwrite,
                prior_genome=pipeline.prior_genome,
                restart_jobs=pipeline.args.restart_jobs,
                train_mode=True,
                use_gpu=pipeline.args.use_gpu,
                use_regions_shuffle=False,
                track_resources=pipeline.args.benchmark,
                benchmarking_file=output_file,
            ).run()

            # --- switch the dependencies so that prior becomes current before the next iteration starts ---#
            are_next_genome_jobs_running = check_if_all_same(
                pipeline.next_genome_deps, None
            )
            pipeline.end_iteration()
            print(f"NO NEXT GENOME JOBS RUNNING? {are_next_genome_jobs_running}")

            pipeline.current_genome_deps = pipeline.next_genome_deps
            pipeline.next_genome_deps = create_deps()

        # elif no_prior_jobs_run and itr != begining:
        #     logger.info(
        #         f"============ SKIPPING [Trio{pipeline.current_trio_num}] - [{pipeline.current_genome}] ============"
        #     )
        #     continue

    ### ---------------------------- ###
    Wrapper(__file__, "end").wrap_script(timestamp())


def __init__():
    """
    Determine what happens if this script is run
    from the command line, rather than imported
    as a module into other Python code.
    """
    run_trio_train(eval_genome="Child")


# Execute functions created
if __name__ == "__main__":
    __init__()
