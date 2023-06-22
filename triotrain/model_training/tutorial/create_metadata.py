#!/usr/bin/python3
"""
description: creates a tutorial metadata file from the Human GIAB data downloaded during the walk-through
example:
    python3 triotrain/model_training/tutorial/create_metadata.py
"""

import os
import sys
from pathlib import Path
import regex

# get the relative path to the triotrain/ dir
h_path = str(Path(__file__).parent.parent.parent)
sys.path.append(h_path)
import helpers

# Collect start time
helpers.h.Wrapper(__file__, "start").wrap_script(helpers.h.timestamp())

# Create error log
current_file = os.path.basename(__file__)
module_name = os.path.splitext(current_file)[0]
logger = helpers.log.get_logger(module_name)

defaults = {
    "RunOrder": 1,
    "RunName": "Human_tutorial",
    "ChildSampleID": "NA24385",
    "ChildLabID": "HG002",
    "FatherSampleID": "NA24149",
    "FatherLabID": "HG003",
    "MotherSampleID": "NA24695",
    "MotherLabID": "HG004",
    "ChildSex": "M",
    "RefFASTA": "/triotrain/variant_calling/data/GIAB/reference/GRCh38_no_alt_analysis_set.fasta",
    "PopVCF": "/triotrain/variant_calling/data/GIAB/allele_freq/cohort.release_missing2ref.no_calls.vcf.gz",
    "RegionsFile": "NA",
    "ChildReadsBAM": "/triotrain/variant_calling/data/GIAB/bam/HG002.GRCh38.2x250.bam",
    "ChildTruthVCF": "/triotrain/variant_calling/data/GIAB/benchmark/HG002_GRCh38_1_22_v4.2.1_benchmark.vcf.gz",
    "ChildCallableBED": "/triotrain/variant_calling/data/GIAB/benchmark/HG002_GRCh38_1_22_v4.2.1_benchmark.bed",
    "FatherReadsBAM": "/triotrain/variant_calling/data/GIAB/bam/HG003.GRCh38.2x250.bam",
    "FatherTruthVCF": "/triotrain/variant_calling/data/GIAB/benchmark/HG003_GRCh38_1_22_v4.2.1_benchmark.vcf.gz",
    "FatherCallableBED": "/triotrain/variant_calling/data/GIAB/benchmark/HG003_GRCh38_1_22_v4.2.1_benchmark.bed",
    "MotherReadsBAM": "/triotrain/variant_calling/data/GIAB/bam/HG004.GRCh38.2x250.bam",
    "MotherTruthVCF": "/triotrain/variant_calling/data/GIAB/benchmark/HG004_GRCh38_1_22_v4.2.1_benchmark.bed",
    "MotherCallableBED": "/triotrain/variant_calling/data/GIAB/benchmark/HG004_GRCh38_1_22_v4.2.1_benchmark.vcf.gz",
    "Test1ReadsBAM": "/triotrain/variant_calling/data/GIAB/bam/HG005.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.300x.bam",
    "Test1TruthVCF": "/triotrain/variant_calling/data/GIAB/benchmark/HG005_GRCh38_1_22_v4.2.1_benchmark.vcf.gz",
    "Test1CallableBED": "/triotrain/variant_calling/data/GIAB/benchmark/HG005_GRCh38_1_22_v4.2.1_benchmark.bed",
    "Test2ReadsBAM": "/triotrain/variant_calling/data/GIAB/bam/HG006.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.100x.bam",
    "Test2TruthVCF": "/triotrain/variant_calling/data/GIAB/benchmark/HG006_GRCh38_1_22_v4.2.1_benchmark.vcf.gz",
    "Test2CallableBED": "/triotrain/variant_calling/data/GIAB/benchmark/HG006_GRCh38_1_22_v4.2.1_benchmark.bed",
    "Test3ReadsBAM": "/triotrain/variant_calling/data/GIAB/bam/HG007.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.100x.bam",
    "Test3TruthVCF": "/triotrain/variant_calling/data/GIAB/benchmark/HG007_GRCh38_1_22_v4.2.1_benchmark.vcf.gz",
    "Test3CallableBED": "/triotrain/variant_calling/data/GIAB/benchmark/HG007_GRCh38_1_22_v4.2.1_benchmark.bed",
}

cwd = Path.cwd()
output_dict = dict()

for k, v in defaults.items():
    match = regex.search(r"\/triotrain\/variant_calling\/.*", str(v))
    if match:
        helpers.h.add_to_dict(
            update_dict=output_dict,
            new_key=k,
            new_val=f"{cwd}{v}",
            logger=logger,
            logger_msg="[tutorial]"
        )
    else:
        helpers.h.add_to_dict(
            update_dict=output_dict,
            new_key=k,
            new_val=v,
            logger=logger,
            logger_msg="[tutorial]",
        )

output_file = helpers.h.WriteFiles(
    path_to_file=str(cwd / "triotrain" / "model_training" / "tutorial"),
    file=f"GIAB.Human_tutorial_metadata.csv",
    logger=logger,
    logger_msg="[tutorial]",
)

output_file.check_missing()

if output_file.file_exists:
    logger.info("[tutorial]: tutorial metadata file already exists... SKIPPING AHEAD")
else:
    logger.info("[tutorial]: creating a tutorial metadata file now...")
    output_file.add_rows(col_names=output_dict.keys(), data_dict=output_dict)
    output_file.check_missing()
    if output_file.file_exists:
        logger.info("[tutorial]: successfully created the tutorial metadata file")

# Collect end time
helpers.h.Wrapper(__file__, "start").wrap_script(helpers.h.timestamp())
