#!/usr/bin/bash
# deep-variant/results/v1.4.0/R_visuals/data

cd /Users/JAKTH2/Documents/Graduate_School/Research/deep-variant/results/v1.4.0/R_visuals/data

declare -a training_genomes=( "Father" "Mother" )

# Downloading raw .metrics files from the best checkpoints onto my local machine
for i in $(seq 1 15); do
    for t in ${training_genomes[@]}; do
        scp lewis42:/storage/hpc/group/UMAG_test/WORKING/jakth2/TRIO_TRAINING_OUTPUTS/220913_NewTrios/PASS${i}/train_${t}/eval_Child/best_checkpoint.metrics ./trio${i}.${t}.best_checkpoint.metrics
    done
done