#!/bin/bash
## copy_prior_VCFs.sh

### THIS SCRIPT TAKES THES VCFS PRODUCED DURING MODEL TESTING AND CREATES A COPY 
### IN THE SAME LOCATION AS THE PARENT VCFS. THIS IS NECESSARY FOR MIE RATE CALUCATIONS,
### AND TO AVOID REPEADEDLY CALLING VARIANTS IN THE SAME SAMPLES, WITH THE SAME CHECKPOINTS

# declare -A PHASE_NAME=(["Phase1"]="PASS6" ["Phase2"]="PASS9")
declare -A PHASE_NAME=(["Phase1"]="PASS6")

declare -A SAMPLE_NAMES=(["test14"]="UMCUSAM000000341496" ["test15"]="UMCUSAF000000341497" ["test16"]="UMCUSAM000000341713" ["test17"]="UMCUSAM000009341496" ["test18"]="UMCUSAF000009341497" ["test19"]="UMCUSAM000009341713")

for phase in "${!PHASE_NAME[@]}"; do
    echo "--- key: $phase"
    echo "--- value: ${PHASE_NAME[$phase]}"
    for sample in "${!SAMPLE_NAMES[@]}"; do
        cp /storage/hpc/group/UMAG_test/WORKING/jakth2/TRIO_TRAINING_OUTPUTS/240429_NoPopVCF/${PHASE_NAME[$phase]}/test_Mother/$sample-Mother.vcf.gz /storage/hpc/group/UMAG_test/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/240528_Benchmarking/DV1.4_cattle1/${SAMPLE_NAMES[$sample]}.vcf.gz
        cp /storage/hpc/group/UMAG_test/WORKING/jakth2/TRIO_TRAINING_OUTPUTS/240429_NoPopVCF/${PHASE_NAME[$phase]}/test_Mother/$sample-Mother.vcf.gz /storage/hpc/group/UMAG_test/WORKING/jakth2/VARIANT_CALLING_OUTPUTS/240528_Benchmarking/DV1.4_cattle1/${SAMPLE_NAMES[$sample]}.vcf.gz.tbi
    done
done

