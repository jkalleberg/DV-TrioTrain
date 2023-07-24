#!/usr/bin/python3
"""
description: contains all of the functions specific to call_variants phase of TrioTrain.

usage:
    from call import CallVariants
"""
import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from sys import exit
from typing import List, Union

from helpers.files import WriteFiles
from helpers.iteration import Iteration
from helpers.jobs import is_job_index, is_jobid
from helpers.outputs import check_expected_outputs, check_if_output_exists
from helpers.utils import (
    check_if_all_same,
    create_deps,
    find_NaN,
    find_not_NaN,
    generate_job_id,
)
from model_training.slurm.sbatch import SBATCH, SubmitSBATCH
from regex import compile
from variant_calling.compare import CompareHappy
from variant_calling.convert import ConvertHappy


@dataclass
class CallVariants:
    """
    Define what data to store for the call_variants phase of the TrioTrain Pipeline.
    """

    # required values
    itr: Iteration
    slurm_resources: dict
    model_label: str

    # optional values
    benchmarking_file: Union[WriteFiles, None] = None
    call_variants_job_nums: List = field(default_factory=list)
    overwrite: bool = False
    track_resources: bool = False
    use_gpu: bool = False

    # internal, imutable values
    _compare_dependencies: Union[List[Union[str, None]], None] = field(
        default_factory=list, repr=False, init=False
    )
    _phase: str = field(default="call_variants", init=False, repr=False)
    _skipped_counter: int = field(default=0, init=False, repr=False)
    _skip_phase: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        self.n_parts = self.slurm_resources[self._phase]["ntasks"]
        if self.track_resources:
            assert (
                self.benchmarking_file is not None
            ), "missing a WriteFiles() object to save SLURM job numbers"

        if self.itr.current_genome_dependencies[3] is None:
            self._select_ckpt_job = []
        else:
            self._select_ckpt_job = [self.itr.current_genome_dependencies[3]]
        self._compare_dependencies = create_deps(num=self.itr.total_num_tests)
        
        if self.itr.train_genome is None:
            self.logger_msg = f"{self.itr._mode_string} - [{self._phase}]"
        else:
            self.logger_msg = (
                f"{self.itr._mode_string} - [{self._phase}] - [{self.itr.train_genome}]"
            )

    def set_genome(self) -> None:
        """
        Assign a genome label.
        """
        if self.itr.env is not None:
            if "baseline" in self.model_label or self.itr.current_genome_num == 0:
                self.genome = None
                self.outdir = str(self.itr.env.contents["BaselineModelResultsDir"])
            elif self.itr.current_trio_num is None:
                self.genome = None
                self.outdir = str(self.itr.env.contents["RunDir"])
            else:
                self.genome = self.itr.train_genome
                self.outdir = str(self.itr.env.contents[f"{self.genome}TestDir"])

    def set_container(self) -> None:
        """
        Determine which Apptainer container to use.

        NOTE: Much match the hardware requested via SLURM.
        """
        if self.use_gpu:
            self.container = f"deepvariant_{self.itr._version}-gpu.sif"
            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"{self.logger_msg}: using the GPU container | '{self.container}'"
                )
        else:
            self.container = f"deepvariant_{self.itr._version}.sif"
            if self.itr.debug_mode:
                self.itr.logger.info(
                    f"{self.logger_msg}: using the CPU container | '{self.container}'"
                )

    def find_restart_jobs(self) -> None:
        """
        Collect any SLURM job ids for running tests to avoid submitting a job while it's already running.
        """
        self._ignoring_select_ckpt = check_if_all_same(self._select_ckpt_job, None)
        self._ignoring_restart_jobs = check_if_all_same(
            self.call_variants_job_nums, None
        )

        if not self._ignoring_select_ckpt:
            select_ckpt_run = find_not_NaN(self._select_ckpt_job)
            if select_ckpt_run:
                self._jobs_to_run = list(range(0, self.itr.total_num_tests))
            else:
                self._jobs_to_run = select_ckpt_run
            self._num_to_ignore = len(find_NaN(self._select_ckpt_job))
            self._num_to_run = len(self._jobs_to_run)

        elif not self._ignoring_restart_jobs:
            self._jobs_to_run = find_not_NaN(self.call_variants_job_nums)
            self._num_to_run = len(self._jobs_to_run)
            self._num_to_ignore = len(find_NaN(self.call_variants_job_nums))

        else:
            self._num_to_run = 0
            self._num_to_ignore = self.itr.total_num_tests
            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"{self.logger_msg}: running job ids were NOT provided"
                )

        if 0 < self._num_to_run <= self.itr.total_num_tests:
            if self._jobs_to_run and not self._ignoring_restart_jobs:
                updated_jobs_list = []

                for index in self._jobs_to_run:
                    if is_jobid(self.call_variants_job_nums[index]):
                        self._num_to_run -= 1
                        self._num_to_ignore += 1
                        self._skipped_counter += 1
                        self._compare_dependencies[index] = str(
                            self.call_variants_job_nums[index]
                        )
                    elif is_job_index(
                        self.call_variants_job_nums[index],
                        max_jobs=self.itr.total_num_tests,
                    ):
                        updated_jobs_list.append(index)

                if updated_jobs_list:
                    self._jobs_to_run = updated_jobs_list

        if self._num_to_ignore == 0:
            return
        elif 0 < self._num_to_ignore < self.itr.total_num_tests:
            self.itr.logger.info(
                f"{self.logger_msg}: ignoring {self._num_to_ignore}-of-{self.itr.total_num_tests} SLURM jobs"
            )
        
        elif self._num_to_ignore == self.itr.total_num_tests:
            if self.call_variants_job_nums:
                self.itr.logger.info(
                    f"{self.logger_msg}: completed '{self._phase}'... SKIPPING AHEAD"
                )
        else:
            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"{self.logger_msg}: --running-jobids triggered reprocessing {self._num_to_run} jobs"
                )

            self.itr.logger.error(
                f"{self.logger_msg}: incorrect format for 'call_variants_job_nums'"
            )
            self.itr.logger.error(
                f"{self.logger_msg}: expected a list of {self.itr.total_num_tests} SLURM jobs (or 'None' as a place holder)"
            )

    def load_variables(self) -> None:
        """
        Load in variables from the env file, and define python variables.
        """
        if self.itr.current_genome_num == 0:
            self.itr.logger.warning(
                f"{self.logger_msg}: using the default model checkpoint"
            )
        else:
            self.itr.logger.info(
                f"{self.logger_msg}: using a custom model checkpoint",
            )
            
        if self.itr.env is not None:
            if "N_Parts" not in self.itr.env.contents:
                self.itr.env.add_to(
                    key="N_Parts",
                    value=str(self.n_parts),
                    dryrun_mode=self.itr.dryrun_mode,
                    msg=self.logger_msg,
                )
            else:
                self.n_parts = self.itr.env.contents["N_Parts"]

            env_vars = [
                "RunOrder",
                "CodePath",
                "RefFASTA_Path",
                "RefFASTA_File",
            ]

            if self.genome is None or self.itr.current_genome_num == 0:
                if "BaselineTestCkptName" in self.itr.env.contents:
                    extra_vars = ["BaselineModelResultsDir"]
                    self.test_ckpt_path = str(
                        self.itr.env.contents["BaselineTestCkptPath"]
                    )
                    self.test_ckpt_name = str(
                        self.itr.env.contents["BaselineTestCkptName"]
                    )
                    ckpt_used = (
                        Path(self.test_ckpt_path)
                        / f"{self.test_ckpt_name}.data-00000-of-00001"
                    )
                    assert (
                        ckpt_used.exists()
                    ), f"Non-existant test checkpoint provided [{str(ckpt_used)}]"
                elif "TestCkptName" in self.itr.env.contents:
                    extra_vars = ["RunDir"]
                    self.test_ckpt_path = str(self.itr.env.contents["TestCkptPath"])
                    self.test_ckpt_name = str(self.itr.env.contents["TestCkptName"])
                    ckpt_used = (
                        Path(self.test_ckpt_path)
                        / f"{self.test_ckpt_name}.data-00000-of-00001"
                    )
                    assert (
                        ckpt_used.exists()
                    ), f"Non-existant test checkpoint provided [{str(ckpt_used)}]"

                else:
                    # default ckpt will be used
                    extra_vars = ["BaselineModelResultsDir"]
                    self.test_ckpt_path = None
                    self.test_ckpt_name = None
            else:
                extra_vars = [f"{self.genome}TestDir"]
                if self.itr.demo_mode:
                    # a default ckpt will be used
                    self.test_ckpt_path = str(
                        self.itr.env.contents[f"{self.itr.train_genome}StartCkptPath"]
                    )
                    self.test_ckpt_name = str(
                        self.itr.env.contents[f"{self.itr.train_genome}StartCkptName"]
                    )
                else:
                    # define custom model ckpt
                    self.test_ckpt_path = str(
                        self.itr.env.contents[f"{self.itr.train_genome}TestCkptPath"]
                    )
                    if f"{self.itr.train_genome}TestCkptName" in self.itr.env.contents:
                        self.test_ckpt_name = str(
                            self.itr.env.contents[
                                f"{self.itr.train_genome}TestCkptName"
                            ]
                        )
                        ckpt_used = (
                            Path(self.test_ckpt_path)
                            / f"{self.test_ckpt_name}.data-00000-of-00001"
                        )
                        assert (
                            ckpt_used.exists()
                        ), f"Non-existant test checkpoint provided [{str(ckpt_used)}]"
                    else:
                        self.test_ckpt_name = (
                            f"${{{self.itr.train_genome}TestCkptName}}"
                        )

            vars = env_vars + extra_vars

            try:
                (
                    self._trio_num,
                    self._code_path,
                    self._ref_dir,
                    self._ref_file,
                    self._output_dir,
                ) = self.itr.env.load(*vars)
            except KeyError:
                self.itr.logger.info(
                    f"{self.logger_msg}: env is missing variables for Test{self.test_num}... SKIPPING AHEAD"
                )
                return

            self.reference_genome = Path(self._ref_dir) / self._ref_file
            assert (
                self.reference_genome.exists()
            ), "Non-existant Reference Genome FASTA file provided"

            if (
                "PopVCF_Path" in self.itr.env.contents
                and "PopVCF_File" in self.itr.env.contents
            ):
                self.pop_path = str(self.itr.env.contents[f"PopVCF_Path"])
                self.pop_file = str(self.itr.env.contents[f"PopVCF_File"])
                self.pop_vcf = Path(self.pop_path) / self.pop_file
                assert (
                    self.pop_vcf.exists()
                ), "missing the population VCF file"
                self.use_pop = True
                self.itr.logger.info(
                    f"{self.logger_msg}: using both [8: 'allele_frequency', 19: 'insert_size'] channels in test genome examples"
                )
            elif "PopVCF" in self.itr.env.contents:
                self.use_pop = False
                self.itr.logger.info(
                    f"{self.logger_msg}: using default [19: 'insert_size'] channel in test genome examples"
                )
            else:
                self.use_pop = False

    def set_test_genome(self, current_test_num: Union[int, None] = None) -> None:
        """
        Loads in input files, if a valid test number is provided.
        """
        if (
            self.itr.env is not None
            and self.itr.total_num_tests is not None
            and current_test_num is not None
        ):
            self.test_num = current_test_num

            if self.itr.demo_mode:
                if "chr" in self.itr.demo_chromosome.lower():
                    self.prefix = f"test{self.test_num}_{self.itr.demo_chromosome}"
                    self.job_name = f"test{self.test_num}_{self.itr.demo_chromosome}"
                else:
                    self.prefix = f"test{self.test_num}_chr{self.itr.demo_chromosome}"
                    self.job_name = f"test{self.test_num}_chr{self.itr.demo_chromosome}"
            elif "baseline" in self.model_label or self.itr.current_genome_num == 0:
                self.prefix = f"test{self.test_num}"
                self.job_name = f"test{self.test_num}"
            elif self.itr.current_trio_num is None:
                self.prefix = f"test{self.test_num}"
                self.job_name = f"test{self.test_num}"
            else:
                self.prefix = f"test{self.test_num}-{self.genome}"
                self.job_name = (
                    f"test{self.test_num}-{self.genome}{self.itr.current_trio_num}"
                )
            self.test_logger_msg = f"{self.logger_msg} - [test{self.test_num}]"

            if f"Test{self.test_num}ReadsBAM" in self.itr.env.contents:
                self.test_genome = None
            else:
                self._bam_dir = str(
                    self.itr.env.contents[f"Test{self.test_num}ReadsBAM_Path"]
                )
                self._bam_file = str(
                    self.itr.env.contents[f"Test{self.test_num}ReadsBAM_File"]
                )
                self.test_genome = Path(self._bam_dir) / self._bam_file
                assert (
                    self.test_genome.exists()
                ), f"missing a required BAM file | '{str(self.test_genome)}'"
        else:
            self.itr.logger.error(
                f"{self.logger_msg}: expected a numerical value for total_num_tests and/or current_test_num",
            )
            self.itr.logger.warning(
                f"{self.logger_msg}: fatal error encountered, unable to proceed further with pipeline.\nExiting... ",
            )
            exit(1)

    def benchmark(self) -> None:
        """
        Saves the SLURM job numbers to a file for future resource usage metrics.
        """
        headers = ["AnalysisName", "RunName", "Parent", "Phase", "JobList"]
        if self._compare_dependencies is None:
            deps_string = "None"
        else:
            deps_string = ",".join(filter(None, self._compare_dependencies))
        data = {
            "AnalysisName": self.model_label,
            "RunName": self.itr.run_name,
            "Phase": self._phase,
            "Parent": self.itr.train_genome,
            "JobList": deps_string,
        }

        if not self.itr.dryrun_mode and self.benchmarking_file is not None:
            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"{self.logger_msg}: writing SLURM job numbers to [{self.benchmarking_file.file}]",
                )
            self.benchmarking_file.add_rows(headers, data_dict=data)
        else:
            self.itr.logger.info(f"{self.logger_msg}: benchmarking is active")

    def build_apptainer_command(self, normalize_reads: bool = False) -> None:
        """
        Create the command line string to execute Apptainer.
        """
        bindings = [
            "/usr/lib/locale/:/usr/lib/locale/",
            f"{self._code_path}/:/run_dir/",
            f"{self._ref_dir}/:/ref_dir/",
            f"{self._bam_dir}/:/bam_dir/",
            f"{self._output_dir}/:/out_dir/",
        ]

        # define which regions to include when calling variants
        # under demo mode...
        if self.itr.demo_mode:
            regions_flag = f'--regions="{self.itr.demo_chromosome}"'

        # and when testing a new model....
        # NOTE: this should be the autosomes + X chromosome only!
        #       in the default regions file created by the pipeline
        elif (
            self.itr.default_region_file is not None
            and self.itr.default_region_file.exists()
        ):
            bindings.append(f"{self.itr.default_region_file.parent}/:/region_dir/")
            regions_flag = (
                f'--regions="/region_dir/{self.itr.default_region_file.name}"'
            )
        else:
            regions_flag = None

        # set the custom testing ckpt to be used
        self.model_used = f"{self.test_ckpt_name}"
        bindings.append(f"{self.test_ckpt_path}/:/start_dir/")
        starting_point_flag = f'--customized_model="/start_dir/{self.test_ckpt_name}"'

        # determine if non-baseline tests should include the 'allele_frequency' channel
        if self.use_pop:
            bindings.append(f"{self.pop_path}/:/popVCF_dir/")
            pop_flag = (
                f"use_allele_frequency=true,population_vcfs=/popVCF_dir/{self.pop_file}"
            )
        else:
            pop_flag = None

        if normalize_reads:
            normalize_reads_flag = "normalize_reads=true"
            if pop_flag is not None:
                extra_args = (
                    f'--make_examples_extra_args="{normalize_reads_flag},{pop_flag}"'
                )
            else:
                extra_args = f'--make_examples_extra_args="{normalize_reads_flag}"'
        else:
            extra_args = f'--make_examples_extra_args="{pop_flag}"'

        bindings_string = ",".join(bindings)
        apptainer_string = "time apptainer run"
        gpu_string = f"srun -l --gres=gpu:1 {apptainer_string} --nv"

        self.apptainer_cmd_string = f'-B {bindings_string} {self.container} /opt/deepvariant/bin/run_deepvariant --model_type=WGS --ref="/ref_dir/{self._ref_file}" --reads="/bam_dir/{self._bam_file}" --output_vcf="/out_dir/{self.prefix}.vcf.gz" --intermediate_results_dir="/out_dir/tmp/{self.prefix}/" --num_shards={self.n_parts}'

        if self.use_gpu:
            self.apptainer_cmd_string = f"{gpu_string} {self.apptainer_cmd_string}"
        else:
            self.apptainer_cmd_string = (
                f"{apptainer_string} {self.apptainer_cmd_string}"
            )

        if regions_flag is not None:
            self.apptainer_cmd_string = f"{self.apptainer_cmd_string} {regions_flag}"

        if starting_point_flag is not None:
            self.apptainer_cmd_string = (
                f"{self.apptainer_cmd_string} {starting_point_flag}"
            )

        if extra_args is not None:
            self.apptainer_cmd_string = f"{self.apptainer_cmd_string} {extra_args}"

        apptainer_cmd_list = self.apptainer_cmd_string.split(" ")
        if self.itr.debug_mode and not self.itr.dryrun_mode:
            self.itr.logger.debug(f"{self.logger_msg}: commands for Apptainer include:")
            print("-------------------------------------")
            for cmd in apptainer_cmd_list:
                print(cmd)
            print("-------------------------------------")

    def make_job(self, index: int = 0) -> Union[SBATCH, None]:
        """
        Defines the contents of the SLURM job for the call_variant phase for TrioTrain Pipeline.
        """
        self.build_apptainer_command()

        # initialize a SBATCH Object
        self.handler_label = f"{self._phase}: {self.prefix}"

        slurm_job = SBATCH(
            self.itr,
            self.job_name,
            self.model_label,
            self.handler_label,
            self.test_logger_msg,
        )
        if slurm_job.check_sbatch_file():
            prior_job = self._select_ckpt_job[0] is not None

            if index < len(self.call_variants_job_nums):
                resub_jobs = self.call_variants_job_nums[index] is not None
            else:
                resub_jobs = False

            if (prior_job or resub_jobs) and self.overwrite:
                self.itr.logger.info(
                    f"{self.test_logger_msg}: --overwrite=True; re-writing the existing SLURM job now... "
                )
            else:
                self.itr.logger.info(
                    f"{self.test_logger_msg}: --overwrite=False; SLURM job file already exists... SKIPPING AHEAD"
                )
                return
        else:
            if self.itr.debug_mode:
                self.itr.logger.debug(
                    f"{self.test_logger_msg}: creating job file now... "
                )

        if self.itr.current_trio_num == 0:
            self.command_list = [
                f'echo "INFO: testing {self.itr.model_label} | {self.model_used}] with test genome #{self.test_num}:"',
                self.apptainer_cmd_string,
            ]
        else:
            self.command_list = [
                f'echo "INFO: testing custom model [TRIO-{self.itr.train_genome}{self._trio_num} | {self.model_used}] with test genome #{self.test_num}:"',
                self.apptainer_cmd_string,
            ]
        slurm_job.create_slurm_job(
            self.handler_label,
            command_list=self.command_list,
            overwrite=self.overwrite,
            **self.slurm_resources[self._phase],
        )

        return slurm_job

    def find_outputs(
        self,
        phase: Union[str, None] = None,
        find_all: bool = False,
        number_outputs_per_test=2,
    ) -> Union[bool, None]:
        """
        Determines if call_variants phase has completed successfully.
        """
        self.set_genome()
        if phase is None:
            logging_msg = self.logger_msg
        else:
            if self.itr.train_genome is None:
                logging_msg = f"{self.itr._mode_string} - [{phase}]"
            else:
                logging_msg = (
                    f"{self.itr._mode_string} - [{phase}] - [{self.itr.train_genome}]"
                )

        if find_all:
            msg = "all the DeepVariant VCF outputs"
            if self.itr.total_num_tests is not None:
                expected_outputs = int(
                    self.itr.total_num_tests * number_outputs_per_test
                )
            else:
                expected_outputs = number_outputs_per_test

            vcf_pattern = r"test.*(\.tbi$|\.gz$)"
        else:
            msg = "DeepVariant VCF output"
            expected_outputs = number_outputs_per_test
            logging_msg = logging_msg + f" - [test{self.test_num}]"
            vcf_output_regex = fnmatch.translate(f"{self.prefix}.vcf.gz*")
            vcf_pattern = compile(vcf_output_regex)

        if self.itr.args.debug:
            self.itr.logger.debug(
                f"{logging_msg}: regular expression used | {vcf_output_regex}"
            )

        # Confirm Genome's output VCF does not already exist
        (
            self.existing_output_vcf,
            self.num_vcfs_found,
            files,
        ) = check_if_output_exists(
            vcf_pattern,
            msg,
            Path(self.outdir),
            logging_msg,
            self.itr.logger,
            debug_mode=self.itr.debug_mode,
            dryrun_mode=self.itr.dryrun_mode,
        )

        if self.existing_output_vcf:
            missing_files = check_expected_outputs(
                self.num_vcfs_found,
                expected_outputs,
                logging_msg,
                "DeepVariant outputs",
                self.itr.logger,
            )
            if missing_files:
                self._outputs_exist = False
            else:
                self._outputs_exist = True
        else:
            self._outputs_exist = False

    def find_all_outputs(self, phase: str = "find_outputs") -> Union[bool, None]:
        """
        Determine if 'TestModel' outputs already exist.
        """
        convert_results = ConvertHappy(
            itr=self.itr,
            slurm_resources=self.slurm_resources,
            model_label=self.model_label,
            track_resources=self.track_resources,
            benchmarking_file=self.benchmarking_file,
            overwrite=self.overwrite,
        )

        convert_results.find_outputs(phase=phase, find_all=True)

        if convert_results._outputs_exist:
            compare_results = CompareHappy(
                itr=self.itr,
                slurm_resources=self.slurm_resources,
                model_label=self.model_label,
                track_resources=self.track_resources,
                benchmarking_file=self.benchmarking_file,
                overwrite=self.overwrite,
            )
            compare_results.find_outputs(phase=phase, find_all=True)

            if compare_results._outputs_exist:
                self.find_outputs(phase=phase, find_all=True)
            else:
                self._outputs_exist = False
        else:
            self._outputs_exist = False

    def submit_job(self, msg: str = "sub", dependency_index: int = 0, total_jobs: int = 1, resubmission: bool = False) -> None:
        """
        Submits a SLURM job to the queue.
        """
        if (self._outputs_exist and self.overwrite is False) or (
            self._outputs_exist and self._ignoring_restart_jobs and self.overwrite is False
        ):
            self._skipped_counter += 1
            self._compare_dependencies[dependency_index] = None
            if resubmission:
                self.itr.logger.info(
                    f"{self.test_logger_msg}: --overwrite=False; skipping job because found DeepVariant VCF file"
                )
        
        slurm_job = self.make_job(index=dependency_index)
        
        if slurm_job is not None:
            if self.itr.dryrun_mode:
                slurm_job.display_job()
            else:
                slurm_job.write_job()

        if not self.overwrite and self._ignoring_select_ckpt and resubmission:
            self.itr.logger.info(
                f"{self.test_logger_msg}: --overwrite=False; {msg}mitting job because missing DeepVariant VCF file"
                )
        
        elif self.overwrite and self._outputs_exist:
            self.itr.logger.info(
                f"{self.test_logger_msg}: --overwrite=True; {msg}mitting job because replacing existing DeepVariant VCF file"
            )
            
        else:
            self.itr.logger.info(
                f"{self.test_logger_msg}: {msg}mitting job to call variants with DeepVariant"
            )
 
        slurm_job = SubmitSBATCH(
            self.itr.job_dir,
            f"{self.job_name}.sh",
            self.handler_label,
            self.itr.logger,
            self.test_logger_msg,
        )
        
        # if there is a running select-ckpt job...
        if self.itr.current_genome_dependencies[3] is not None:
            # include it as a dependency
            slurm_job.build_command(self.itr.current_genome_dependencies[3])
        else: 
            slurm_job.build_command(None)

        if self.itr.demo_mode:
            slurm_job.display_command(
                display_mode=self.itr.dryrun_mode,
            )
        else:
            slurm_job.display_command(
                current_job=self.job_num,
                total_jobs=total_jobs,
                display_mode=self.itr.dryrun_mode,
                debug_mode=self.itr.debug_mode,
            )
        
        if self.itr.dryrun_mode:
            self._compare_dependencies[dependency_index] = generate_job_id()
        else:
            if self.itr.demo_mode:
                slurm_job.get_status(
                    total_jobs=total_jobs, debug_mode=self.itr.debug_mode
                )
            else:
                slurm_job.get_status(
                    current_job=self.job_num,
                    total_jobs=total_jobs,
                    debug_mode=self.itr.debug_mode,
                )

            if slurm_job.status == 0:
                if self._compare_dependencies:
                    self._compare_dependencies[dependency_index] = slurm_job.job_number
            else:
                self.itr.logger.warning(
                    f"{self.test_logger_msg}: unable to {msg}mit SLURM job",
                )
                self._compare_dependencies[dependency_index] = None

    def check_submissions(self) -> None:
        """
        Checks if the SLURM job file was submitted to the SLURM queue successfully.
        """
        if self.itr.debug_mode:
            self.itr.total_num_tests = 2

        call_vars_results = check_if_all_same(self._compare_dependencies, None)

        if call_vars_results is False:
            if self._compare_dependencies and len(self._compare_dependencies) == 1:
                print(
                    f"============ {self.logger_msg} Job Number - {self._compare_dependencies} ============"
                )
            else:
                print(
                    f"============ {self.logger_msg} Job Numbers ============\n{self._compare_dependencies}\n============================================================"
                )
            
            if self.track_resources and self.benchmarking_file is not None:
                self.benchmark()
        
        elif self._skipped_counter != 0:
            if self._skipped_counter == self.itr.total_num_tests:
                self._compare_dependencies = None
        else:
            self.itr.logger.error(
                f"{self.logger_msg}: expected SLURM jobs to be submitted, but they were not",
            )
            self._compare_dependencies = None
            self.itr.logger.warning(
                f"[{self.logger_msg}: fatal error encountered, unable to proceed further with pipeline.\nExiting... ",
            )
            exit(1)

    def run(self) -> Union[List[Union[str, None]], None]:
        """
        Combine all the steps for testing a DV model into one step.
        """
        self.set_genome()
        self.set_container()
        self.find_restart_jobs()

        skip_re_runs = check_if_all_same(self.call_variants_job_nums, None)

        if skip_re_runs and self._outputs_exist is False:
            msg = "sub"
        else:
            msg = "re-sub"

        # Determine if we are re-running some of the test genomes with call variants
        if not self._ignoring_restart_jobs or not self._ignoring_select_ckpt:
            if self._num_to_run == 0:
                self._skipped_counter = self._num_to_ignore
                if (
                    self._compare_dependencies
                    and check_if_all_same(self._compare_dependencies, None) is False
                ):
                    self.itr.logger.info(
                        f"{self.logger_msg}: compare_happy dependencies updated | '{self._compare_dependencies}'"
                    )
                else:
                    self._compare_dependencies = None
            else:
                if not self._ignoring_select_ckpt:
                    self.itr.logger.info(
                        f"{self.logger_msg}: select_ckpt job was submitted...",
                    )

                if self._num_to_run <= self.itr.total_num_tests:
                    self.itr.logger.info(
                            f"{self.logger_msg}: attempting to {msg}mit {self._num_to_run}-of-{self.itr.total_num_tests} SLURM jobs to the queue",
                        )
                else:
                    self.itr.logger.error(
                        f"{self.logger_msg}: max number of {msg}mission SLURM jobs is {self._total_regions} but {self._num_to_run} were provided.\nExiting... ",
                        )
                    exit(1)

                self.load_variables()

                for r in self._jobs_to_run:
                    if skip_re_runs:
                        test_index = r
                    else:
                        test_index = self.call_variants_job_nums[r]

                    self.job_num = (
                        test_index + 1
                    )  # THIS HAS TO BE +1 to avoid starting with a region0

                    self.set_test_genome(current_test_num=self.job_num)
                    if self.test_genome is None:
                        continue
                    else:
                        self.submit_job(
                            msg=msg,
                            dependency_index=test_index,
                            total_jobs=self.itr.total_num_tests,
                            resubmission=True,
                        )  # THIS (^) HAS TO BE test_index to ensure the dependencies maintain appropriate order

        # Determine if we are submitting all tests
        else:
            if self._outputs_exist:
                return self._compare_dependencies
            
            self.load_variables()

            for t in range(0, int(self.itr.total_num_tests)):
                # THIS HAS TO BE +1 to avoid starting with a test0
                self.job_num = t + 1
                self.set_test_genome(current_test_num=self.job_num)

                if self.test_genome is None:
                    continue
                else:
                    self.find_outputs()
                    self.submit_job(
                        msg=msg,
                        dependency_index=t, total_jobs=self.itr.total_num_tests
                    )

        self.check_submissions()
        return self._compare_dependencies
