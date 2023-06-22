#!/usr/bin/python3
"""
description: parse the SLURM resources used to complete a set of jobs, summarize per phase, and write to a new CSV file.

example:
    python3 triotrain/model_training/pipeline/benchmark.py             \\
        --env-file envs/demo.env                            \\
        --csv-file /path/to/SLURM_jobs.csv                  \\
        --dry-run
"""

# Load python libs
import argparse
import csv
import datetime
import os
import subprocess
import sys
from dataclasses import dataclass, field
from logging import Logger
from pathlib import Path
from typing import Dict

import helpers as h
import helpers_logger
import pandas as pd
from regex import compile


def collect_args():
    """
    Process the command line arguments to execute script.
    """
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "-e",
        "--env-file",
        dest="env_file",
        help="[REQUIRED]\ninput file (.env)\nprovides environment variables",
        type=str,
        metavar="</path/file>",
    )
    parser.add_argument(
        "-c",
        "--csv-file",
        dest="csv_file",
        help="[REQUIRED]\ninput file (.csv)\ncontain a list of SLURM Job Numbers",
        metavar="</path/file>",
    )
    parser.add_argument(
        "-f",
        "--find-job-nums",
        dest="find_job_nums",
        help="If True, search the log dirs for potential job numbers to benchmark",
        action="store_true",
    )
    parser.add_argument(
        "-d",
        "--debug",
        dest="debug",
        help="if True, enables printing detailed messages",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        help="if True, display commands to be used to the screen",
        action="store_true",
    )
    parser.add_argument(
        "-p",
        "--phases",
        dest="phase_list",
        help="delimited list of jobs to benchmark",
        type=lambda s: [str(item) for item in s.split(",")],
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
            "compare_neat",
        ],
    )
    return parser.get_default("phase_list"), parser.parse_args()


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
        logger.debug(f"using DeepVariant version | {os.environ.get('BIN_VERSION_DV')}")

    if args.dry_run:
        logger.info("[DRY_RUN]: output will display to screen and not write to a file")

    assert (
        args.env_file
    ), "Missing --env-file; Please provide a file with environment variables for the current analysis"
    # assert (
    #     args.csv_file
    # ), "Missing --csv-file; Please provide a file with a list of SLURM Job Numbers"


@dataclass
class Benchmark:
    """
    Define what data to store when benchmarking the TrioTrain Pipeline.
    """

    # required parameters
    args: argparse.Namespace
    logger: Logger
    list_of_phases: list = field(default_factory=list)

    # optional values
    use_default_phases: bool = True
    use_neat: bool = False

    # internal, imutable values
    _digits_only = compile(r"\d+")
    _job_nums: list = field(default_factory=list, init=False, repr=False)
    _keep_decimal = compile(r"[^\d.]+")
    _metrics_list_of_dicts: list = field(default_factory=list, init=False, repr=False)
    _phases_used: list = field(default_factory=list, init=False, repr=False)
    _phase_core_hours: dict = field(default_factory=dict, init=False, repr=False)
    _resources_used: list = field(default_factory=list, init=False, repr=False)
    _skipped_jobs: list = field(default_factory=list, init=False, repr=False)
    _slurm_jobs: Dict = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        # variables to save total core time charged
        self._total_hours = 0
        self._total_minutes = 0
        self._total_seconds = 0
        self._num_jobs = 0

    def get_sec(self, time_str: str) -> int:
        """
        Get seconds from D-HH:MM:SS or HH:MM:SS time
        Source: https://stackoverflow.com/questions/6402812/how-to-convert-an-hmmss-time-string-to-seconds-in-python
        """
        time = time_str.split("-")
        if len(time) == 1:
            days = 0
            hms_string = time[0]
        elif len(time) == 2:
            days = int(time[0])
            hms_string = time[1]
        else:
            self.logger.error(
                f"expected either 'D-HH:MM:SS' or 'HH:MM:SS' format, but {len(time)} inputs were detected | '{time}'... SKIPPING AHEAD"
            )
            return 0
        h, m, s = hms_string.split(":")
        return int(days) * 86400 + int(h) * 3600 + int(m) * 60 + int(s)

    def get_timedelta(self, total_seconds: int) -> datetime.timedelta:
        """
        Convert number of seconds into a timedelta format.
        """
        return datetime.timedelta(seconds=total_seconds)

    def get_timedelta_str(self, tdelta) -> str:
        """
        Re-formats a '0 days 00:00:00' timedelta object back into a '0-00:00:00' from SLURM. Used internally by summary() only.
        """
        d = {"days": tdelta.days}
        d["hours"], remainder = divmod(tdelta.seconds, 3600)
        d["minutes"], d["seconds"] = divmod(remainder, 60)
        for key, value in d.items():
            if key != "days":
                d[key] = str(value).zfill(2)
        return f'{d["days"]}-{d["hours"]}:{d["minutes"]}:{d["seconds"]}'

    def str_mem(self, mem: float) -> str:
        """
        Re-formats a float memory used back to '00.00G' string.
        Used internally by process_resources() and summary().
        """
        mem_string = f"{round(mem,2)}G"
        return mem_string

    def load_variables(self) -> None:
        """
        Load in variables from the env_file
        """
        # Confirm that the env file exists before setting variables
        env = h.Env(str(self.args.env_file), self.logger)
        # Load in environment variables
        var_list = ["RunName", "CodePath", "ResultsDir"]
        self.name, code_path, results_dir = env.load(*var_list)
        self._results_dir = Path(results_dir)

        if os.getcwd() != code_path:
            self.logger.error(
                f"execute {__file__} from {code_path}, not {os.getcwd()}\nExiting..."
            )
            sys.exit()

        self._search_path = self._results_dir.parent

    def find_job_logs(self, phase_name: str = "call_variants") -> None:
        """
        Look for potential job numbers in log files
        """

        if phase_name == "make_examples":
            search_pattern = r"examples-parallel-\w+-\w+\.out"
        elif phase_name == "beam_shuffle":
            search_pattern = r"beam-shuffle-\w+-\w+\.out"
        elif phase_name == "re_shuffle":
            search_pattern = r"re-shuffle-\w+\.out"
        elif phase_name == "train_eval":
            search_pattern = r"train-\w+-eval-Child_\d+\.out"
        elif phase_name == "select_ckpt":
            search_pattern = r"select-ckpt-\w+\.out"
        elif phase_name == "call_variants":
            search_pattern = r"test\d+-\w+\.out"
        elif phase_name == "compare_happy":
            search_pattern = r"happy\d+-no-flags-\w+\.out"
        elif phase_name == "convert_happy":
            search_pattern = r"convert-\D+\d+-\w+\.out"
        else:
            self.logger.error(
                f"unable to identify a search pattern for '{phase_name}'... SKIPPING AHEAD"
            )
            return

        search_dirs = [d for d in os.listdir(str(self._search_path)) if d != "summary"]

        if self.args.debug:
            iter = [search_dirs[0]]
        else:
            iter = search_dirs

        for dir in iter:
            logs_exist, total_jobs_in_phase, log_file_names = h.check_if_output_exists(
                match_pattern=search_pattern,
                file_type="SLURM log files",
                search_path=self._search_path / dir / "logs",
                label="benchmarking",
                logger=self.logger,
                debug_mode=self.args.debug,
                dryrun_mode=self.args.dry_run,
            )
            if logs_exist:
                if phase_name in self.list_of_phases:
                    self._phases_used.extend([phase_name] * total_jobs_in_phase)

                for f in log_file_names:
                    job_ext = f.split("_")[1]
                    match = self._digits_only.search(job_ext)
                    if match:
                        self._job_nums.append(int(match.group()))
                        self._num_jobs += 1

    def open_file(self) -> None:
        """
        Open up a csv file, return a dict with each line in the file.
        Used internally by process_csv_file() only.
        """
        try:
            assert Path(
                self.args.csv_file
            ).exists(), (
                f"Unable to open [{self.args.csv_file}] because it does not exist"
            )
            with open(self.args.csv_file, mode="r") as csv_file:
                csv_reader = csv.DictReader(csv_file)
                line_count = 0
                for row in csv_reader:
                    line_count += 1
                    self._slurm_jobs[line_count] = row
                assert (
                    self._slurm_jobs
                ), f"Unable to load in input data from [{self.args.csv_file}]"
        except AssertionError as err:
            self.logger.exception(f"{err}\nExiting... ")
            sys.exit()

    def process_csv_file(self) -> None:
        """
        Open up the csv file, create a new list of the phases contained in the csv file and a second list containing the SLURM job IDs.
        """
        self.open_file()
        for key, value in self._slurm_jobs.items():
            for k, v in value.items():
                if k == "JobList":
                    if len(v) != 0:
                        jobs = v.split(",")
                        total_jobs_in_phase = len(jobs)
                        phase_name = h.process_phase(value["phase"].lower())
                        if phase_name in self.list_of_phases:
                            self._job_nums.extend(jobs)
                            self._phases_used.extend([phase_name] * total_jobs_in_phase)
                        else:
                            self.logger.warning(
                                f"Skipping {total_jobs_in_phase} jobs in [{phase_name}] phase because not in [{', '.join(self.list_of_phases)}]",
                            )
                    else:
                        self.logger.warning(
                            f"Skipping a bad input row [# {key}:\n{value}]"
                        )
        self._num_jobs = len(self._job_nums)
        self.logger.info(
            f"Found [{int(self._num_jobs):,}] job numbers for [{Path(self.args.csv_file).name}]"
        )

    def process_resources(self) -> None:
        """
        Iterate through a list of job numbers, and use 'sacct' to calaculate resources used per job.
        """

        for count, job in enumerate(self._job_nums):
            current_phase = self._phases_used[count]

            if "neat" in current_phase:
                if not self.use_neat and self.use_default_phases:
                    # define the row index order
                    self.indexes = self.list_of_phases[:-1]
                    if self.args.debug:
                        self.logger.debug(f"--use_neat is unset; skipping job [{job}]")
                    continue
            else:
                self.indexes = self.list_of_phases

            # Initalize the lists that will become a dictionary
            keys = ["phase"]
            values = [current_phase]

            try:
                # Collect the resources used by the current job number
                # if the job state=COMPLETED and make the output
                # parsable with '|' but don't include a trailing '|'
                resources = subprocess.run(
                    [
                        "sacct",
                        f"-j{job}",
                        "--state=COMPLETED",
                        "--format=JobID,JobName%50,State,ExitCode,Elapsed,Alloc,CPUTime,MaxRSS,MaxVMSize",
                        "--units=G",
                        "--parsable2",
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )
            except subprocess.CalledProcessError as err:
                self.logger.error(
                    f"Resource collection stopped at {int(count):,}-of-{int(self._num_jobs):,} for [Job#:{job}]",
                )
                self.logger.error(f"{err}\n{err.stderr}\nExiting... ")
                sys.exit(err.returncode)

            # remove trailing new line from output string
            # and split lines into a list of 3 lines (header, slurm batch job, child process(es))
            output = resources.stdout.strip().split("\n")

            # parse out the header line
            metric_names = output[0].split("|")[:9]

            # some jobs may have more than 1 child process
            if len(output) == 3:
                # parse out the more informative job name + jobid line
                core_hours = output[1].split("|")[:7]

                # grab the child process(es) memory usage
                memory = output[2].split("|")[7:9]

                self._resources_used = core_hours + memory
            elif len(output) > 3:
                if "train_eval" in current_phase:
                    core_hours = output[1].split("|")[:7]
                    train_memory = output[3].split("|")[7:9]
                    eval_memory = output[4].split("|")[7:9]
                    RSS1 = float(self._keep_decimal.sub("", train_memory[0]))
                    RSS2 = float(self._keep_decimal.sub("", eval_memory[0]))
                    max_RSS = max(RSS1, RSS2)
                    VM1 = float(self._keep_decimal.sub("", train_memory[1]))
                    VM2 = float(self._keep_decimal.sub("", eval_memory[1]))
                    max_VM = max(VM1, VM2)
                    max_memory = [self.str_mem(max_RSS), self.str_mem(max_VM)]
                    self._resources_used = core_hours + max_memory
                else:
                    self.logger.error(
                        f"I haven't been told  how to handle {len(output)} child process(es) {current_phase} yet!\n{output}",
                    )
                    sys.exit(2)
            elif len(output) < 3:
                self._skipped_jobs.append(job)
                self.logger.warning(
                    f"Skipping job [{job}] because invalid output format\n{output}"
                )
                continue
            else:
                self.logger.error(
                    f"I haven't been told  how to handle {len(output)} child process(es) {current_phase} yet!\n{output}",
                )
                sys.exit(2)

            # Convert CPUTime in days into seconds
            CPUTime = self._resources_used[6]
            CPU_seconds = self.get_sec(CPUTime)

            # keep a rolling total of CORE HOUR USAGE ------------
            self._total_seconds += CPU_seconds
            print(current_phase)
            print(self._total_seconds)
            add_minute, remainder_s = divmod(self._total_seconds, 60)
            self._total_minutes += add_minute
            self._total_seconds = remainder_s
            add_hour, remainder_m = divmod(self._total_minutes, 60)
            self._total_hours += add_hour
            self._total_minutes = remainder_m
            add_day, remainder_h = divmod(self._total_hours, 24)
            self._total_days = add_day

            # Remove the 'G' from memory resources ---------------
            # convert from int to float
            MaxRSS = float(self._keep_decimal.sub("", self._resources_used[7]))
            MaxVMSize = float(self._keep_decimal.sub("", self._resources_used[8]))
            self._resources_used[7] = str(MaxRSS)
            self._resources_used[8] = str(MaxVMSize)

            # Add the unit back to column name
            metric_names[7] = "MaxRSS_G"
            metric_names[8] = "MaxVMSize_G"

            # combine phase with resource usage data
            keys.extend(metric_names)
            values.extend(self._resources_used)

            # save clean data to a dictionary
            d = dict(zip(keys, values))
            self._metrics_list_of_dicts.append(d)
            self.column_names = list(self._metrics_list_of_dicts[0].keys())

            # Print a status message for chunks of jobs
            if self.args.debug:
                chunk_size = 10
            else:
                chunk_size = 100

            if (count + 1) % chunk_size == 0:
                self.logger.info(
                    f"finished {int(count + 1):,}-of-{int(self._num_jobs):,} jobs"
                )
                self._core_hours_str = f"{int(self._total_days):,}-{int(remainder_h):,}:{int(self._total_minutes)}:{self._total_seconds}"
                self.logger.info(
                    f"running total CORE HOURS = {int(self._total_hours):,} | {self._core_hours_str}",
                )
                if self.args.debug:
                    self.logger.debug(f"row{int(count + 1):,} = {d}")

    def summary(self) -> None:
        """
        Calculate summary stats about resourced used for each phase.
        """
        # convert dict obj to dataframe
        df = pd.DataFrame.from_records(
            self._metrics_list_of_dicts, columns=self.column_names
        )

        # Ensure you only average usage across non-replicate jobs
        df = df.drop_duplicates(subset=["JobName"])

        df.insert(
            loc=6,
            column="Elapsed_seconds",
            value=df[["Elapsed"]].applymap(self.get_sec),
        )

        # Convert to str to timedelta obj for descriptive stats
        df.insert(
            loc=7,
            column="Elapsed_Time",
            value=df[["Elapsed_seconds"]].applymap(self.get_timedelta),
        )

        # Convert to str to float obj for descriptive stats
        df[["MaxRSS_G", "MaxVMSize_G"]] = df[["MaxRSS_G", "MaxVMSize_G"]].apply(
            pd.to_numeric
        )

        if self.args.debug:
            self.logger.debug(f"accounting output for all jobs |'")
            print(
                "---------------------------------------------------------------------------------------------------------------------------------------"
            )
            print(df)
            print(
                "---------------------------------------------------------------------------------------------------------------------------------------"
            )

        # handle elapsed wall time
        durration_summary = pd.DataFrame(
            df.groupby("phase").Elapsed_Time.describe(datetime_is_numeric=False)[
                ["count", "mean", "max"]
            ]
        )
        durration_summary[["mean", "max"]] = durration_summary[
            ["mean", "max"]
        ].applymap(self.get_timedelta_str)
        durration_summary.reindex(self.indexes)

        if self.args.debug:
            self.logger.debug(
                f"Duration\n---------------------------------------------\n{durration_summary}\n---------------------------------------------",
            )

        # handle REAL memory usage
        real_mem_summary = pd.DataFrame(
            df.groupby("phase").MaxRSS_G.describe()[["count", "mean", "max"]]
        )

        real_mem_summary[["mean", "max"]] = real_mem_summary[["mean", "max"]].applymap(
            self.str_mem
        )
        real_mem_summary.reindex(self.indexes)

        if self.args.debug:
            self.logger.debug(
                f"Memory Used\n---------------------------------------------\n{real_mem_summary}\n---------------------------------------------"
            )

        # Merge and clean up the two dfs ------------
        # remove duplicate columns to avoid 2 count columns with the same value
        counts = list(durration_summary["count"])
        durration_summary.drop("count", inplace=True, axis=1)
        real_mem_summary.drop("count", inplace=True, axis=1)

        # join 2 dataframes
        self._merged_df = durration_summary.join(
            real_mem_summary, lsuffix="_runtime", rsuffix="_mem"
        )

        # add back the job count column
        self._merged_df.insert(0, "job_count", counts)

        # keep the rows in run_order
        self._merged_df.reindex(self.indexes)

        # add the phase core hours
        self._merged_df.loc[list(self._phase_core_hours), "core_hours"] = pd.Series(
            self._phase_core_hours
        )

        # Create a column with phases, rather than row names
        self._merged_df.reset_index(inplace=True)

        self.logger.info(
            f"Resources Used per phase\n===============================\n{self._merged_df}\n===============================",
        )
        self.logger.info(
            f"Finished all {int(self._num_jobs):,} jobs\n======= {int(self._num_jobs - len(self._skipped_jobs)):,}-of-{int(self._num_jobs):,} JOBS =======\nTOTAL CORE HOURS = {int(self._total_hours):,} | {self._core_hours_str}\n===============================",
        )

        if len(self._skipped_jobs) > 0:
            self.logger.warning(
                f"{len(self._skipped_jobs)} SLURM jobs were not included in the CPUTime total. Their job numbers are:\n{self._skipped_jobs}",
            )

    def write_results(self) -> None:
        """
        If dryrun mode, display the intermediate outputs to the screen.

        Otherwise, write the intermediate outputs to files.
        """
        if self.args.dry_run:
            self.logger.info(
                f"Contents of '{str(self._results_dir)}/{self.name}.summary_resources.csv' |\n---------------------------------------------",
            )
            print(self._merged_df)
            print("---------------------------------------------")
        else:
            # Define the summary output CSV file to be created
            summary_file = h.WriteFiles(
                str(self._results_dir),
                f"{self.name}.summary_resources.csv",
                self.logger,
            )
            summary_file.check_missing()
            if summary_file.file_exists:
                if self.args.debug:
                    self.logger.debug(f"{summary_file.file_path.name} written")
            else:
                self._merged_df.to_csv(summary_file.file_path, index=False)
                assert (
                    summary_file.file_path.exists()
                ), f"{summary_file.file_path.name} was not written correctly"
                if self.args.debug:
                    self.logger.debug(f"{summary_file.file_path.name} written")

    def run(self) -> None:
        """
        Combine the benchmark class into a single, callable function.
        """
        self.load_variables()

        if self.args.find_job_nums:
            self.find_job_logs()
        else:
            self.process_csv_file()

        self.process_resources()
        self.summary()
        self.write_results()


def __init__():
    """
    Iterating through SLURM job numbers, totalling up core hours charged,
    and calculating summary statistics for Wall Time, Memory Usage to inform
    resources to request for each phase's jobs.
    """
    # Collect command line args
    default_phases, args = collect_args()

    # Collect start time
    h.Wrapper(__file__, "start").wrap_script(h.timestamp())

    # Create error log
    current_file = os.path.basename(__file__)
    module_name = os.path.splitext(current_file)[0]
    logger = helpers_logger.get_logger(module_name)

    # Check command-line args
    check_args(args, logger)

    logger.info(f"PHASE DEFAULTS: {default_phases}")
    logger.info(f"PHASE INPUTS: {args.phase_list}")

    if default_phases == args.phase_list:
        use_defaults = True
        phases = default_phases
    else:
        use_defaults = False
        phases = args.phase_list

    Benchmark(args, logger, phases, use_default_phases=use_defaults).run()

    h.Wrapper(__file__, "end").wrap_script(h.timestamp())


# Execute functions created
if __name__ == "__main__":
    __init__()
