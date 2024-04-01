# from model_training.slurm.sbatch import SBATCH, SubmitSBATCH
# from helpers.iteration import Iteration

# from helpers.utils import generate_job_id, check_if_all_same

# _job_nums: List = field(default_factory=list, repr=False, init=False)
# _num_processed: int = field(default=0, init=False, repr=False)
# _num_skipped: int = field(default=0, init=False, repr=False)
# _num_submitted: int = field(default=0, init=False, repr=False)

# def __post_init__(self) -> None:
#     with open(str(self.args.resource_config), mode="r") as file:
#         self._slurm_resources = load(file)

# parser.add_argument(
#     "-r",
#     "--resources",
#     dest="resource_config",
#     help="[REQUIRED]\ninput file (.json)\ndefines HPC cluster resources for SLURM",
#     type=str,
#     metavar="</path/file>",
# )

# assert (
#     args.resource_config
# ), "Missing --resources; Please designate a path to pipeline compute resources in JSON format"


#     def make_job(self) -> Union[SBATCH, None]:
#         """
#         Define the contents of the SLURM job for the rtg-mendelian phase for TrioTrain Pipeline.
#         """
#         # initialize a SBATCH Object
#         vcf_name = Path(self._clean_filename).name
#         if self._sampleID not in vcf_name:
#             self.logger.warning(f"{self._logger_msg}: discrepancy between sampleID '{self._sampleID}' and file name '{vcf_name}'")
#             # if "-" in vcf_name:
#             #     self.logger.info(f"{self._logger_msg}: job name will use vcf_name | '{vcf_name}'")
#             #     self.job_name = f"stats.{vcf_name}.{self._caller}"
#             # else:
#             self.logger.info(f"{self._logger_msg}: job name will use sampleID | '{self._sampleID}'")
#             self.job_name = f"stats.{self._sampleID}.{self._caller}"
#         else:
#             self.job_name = f"stats.{vcf_name}.{self._caller}"

#         self.itr.job_dir = Path(self._clean_filename).parent
#         self.itr.log_dir = Path(self._clean_filename).parent

#         slurm_job = SBATCH(
#             self.itr,
#             self.job_name,
#             self._caller,
#             None,
#             self._logger_msg,
#         )

#         if slurm_job.check_sbatch_file():
#             if self.overwrite:
#                 self.itr.logger.info(
#                     f"{self._logger_msg}: --overwrite=True, re-writing the existing SLURM job now..."
#                 )
#             else:
#                 self.itr.logger.info(
#                     f"{self._logger_msg}: SLURM job file already exists... SKIPPING AHEAD"
#                 )
#                 self._num_skipped += 1
#                 return
#         else:
#             if self.itr.debug_mode:
#                 self.itr.logger.debug(f"{self._logger_msg}: creating file job now... ")

#         slurm_job.create_slurm_job(
#             None,
#             command_list=self._command_list,
#             overwrite=self.overwrite,
#             **self._slurm_resources[self._phase],
#         )
#         return slurm_job

#     def submit_job(self, index: int = 0) -> None:
#         """
#         Submit SLURM jobs to queue.
#         """
#         # only submit a job if a new SLURM job file was created
#         if self._slurm_job is None:
#             return

#         if self.itr.dryrun_mode:
#             self._slurm_job.display_job()
#         else:
#             self._slurm_job.write_job()

#         # submit the training eval job to queue
#         submit_slurm_job = SubmitSBATCH(
#             self.itr.job_dir,
#             f"{self.job_name}.sh",
#             "None",
#             self.logger,
#             self._logger_msg,
#         )

#         submit_slurm_job.build_command(
#             prior_job_number=self.itr.current_genome_dependencies
#         )
#         submit_slurm_job.display_command(current_job=(index+1), total_jobs=self._total_lines, display_mode=self.itr.dryrun_mode, debug_mode=self.itr.debug_mode)

#         if self.itr.dryrun_mode:
#             self._job_nums.append(generate_job_id())
#             self._num_submitted += 1
#         else:
#             submit_slurm_job.get_status(debug_mode=self.itr.debug_mode, current_job=(index+1), total_jobs=self._total_lines)

#             if submit_slurm_job.status == 0:
#                 self._num_submitted += 1
#                 self._job_nums.append(submit_slurm_job.job_number)
#             else:
#                 self.logger.error(
#                     f"{self._logger_msg}: unable to submit SLURM job",
#                 )
#                 self._job_nums.append(None)

#     def check_submission(self) -> None:
#         """
#         Check if the SLURM job file was submitted to the SLURM queue successfully
#         """
#         # look at job number list to see if all items are 'None'
#         _results = check_if_all_same(self._job_nums, None)
#         if _results is False:
#             if self.args.dry_run:
#                 print(
#                     f"============ [DRY RUN] - [{self._phase}] Job Numbers - {self._job_nums} ============"
#                 )
#             else:
#                 print(
#                     f"============ [{self._phase}] Job Numbers - {self._job_nums} ============"
#                 )
#         elif self._num_skipped == self._total_lines:
#             self.logger.info(
#                 f"{self._logger_msg}: no SLURM jobs were submitted... SKIPPING AHEAD"
#                 )
#         else:
#             self.logger.warning(
#                 f"{self._logger_msg}: expected SLURM jobs to be submitted, but they were not",
#             )
#             self.logger.warning(
#                 f"{self._logger_msg}: fatal error encountered, unable to proceed further with pipeline.\nExiting... ",
#             )
#             exit(1)
