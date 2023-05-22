#!/bin/bash
# scripts/setup/download_shuffle.sh
echo -e "=== scripts/setup/download_shuffle.sh > start $(date)"

##======= Download Shuffle Script =================================##
export SHUFFLE_VERSION=${BIN_VERSION_DV:0:3}

echo "INFO: Downloading Google Beam Shuffling Script - v${SHUFFLE_VERSION}"
curl -C - https://raw.githubusercontent.com/google/deepvariant/r${SHUFFLE_VERSION}/tools/shuffle_tfrecords_beam.py -o triotrain/model_training/prep/shuffle_tfrecords_beam.py

##=================================================================##

echo -e "=== scripts/setup/download_shuffle.sh > end $(date)"