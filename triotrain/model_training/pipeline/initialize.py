from pathlib import Path
import re
from helpers.iteration import Iteration
from model_training.pipeline.setup import Setup
from helpers.environment import Env
from sys import exit

def initalize_weights(setup: Setup, itr: Iteration):
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
                    Path(itr.env.contents["OutPath"]) /
                    "envs" /
                    f"run{setup.prior_trio_num}.env"
                )
                prior_env = Env(
                    str(prior_env_path), itr.logger, dryrun_mode=itr.dryrun_mode
                )
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

    if current_starting_point and itr.env is not None:
        # If only a directory is found, add just the PATH
        if current_starting_point.is_dir():
            itr.env.add_to(
                path,
                str(current_starting_point),
                dryrun_mode=setup.args.dry_run,
                msg=logging_msg
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
                    msg=logging_msg,
                )

                itr.env.add_to(
                    file,
                    str(current_starting_point.name),
                    dryrun_mode=setup.args.dry_run,
                    msg=logging_msg,
                )
            else:
                itr.logger.error(
                    f"{logging_msg}: unable to initalize model; missing starting ckpt | '{current_starting_point}'.\nExiting..."
                )
                exit(1)
    else:
        if itr.args.use_deeptrio:
            itr.logger.info(
                f"{logging_msg}: running with the DeepTrio model as the starting ckpt"
            )
        else:
            itr.logger.error(
                f"{logging_msg}: unable to find a warm-starting model location.\nExiting..."
            )
            exit(1)
    
    ### TRAINING SPECIFIC STEPS -----------------------------------###
    if (
        itr.args.first_genome is not None
        and itr.current_genome_num > 0
        and itr.env is not None
        and not itr.demo_mode
    ):
        # Update the CURRENT ENV to include the testing ckpt PATH
        itr.env.add_to(
            f"{itr.train_genome}TestCkptPath",
            str(itr.train_dir),
            dryrun_mode=setup.args.dry_run,
            msg=logging_msg,
        )

        ### Include the NEXT starting ckpt PATH -------------------###
        update_this_env = None
        # Determine if we need to update a completely different file...
        if setup.current_trio_num != setup.next_trio_num:
            #  Set the CURRENT training PATH as the NEXT genome's starting PATH
            if setup.next_trio_num is not None:
                if not setup.args.dry_run:
                    next_env_path = (
                        Path(itr.env.contents["OutPath"]) /
                        "envs" /
                        f"run{setup.next_trio_num}.env"
                    )

                    if next_env_path.exists() is False:
                        next_itr = itr.current_genome_num + 1
                        setup.process_env(
                            itr_num=next_itr,
                        )

                    next_env = Env(
                        str(next_env_path),
                        itr.logger,
                        debug_mode=setup.args.debug,
                        dryrun_mode=setup.args.dry_run,
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
            elif setup.meta.itr_num+1 == setup.meta.num_of_iterations:
                
                itr.logger.info(
                    f"[{itr._mode_string}]: final iteration detected; unable to update next trio env file")
                return
            else:
                itr.logger.error(
                    f"[{itr._mode_string}]: next_trio_num can not be 'None', unable to update next trio env file.\nExiting..."
                )
                exit(1)
        # or if we can update the CURRENT ENV
        else:
            update_this_env = itr.env

        if update_this_env is not None:
            update_this_env.add_to(
                f"{setup.next_genome}StartCkptPath",
                str(itr.train_dir),
                dryrun_mode=setup.args.dry_run,
                msg=logging_msg,
            )
