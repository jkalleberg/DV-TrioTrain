#!/bin/bash
# scripts/setup/build.sh

# NOTE: Begin an interactive session first!
# source scripts/start_interactive.sh

echo -e "=== scripts/setup/build.sh > start $(date)"

# Load cluster-specific modules
# NOTE: You will need to change this bash script to 
# match your own system modules available
# Reach out to your cluster's sys admin for 
# installation guidelines
source scripts/setup/modules.sh

# NOTE: both are required, since can't run the 
# GPU version used for training 
# on a non-GPU hardware

# Install GPU-specific apptainer container
bash scripts/setup/build_containers.sh DeepVariant-GPU

# Install CPU-specific apptainer container
bash scripts/setup/build_containers.sh DeepVariant-CPU

echo -e "=== scripts/setup/build.sh > end $(date)"