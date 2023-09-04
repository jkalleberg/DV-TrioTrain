#!/bin/bash
# scripts/setup/build_rtg_tools.sh

echo -e "=== scripts/setup/build_rtg_tools.sh > start $(date)"

##======= Create RTG-TOOLS SDF ======================================##
# required for using rtg-tools 'mendelian'
if [ ! -f ./triotrain/variant_calling/data/GIAB/reference/rtg_tools/reference.txt ]; then
    rtg format -o ./triotrain/variant_calling/data/GIAB/reference/rtg_tools/ ./triotrain/variant_calling/data/GIAB/reference/GRCh38_no_alt_analysis_set.fasta
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: RTG-TOOLS SDF already exists... SKIPPING AHEAD"
fi

echo -e "=== scripts/setup/build_rtg_tools.sh> end $(date)"