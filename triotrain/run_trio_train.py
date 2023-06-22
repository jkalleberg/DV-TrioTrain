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
import os
import re
import sys
from pathlib import Path

import helpers
import model_training as pipe


def initalize_weights(setup: pipe.Setup, itr: helpers.Iteration):
    """
    Determine what weights to use to initalize model
    """
    logging_msg = f"[{itr._mode_string}] - [initalize]"

    if itr.args.first_genome is None:
        path = "TestCkptPath"
        file = "TestCkptName"
    else:
        if itr.current_genome_num == 0:
            path = "BaselineTestCkptPath"
            file = "BaselineTestCkptName"
        else:
            path = f"{setup.current_genome}StartCkptPath"
            file = f"{setup.current_genome}StartCkptName"
    current_starting_point = None

    # If running GIAB benchmarking, using a default model or a CL-arg ckpt,
    if setup.meta.checkpoint_name is not None:
        # define the complete path to the ckpt file.
        current_starting_point = Path(
            f"{str(setup.meta._checkpoint_path)}/{str(setup.meta.checkpoint_name)}"
        )

    # Look for where the starting checkpoint could be:
    else:
        # First, check if CURRENT ENV has a starting ckpt already...
        if (
            itr.env is not None
            and path in itr.env.contents
            and file in itr.env.contents
        ):
            warm_starting_ckpt_path = itr.env.contents[path]
            warm_starting_ckpt_name = itr.env.contents[file]

            current_starting_point = Path(
                f"{str(warm_starting_ckpt_path)}/{str(warm_starting_ckpt_name)}"
            )

        # Second, look a PRIOR ENV to define starting ckpt PATH only.
        if current_starting_point is None and itr.args.first_genome is not None:
            # Determine if we need to look in a completely different file...
            if setup.prior_trio_num != setup.current_trio_num:
                prior_env_path = (
                    Path(os.getcwd())
                    / "envs"
                    / f"{setup.args.name}-run{setup.prior_trio_num}.env"
                )
                prior_env = helpers.h.Env(str(prior_env_path), itr.logger)
                try:
                    prior_env.check_out()
                    check_this_env = prior_env
                except ValueError as e:
                    check_this_env = None
                    itr.logger.warning(f"{logging_msg}: {e}")
                    return

            # Or if we can search in the CURRENT ENV.
            else:
                check_this_env = itr.env

            # Determine if previous iteration has a testing ckpt PATH set
            if (
                check_this_env is not None
                and f"{setup.prior_genome}TestCkptPath" in check_this_env.contents
            ):
                found_starting_point = check_this_env.contents[
                    f"{setup.prior_genome}TestCkptPath"
                ]
                if found_starting_point:
                    current_starting_point = Path(found_starting_point)

        # Third, define the starting ckpt PATH by replacing the
        # CURRENT iteration number with the PRIOR iteration number
        if current_starting_point is None and setup.prior_trio_num is not None:
            train_path_parent = Path(itr.env.contents["OutPath"])  # type: ignore
            prior_run_name = re.sub(
                r"\d+",
                str(setup.prior_trio_num),
                str(itr.run_name),
                count=1,
            )
            current_starting_point = (
                train_path_parent / prior_run_name / f"train_{setup.prior_genome}"
            )

        ### TRAINING SPECIFIC STEPS -----------------------------------###
        if (
            itr.args.first_genome is not None
            and itr.current_genome_num is not None
            and itr.env is not None
        ):
            # Update the CURRENT ENV to include the testing ckpt PATH
            itr.env.add_to(
                f"{itr.train_genome}TestCkptPath",
                str(itr.train_dir),
                dryrun_mode=setup.args.dry_run,
                msg=f"{logging_msg}",
            )

            ### Include the NEXT starting ckpt PATH -------------------###
            update_this_env = None
            # Determine if we need to update a completely different file...
            if setup.current_trio_num != setup.next_trio_num:
                #  Set the CURRENT training PATH as the NEXT genome's starting PATH
                if setup.next_trio_num is not None:
                    if not setup.args.dry_run:
                        next_env_path = (
                            Path(os.getcwd())
                            / "envs"
                            / f"{itr.args.name}-run{setup.next_trio_num}.env"
                        )

                        if next_env_path.exists() is False:
                            next_itr = itr.current_genome_num + 1
                            setup.process_env(
                                itr_num=next_itr,
                            )

                        next_env = helpers.h.Env(
                            str(next_env_path),
                            itr.logger,
                            debug_mode=setup.args.debug,
                        )
                        try:
                            next_env.check_out()
                            update_this_env = next_env
                        except ValueError as e:
                            itr.logger.warning(f"{logging_msg}: {e}")
                    else:
                        itr.logger.info(
                            f"[DRY_RUN] - {logging_msg}: unable to update next trio env file"
                        )
                else:
                    itr.logger.error(
                        f"[{itr._mode_string}]: next_trio_num can not be 'None', unable to update next trio env file.\nExiting..."
                    )
                    sys.exit(1)
            # or if we can update the CURRENT ENV
            else:
                update_this_env = itr.env

            if update_this_env is not None:
                update_this_env.add_to(
                    f"{setup.next_genome}StartCkptPath",
                    str(itr.train_dir),
                    dryrun_mode=setup.args.dry_run,
                )

    if current_starting_point and itr.env is not None:
        # If only a directory is found, add just the PATH
        if current_starting_point.is_dir():
            itr.env.add_to(
                path,
                str(current_starting_point),
                dryrun_mode=setup.args.dry_run,
            )
            itr.logger.info(
                f"{logging_msg}: warm-starting model location | '{current_starting_point}'"
            )
        else:
            weights_file = current_starting_point.with_suffix(
                current_starting_point.suffix + ".data-00000-of-00001"
            )

            if weights_file.is_file():
                itr.logger.info(
                    f"{logging_msg}: warm-starting with the following checkpoint | '{current_starting_point}'"
                )

                itr.env.add_to(
                    path,
                    str(current_starting_point.parent),
                    dryrun_mode=setup.args.dry_run,
                    msg=f"{logging_msg}",
                )

                itr.env.add_to(
                    file,
                    str(current_starting_point.name),
                    dryrun_mode=setup.args.dry_run,
                    msg=f"{logging_msg}",
                )
            else:
                itr.logger.error(
                    f"{logging_msg}: unable to initalize model; missing starting ckpt | '{current_starting_point}'.\nExiting..."
                )
                sys.exit(1)
    else:
        if itr.args.use_deeptrio:
            itr.logger.info(
                f"{logging_msg}: running with the DeepTrio model as the starting ckpt"
            )
        else:
            itr.logger.error(
                f"{logging_msg}: unable to find a warm-starting model location.\nExiting..."
            )
            sys.exit(1)


def run_trio_train(eval_genome="Child"):
    """
    Complete an Iteration of the TrioTrain pipeline.

    An Iteration is either:
        1. testing a baseline model checkpoint
        2. re-training with a parent-child duo within a trio
    """
    # Collect command line arguments
    parser = pipe.collect_args()
    channel_defaults = pipe.get_defaults(parser, "channel_info")
    args = pipe.get_args(parser=parser)

    # Collect start time
    helpers.h.Wrapper(__file__, "start").wrap_script(helpers.h.timestamp())

    # Create error log
    current_file = os.path.basename(__file__)
    module_name = os.path.splitext(current_file)[0]
    logger = helpers.log.get_logger(module_name)

    # Check command line args
    pipe.check_args(args=args, logger=logger, default_channels=channel_defaults)

    # Process any trio dependencies in args
    convert = lambda i: None if i == "None" else str(i)
    if args.trio_dependencies:
        current_genome_deps = [
            convert(dep) for dep in args.trio_dependencies.split(",")
        ]
        if current_genome_deps[3] is not None:
            next_genome_deps = [None, None, current_genome_deps[3], None]
        else:
            next_genome_deps = helpers.h.create_deps()
    else:
        current_genome_deps = helpers.h.create_deps()
        next_genome_deps = helpers.h.create_deps()

    pipeline = pipe.Setup(
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
    else:
        begining = 0

    # Define the baseline environment
    new_env = pipeline.process_env(begining)

    if pipeline.args.terminate:
        if pipeline.args.terminate < begining:
            logger.error(
                f"The value for --stop-itr must be greater than or equal to '{begining}'.\nExiting... "
            )
            sys.exit(1)
        else:
            end = pipeline.args.terminate
    else:
        end = begining + 1

    if end != pipeline.meta.num_of_iterations and pipeline.args.terminate is None:
        end = pipeline.meta.num_of_iterations

    if pipeline.args.demo_mode and pipeline.args.show_regions:
        begining = 1
        end = 2
        # Determine if show_regions file is valid
        pipeline.find_show_regions_file()

    number_completed_itrs = 0
    for itr in range(begining, end):
        if itr != begining:
            new_env = pipeline.process_env(itr_num=itr)

        number_completed_itrs += 1
        pipeline.start_iteration(
            current_deps=pipeline.current_genome_deps,
            next_deps=pipeline.next_genome_deps,
        )
        new_env = pipeline.meta.env

        if pipeline.args.first_genome is None:
            current_itr = helpers.Iteration(
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
            current_itr = helpers.Iteration(
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
            current_itr = helpers.Iteration(
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
            output_file = helpers.h.WriteFiles(
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
            pipe.Run(
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
            pipe.Run(
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
            # no_prior_jobs_run = helpers.h.check_if_all_same(pipeline.next_genome_deps, None)
            pipeline.end_iteration()
            pipeline.current_genome_deps = pipeline.next_genome_deps
            pipeline.next_genome_deps = helpers.h.create_deps()

        ### Create Demo Runs ------------------------------------------###
        elif current_itr.demo_mode:
            current_itr.logger.info(f"{logging_msg}: --demo_mode is active")
            pipe.Run(
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
            pipe.Run(
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
            are_next_genome_jobs_running = helpers.h.check_if_all_same(
                pipeline.next_genome_deps, None
            )
            pipeline.end_iteration()
            print(f"NO NEXT GENOME JOBS RUNNING? {are_next_genome_jobs_running}")

            pipeline.current_genome_deps = pipeline.next_genome_deps
            pipeline.next_genome_deps = helpers.h.create_deps()

        # elif no_prior_jobs_run and itr != begining:
        #     logger.info(
        #         f"============ SKIPPING [Trio{pipeline.current_trio_num}] - [{pipeline.current_genome}] ============"
        #     )
        #     continue

    ### ---------------------------- ###
    helpers.h.Wrapper(__file__, "end").wrap_script(helpers.h.timestamp())


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
