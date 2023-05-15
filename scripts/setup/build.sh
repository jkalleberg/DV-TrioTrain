#!/bin/bash
# scripts/setup/build.sh

# NOTE: Begin an interactive session first!
# source scripts/start_interactive.sh

echo -e "=== scripts/setup/build.sh > start $(date)"

# Load cluster-specific modules
# NOTE: You will need to change this bash script to match your own system modules available
# Reach out to your cluster's sys admin for installation guidelines
source scripts/setup/modules.sh

echo -e "=== scripts/setup/build.sh > end $(date)"