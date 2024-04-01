# import subprocess
# parser.add_argument(
#     "--filter-GQ",
#     dest="filter_GQ",
#     help="if True, subset +smpl-stats metrics by the following GQ values: [10, 13, 20, 30]",
#     action="store_true",
# )

# _filter_applied: Union[str, None] = field(default=None, init=False, repr=False)

#     def execute(self, command_list: list, type: str, run_interactive: bool = False, keep_output: bool = False) -> None:
#         """
#         Run a command line subprocess and check the output.
#         """
#         command_str = " ".join(command_list)
#         if not run_interactive:
#             self._command_list.append(command_str)
#             if self.args.dry_run:
#                 self.logger.info(
#                     f"[DRY_RUN] - {self._logger_msg}: pretending to add the following line(s) to a SLURM job file |\n'{command_str}'"
#                 )
#             return
#         elif self.args.dry_run and not keep_output:
#             self.logger.info(
#                 f"[DRY RUN] - {self._logger_msg}: pretending to execute the following | '{command_str}'"
#             )
#             breakpoint()
#             return
#         else:
#             if keep_output:
#                 result = subprocess.run(
#                     command_list,
#                     check=True,
#                     capture_output=True,
#                     text=True,
#                 )
#             else:
#                 result = subprocess.run(
#                     command_list,
#                     check=True,
#                 )

#             if self.args.debug:
#                 self.logger.debug(f"{self._logger_msg}: done with '{type}'")

#             if result.returncode != 0:
#                 self.logger.error(
#                     f"{self._logger_msg}: command used | '{command_str}'"
#                 )
#                 self.logger.error(f"{self._logger_msg}: {result.stdout}")
#                 raise ChildProcessError(f"unable to complete '{type}'")
#             elif keep_output and result.returncode == 0:
#                 self._output_file_contents = str(result.stdout).strip().split("\n")
#                 # self._mie_metrics.write_list(output_file_contents)
#                 # self.handle_mie_data(input=output_file_contents)

#     def filter(self, filter_flag: str, input: str, output: str) -> None:
#         """
#         Filter the contents of a VCF and create a new VCF file
#         """
#         # Determine if filtered VCF files exist
#         _vcf = TestFile(file=output, logger=self.logger)
#         _vcf.check_existing(
#             logger_msg=self._logger_msg, debug_mode=self.args.debug
#         )
#         if _vcf.file_exists:
#             if self.args.debug:
#                 self.logger.debug(
#                     f"{self._logger_msg}: filtered VCF '{_vcf.file}' already exists... SKIPPING AHEAD"
#                     )
#         else:
#             self.logger.info(
#                 f"{self._logger_msg}: using 'bcftools view' to create a filtered VCF | '{output}'",
#             )

#             convert_cmd = [
#                 "bcftools",
#                 "view",
#                 "--threads",
#                 "2",
#                 filter_flag,
#                 "--output-type",
#                 "z",
#                 "--output",
#                 output,
#                 input,
#             ]

#             self.execute(command_list=convert_cmd, type="bcftools view")

#     def index_vcf(self, vcf_input: Union[str, Path]) -> None:
#         """
#         Create the required TABIX index file for 'bcftools +smpl-stats'
#         """
#         # Determine if indexed VCF files exist
#         _tbi = TestFile(file=f"{vcf_input}.tbi", logger=self.logger)
#         _tbi.check_existing(
#             logger_msg=self._logger_msg, debug_mode=self.args.debug
#         )
#         if _tbi.file_exists:
#             if self.args.debug:
#                 self.logger.debug(
#                     f"{self._logger_msg}: tabix-indexed VCF '{_tbi.file}' already exists... SKIPPING AHEAD"
#                     )
#         else:
#             self.logger.info(
#                 f"{self._logger_msg}: using 'tabix index' to create .TBI index file | '{str(vcf_input)}.tbi'",
#             )

#             index_cmd = [
#                 "tabix",
#                 "-p",
#                 "vcf",
#                 str(vcf_input),
#             ]
#             self.execute(command_list=index_cmd, type="tabix index")

#     def find_filter(self, file_input: str) -> Union[str, None]:
#         """
#         Identify the 'GQ##' pattern in an input string.
#         """
#         _gq_regex = compile(rf"GQ\d+")
#         match = _gq_regex.search(file_input)
#         if match:
#             if self.args.debug:
#                 self.logger.debug(
#                         f"{self._logger_msg}: INPUT CLEAN_FILENAME | '{match.group()}'")
#             return match.group()


#             # Exclude based on GQ
#             if self.args.filter_GQ:
#                 GQ_scores = [10, 13, 20, 30]
#                 for g in GQ_scores:
#                     label = f"{self._clean_filename}.GQ{g}.vcf.gz"

#                     _gq_vcf = TestFile(label, self.logger)
#                     _gq_vcf.check_existing(
#                         logger_msg=self._logger_msg, debug_mode=self.args.debug
#                     )
#                     if _gq_vcf.file_exists:
#                         if self.args.debug:
#                             self.logger.debug(
#                             f"{self._logger_msg}: GQ.VCF file '{_gq_vcf.file}' already exists... SKIPPING AHEAD"
#                             )
#                         self.stats(label, create_job=False)
#                         continue
#                     else:
#                         self.logger.info(
#                             f"{self._logger_msg}: missing GQ.VCF file | '{_gq_vcf.file}'")
#                         self.filter(f"--exclude 'GQ<{g}'", self._vcf_file.file, label)
#                         self.index_vcf(label)
#                         self.stats(label, create_job=True)
