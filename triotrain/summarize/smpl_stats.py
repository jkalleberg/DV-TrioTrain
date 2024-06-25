#!/bin/python3
"""
description: 

"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from sys import path
from typing import TYPE_CHECKING, Dict, List, TextIO, Union


# if TYPE_CHECKING:
#     from logging import Logger


abs_path = Path(__file__).resolve()
module_path = str(abs_path.parent.parent)
path.append(module_path)

from helpers.files import WriteFiles
from model_training.prep.count import count_variants
from pantry import prepare
from summary import SummarizeResults
from summarize.mie import MIE
from summarize._args import check_args, collect_args


@dataclass
class Stats:

    # required parameters
    pickled_data: SummarizeResults

    # optional values
    run_iteractively: bool = False

    # imutable, internal parameters
    _num_samples: int = field(default=0, init=False, repr=False)
    _stats: List[Dict[str, str]] = field(default_factory=list, init=False, repr=False)

    def find_stats_output(self) -> None:
        """
        Check for an existing .STATS file.
        """
        _new_file = Path(
            f"{self.pickled_data._input_file._test_file.clean_filename}.STATS"
        )

        self.pickled_data.output_file.logger.info(
            f"{self.pickled_data.output_file.logger_msg}: searching for existing file | '{_new_file}'"
        )
        self._output = WriteFiles(
            _new_file.parent,
            _new_file.name,
            logger=self.pickled_data._input_file.logger,
            logger_msg=self.pickled_data._input_file.logger_msg,
            debug_mode=self.pickled_data._input_file.debug_mode,
            dryrun_mode=self.pickled_data._input_file.dryrun_mode,
        )
        self._output._test_file.check_existing(
            logger_msg=self.pickled_data._input_file.logger_msg
        )
        self._output.file_exists = self._output._test_file.file_exists

    def get_sample_stats(self) -> None:
        """
        Produce bcftools +smpl-stats for each sample in metadata file, if missing the .STATS file.
        """
        if self.run_iteractively:
            self.pickled_data.output_file.logger.info(
                f"{self.pickled_data.output_file.logger_msg}: running 'bcftools +smpl-stats' | '{self.pickled_data._input_file.file_path.name}'"
            )
            self._smpl_stats = count_variants(
                self.pickled_data._input_file.file_path,
                self.pickled_data._input_file.logger_msg,
                logger=self.pickled_data._input_file.logger,
                count_pass=False,
                count_ref=False,
                debug_mode=self.pickled_data._input_file.debug_mode,
            )
        else:
            self._smpl_stats = [
                "bcftools",
                "+smpl-stats",
                "--output",
                self._output.file,
                self.pickled_data._input_file._test_file.file,
            ]

    def process_stats(self, data: Union[list, TextIO]) -> None:
        """
        Save only the FLT0 line values as a dictionary.
        """
        self._header_keys = [
            "sampleID",
            "num_pass_filter",
            "num_non_ref",
            "num_hom_ref",
            "num_hom_alt",
            "num_het",
            "num_hemi",
            "num_snv",
            "num_indel",
            "num_singleton",
            "num_missing",
            "num_transitions",
            "num_transversions",
            "ts_tv",
        ]

        for line in data:
            if line.startswith("FLT"):
                self._num_samples += 1
                _data_dict = {}
                line_values = line.split()[1:]  # Excludes the FLT0 field
                for i, v in enumerate(line_values):
                    _data_dict[self._header_keys[i]] = v

                # make sure no sampleID values are 'default'
                # if _data_dict["sampleID"] == "default":
                #     _data_dict["sampleID"] = self.pickled_data.sample_metadata[
                #         "sampleID"
                #     ]

                if int(_data_dict["num_hom_alt"]) == 0:
                    _data_dict["hets_homalts"] = ""
                else:
                    het_homalt_ratio = int(_data_dict["num_het"]) / int(
                        _data_dict["num_hom_alt"]
                    )
                _data_dict["hets_homalts"] = f"{het_homalt_ratio:.2f}"

                if int(_data_dict["num_indel"]) == 0:
                    _data_dict["snvs_indels"] = ""
                else:
                    snv_indel_ratio = int(_data_dict["num_snv"]) / int(
                        _data_dict["num_indel"]
                    )
                _data_dict["snvs_indels"] = f"{snv_indel_ratio:.2f}"
                self._stats.append(_data_dict)
            else:
                # Skip any unnecessary lines in output
                pass

    def test_process_stats(self) -> None:
        """
        Confirm that at least one sample was processed.
        """
        if self._num_samples > 0:
            self.pickled_data._input_file.logger.info(
                f"{self.pickled_data._input_file.logger_msg}: processed {self._num_samples} files"
            )
        else:
            self.pickled_data._input_file.logger.error(
                f"{self.pickled_data._input_file.logger_msg}: {self._num_samples} files processed"
            )

    def add_metadata(self) -> None:
        """
        Merge the user-provided metadata with sample_stats
        """
        if isinstance(self.pickled_data.sample_metadata, dict):
            clean_metadata = {
                key: val
                for key, val in self.pickled_data.sample_metadata.items()
                if key != "file_path"
            }
            clean_stats = self._stats[0]
            self._merged_data = {**clean_metadata, **clean_stats}
        else:
            clean_metadata = [
                {key: val for key, val in d.items() if key != "file_path"}
                for d in self.pickled_data.sample_metadata
            ]

            rekeyed_metadata = OrderedDict({d["sampleID"]: d for d in clean_metadata})
            rekeyed_statsdata = {d["sampleID"]: d for d in self._stats}
            combined = OrderedDict()

            for key in rekeyed_metadata:
                temp = rekeyed_metadata[key]
                temp.update(rekeyed_statsdata[key])
                combined[key] = temp

            self._merged_data = list(combined.values())

    # def write_output(self, unique_records_only: bool = False) -> None:
    #     """
    #     Save the combined metrics to a new CSV output, or display to screen.
    #     """
    #     self.pickled_data.output_file._test_file.check_existing()

    #     if unique_records_only and self.pickled_data.output_file._test_file.file_exists:
    #         with open(str(self.pickled_data.output_file.file_path), "r") as file:
    #             dict_reader = DictReader(file)
    #             current_records = list(dict_reader)

    #         for r in current_records:
    #             if isinstance(self._merged_data, list):
    #                 if r in self._merged_data:
    #                     if self.pickled_data._input_file.debug_mode:
    #                         self.pickled_data._input_file.logger.debug(
    #                             f"{self.pickled_data._input_file.logger_msg}: skipping a previously processed file | '{self.pickled_data._input_file.file}'"
    #                         )
    #                     self.pickled_data._input_file.logger.info(
    #                         f"{self.pickled_data._input_file.logger_msg}: data has been written previously... SKIPPING AHEAD"
    #                     )
    #                     return
    #                 else:
    #                     continue

    #             else:
    #                 if self._merged_data == r:
    #                     if self.pickled_data._input_file.debug_mode:
    #                         self.pickled_data._input_file.logger.debug(
    #                             f"{self.pickled_data._input_file.logger_msg}: skipping a previously processed file | '{self.pickled_data._input_file.file}'"
    #                         )
    #                     self.pickled_data._input_file.logger.info(
    #                         f"{self.pickled_data._input_file.logger_msg}: data has been written previously... SKIPPING AHEAD"
    #                     )
    #                     return
    #                 else:
    #                     continue

    #     # ensure that output doesn't have duplicate sampleID column
    #     if isinstance(self._merged_data, dict):
    #         col_names = list(self._merged_data.keys())
    #         self.pickled_data.output_file.add_rows(
    #             col_names=col_names, data_dict=self._merged_data
    #         )
    #     else:
    #         for row in self._merged_data:
    #             col_names = list(row.keys())
    #             self.pickled_data.output_file.add_rows(
    #                 col_names=col_names, data_dict=row
    #             )

    #     # self._num_processed += 1

    def save_stats(self) -> None:
        """
        If sample stats data was created, save the new format.

        Otherwise, returns a SLURM job command list.
        """
        self.find_stats_output()

        if self._output.file_exists:
            with open(self._output.file_path, "r") as stats_data:
                self.process_stats(data=stats_data)
            self.test_process_stats()
        else:
            self.get_sample_stats()
            if self.run_iteractively:
                if (
                    self._output.file_exists is False
                    and self.pickled_data._input_file.dryrun_mode is False
                ):
                    self._output.write_list(line_list=self._smpl_stats)
                self.process_stats(data=self._smpl_stats)  # type: ignore
                self.test_process_stats()
            else:
                return

        self.add_metadata()

        if self.pickled_data._input_file.dryrun_mode:
            self.pickled_data._input_file.logger.info(
                f"[DRY RUN] - {self.pickled_data._input_file.logger_msg}: pretending to add {self._num_samples} rows to a CSV | '{self.pickled_data.output_file.file}'"
            )
            print("---------------------------------------------")
            if isinstance(self._merged_data, list):
                print(",".join(self._merged_data[0].keys()))
                for sample in self._merged_data:
                    print(",".join(sample.values()))
            else:
                print(",".join(self._merged_data.keys()))
                print(",".join(self._merged_data.values()))

        else:
            self.write_output(unique_records_only=True)


def __init__() -> None:
    from os import path as p

    from helpers.utils import get_logger
    from helpers.wrapper import Wrapper, timestamp

    # Collect command line arguments
    args = collect_args(postprocess=True)

    # Collect start time
    Wrapper(__file__, "start").wrap_script(timestamp())

    # Create error log
    current_file = p.basename(__file__)
    module_name = p.splitext(current_file)[0]
    logger = get_logger(module_name)

    # Check command line args
    check_args(args, logger=logger, postprocess=True)

    try:
        new_data = prepare(pickled_path=Path(args.pickle_file))
        
        new_data.output_file.logger = logger
        new_data.output_file.debug_mode = args.debug
        new_data.output_file.dryrun_mode = args.dry_run
        
        if args.dry_run:
            new_data.output_file.logger_msg = f"[DRY_RUN] - [post_process]"
        else:
            new_data.output_file.logger_msg = f"[post_process]"
        new_data.check_file_path()

        _get_mie = MIE(args, logger)
        _get_mie._summary._pickled_data = new_data
        _get_mie._summary._logger_msg = new_data.output_file.logger_msg
        _get_mie.args = new_data.args
        _get_mie.process_sample(itr=new_data._index,row_data=new_data.sample_metadata[0])

        run_stats = Stats(pickled_data=new_data, run_iteractively=True)
        run_stats.save_stats()
    except AssertionError as E:
        logger.error(E)

    Wrapper(__file__, "end").wrap_script(timestamp())


# Execute functions created
if __name__ == "__main__":
    __init__()
