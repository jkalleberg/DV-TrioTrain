#!/bin/bash
# scripts/setup/build_rtg_tools.sh

echo -e "=== scripts/setup/build_rtg_tools.sh > start $(date)"

##======= Create RTG-TOOLS SDF file ==================================##
# required for using rtg-tools 'mendelian'
if [ ! -f ./triotrain/model_training/data/rtg_tools/human_reference/reference.txt ]; then
    rtg format -o ./triotrain/model_training/data/rtg_tools/human_reference ./triotrain/variant_calling/data/GIAB/reference/GRCh38_no_alt_analysis_set.fasta
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: RTG-TOOLS SDF file already exists... SKIPPING AHEAD"
fi

echo -e "=== scripts/setup/build_rtg_tools.sh> end $(date)"