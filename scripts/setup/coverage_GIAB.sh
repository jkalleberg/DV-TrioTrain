#!/bin/bash
# scripts/setup/coverage_GIAB.sh
echo -e "=== scripts/setup/coverage_GIAB.sh > start $(date)"

# NOTES --------------------------------------------------------------#
# The DV developers use the following data in their walk-through docs:
# 1) Reference Genome Version: GRCh38_no_alt_analysis_set.fasta
# 2) Benchmark Sample: HGOO3 [AshkenazimTrio-Father], typically only Chr20.
# 3) PopVCF (without genotypes): v3_missing2ref

# However, for a direct comparision between our cattle model and previous models, we need to calculate Mendelian Inheritance Errors (MIE). Therefore, we will be downloading the parents in this trio. We'll also need to download the reference PopVCF used to build the humanWGS_AF model.

#-------------------------------------------------------------------#
#                            GIAB Trio1                             #
#-------------------------------------------------------------------#
# Known as the Ashkenazi Jew Trio
# From Personal Genome Project
# AJ Son = HG002_NA24385_son
# AJ Father = HG003_NA24149_father
# AJ Mother = HG004_NA24143_mother

#-------------------------------------------------------------------#
#                            GIAB Trio2                             #
#-------------------------------------------------------------------#
# Known as the Han Chinese Trio
# From Personal Genome Project
# Chinese Son = HG005_NA24631_son
# Chinese Father = HG006_NA24694_father
# Chinese Mother = HG007_NA24695_mother

# A preprint describing these calls is at https://doi.org/10.1101/2020.07.24.212712.  The paper(s) above can be cited for use of the benchmark, and please cite http://www.nature.com/articles/sdata201625 (doi:10.1038/sdata.2016.25) when using the corresponding sequencing data.


cd triotrain/variant_calling/data/GIAB/bam

OUTPUT="./mean_coverage.csv"
if [ -f "$OUTPUT" ]
then
    echo "INFO: existing output found | ${OUTPUT}"
else
    echo "INFO: missing output file | ${OUTPUT}"
    echo "sample_id,mean_coverage" > $OUTPUT
    for file in *.coverage; do
        # echo "FILE=${file}"
        SAMPLE_ID=$(echo $file | cut -d "." -f 1)
        echo "INFO: calculating average coverage | ${SAMPLE_ID}"
        # echo "SAMPLE=${SAMPLE_ID}"
        awk -v id="$SAMPLE_ID" 'NR != 1 && NR <26 { total += $7; count++ } END { print id","total/count }' ./$file >> $OUTPUT
    done
fi

echo -e "=== scripts/setup/coverage_GIAB.sh > start $(date)"