#!/bin/python3
"""
description: 

usage:
    from process_hap import Process
"""

import argparse
import csv
import operator
import os
import subprocess
import sys
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import DefaultDict, Union

import args_process_hap
import helpers as h
import helpers_logger
from slurm_convert_hap import Convert


@dataclass
class Process:
    """
    Define what data to keep when processing hap.py results.
    """

    # required values
    args: argparse.Namespace
    logger: h.Logger

    # internal, imutable values
    _combinations: list = field(default_factory=list, init=False, repr=False)
    _conditions_used: list = field(default_factory=list, init=False, repr=False)
    _counts_default_dict: DefaultDict = field(
        default_factory=lambda: defaultdict(int), init=False, repr=False
    )
    _counts_dict: OrderedDict = field(
        default_factory=lambda: OrderedDict({}), init=False, repr=False
    )
    _internal_dict1: OrderedDict = field(
        default_factory=lambda: OrderedDict({}), init=False, repr=False
    )
    _internal_dict2: OrderedDict = field(
        default_factory=lambda: OrderedDict({}), init=False, repr=False
    )
    _metadata: OrderedDict = field(
        default_factory=lambda: OrderedDict({}), init=False, repr=False
    )
    _output_dict: OrderedDict = field(
        default_factory=lambda: OrderedDict({}), init=False, repr=False
    )
    _phase: str = field(default="process_happy", init=False, repr=False)
    _processed_keys: list = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        self.convert_happy = Convert(self.args, self.logger)
        self.convert_happy.run()
        self._valid_keys = [
            "ModelUsed",
            "TestName",
            "SampleID",
            "TestLabID",
            "TestBreed",
            "TestSex",
            "TestCoverage",
            "Checkpoint",
            "Conditions",
            "TotalTruth_INDEL",
            "TotalTruth_SNP",
            "TotalTruthLoci",
            "TotalTest_INDEL",
            "TotalTest_SNP",
            "TotalTestLoci",
        ]
        self._combinations = [
            "FN_FP",
            "FN_N",
            "FN_TP",
            "FN_.",
            "TP_FP",
            "TP_N",
            "TP_TP",
            "TP_.",
            "._TP",
            "._FP",
            "._N",
            "N_.",
            "N_N",
            "UNK_UNK",
        ]
        self._logger_msg = f"[{self.convert_happy._mode}] - [{self._phase}] - [{self.convert_happy._test_msg}]"

    def type_filter(self) -> None:
        """
        Filter metrics based on variant type, meaning count per SNP/INDEL/NOCALL metrics.
        """
        if self.args.debug:
            self.logger.debug(
                f"{self._logger_msg}: counting combinations of SNP/INDEL/NOCALL metrics now... "
            )
        self.expected_num_metrics = (len(self._combinations) * 3) * 3
        self._columns = [
            "truth_label",
            "test_label",
            "truth_variant_type",
            "test_variant_type",
        ]
        TypeList = ["SNP", "INDEL", "NOCALL"]
        self._type_combinations = []
        for combo in self._combinations:
            for t in TypeList:
                for t2 in TypeList:
                    new_combo = f"{combo}_{t}_{t2}"
                    self._type_combinations.append(new_combo)
                    if new_combo not in self._counts_default_dict.keys():
                        # assigning to a variable prints fewer confusing msgs
                        quiet = self._counts_default_dict[new_combo]

    def get_sampleID(self) -> None:
        """
        Add the SampleID from the VCF to processed metadata
        """
        if self.args.debug:
            self.logger.debug(f"{self._logger_msg}: finding the SampleID now...")
        awk_command = '$1=="#CHROM" {print $10}'

        if awk_command is not None:
            zcat = subprocess.Popen(
                [
                    "zcat",
                    str(self.convert_happy._test_vcf_file_path),
                ],
                stdout=subprocess.PIPE,
            )
            awk = subprocess.run(
                ["awk", awk_command],
                stdin=zcat.stdout,
                capture_output=True,
                text=True,
                check=True,
            )

            if awk:
                if self.args.debug:
                    self.logger.debug(f"{self._logger_msg}: done with finding SampleID")
                self.sampleID = str(awk.stdout).strip()
            else:
                self.logger.warning(f"{self._logger_msg}: unable to find a SampleID")
                self.sampleID = None

    def class_filter(self) -> None:
        """
        WIP: Filter metrics based on genotype class, meaning count per HomRef/Het/HomAlt.
        """
        self.expected_num_metrics = len(self._combinations) * 4
        self._columns = ["test_genotype_class", "truth_label", "test_label"]
        ClassList = ["homalt", "nocall", "het", "hetalt"]
        self._class_combinations = []
        for combo in self._combinations:
            for C in ClassList:
                new_combo = f"{combo}_{C}"
                self._class_combinations.append(new_combo)
                if new_combo not in self._counts_default_dict.keys():
                    # assigning to a variable prints fewer confusing msgs
                    quiet = self._counts_default_dict[new_combo]

    def chr_filter(self) -> None:
        """
        WIP: Filter metrics based on genomic order, meaning count per CHR.
        """
        self.expected_num_metrics = len(self._combinations) * 29
        self._columns = ["chromosome", "truth_label", "test_label"]

        self._chr_combinations = []
        for combo in self._combinations:
            for c in self.convert_happy.CHR:
                new_combo = f"{c}_{combo}"
                self._chr_combinations.append(new_combo)
                if new_combo not in self._counts_default_dict.keys():
                    # assigning to a variable prints fewer confusing msgs
                    quiet = self._counts_default_dict[new_combo]

    def create_metadata(self) -> None:
        """
        Define analysis-specific condition and labels.
        """
        self.get_sampleID()

        if (
            "beam" in self.convert_happy._input_pattern.lower()
            and "baseline" not in self.convert_happy._input_pattern.lower()
        ):
            self._conditions_used.append("RegionsShuffling")

        if self.convert_happy._custom_model:
            self._conditions_used.append("RegionsShuffling")

        if "nopop" in self.convert_happy._input_pattern.lower():
            self._conditions_used.append("withoutPopVCF")
        else:
            self._conditions_used.append("withPopVCF")

        if len(self._conditions_used) > 0:
            analysis_conditions_used = ",".join(set(self._conditions_used))
        else:
            analysis_conditions_used = None

        # Add decription about the model checkpoint used to output dict
        # Also, adding sum keys for each type
        self._metadata.update(
            {
                "ModelUsed": self.convert_happy._model_used,
                "TestName": self.convert_happy._test_name,
                "SampleID": self.sampleID,
                "Checkpoint": self.convert_happy._checkpoint,
                "Conditions": analysis_conditions_used,
                "TotalTruth_INDEL": 0,
                "TotalTruth_SNP": 0,
                "TotalTruthLoci": 0,
                "TotalTest_INDEL": 0,
                "TotalTest_SNP": 0,
                "TotalTestLoci": 0,
            }
        )

    def record_counts(self, in_string: str, dict: dict):
        """
        Increment the value in a dictionary by 1, each time a string key is observed.
        """
        if in_string in dict:
            dict[in_string] += 1
        else:
            dict[in_string] = 1

    def count_metrics(self, line: dict, show_weirdos: bool = False) -> None:
        """
        Given a line of a TSV-input, count the number of times a metric combitination is observed.
        """
        # Obtain the line number and convert lines to dict
        filtered_values = {k: v for k, v in line.items() if k in self._columns}

        KeepRecords = ["SNP", "INDEL"]
        truth = filtered_values["truth_variant_type"]
        test = filtered_values["test_variant_type"]

        # Calculate the 'TRUTH' SNPS & INDELS
        if truth in KeepRecords:
            # Count the sum
            self.record_counts("TotalTruthLoci", self._metadata)
            # Count SNPs only
            if truth == "SNP":
                self.record_counts("TotalTruth_SNP", self._metadata)
            # Count INDELs only
            elif truth == "INDEL":
                self.record_counts("TotalTruth_INDEL", self._metadata)

        # Calculate the 'QUERY' SNPS & INDELS
        if test in KeepRecords:
            # Count the sum
            self.record_counts("TotalTestLoci", self._metadata)
            # Count SNPs only
            if test == "SNP":
                self.record_counts("TotalTest_SNP", self._metadata)
            # Count INDELs only
            elif test == "INDEL":
                self.record_counts("TotalTest_INDEL", self._metadata)

        # Count based on filters
        # Get values from a subset of self._columns
        reordered_values = {k: filtered_values[k] for k in self._columns}

        # Join those values into string patterns to count
        hash_key = "_".join(reordered_values.values())

        if show_weirdos and self._weirdos is not None:
            if hash_key in self._weirdos:
                print(
                    "MISSING PATTERN CONTENTS EXAMPLE: ------------------------------"
                )
                print("PATTERN:", hash_key)
                print("\t".join(line.values()))
                self.logger.error(
                    f"{self._logger_msg}: edit {os.path.basename(__file__)} to include the missing pattern(s)"
                )
                sys.exit(1)

        # Count how many times each value combination is observed
        self.record_counts(hash_key, self._counts_default_dict)

    def order_counts_decreasing(self) -> dict:
        """
        Sort the values in a dictionary, in decreasing order.
        """
        sorted_d = dict(
            sorted(
                self._counts_default_dict.items(),
                key=operator.itemgetter(1),
                reverse=True,
            )
        )
        return sorted_d

    def order_counts_by_chr(self):
        """
        WIP: Obtain the 'key=value' pairs in a dictionary, split the key into a chromosome number, use a custom sort function to keep the
        results in genomic order, and sort the keys by numerical values in decreasing order.
        """
        for k, v in self._counts_default_dict.items():
            chrom = k.split("_")[0]
            self._counts_default_dict[k] = [v, chrom]

        test = OrderedDict(sorted(self._counts_default_dict.items(), key=lambda x: self.CHR_Order.get(x[1][1])))  # type: ignore
        sortedDict = {}
        for k, v in test.items():
            sortedDict.update({k: v[0]})
        return sortedDict

    def load_raw_data(
        self, sort_decreasing: bool = False, reload: bool = False
    ) -> OrderedDict:
        """
        Read lines of a TSV (tab-separated values) file as an array of dicts.

            NOTE: the input file should include a header line consisting of column names.

        Each dict represents a row in the input file, with column names as keys.
        """
        # Confirm input data is an existing file
        if self.convert_happy.file_tsv.exists():
            with open(self.convert_happy.file_tsv, mode="r") as data:
                # Open the file as read only
                for line in csv.DictReader(data, delimiter="\t"):
                    self.count_metrics(line=line, show_weirdos=reload)
        else:
            if self.args.dry_run:
                # stream in the convert-tsv stdout to process without writing an intermediate file
                for line in csv.DictReader(
                    self.convert_happy.tsv_format,
                    fieldnames=self.convert_happy._custom_header,
                    delimiter="\t",
                ):
                    self.count_metrics(line=line, show_weirdos=reload)
            else:
                self.logger.error(
                    f"{self._logger_msg}: unable to find existing TSV file | '{self.convert_happy.file_tsv}'\nExiting..."
                )
                sys.exit(1)

        if len(self._counts_default_dict.keys()) != self.expected_num_metrics:
            self.logger.warning(
                f"{self._logger_msg}: expected [{self.expected_num_metrics}] metrics, but [{len(self._counts_default_dict.keys())}] were detected"
            )
            print("--- Count Dictionary Contents:")
            for key, value in self._counts_default_dict.items():
                print(f"KEY: {key}\t VALUE:{value}")
            print("Exiting...")
            sys.exit(1)

        # Sort the Dictionary
        if sort_decreasing:
            # Sorting by count in decreasing order
            sorted_counts = self.order_counts_decreasing()
        else:
            sorted_counts = dict(sorted(self._counts_default_dict.items()))

        return OrderedDict(sorted_counts)

    def load_counts_data(self, re_count: bool = False) -> None:
        """
        Either load in the intermediate counts from file, or produce filtered metric counts internally.
        """
        self.create_metadata()
        if self.convert_happy.missing_csv or re_count:
            self.type_filter()
            data = self.load_raw_data(reload=re_count)
            self._counts_dict.update(self._metadata)
            self._counts_dict.update(data)

            if self.args.debug:
                self.logger.debug(
                    f"{self._logger_msg}: done counting metrics combinations"
                )

            self._clean_counts = {k: v for k, v in self._counts_dict.items() if v}
            self.write_output(
                outfile=self.convert_happy.interm_file_csv,
                out_dict=self._clean_counts,
            )
        else:
            self.logger.info(
                f"{self._logger_msg}: existing intermediate CSV file detected | '{self.convert_happy.interm_file_csv.name}'... SKIPPING AHEAD"
            )

            # read in the existing counts data from file
            with open(str(self.convert_happy.interm_file_csv), "r") as data:
                for row in csv.reader(data):
                    h.add_to_dict(
                        update_dict=self._counts_dict,
                        new_key=row[0],
                        new_val=row[1],
                        valid_keys=None,
                        logger=self.logger,
                        logger_msg=self._logger_msg,
                    )

            for k, v in self._counts_dict.items():
                if k in self._valid_keys and k not in self._metadata.keys():
                    h.add_to_dict(
                        update_dict=self._metadata,
                        new_key=k,
                        new_val=v,
                        logger=self.logger,
                        logger_msg=self._logger_msg,
                    )

    def count(self, patterns_dict: dict, type: Union[str, None] = None) -> None:
        """
        Calculate INDEL and SNP totals
        """
        _sum = 0
        if type is not None:
            if type in ["IGNORED", "MISSING"]:
                label = f"{type}_"
            else:
                label = f"{type}s_"
            if self.args.debug:
                self.logger.debug(f"{self._logger_msg}: counting {type} now...")
        else:
            label = ""

        for metric, combo_list in patterns_dict.items():
            if self.args.debug:
                self.logger.debug(f"{self._logger_msg}: METRIC = {metric}")
            running_total = 0
            for key in combo_list:
                self._processed_keys.append(key)
                if key in self._counts_dict.keys():
                    running_total += int(self._counts_dict[key])
                    if self.args.debug:
                        self.logger.debug(
                            f"{self._logger_msg}: RUNNING TOTAL = {running_total}"
                        )
                else:
                    running_total += 0

            _sum += running_total
            if metric in ["IGNORED", "MISSING"]:
                metric_label = f"{label}{metric}"
            else:
                metric_label = f"{label}{metric}s"
            h.add_to_dict(
                update_dict=self._internal_dict1,
                new_key=metric_label,
                new_val=running_total,
                logger=self.logger,
                logger_msg=self._logger_msg,
            )

        sum_label = f"{label}Total"
        if self.args.debug:
            self.logger.debug(f"{self._logger_msg}: SUM = {_sum}")
        h.add_to_dict(
            update_dict=self._internal_dict1,
            new_key=sum_label,
            new_val=_sum,
            logger=self.logger,
            logger_msg=self._logger_msg,
        )
        self._output_dict.update(self._internal_dict1)

    def make_proportional(self, label: Union[str, None] = None) -> None:
        """
        Create proportional values for metrics relative to the total variants in the QUERY VCF from Hap.py
        """
        if label is not None:
            if self.args.debug:
                self.logger.debug(f"{self._logger_msg}: LABEL = {label}")
            for k, v in self._internal_dict1.items():
                if label in ["IGNORED", "MISSING"]:
                    key = f"{label}_Total"
                    match_string = label
                else:
                    key = f"{label}s_Total"
                    match_string = f"{label}s"
                total = int(self._internal_dict1[key])
                if "_Total" not in k and label in k:
                    metric = k.split("_")[1]

                    if metric == match_string:
                        metric = k.split("_")[0]

                    if total == 0:
                        proportion = total
                    else:
                        proportion = round(((v / total) * 100), ndigits=2)
                    new_key = f"{match_string}_%{metric}"

                    if self.args.debug:
                        self.logger.debug(f"{self._logger_msg}: KEY = {k}")
                        self.logger.debug(f"{self._logger_msg}: METRIC = {metric}")
                        self.logger.debug(
                            f"{self._logger_msg}: {new_key} = {proportion}%"
                        )

                    h.add_to_dict(
                        update_dict=self._internal_dict2,
                        new_key=new_key,
                        new_val=f"{proportion}%",
                        logger=self.logger,
                        logger_msg=self._logger_msg,
                    )

    def indel_totals(self) -> None:
        """
        Calculate the total INDEL metrics.
        """
        # NOTE: FN_FP means truth was 0/1 but query was 1/1, aka missed the het call in truth (FN), but added a second copy of the variant (FP).
        # NOTE: Genotype Error, vs. completely wrong = ._FP
        indels = {
            "FP": [
                "._FP_NOCALL_INDEL",
                "FN_FP_SNP_INDEL",
                "FN_FP_INDEL_INDEL",
                "TP_FP_INDEL_INDEL",
                "TP_FP_SNP_INDEL",
            ],
            "TP": [
                "TP_._INDEL_NOCALL",
                "TP_FP_INDEL_INDEL",
                "TP_FP_INDEL_SNP",
                "TP_TP_INDEL_INDEL",
                "TP_TP_INDEL_SNP",
            ],
            "FN": [
                "FN_._INDEL_NOCALL",
                "FN_FP_INDEL_INDEL",
                "FN_FP_INDEL_SNP",
                "FN_TP_INDEL_INDEL",
                "FN_TP_INDEL_SNP",
            ],
            "IGNORED": [
                "UNK_UNK_NOCALL_INDEL",
                "UNK_UNK_INDEL_INDEL",
                "UNK_UNK_INDEL_SNP",
                "._N_NOCALL_INDEL",
            ],
            "MISSING": [
                "UNK_UNK_INDEL_NOCALL",
                "N_._INDEL_NOCALL",
                "N_N_INDEL_SNP",
                "N_N_INDEL_INDEL",
            ],
        }
        self.count(type="INDEL", patterns_dict=indels)
        self._output_dict.update(self._internal_dict1)
        self.make_proportional(label="INDEL")
        self.performance(label="INDELs")
        self._output_dict.update(self._internal_dict2)

    def snp_totals(self) -> None:
        """
        Calculate the total SNP metrics.

        IGNORED are variants outside the callable regions.
        MISSING are ambiguous variants within the callable regions.
        """
        snps = {
            "FP": [
                "FN_FP_INDEL_SNP",
                "._FP_NOCALL_SNP",
                "FN_FP_SNP_SNP",
                "TP_FP_INDEL_SNP",
                "TP_FP_SNP_SNP",
            ],
            "TP": [
                "TP_._SNP_NOCALL",
                "TP_TP_SNP_INDEL",
                "TP_TP_SNP_SNP",
                "TP_FP_INDEL_SNP",
            ],
            "FN": [
                "FN_._SNP_NOCALL",
                "FN_FP_SNP_INDEL",
                "FN_FP_SNP_SNP",
                "FN_TP_SNP_INDEL",
                "FN_TP_SNP_SNP",
            ],
            "IGNORED": [
                "UNK_UNK_NOCALL_SNP",
                "UNK_UNK_SNP_SNP",
                "UNK_UNK_SNP_INDEL",
                "._N_NOCALL_SNP",
            ],
            "MISSING": [
                "UNK_UNK_SNP_NOCALL",
                "N_N_SNP_SNP",
                "N_._SNP_NOCALL",
            ],
        }
        self.count(type="SNP", patterns_dict=snps)
        self._output_dict.update(self._internal_dict1)
        self.make_proportional(label="SNP")
        self.performance(label="SNPs")
        self._output_dict.update(self._internal_dict2)

    def metric_totals(
        self,
    ):
        """
        Calculate the sum of metrics
        """
        metrics = ["FP", "TP", "FN", "IGNORED", "MISSING"]
        for metric in metrics:
            _sum = sum(v for k, v in self._internal_dict1.items() if metric in k)
            if metric in ["IGNORED", "MISSING"]:
                key = f"{metric}_Total"
            else:
                key = f"{metric}s_Total"

            h.add_to_dict(
                update_dict=self._internal_dict1,
                new_key=key,
                new_val=_sum,
                logger=self.logger,
                logger_msg=self._logger_msg,
            )

            self.make_proportional(label=metric)
        self.performance(label="Total")

    def precision(self, n_TP: int, n_FP: int) -> float:
        """
        Calculates precision -
        """
        return round(n_TP / (n_TP + n_FP), ndigits=6)

    def recall(self, n_TP: int, n_FN: int) -> float:
        """
        Calculates recall -
        """
        return round(n_TP / (n_TP + n_FN), ndigits=6)

    def f1_score(self, precision: float, recall: float) -> float:
        """
        Calculates the F1-Score - the harmonic mean between precision and recall.
        """
        return round(2 * ((precision * recall) / (precision + recall)), ndigits=6)

    def performance(
        self, warning_threshold: float = 0.96, label: Union[str, None] = None
    ) -> None:
        """
        Calculate overall performance metrics including Precision, Recall and the F1-Score (harmonic mean between Precision & Recall).
        """

        if label == "Total":
            TPs = self._internal_dict1[f"TPs_{label}"]
            FPs = self._internal_dict1[f"FPs_{label}"]
            FNs = self._internal_dict1[f"FNs_{label}"]
        else:
            TPs = self._internal_dict1[f"{label}_TPs"]
            FPs = self._internal_dict1[f"{label}_FPs"]
            FNs = self._internal_dict1[f"{label}_FNs"]

        p = self.precision(n_TP=TPs, n_FP=FPs)
        r = self.recall(n_TP=TPs, n_FN=FNs)
        f1 = self.f1_score(precision=p, recall=r)

        self._performance = {
            f"{label}_Precision": p,
            f"{label}_Recall": r,
            f"{label}_F1-Score": f1,
        }

        for k, m in self._performance.items():
            if m < warning_threshold:
                difference = m - warning_threshold
                self.logger.warning(
                    f"{self._logger_msg}: {k} is below threshold ({warning_threshold}) | {k}='{m:.5f}' | delta='{round(difference, ndigits=6)}'"
                )
            else:
                if self.args.debug:
                    self.logger.debug(f"{self._logger_msg}: '{k}={m:.6f}'")
            self._internal_dict2.update(self._performance)

    def check_if_missing_metrics(self) -> None:
        """
        Confirm that no values in raw counts were missed when filtered.
        """
        missing_values = {}
        num_missing_items = 0
        for k, v in self._counts_dict.items():
            if k not in self._processed_keys and k not in self._valid_keys:
                if int(v) > 0:
                    if "._TP" in k:
                        continue
                    else:
                        num_missing_items += 1
                        h.add_to_dict(
                            update_dict=missing_values,
                            new_key=k,
                            new_val=v,
                            logger=self.logger,
                            logger_msg=self._logger_msg,
                        )

        if num_missing_items > 0:
            print("MISSING PATTERNS ------------------------------")
            for k, v in missing_values.items():
                print(f"{k}={v}")
            self._weirdos = list(missing_values.keys())
            self.load_counts_data(re_count=True)
            self.logger.error(
                f"{self._logger_msg}: unexpected patterns detected.\nExiting..."
            )
            sys.exit(1)

    def write_output(self, outfile: Path, out_dict: dict) -> None:
        """
        Either display contents, or write to a new file.
        """
        if self.args.dry_run:
            self.logger.info(
                f"[DRY_RUN] - {self._logger_msg}: metrics by type contents:"
            )

        file = h.WriteFiles(
            str(outfile.parent),
            outfile.name,
            self.logger,
            dryrun_mode=self.args.dry_run,
            logger_msg=self._logger_msg,
        )
        file.check_missing()
        file.write_csv(write_dict=out_dict)

    def run(self) -> None:
        """
        Combine all the steps required to proccess results from hap.py into one step.
        """
        self.load_counts_data()

        if (
            self.convert_happy.final_output_file_csv.exists() is False
            or self.args.dry_run
        ):
            self._output_dict.update(self._metadata)
            self.indel_totals()
            self.snp_totals()
            self.metric_totals()
            self._output_dict.update(self._internal_dict1)
            self.check_if_missing_metrics()
            self._output_dict.update(self._internal_dict2)
            self.write_output(
                outfile=self.convert_happy.final_output_file_csv,
                out_dict=self._output_dict,
            )
        else:
            self.logger.info(
                f"{self._logger_msg}: existing output CSV file already exists | '{self.convert_happy.final_output_file_csv.name}'... SKIPPING AHEAD"
            )


def __init__():
    """
    Open a VCF file and split the INFO field into multiple self._columns.

    Each row represents a genomic position in the cattle genome.

    The self._columns compare the variants between a 'truth' VCF and a 'test' VCF to identify similarities and differences that result after model re-training.
    """
    # Collect command line arguments
    args = args_process_hap.collect_args()

    # Collect start time
    h.Wrapper(__file__, "start").wrap_script(h.timestamp())

    # Create error log
    current_file = os.path.basename(__file__)
    module_name = os.path.splitext(current_file)[0]
    logger = helpers_logger.get_logger(module_name)

    # Check command line args
    args_process_hap.check_args(args, logger)

    if args.dry_run:
        logger.info("flag --dry-run set; metrics will not be written to a file")

    try:
        Process(
            args,
            logger,
        ).run()
    except AssertionError as error:
        print(f"{error}\nExiting...")
        sys.exit(1)

    h.Wrapper(__file__, "end").wrap_script(h.timestamp())


# Execute functions created
if __name__ == "__main__":
    __init__()
