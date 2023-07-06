#!/usr/bin/python
"""
description: combines all potential Iteration options for the TrioTrain pipeline.

usage:
    from pipeline_run import Run
"""
from dataclasses import dataclass, field
from json import load
from sys import exit
from typing import TextIO, Union

# Custom helper modules
from helpers.files import WriteFiles
from helpers.iteration import Iteration
from helpers.outputs import check_expected_outputs
from helpers.utils import check_if_all_same
from model_training.pipeline.select_ckpt import SelectCheckpoint
from model_training.pipeline.train_eval import TrainEval
from model_training.prep.examples_make import MakeExamples
from model_training.prep.examples_re_shuffle import ReShuffleExamples
from model_training.prep.examples_regions import MakeRegions
from model_training.prep.examples_show import ShowExamples
from model_training.prep.examples_shuffle import BeamShuffleExamples
from variant_calling.call import CallVariants
from variant_calling.compare import CompareHappy
from variant_calling.convert import ConvertHappy


@dataclass
class RunTrioTrain:
    """
    Collect data to run an Iteration of the TrioTrain Pipeline.
    """

    # required values
    itr: Iteration
    resource_file: TextIO

    # optional values
    benchmarking_file: Union[WriteFiles, None] = None
    eval_mode: bool = False
    est_examples: float = 1.5
    expected_jobs: int = 0
    max_examples: int = 200000
    next_genome: Union[str, None] = None
    num_tests: int = 1
    overwrite: bool = False
    prior_genome: Union[str, None] = None
    restart_jobs: dict = field(default_factory=dict)
    show_regions_file: Union[str, None] = None
    track_resources: bool = False
    train_mode: bool = True
    use_gpu: bool = False
    use_regions_shuffle: bool = True

    # internal, imutable values
    _jobIDs: list = field(default_factory=list, init=False, repr=False)
    _jobs_found: int = field(default=0, init=False, repr=False)
    _n_regions: Union[int, None] = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        assert (
            self.train_mode != self.eval_mode
        ), f"Either train_mode is on, or eval_mode is on; both can not be on at once"

        if self.train_mode:
            self.genome = self.itr.train_genome
        else:
            self.genome = self.itr.eval_genome

        if self.itr.demo_mode:
            if "chr" in self.itr.demo_chromosome.lower():
                self.logger_msg = f"DEMO] - [TRIO{self.itr.current_trio_num}] - [{self.itr.demo_chromosome}"
            else:
                self.logger_msg = f"DEMO] - [TRIO{self.itr.current_trio_num}] - [CHR{self.itr.demo_chromosome}"
            self._n_regions = 1
            self.model_label = f"Baseline-v{self.itr._version}"
            self.genome_specific_label = self.model_label
        elif self.itr.current_genome_num == 0:
            self.genome = None
            self.logger_msg = "default model"
            self.model_label = f"Baseline-v{self.itr._version}"
            self.genome_specific_label = self.model_label
        elif self.itr.current_trio_num is None:
            self.genome = None
            self.logger_msg = "benchmark"
            self.model_label = f"{self.itr.run_name}"
            self.genome_specific_label = self.model_label
        else:
            self.logger_msg = self.genome
            self.model_label = f"{self.itr.run_name}-{self.itr.train_genome}"
            self.genome_specific_label = f"{self.itr.run_name}-{self.logger_msg}"

        if self.track_resources:
            assert (
                self.benchmarking_file is not None
            ), "unable to proceed, missing a WriteFiles object to save SLURM job IDs"

        with open(str(self.resource_file), mode="r") as file:
            self.resource_dict = load(file)

    def set_job_expectations(self) -> None:
        """
        Defines how many job files are expected
        """
        jobs_per_test_genome = self.num_tests * 3
        # Demo mode requires fewest jobs...
        if self.itr.demo_mode:
            self.expected_jobs = 3

        # However, baseline iteration requires fewer jobs compared to...
        elif self.itr.current_genome_num == 0:
            self.expected_jobs = jobs_per_test_genome

        # ... training genome jobs only
        elif (
            self.itr.train_num_regions is not None and self.itr.eval_num_regions is None
        ):
            self.expected_jobs = (
                3 + (self.itr.train_num_regions * 2) + (jobs_per_test_genome)
            )

        # ... evaluation genome only
        elif self.itr.eval_num_regions is not None:
            self.expected_jobs = 1 + (self.itr.eval_num_regions * 2)

        # ... an entire Iteration
        elif (
            self.itr.train_num_regions is not None
            and self.itr.eval_num_regions is not None
        ):
            train_jobs = 3 + (self.itr.train_num_regions * 2) + (jobs_per_test_genome)
            eval_jobs = 2 + (self.itr.eval_num_regions * 2)
            self.expected_jobs = train_jobs + eval_jobs

        else:
            if self._n_regions is not None:
                main_jobs = 2 + (self._n_regions * 2)
            else:
                main_jobs = 2
            self.expected_jobs = main_jobs

    def convert_jobids(self) -> None:
        """
        Convert any "None" strings, into None types.
        """
        for key, value in self.restart_jobs.items():
            jobids_list = []
            for index, jobid in enumerate(value):
                if jobid == "None":
                    jobid = None
                jobids_list.insert(index, jobid)
            self.restart_jobs[key] = jobids_list

    def process_re_runs(
        self, phase: str, total_jobs_in_phase: int = 1, genome: Union[str, None] = None
    ) -> None:
        """
        Determine if any jobs need to be re-submitted to the queue
        """
        self.re_running_jobs = None
        if genome is None:
            logger_msg = f"[{self.itr._mode_string}] - [{phase}]"
        else:
            logger_msg = f"[{self.itr._mode_string}] - [{phase}] - [{genome}]"

        if not self.restart_jobs:
            return

        self._jobIDs = [None] * total_jobs_in_phase
        if genome is not None and f"{phase}:{genome}" in self.restart_jobs.keys():
            self.itr.logger.info(
                f"{logger_msg}: re-starting jobs were provided for '{phase}:{genome}'"
            )
            inputs = self.restart_jobs[f"{phase}:{genome}"]
        elif phase in self.restart_jobs.keys():
            inputs = self.restart_jobs[phase]
        else:
            inputs = None
        if inputs is not None:
            # check if all elements in inputs are integers
            if all([isinstance(item, int) for item in inputs]):
                # check if all elements in inputs are SLURM job #s vs. region#/indexes
                if all([item <= total_jobs_in_phase for item in inputs]):
                    # handle if the user provides region numbers,
                    if 0 not in inputs:
                        indexes = [x - 1 for x in inputs]
                    # rather than a list of indexes
                    else:
                        indexes = inputs
                else:
                    indexes = inputs
            else:
                indexes = inputs
        else:
            indexes = [None] * total_jobs_in_phase

        for i, index in enumerate(indexes):
            if index is not None:
                if self.overwrite and (
                    isinstance(index, str) or index > total_jobs_in_phase
                ):
                    if total_jobs_in_phase > 1:
                        _num = i + 1
                        if phase in ["make_examples", "beam_shuffle"]:
                            self.itr.logger.info(
                                f"{logger_msg} - [region{_num}]: currently running SLURM job ID | {index}"
                            )
                        if phase in ["call_variants", "compare_happy", "convert_happy"]:
                            self.itr.logger.info(
                                f"{logger_msg} - [test{_num}]: currently running SLURM job ID | {index}"
                            )
                    else:
                        self.itr.logger.info(
                            f"{logger_msg}: currently running SLURM job ID | {index}"
                        )

                    self._jobIDs[i] = index
                else:
                    self._jobIDs[index] = index
            else:
                self._jobIDs[i] = None

        if len(self._jobIDs) != total_jobs_in_phase:
            self.itr.logger.error(
                f"{logger_msg}: incorrect format used for --running-jobids"
            )
            if total_jobs_in_phase == 1:
                self.itr.logger.error(
                    f"{logger_msg}: expected a list with {total_jobs_in_phase} value reprenting [a jobID, an index, or 'None'] but only {len(self._jobIDs)} were provided.\nExiting..."
                )
            else:
                self.itr.logger.error(
                    f"{logger_msg}: expected a list containing {total_jobs_in_phase} values reprenting [jobIDs, indexes, or 'None'] but only {len(self._jobIDs)} were provided.\nExiting..."
                )
            exit(1)
        else:
            skip_rerunning_jobs = check_if_all_same(self._jobIDs, None)
            if skip_rerunning_jobs:
                self.re_running_jobs = False
                return
            else:
                self.re_running_jobs = True
                if len(self._jobIDs) == 1:
                    self.itr.logger.info(
                        f"{logger_msg}: attempting to re-submit the only SLURM job now..."
                    )
                else:
                    self.itr.logger.info(
                        f"{logger_msg}: attempting to re-submit all {total_jobs_in_phase} jobs now..."
                    )

    def count_jobs(self, genome: str = "Child") -> None:
        """
        Count how many jobs exist
        """
        # Loop through all files in the jobs dir,
        # count how many are specific to the current iteration
        job_files = []
        self._jobs_found = 0
        if self.itr.job_dir.is_dir():
            for file in self.itr.job_dir.iterdir():
                if (
                    self.next_genome is not None
                    and self.itr.current_genome_num is not None
                    and self.itr.current_genome_num > 0
                ):
                    if (
                        f"{genome}{self.itr.current_trio_num}" in file.name
                        and f"{self.next_genome}{self.itr.next_trio_num}"
                        not in file.name
                    ):
                        job_files.append(file.name)
                        self._jobs_found += 1
                elif self.prior_genome is not None:
                    if (
                        f"{genome}{self.itr.current_trio_num}" in file.name
                        and self.prior_genome not in file.name
                    ):
                        job_files.append(file.name)
                        self._jobs_found += 1
                elif self.itr.current_genome_num == 0 and ".sh" in str(file.name):
                    job_files.append(file.name)
                    self._jobs_found += 1
        else:
            self._jobs_found = 0

    def check_jobs(self, genome: str = "Child") -> None:
        """
        Confirm existing jobs match expectations.

        If not, trigger the creation of any missing jobs.

            expected job files per genome:
                1) make_examples
                2) beam_shuffle
                3) re_shuffle
                4) train_eval
                5) model_select
                6) call_variants
                7) model_compare
        """
        # Determine if missing all slurm job files
        if self._jobs_found == 0:
            self.itr.logger.info(
                f"[{self.itr._mode_string}] - [check_jobs] - [{genome}]: missing SLURM sbatch jobs"
            )
            missing_job_files = True
        else:
            # Determine if missing some job files
            missing_job_files = check_expected_outputs(
                self._jobs_found,
                self.expected_jobs,
                f"[{self.itr._mode_string}] - [check_jobs] - [{genome}]",
                "SLURM sbatch jobs",
                self.itr.logger,
            )

        if missing_job_files:
            if self.itr.debug_mode and not self.itr.dryrun_mode:
                self.itr.logger.info(
                    f"[{self.itr._mode_string}] - [check_jobs] - [{genome}]: creating + submiting SLURM files with --debug set"
                )
            elif not self.itr.debug_mode and self.itr.dryrun_mode:
                self.itr.logger.info(
                    f"[{self.itr._mode_string}] - [check_jobs] - [{genome}]: creating + submiting SLURM files with --dry-run set"
                )
            elif self.itr.debug_mode and self.itr.dryrun_mode:
                self.itr.logger.info(
                    f"[{self.itr._mode_string}] - [check_jobs] - [{genome}]: creating + submiting SLURM files with --debug and --dry-run set"
                )
            else:
                self.itr.logger.info(
                    f"[{self.itr._mode_string}] - [check_jobs] - [{self.genome}]: creating + submiting SLURM files"
                )

    def data_prep_jobs(self) -> None:
        """
        Make and submit data prep jobs
        """
        for index, use_training_genome in enumerate([True, False]):
            if use_training_genome:
                genome = self.itr.train_genome
            else:
                genome = self.itr.eval_genome

            # --- Create Shuffling Regions for Non-Baseline Runs --- ##
            if (
                self.itr.current_genome_num != 0
                and self.use_regions_shuffle
                and self.itr.demo_mode is False
            ):
                self.itr.logger.info(
                    f"[{self.itr._mode_string}] - [setup]: --use-regions-shuffle is set"
                )
                regions = MakeRegions(
                    self.itr,
                    self.max_examples,
                    self.est_examples,
                    train_mode=use_training_genome,
                )

                # create the default regions_file for testing, if necessary
                regions.write_autosomes_withX_regions(
                    output_file_name=f"{self.itr.args.species.lower()}_autosomes_withX.bed"
                )

                # make the regions_shuffling bed files
                current_itr = regions.run()
                if current_itr is not None:
                    self.itr = current_itr
                else:
                    self.itr.logger.error(
                        f"[{self.itr._mode_string}] - [setup]: expected regions to be created, but they were not"
                    )

            # Update the internal variable
            if self.train_mode:
                self._n_regions = self.itr.train_num_regions
            else:
                self._n_regions = self.itr.eval_num_regions

            # Determine if SBATCH job files need to be made
            self.set_job_expectations()
            if genome is not None:
                self.count_jobs(genome=genome)
                self.check_jobs(genome=genome)

            ### ------ MAKE EXAMPLES ------ ###
            if self.itr.current_genome_num is not None:
                if self.itr.current_genome_dependencies[index] is None:
                    phase_skipped_counter = 0
                    # identify any jobs to be re-run
                    if self._n_regions is not None:
                        self.process_re_runs(
                            "make_examples",
                            total_jobs_in_phase=self._n_regions,
                            genome=genome,
                        )
                    else:
                        self.process_re_runs("make_examples", genome=genome)

                    make_examples = MakeExamples(
                        itr=self.itr,
                        slurm_resources=self.resource_dict,
                        model_label=self.genome_specific_label,
                        total_shards=self.n_shards,
                        train_mode=use_training_genome,
                        track_resources=self.track_resources,
                        benchmarking_file=self.benchmarking_file,
                        overwrite=self.overwrite,
                        make_examples_job_nums=self._jobIDs,
                    )

                    if not self.re_running_jobs and not self.overwrite:
                        make_examples.find_all_outputs()

                        # skip ahead if all outputs exist already
                        if make_examples._outputs_exist:
                            self.itr.logger.info(
                                f"------------ SKIPPING [{self.itr._mode_string}] - [data_prep_jobs] - [{genome}] ------------"
                            )
                            continue

                    # make + submit any make_examples jobs
                    examples_job_nums = make_examples.run()

                    # Determine if any 'make_examples' jobs were submitted
                    if examples_job_nums is None:
                        no_dependencies_required = True
                    else:
                        no_dependencies_required = check_if_all_same(
                            examples_job_nums, None
                        )
                        if no_dependencies_required:
                            phase_skipped_counter += 1

                    ### ------ SHUFFLE EXAMPLES ------ ###
                    if self._n_regions is not None:
                        self.process_re_runs(
                            "beam_shuffle",
                            total_jobs_in_phase=self._n_regions,
                            genome=genome,
                        )
                    else:
                        self.process_re_runs("beam_shuffle", genome=genome)

                    # submit with no dependencies
                    if no_dependencies_required and examples_job_nums is None:
                        shuffle_examples = BeamShuffleExamples(
                            itr=self.itr,
                            slurm_resources=self.resource_dict,
                            model_label=self.genome_specific_label,
                            train_mode=use_training_genome,
                            track_resources=self.track_resources,
                            benchmarking_file=self.benchmarking_file,
                            overwrite=self.overwrite,
                            shuffle_examples_job_nums=self._jobIDs,
                        )
                    else:
                        shuffle_examples = BeamShuffleExamples(
                            itr=self.itr,
                            slurm_resources=self.resource_dict,
                            model_label=self.genome_specific_label,
                            train_mode=use_training_genome,
                            track_resources=self.track_resources,
                            benchmarking_file=self.benchmarking_file,
                            overwrite=self.overwrite,
                            shuffle_examples_job_nums=self._jobIDs,
                            make_examples_jobs=examples_job_nums,
                        )

                    beam_job_nums = shuffle_examples.run()

                    if beam_job_nums is None:
                        no_dependencies_required = True
                    else:
                        no_dependencies_required = check_if_all_same(
                            beam_job_nums, None
                        )
                        if no_dependencies_required:
                            phase_skipped_counter += 1

                    ### ------ RE-SHUFFLE EXAMPLES ------ ###
                    self.process_re_runs(
                        "re_shuffle",
                        total_jobs_in_phase=1,
                        genome=genome,
                    )

                    if self.use_regions_shuffle or self.itr.demo_mode:
                        # submit with no dependencies
                        if no_dependencies_required:
                            re_shuffle = ReShuffleExamples(
                                itr=self.itr,
                                slurm_resources=self.resource_dict,
                                model_label=self.genome_specific_label,
                                overwrite=self.overwrite,
                                train_mode=use_training_genome,
                                track_resources=self.track_resources,
                                re_shuffle_job_num=self._jobIDs,
                                benchmarking_file=self.benchmarking_file,
                            )
                        # submit a list of 'beam_shuffle' job numbers
                        # NOTE: re-shuffling must wait to start start
                        #       after all beam-shuffle jobs complete
                        else:
                            re_shuffle = ReShuffleExamples(
                                itr=self.itr,
                                slurm_resources=self.resource_dict,
                                model_label=self.genome_specific_label,
                                overwrite=self.overwrite,
                                train_mode=use_training_genome,
                                track_resources=self.track_resources,
                                benchmarking_file=self.benchmarking_file,
                                re_shuffle_job_num=self._jobIDs,
                                beam_shuffling_jobs=beam_job_nums,
                            )

                        output = re_shuffle.run()

                        if output is not None:
                            self.itr = output

                        if self.itr.current_genome_dependencies[index] is None:
                            no_dependencies_required = True
                        else:
                            no_dependencies_required = False

                        # Determine if any 're_shuffle_examples' jobs were submitted
                        if no_dependencies_required:
                            phase_skipped_counter += 1

                        if phase_skipped_counter == 3:
                            self.itr.logger.info(
                                f"------------ SKIPPING [{self.itr._mode_string}] - [data_prep_jobs] - [{self.logger_msg}] ------------"
                            )
                    else:
                        if self.itr.demo_mode and self.show_regions_file is not None:
                            if examples_job_nums is None:
                                show_examples = ShowExamples(
                                    itr=self.itr,
                                    slurm_resources=self.resource_dict,
                                    model_label=self.genome_specific_label,
                                    show_regions_file=self.show_regions_file,
                                    train_mode=use_training_genome,
                                ).run()
                            else:
                                show_examples = ShowExamples(
                                    itr=self.itr,
                                    slurm_resources=self.resource_dict,
                                    model_label=self.genome_specific_label,
                                    show_regions_file=self.show_regions_file,
                                    make_examples_jobs=examples_job_nums,
                                    train_mode=use_training_genome,
                                ).run()

                            # Determine if any 'show_examples' jobs were submitted
                            no_dependencies_required = check_if_all_same(
                                show_examples, None
                            )
                            # print(f"NoShowExamplesJobs? {no_dependencies_required}")
                else:
                    self.itr.logger.info(
                        f"[{self.itr._mode_string}] - [data_prep_jobs] - [{self.logger_msg}]: jobs are currently running... SKIPPING AHEAD"
                    )
                    self.itr.logger.info(
                        f"------------ SKIPPING [{self.itr._mode_string}] - [data_prep_jobs] - [{self.logger_msg}] ------------"
                    )
            # -- switch from parent to child -- #
            self.train_mode = False
            self.eval_mode = True
            self.__post_init__()

    def re_training_jobs(self, next_genome: Union[str, None] = None) -> None:
        """
        Make and submit model training jobs
        """
        phase_skipped_counter = 0
        self.process_re_runs("train_eval")

        re_training = TrainEval(
            itr=self.itr,
            slurm_resources=self.resource_dict,
            model_label=self.model_label,
            train_job_num=self._jobIDs,
            track_resources=self.track_resources,
            benchmarking_file=self.benchmarking_file,
            overwrite=self.overwrite,
        )

        if not self.re_running_jobs:
            re_training.find_all_outputs("find_outputs")

            # skip ahead if all outputs exist already
            if re_training._outputs_exist:
                self.itr.logger.info(
                    f"------------ SKIPPING [{self.itr._mode_string}] - [re_training_jobs] - [{self.logger_msg}] ------------"
                )
                return

        train_job_num = re_training.run()

        # Determine if a 'train_eval' job was submitted
        if train_job_num is not None:
            no_dependencies_required = check_if_all_same(train_job_num, None)
        else:
            no_dependencies_required = True

        if no_dependencies_required:
            phase_skipped_counter += 1

        if next_genome is not None:
            self.process_re_runs("select_ckpt")

        select_ckpt = SelectCheckpoint(
            itr=self.itr,
            slurm_resources=self.resource_dict,
            model_label=self.model_label,
            train_eval_job_num=train_job_num,
            select_ckpt_job_num=self._jobIDs,
            track_resources=self.track_resources,
            benchmarking_file=self.benchmarking_file,
            overwrite=self.overwrite,
        )
        self.itr = select_ckpt.run()
        breakpoint()
        # else:
        #     self.itr.logger.info(
        #         f"[{self.itr._mode_string}] - [re_training_jobs] - [{self.logger_msg}]: next checkpoint will not be identified since there is no 'next_genome'"
        #     )

        # Determine if a 'select-ckpt' job was submitted
        no_dependencies_required = check_if_all_same(
            self.itr.next_genome_dependencies, None
        )
        if no_dependencies_required:
            phase_skipped_counter += 1

        if phase_skipped_counter == 2:
            self.itr.logger.info(
                f"------------ SKIPPING [{self.itr._mode_string}] - [re_training_jobs] - [{self.logger_msg}] ------------"
            )

    def test_model_jobs(self, useDT: bool = False) -> None:
        """
        Make and submit model testing jobs
        """
        # create the default regions_file for testing, if necessary

        regions = MakeRegions(
            self.itr,
            [self.max_examples],
            [self.est_examples],
        )

        regions.write_autosomes_withX_regions(
            output_file_name=f"{self.itr.args.species.lower()}_autosomes_withX.bed"
        )

        phase_skipped_counter = 0
        if useDT:
            call_vars_job_nums = None
        else:
            ##--- MAKE + SUBMIT CALL_VARIANTS JOBS ---##
            self.process_re_runs("call_variants", total_jobs_in_phase=self.num_tests)

            test_model = CallVariants(
                itr=self.itr,
                slurm_resources=self.resource_dict,
                model_label=self.model_label,
                use_gpu=self.use_gpu,
                call_variants_job_nums=self._jobIDs,
                track_resources=self.track_resources,
                benchmarking_file=self.benchmarking_file,
                overwrite=self.overwrite,
            )

            if not self.re_running_jobs:
                test_model.find_all_outputs(phase="test_model")

                # skip ahead if all outputs exist already
                if test_model._outputs_exist:
                    self.itr.logger.info(
                        f"------------ SKIPPING [{self.itr._mode_string}] - [test_model] - [{self.logger_msg}] ------------"
                    )
                    return

            call_vars_job_nums = test_model.run()

        # Determine if any 'call_variants' jobs were submitted
        if call_vars_job_nums is None:
            no_dependencies_required = True
        else:
            no_dependencies_required = check_if_all_same(call_vars_job_nums, None)

        if no_dependencies_required:
            phase_skipped_counter += 1

        if self.itr.demo_mode:
            return

        ##--- MAKE + SUBMIT COMPARE_HAPPY JOBS ---##
        self.process_re_runs("compare_happy", total_jobs_in_phase=self.num_tests)

        if no_dependencies_required:
            compare_tests = CompareHappy(
                itr=self.itr,
                slurm_resources=self.resource_dict,
                model_label=self.model_label,
                track_resources=self.track_resources,
                benchmarking_file=self.benchmarking_file,
                compare_happy_job_nums=self._jobIDs,
                overwrite=self.overwrite,
            )
        else:
            compare_tests = CompareHappy(
                itr=self.itr,
                slurm_resources=self.resource_dict,
                model_label=self.model_label,
                call_variants_jobs=call_vars_job_nums,
                track_resources=self.track_resources,
                benchmarking_file=self.benchmarking_file,
                compare_happy_job_nums=self._jobIDs,
                overwrite=self.overwrite,
            )

        compare_job_nums = compare_tests.run()

        # Determine if any 'compare_happy' jobs were submitted
        if compare_job_nums is None:
            no_dependencies_required = True
        else:
            no_dependencies_required = check_if_all_same(compare_job_nums, None)

        if no_dependencies_required:
            phase_skipped_counter += 1

        ##--- MAKE + SUBMIT CONVERT_HAPPY JOBS ---##
        self.process_re_runs("convert_happy", total_jobs_in_phase=self.num_tests)

        if no_dependencies_required:
            convert_results = ConvertHappy(
                itr=self.itr,
                slurm_resources=self.resource_dict,
                model_label=self.model_label,
                track_resources=self.track_resources,
                benchmarking_file=self.benchmarking_file,
                convert_happy_job_nums=self._jobIDs,
                overwrite=self.overwrite,
            )
        else:
            convert_results = ConvertHappy(
                itr=self.itr,
                slurm_resources=self.resource_dict,
                model_label=self.model_label,
                compare_happy_jobs=compare_job_nums,
                track_resources=self.track_resources,
                benchmarking_file=self.benchmarking_file,
                convert_happy_job_nums=self._jobIDs,
                overwrite=self.overwrite,
            )

        convert_job_nums = convert_results.run()

        # Determine if any 'convert_happy' jobs were submitted
        no_dependencies_required = check_if_all_same(convert_job_nums, None)
        if no_dependencies_required:
            phase_skipped_counter += 1

        if phase_skipped_counter == 3:
            self.itr.logger.info(
                f"------------ SKIPPING [{self.itr._mode_string}] - [test_model] - [{self.logger_msg}] ------------"
            )

    def make_and_submit_jobs(
        self,
    ) -> Union[str, None]:
        """
        Generates or displays the SLURM job files for an Iteration of the TrioTrain pipeline.
        """
        n_parts = self.resource_dict["make_examples"]["ntasks"]
        if n_parts is not None:
            self.n_shards = n_parts - 1
        else:
            self.n_shards = 1
            # This must be 1 less than n_parts because shards start at 0!

        if self.itr.demo_mode:
            self.data_prep_jobs()
            self.test_model_jobs()
        elif self.itr.current_trio_num is None:
            self.test_model_jobs()
        elif self.itr.current_genome_num == 0:
            self.test_model_jobs()
        elif self.itr.current_genome_num != 0:
            self.data_prep_jobs()
            self.re_training_jobs(self.next_genome)
            self.test_model_jobs()

    def run(self) -> None:
        """
        Combines all necessary functions to produce SLURM jobs for an Iteration of TrioTrain into one step.
        """
        if self.restart_jobs:
            self.convert_jobids()
        self.make_and_submit_jobs()
