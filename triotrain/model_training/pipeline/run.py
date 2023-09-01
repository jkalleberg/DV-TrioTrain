#!/usr/bin/python
"""
description: combines all potential Iteration options for the TrioTrain pipeline.

usage:
    from pipeline_run import Run
"""
from dataclasses import dataclass, field
from json import load
from sys import exit
from typing import List, TextIO, Union

# Custom helper modules
from helpers.files import WriteFiles
from helpers.iteration import Iteration
from helpers.jobs import is_job_index, is_jobid
from helpers.outputs import check_expected_outputs
from helpers.utils import check_if_all_same, generate_job_id
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
    _phase_jobs: Union[List[str], List[int], None] = field(
        default=None, init=False, repr=False
    )

    def __post_init__(self) -> None:
        assert (
            self.train_mode != self.eval_mode
        ), f"Either train_mode is on, or eval_mode is on; both can not be on at once"

        if self.train_mode:
            self.genome = self.itr.train_genome
        else:
            self.genome = self.itr.eval_genome

        if self.itr.dryrun_mode:
            self.logger_msg = f"[DRY_RUN]"

        if self.itr.demo_mode:
            if "chr" in self.itr.demo_chromosome.lower():
                self.logger_msg = f"DEMO] - [TRIO{self.itr.current_trio_num}] - [{self.itr.demo_chromosome.upper()}"
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
            ), "unable to proceed, missing a WriteFiles object to save SLURM job numbers"

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

    def check_restart(
        self,
        phase: str,
        total_jobs_in_phase: int = 1,
        genome: Union[str, None] = None,
        restart: bool = False,
    ) -> None:
        """
        Determine if any jobs need to be re-submitted to the queue
        """
        self.re_running_jobs = None

        if phase in [
            "train_eval",
            "select_ckpt",
            "call_variants",
            "compare_happy",
            "convert_happy",
        ]:
            self._phase_logger_msg = (
                f"{self.itr._mode_string} - [check_restart] - [{genome}]"
            )
            genome = None
        elif genome is None:
            self._phase_logger_msg = f"{self.itr._mode_string} - [check_restart]"
        else:
            self._phase_logger_msg = (
                f"{self.itr._mode_string} - [check_restart] - [{genome}]"
            )

        if restart:
            self._phase_logger_msg = str(self._phase_logger_msg).replace(
                "check_restart", "check_next_phase"
            )

        if not self.restart_jobs:
            return

        self._jobIDs = [None] * total_jobs_in_phase

        if genome is not None:
            if f"{phase}:{genome}" in self.restart_jobs.keys():
                self.itr.logger.info(
                    f"{self._phase_logger_msg}: found jobs to re-submit for '{phase}:{genome}'"
                )
                self._phase_jobs = self.restart_jobs[f"{phase}:{genome}"]
                self.re_running_jobs = True
            else:
                self._phase_jobs = None
                self.re_running_jobs = False
                self.itr.logger.info(
                    f"{self._phase_logger_msg}: there are no jobs to re-submit for '{phase}:{genome}'...  SKIPPING AHEAD"
                )
        elif phase in self.restart_jobs.keys():
            self.itr.logger.info(
                f"{self._phase_logger_msg}: found jobs to re-submit for '{phase}'"
            )
            self._phase_jobs = self.restart_jobs[phase]
            self.re_running_jobs = True
        else:
            self.itr.logger.info(
                f"{self._phase_logger_msg}: there are no jobs to re-submit for '{phase}'... SKIPPING AHEAD"
            )
            self._phase_jobs = None
            self.re_running_jobs = False

    def process_re_runs(
        self,
        phase: str,
        total_jobs_in_phase: int = 1,
        genome: Union[str, None] = None,
        restart: bool = False,
    ) -> None:
        """
        Determine if any jobs need to be re-submitted to the queue
        """
        self.check_restart(
            phase=phase,
            total_jobs_in_phase=total_jobs_in_phase,
            genome=genome,
            restart=restart,
        )
        if self._phase_jobs:
            # check if all elements in self._phase_jobs are integers
            if all([isinstance(item, int) for item in self._phase_jobs]):
                # check if all elements in self._phase_jobss are not SLURM job ids
                if all([not is_jobid(item) for item in self._phase_jobs]):
                    # handle if the user provides region numbers,
                    if 0 not in self._phase_jobs:
                        indexes = [x - 1 for x in self._phase_jobs]
                    # rather than a list of indexes
                    else:
                        indexes = self._phase_jobs
                else:
                    indexes = self._phase_jobs
            else:
                indexes = self._phase_jobs
        else:
            if restart:
                return
            else:
                indexes = [None] * total_jobs_in_phase

        for i, index in enumerate(indexes):
            if index is None:
                continue
            elif is_jobid(index):
                if total_jobs_in_phase > 1:
                    _num = i + 1
                    if phase in ["make_examples", "beam_shuffle"]:
                        self.itr.logger.info(
                            f"{self._phase_logger_msg} - [region{_num}]: currently running SLURM job number | '{index}'"
                        )
                    if phase in ["call_variants", "compare_happy", "convert_happy"]:
                        self.itr.logger.info(
                            f"{self._phase_logger_msg} - [test{_num}]: currently running SLURM job number | '{index}'"
                        )
                else:
                    self.itr.logger.info(
                        f"{self._phase_logger_msg}: currently running SLURM job number | '{index}'"
                    )

                self._jobIDs[i] = index
            elif is_job_index(index, max_jobs=total_jobs_in_phase):
                self._jobIDs[index] = index
            else:
                self.itr.logger.error(
                    f"{self._phase_logger_msg}: invalid index value provided..."
                )
                if index >= total_jobs_in_phase:
                    self.itr.logger.error(
                        f"{self._phase_logger_msg}: you entered '{index + 1}'..."
                    )
                else:
                    self.itr.logger.error(
                        f"{self._phase_logger_msg}: you entered '{index}'..."
                    )

                if total_jobs_in_phase == 1:
                    self.itr.logger.error(
                        f"{self._phase_logger_msg}: did you mean to enter '0' or '{total_jobs_in_phase}'?"
                    )
                else:
                    self.itr.logger.error(
                        f"{self._phase_logger_msg}: did you mean to enter a number between '0 - {total_jobs_in_phase-1}' or '1 - {total_jobs_in_phase}'?"
                    )
                print("Exiting...")
                exit(1)

        if self._phase_jobs:
            if self._jobIDs and len(self._jobIDs) != total_jobs_in_phase:
                self.itr.logger.error(
                    f"{self._phase_logger_msg}: incorrect format used for --running-jobids"
                )
                if total_jobs_in_phase == 1:
                    self.itr.logger.error(
                        f"{self._phase_logger_msg}: expected a list with {total_jobs_in_phase} value reprenting [a jobID, an index, or 'None'] but only {len(self._jobIDs)} were provided.\nExiting..."
                    )
                else:
                    self.itr.logger.error(
                        f"{self._phase_logger_msg}: expected a list containing {total_jobs_in_phase} values reprenting [jobIDs, indexes, or 'None'] but only {len(self._jobIDs)} were provided.\nExiting..."
                    )
                exit(1)

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
        """
        # Determine if missing all slurm job files
        if self._jobs_found == 0:
            self.itr.logger.info(
                f"{self.itr._mode_string} - [check_jobs] - [{genome}]: missing SLURM sbatch jobs"
            )
        else:
            # Determine if missing some job files
            missing_job_files = check_expected_outputs(
                self._jobs_found,
                self.expected_jobs,
                f"{self.itr._mode_string} - [check_jobs] - [{genome}]",
                "SLURM sbatch jobs",
                self.itr.logger,
            )
            if missing_job_files:
                self.itr.logger.info(
                    f"{self.itr._mode_string} - [check_jobs] - [{genome}]: missing SLURM sbatch jobs"
                )

    def find_next_phase(self) -> None:
        """Determine which phase comes next"""
        if self.current_phase == "make_examples":
            self.next_phase = "beam_shuffle"
        elif self.current_phase == "beam_shuffle":
            self.next_phase = "re_shuffle"
        elif self.current_phase == "re_shuffle":
            self.next_phase = "train_eval"
        elif self.current_phase == "train_eval":
            self.next_phase = "select_ckpt"
        elif self.current_phase == "select_ckpt":
            self.next_phase = "call_variants"
        elif self.current_phase == "call_variants":
            self.next_phase = "compare_happy"
        elif self.current_phase == "compare_happy":
            self.next_phase = "convert_happy"

    def check_next_phase(
        self, total_jobs: int, genome: Union[str, None] = None
    ) -> None:
        self.find_next_phase()
        self.process_re_runs(
            phase=self.next_phase,
            total_jobs_in_phase=total_jobs,
            genome=genome,
            restart=True,
        )

        if genome:
            current_phase_str = f"{self.current_phase}:{genome}"
            if "train_eval" in self.next_phase:
                next_phase_str = self.next_phase
            else:
                next_phase_str = f"{self.next_phase}:{genome}"
        else:
            current_phase_str = self.current_phase
            next_phase_str = self.next_phase

        if self.re_running_jobs and self._phase_jobs is not None:
            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"{self.itr._mode_string} - [check_next_phase]: checking for --restart-jobs errors..."
                )
            n_jobs = len(self._phase_jobs)
            jobs_list = [None for n in range(0, total_jobs)]

            for e, j in enumerate(self._phase_jobs):
                if is_jobid(j):
                    _job_num = e + 1
                elif is_job_index(j, max_jobs=total_jobs):
                    _job_num = (
                        j + 1
                    )  # THIS HAS TO BE +1 to avoid starting with a region0

                if self.current_phase == "make_examples":
                    outputs_found = self.make_examples._outputs_exist

                elif self.current_phase == "beam_shuffle":
                    outputs_found = self.shuffle_examples._outputs_exist

                elif self.current_phase == "re_shuffle":
                    outputs_found = self.re_shuffle._outputs_exist

                elif self.current_phase == "train_eval":
                    outputs_found = self.re_training._outputs_exist

                elif self.current_phase == "select_ckpt":
                    outputs_found = self.select_ckpt._outputs_exist

                elif self.current_phase == "call_variants":
                    outputs_found = self.test_model._outputs_exist

                elif self.current_phase == "compare_happy":
                    outputs_found = self.compare_tests._outputs_exist

                elif self.current_phase == "convert_happy":
                    outputs_found = self.convert_results._outputs_exist

                if outputs_found:
                    continue

                else:
                    jobs_list[j] = generate_job_id()

            if not check_if_all_same(jobs_list, None):
                self.itr.logger.error(
                    f"{self.itr._mode_string} - [check_next_phase]: attempting to re-start '{next_phase_str}' without '{current_phase_str}' outputs"
                )

                self.itr.logger.error(
                    f"{self.itr._mode_string} - [check_next_phase]: either remove the '--restart-jobs' flag, or edit to include '{current_phase_str}'\nValid options include:\n\t1. Running SLURM job numbers\n\t\tNOTE: when including running SLURM job numbers, the list for '{current_phase_str}' MUST have a length={total_jobs}; however, 'None' values can be used to skip any completed jobs.\n\t\tExample: '{{\"{current_phase_str}\": {jobs_list}, \"{next_phase_str}\": {self._phase_jobs}}}'\n\t2. Index value(s) the {n_jobs}-of-{total_jobs} SLURM jobs re-submit to the queue.\n\t\tNOTE: including '0' triggers 0-based indexing, while excluding '0' assumes 1-based indexes were provided.\n\t\tExample: '{{\"{current_phase_str}\": {self._phase_jobs}, \"{next_phase_str}\": {self._phase_jobs}}}')\n\t3. A mix of both SLURM job numbers and index values. "
                )
                exit(1)
    
    def create_default_region(
            self,
            use_train_genome: bool = True) -> None:
        """
        Create a BED file with only autosomes and the X chromosome.
        """
        # --- Create Shuffling Regions for Baseline Runs --- ##
        if self.itr.current_genome_num == 0:
            self.regions = MakeRegions(
                self.itr,
                [self.max_examples],
                [self.est_examples],
            )
        else:
            # --- Create Shuffling Regions for Non-Baseline Runs --- ##
            self.regions = MakeRegions(
                        self.itr,
                        self.max_examples,
                        self.est_examples,
                        train_mode=use_train_genome,
                    )

        # create the default regions_file for testing, if necessary
        if self.itr.default_region_file is None or not self.itr.default_region_file.is_file():
            self.regions.write_autosomes_withX_regions(
                output_file_name=f"{self.itr._reference_genome.stem}_autosomes_withX.bed"
            )

    def data_prep_jobs(self) -> None:
        """
        Make and submit SLURM jobs.
        """
        self._data_prep_phases = ["make_examples", "beam_shuffle", "re_shuffle"]
        for index, use_training_genome in enumerate([True, False]):
            if use_training_genome:
                genome = self.itr.train_genome
            else:
                genome = self.itr.eval_genome

            # skip the child on the second parent for multi-iteration runs only!
            if (self.itr.total_num_iterations > 2 and self.itr.current_genome_num % 2 == 0 and not use_training_genome):
                self.itr.logger.info(
                    f"{self.itr._mode_string} - [data_prep_jobs] - [{genome}]: avoiding duplicate Child jobs... SKIPPING AHEAD"
                )
                return

            if (self.use_regions_shuffle
                and self.itr.demo_mode is False
            ):
                self.itr.logger.info(
                    f"{self.itr._mode_string} - [region_shuffling] - [{genome}]: --use-regions-shuffle is set"
                )
                self.create_default_region(use_train_genome=use_training_genome)
                breakpoint()
                # make the regions_shuffling bed files
                current_itr = self.regions.run()

                if self.current_itr.default_region_file.is_file:
                    self.itr = current_itr
                else:
                    self.itr.logger.error(f"{self._mode_string}: missing default regions file | '{self.default_region_file}'")
                    self.itr.logger.error(
                        f"{self.itr._mode_string} - [region_shuffling] - [{genome}]: expected regions to be created, but they were not\nExiting..."
                    )
                    exit(1)

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
                    self.current_phase = self._data_prep_phases[0]

                    # identify any jobs to be re-run
                    if self._n_regions is not None:
                        self.process_re_runs(
                            self.current_phase,
                            total_jobs_in_phase=self._n_regions,
                            genome=genome,
                        )
                    else:
                        self.process_re_runs(self.current_phase, genome=genome)

                    self.make_examples = MakeExamples(
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

                    self.make_examples.set_genome()
                    self.make_examples.find_all_outputs(phase="find_all_outputs")

                    # skip ahead if all outputs exist already
                    if self.make_examples._outputs_exist and not self.restart_jobs:
                        self.itr.logger.info(
                            f"============ SKIPPING {self.itr._mode_string} - [data_prep_jobs] - [{genome}] ============"
                        )
                        continue

                    if self.restart_jobs and self._phase_jobs is None:
                        self.check_next_phase(total_jobs=self._n_regions, genome=genome)
                    else:
                        self.make_examples.find_outputs(
                            self.current_phase, find_all=True
                        )

                    examples_job_nums = self.make_examples.run()

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
                    self.current_phase = self._data_prep_phases[1]
                    if self._n_regions is not None:
                        self.process_re_runs(
                            self.current_phase,
                            total_jobs_in_phase=self._n_regions,
                            genome=genome,
                        )
                    else:
                        self.process_re_runs(self.current_phase, genome=genome)

                    # submit with no dependencies
                    if no_dependencies_required and examples_job_nums is None:
                        self.shuffle_examples = BeamShuffleExamples(
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
                        self.shuffle_examples = BeamShuffleExamples(
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

                    self.shuffle_examples.set_genome()
                    self.shuffle_examples.find_outputs(
                        phase=self.current_phase, find_all=True
                    )

                    if self.restart_jobs and self._phase_jobs is None:
                        self.check_next_phase(total_jobs=self._n_regions, genome=genome)

                    beam_job_nums = self.shuffle_examples.run()

                    if beam_job_nums is None:
                        no_dependencies_required = True
                    else:
                        no_dependencies_required = check_if_all_same(
                            beam_job_nums, None
                        )

                    if no_dependencies_required:
                        phase_skipped_counter += 1

                    ### ------ RE-SHUFFLE EXAMPLES ------ ###
                    self.current_phase = self._data_prep_phases[2]
                    self.process_re_runs(
                        self.current_phase,
                        total_jobs_in_phase=1,
                        genome=genome,
                    )

                    if self.use_regions_shuffle or self.itr.demo_mode:
                        # submit with no dependencies
                        if no_dependencies_required:
                            self.re_shuffle = ReShuffleExamples(
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
                            self.re_shuffle = ReShuffleExamples(
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

                        self.re_shuffle.set_genome()
                        self.re_shuffle.find_outputs(phase=self.current_phase)

                        if self.restart_jobs and self._phase_jobs is None:
                            self.check_next_phase(total_jobs=1, genome=genome)

                        output = self.re_shuffle.run()

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
                                f"============ SKIPPING {self.itr._mode_string} - [data_prep_jobs] - [{genome}] ============"
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
                else:
                    self.itr.logger.info(
                        f"{self.itr._mode_string} - [data_prep_jobs] - [{genome}]: jobs are currently running... SKIPPING AHEAD"
                    )
                    self.itr.logger.info(
                        f"============ SKIPPING {self.itr._mode_string} - [data_prep_jobs] - [{genome}] ============"
                    )
            # -- switch from parent to child -- #
            self.train_mode = False
            self.eval_mode = True
            self.__post_init__()

    def re_training_jobs(self) -> None:
        """
        Make and submit model training jobs
        """
        self._re_training_phases = ["train_eval", "select_ckpt"]
        phase_skipped_counter = 0
        ### ------ RE-TRAIN + EVAL ------ ###
        self.current_phase = self._re_training_phases[0]
        self.process_re_runs(self.current_phase, genome=self.itr.train_genome)

        self.re_training = TrainEval(
            itr=self.itr,
            slurm_resources=self.resource_dict,
            model_label=self.model_label,
            train_job_num=self._jobIDs,
            track_resources=self.track_resources,
            benchmarking_file=self.benchmarking_file,
            overwrite=self.overwrite,
        )

        self.re_training.find_all_outputs("find_all_outputs", verbose=True)

        # skip ahead if all outputs exist already
        if self.re_training._outputs_exist and not self.restart_jobs:
            self.itr.logger.info(
                f"============ SKIPPING {self.itr._mode_string} - [re_training_jobs] ============"
            )
            return

        elif self.restart_jobs and self._phase_jobs is None:
            self.check_next_phase(total_jobs=1, genome=self.itr.train_genome)
            matches = [
                k
                for k in self.restart_jobs.keys()
                if any(p in k for p in self._data_prep_phases)
            ]
            restart_dataprep = any(matches)

            if restart_dataprep and self.overwrite is False:
                self.itr.logger.warning(
                    f"{self.itr._mode_string} - [re_training_jobs]: option '--restart-jobs' includes data_prep phase(s) | {matches}"
                )
                self.itr.logger.error(
                    f"{self.itr._mode_string} - [re_training_jobs]: however, 'train_eval' is attempting to ignore upstream job(s)"
                )
                self.itr.logger.error(
                    f"{self.itr._mode_string} - [re_training_jobs]: to ensure proper SLURM depenencies for train_eval, either:\n\t1. remove '--restart-jobs' flag, or\n\t2. add the '--overwrite' flag\nExiting..."
                )
                exit(1)

        train_job_num = self.re_training.run()

        # Determine if a 'train_eval' job was submitted
        if train_job_num is not None:
            no_dependencies_required = check_if_all_same(train_job_num, None)
        else:
            no_dependencies_required = True

        if no_dependencies_required:
            phase_skipped_counter += 1

        ### ------ SELECT CKPT ------ ###
        # if next_genome is not None:
        self.current_phase = self._re_training_phases[1]
        self.process_re_runs(self.current_phase, genome=self.itr.train_genome)

        self.select_ckpt = SelectCheckpoint(
            itr=self.itr,
            slurm_resources=self.resource_dict,
            model_label=self.model_label,
            train_eval_job_num=train_job_num,
            select_ckpt_job_num=self._jobIDs,
            track_resources=self.track_resources,
            benchmarking_file=self.benchmarking_file,
            overwrite=self.overwrite,
        )

        self.select_ckpt.find_outputs()

        if self.restart_jobs and self._phase_jobs is None:
            self.check_next_phase(total_jobs=1, genome=self.itr.train_genome)

        self.itr = self.select_ckpt.run()

        # Determine if a 'select-ckpt' job was submitted
        no_dependencies_required = check_if_all_same(
            self.itr.next_genome_dependencies, None
        )
        if no_dependencies_required:
            phase_skipped_counter += 1

        if phase_skipped_counter == 2:
            self.itr.logger.info(
                f"============ SKIPPING {self.itr._mode_string} - [re_training_jobs] - [{self.itr.train_genome}] ============"
            )

    def test_model_jobs(self, useDT: bool = False) -> None:
        """
        Make and submit model testing jobs
        """
        phase_skipped_counter = 0

        self.create_default_region()
        breakpoint()

        if useDT:
            call_vars_job_nums = None
        else:
            ##--- MAKE + SUBMIT CALL_VARIANTS JOBS ---##
            self.current_phase = "call_variants"
            self.process_re_runs(
                self.current_phase,
                total_jobs_in_phase=self.num_tests,
                genome=self.itr.train_genome,
            )

            self.test_model = CallVariants(
                itr=self.itr,
                slurm_resources=self.resource_dict,
                model_label=self.model_label,
                use_gpu=self.use_gpu,
                call_variants_job_nums=self._jobIDs,
                track_resources=self.track_resources,
                benchmarking_file=self.benchmarking_file,
                overwrite=self.overwrite,
            )

            if self.itr.demo_mode:
                self.test_model.find_outputs(find_all=True)
            else:
                self.test_model.find_all_outputs(phase="find_all_outputs")

            if self.test_model._outputs_exist and not self.restart_jobs:
                if self.itr.train_genome is None:
                    self.itr.logger.info(
                        f"============ SKIPPING {self.itr._mode_string} - [test_model] ============"
                    )
                else:
                    self.itr.logger.info(
                        f"============ SKIPPING {self.itr._mode_string} - [test_model] - [{self.itr.train_genome}] ============"
                    )
                return
            # elif self.test_model._outputs_exist is False:
            #     self.test_model.find_outputs(find_all=True)

            if self.restart_jobs and self._phase_jobs is None:
                self.check_next_phase(
                    total_jobs=self.itr.total_num_tests, genome=self.itr.train_genome
                )

            call_vars_job_nums = self.test_model.run()

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
        self.current_phase = "compare_happy"
        self.process_re_runs(
            self.current_phase,
            total_jobs_in_phase=self.num_tests,
            genome=self.itr.train_genome,
        )

        self.compare_tests = CompareHappy(
            itr=self.itr,
            slurm_resources=self.resource_dict,
            model_label=self.model_label,
            call_variants_jobs=call_vars_job_nums,
            track_resources=self.track_resources,
            benchmarking_file=self.benchmarking_file,
            compare_happy_job_nums=self._jobIDs,
            overwrite=self.overwrite,
        )

        self.compare_tests.find_outputs(self.current_phase, find_all=True)

        if self.restart_jobs and self._phase_jobs is None:
            self.check_next_phase(
                total_jobs=self.itr.total_num_tests, genome=self.itr.train_genome
            )

        compare_job_nums = self.compare_tests.run()

        # Determine if any 'compare_happy' jobs were submitted
        if compare_job_nums is None:
            no_dependencies_required = True
        else:
            no_dependencies_required = check_if_all_same(compare_job_nums, None)

        if no_dependencies_required:
            phase_skipped_counter += 1

        ##--- MAKE + SUBMIT CONVERT_HAPPY JOBS ---##
        self.current_phase = "convert_happy"
        self.process_re_runs(
            self.current_phase,
            total_jobs_in_phase=self.num_tests,
            genome=self.itr.train_genome,
        )

        self.convert_results = ConvertHappy(
            itr=self.itr,
            slurm_resources=self.resource_dict,
            model_label=self.model_label,
            compare_happy_jobs=compare_job_nums,
            track_resources=self.track_resources,
            benchmarking_file=self.benchmarking_file,
            convert_happy_job_nums=self._jobIDs,
            overwrite=self.overwrite,
        )
        self.convert_results.find_outputs(self.current_phase, find_all=True)
        self.convert_results.double_check(phase_to_check="process_happy", find_all=True)

        convert_job_nums = self.convert_results.run()

        # Determine if any 'convert_happy' jobs were submitted
        no_dependencies_required = check_if_all_same(convert_job_nums, None)
        if no_dependencies_required:
            phase_skipped_counter += 1

        if phase_skipped_counter == 3:
            if self.itr.train_genome is None:
                self.itr.logger.info(
                    f"============ SKIPPING {self.itr._mode_string} - [test_model] ============"
                )
            else:
                self.itr.logger.info(
                    f"============ SKIPPING {self.itr._mode_string} - [test_model] - [{self.itr.train_genome}] ============"
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
            self.re_training_jobs()
            self.test_model_jobs()

    def run(self) -> None:
        """
        Combines all necessary functions to produce SLURM jobs for an Iteration of TrioTrain into one step.
        """
        if self.restart_jobs:
            self.convert_jobids()
        self.make_and_submit_jobs()
