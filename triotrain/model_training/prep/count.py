#!/usr/bin/python3
"""
description: count the variants present in a VCF file

example:
    from model_training.prep.count import count_variants
"""

from logging import Logger
from pathlib import Path
from subprocess import run, Popen, PIPE
from sys import exit
from typing import Dict, List, Union


def count_variants(
    truth_vcf: Path,
    logger_msg: str,
    logger: Logger,
    count_pass: bool = True,
    count_ref: bool = False,
    debug_mode: bool = False,
    use_bcftools: bool = True,
    stats_filter: Union[List[str], str, None] = None,
    
) -> Union[List[str], int, Dict[str, int], None]:
    """
    Use 'bcftools +smpl-stats' to count either REF/REF or PASS positions.
    """
    if count_pass and count_ref:
        awk_filter = "BOTH"
        awk_command = '$1=="FLT0"{hom_ref=$5}$1=="SITE0"{pass=$2}END{print hom_ref,pass}'
    elif count_pass and not count_ref:
        awk_filter = "PASS"
        awk_command = '$1=="SITE0" {print $2}'
    elif not count_pass and count_ref:
        awk_filter = "REF/REF"
        awk_command = '$1=="FLT0" {print $5}'
    else:
        awk_filter = None
        awk_command = None

    if debug_mode and filter is not None:
        logger.debug(
            f"{logger_msg}: applying a filter with awk | '{awk_filter}'",
        )
    
    if stats_filter is None:
        logger.info(
            f"{logger_msg}: all variants included with bcftools | stats_filter='None'",
        )
        _bcftools_cmd = ["bcftools", "+smpl-stats", str(truth_vcf)]
    else:
        if isinstance(stats_filter, list):
            _stats_filter_str = " ".join(stats_filter)
            _stats_filter_list = stats_filter
        elif isinstance(stats_filter, str):
            _stats_filter_str = stats_filter
            _stats_filter_list = stats_filter.split(" ")    
        
        logger.info(
            f"{logger_msg}: applying a filter with bcftools | stats_filter='{_stats_filter_str}'",
        )
        _bcftools_cmd = ["bcftools", "+smpl-stats"] + _stats_filter_list + [str(truth_vcf)]
    
    if debug_mode:
        _cmd_str = " ".join(_bcftools_cmd)
        logger.debug(f"{logger_msg}: bcftools command | '{_cmd_str}'")

    if use_bcftools:
        if debug_mode:
            logger.debug(
                f"{logger_msg}: using 'bcftools +smpl-stats' to count records | '{truth_vcf.name}'",
            )
        if awk_command is None:
            bcftools_smpl_stats = run(
                _bcftools_cmd,
                check=True,
                capture_output=True,
                text=True,
            )

            ## GETTING REALTIME OUTPUT WITH SUBPROCESS ##
            # ---- SOURCE: https://www.endpointdev.com/blog/2015/01/getting-realtime-output-using-python/
            # while True:
            #     output = bcftools_smpl_stats.stdout.readline()
            #     if output == '' and bcftools_smpl_stats.poll() is not None:
            #         break
            #     if output:
            #         print(output.strip())
            # return_code = bcftools_smpl_stats.poll()
            # return return_code

            if debug_mode:
                logger.debug(f"{logger_msg}: done with 'bcftools +smpl-stats'")
            if bcftools_smpl_stats.returncode == 0:
                return str(bcftools_smpl_stats.stdout).split("\n")
            else:
                raise ChildProcessError("Unable to run bcftools +smpl-stats")

        else:
            bcftools_smpl_stats = Popen(
                _bcftools_cmd,
                stdout=PIPE,
            )
            bcftools_awk = run(
                ["awk", str(awk_command)],
                stdin=bcftools_smpl_stats.stdout,
                capture_output=True,
                text=True,
                check=True,
            )

            if bcftools_awk:
                if debug_mode:
                    logger.debug(f"{logger_msg}: done with 'bcftools +smpl-stats'")
                    logger.debug(f"{logger_msg}: extracting counts with awk")
                if awk_filter is not None and "both" in awk_filter.lower():
                    multiple_results = bcftools_awk.stdout.split()
                    if len(multiple_results) != 2:
                        logger.error(
                            f"{logger_msg}: bcftools_awk() subproccess returned an unexpected number of results.\nExiting..."
                        )
                        exit(1)
                    else:
                        num_RR_found = int(multiple_results[0])
                        num_pass_found = int(multiple_results[1])
                        num_variants_found = {
                            "ref/ref": num_RR_found,
                            "pass": num_pass_found,
                        }
                    if debug_mode:
                        logger.debug(f"{logger_msg}: done extracting counts with awk")
                elif awk_filter is not None and "pass" in awk_filter.lower():
                    num_variants_found = int(bcftools_awk.stdout.strip())
                elif awk_filter is not None and "ref" in awk_filter.lower():
                    num_variants_found = int(bcftools_awk.stdout.strip())
                else:
                    num_variants_found = None
            else:
                num_variants_found = None
            return num_variants_found
    else:
        if debug_mode:
            logger.debug(
                f"{logger_msg}: counting records in [{truth_vcf.name}] using awk {command}",
            )
        count = 0
        with open(str(truth_vcf), "r") as count_file:
            for count, line in enumerate(count_file):
                pass
        if count != 0:
            num_variants_found = count + 1
        else:
            num_variants_found = None

        return num_variants_found
