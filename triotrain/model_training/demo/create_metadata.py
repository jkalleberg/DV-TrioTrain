#!/usr/bin/python3
"""
description: creates a demo metadata file from the Human GIAB data downloaded during the walk-through
example:
    python3 triotrain/model_training/demo/create_metadata.py
"""

defaults = {
    "RunOrder": 1,
    "RunName": "demo",
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
    "ChildReadsBAM" : "/triotrain/variant_calling/data/GIAB/bam/HG002.GRCh38.2x250.bam",
    "ChildTruthVCF" : "/triotrain/variant_calling/data/GIAB/benchmark/HG002_GRCh38_1_22_v4.2_benchmark.vcf.gz",
    "ChildCallableBED" : "/triotrain/variant_calling/data/GIAB/benchmark/HG002_GRCh38_1_22_v4.2_benchmark.bed",
    "FatherReadsBAM" : "/triotrain/variant_calling/data/GIAB/bam/HG003.GRCh38.2x250.bam",
    "FatherTruthVCF" : "/triotrain/variant_calling/data/GIAB/benchmark/HG003_GRCh38_1_22_v4.2_benchmark.vcf.gz",
    "FatherCallableBED" : "/triotrain/variant_calling/data/GIAB/benchmark/HG003_GRCh38_1_22_v4.2_benchmark.bed",
    "MotherReadsBAM" : "/triotrain/variant_calling/data/GIAB/bam/HG004.GRCh38.2x250.bam",
    "MotherTruthVCF" : "/triotrain/variant_calling/data/GIAB/benchmark/HG004_GRCh38_1_22_v4.2_benchmark.bed",
    "MotherCallableBED" : "/triotrain/variant_calling/data/GIAB/benchmark/HG004_GRCh38_1_22_v4.2_benchmark.vcf.gz",
    "Test1ReadsBAM" : "/triotrain/variant_calling/data/GIAB/bam/HG005.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.300x.bam",
    "Test1TruthVCF" : "/triotrain/variant_calling/data/GIAB/benchmark/HG005_GRCh38_1_22_v4.2_benchmark.vcf.gz",
    "Test1CallableBED" : "/triotrain/variant_calling/data/GIAB/benchmark/HG005_GRCh38_1_22_v4.2_benchmark.bed",
    "Test2ReadsBAM" : "/triotrain/variant_calling/data/GIAB/bam/HG006.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.100x.bam",
    "Test2TruthVCF" : "/triotrain/variant_calling/data/GIAB/benchmark/HG006_GRCh38_1_22_v4.2_benchmark.vcf.gz",
    "Test2CallableBED" : "/triotrain/variant_calling/data/GIAB/benchmark/HG006_GRCh38_1_22_v4.2_benchmark.bed",
    "Test3ReadsBAM" : "/triotrain/variant_calling/data/GIAB/bam/HG007.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.100x.bam",
    "Test3TruthVCF" : "/triotrain/variant_calling/data/GIAB/benchmark/HG007_GRCh38_1_22_v4.2_benchmark.vcf.gz",
    "Test3CallableBED" : "/triotrain/variant_calling/data/GIAB/benchmark/HG007_GRCh38_1_22_v4.2_benchmark.bed",
    }

for k,v in defaults.items():
    print("KEY:", k, "; VALUE:", v) 