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

# Install the happ.py apptainer container
bash scripts/setup/build_happy.sh

# Download the appropriate shuffling script from Google Genomoics Health Group
bash scripts/setup/download_shuffle.sh

# Download pre-trained models
bash scripts/setup/download_models.sh

# Download GIAB trio data v4.2.1 for benchmarking
bash scripts/setup/download_GIAB.sh

# Install the conda env needed for python package 'triotrain'
source scripts/setup/build_beam.sh

# Create the rtg-tools reference files for the Human ref genome GRCh38
bash scripts/setup/build_rtg_tools.sh

echo -e "=== scripts/setup/build.sh > end $(date)"