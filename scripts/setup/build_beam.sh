#!/bin/bash
# scripts/setup/build_beam.sh

echo -e "=== scripts/setup/build_beam.sh > start $(date)"

##--- NOTE: ----##
##  You must have an interactive session
##  with more mem than defaults to work!
##--------------##

if [ ! -d ./miniconda_envs/beam_v2.30 ] ; then
     # If missing an enviornment called "beam_v2.30", 
     # initalize this env with only the anaconda package 
     conda create --yes --prefix ./miniconda_envs/beam_v2.30
fi

# Then, activate the new environment
source ${CONDA_BASE}/etc/profile.d/conda.sh
conda deactivate
conda activate ./miniconda_envs/beam_v2.30

##--- Configure an environment-specific .condarc file ---##
## NOTE: Only performed once:
# Changes the (env) prompt to avoid printing the full path
conda config --env --set env_prompt '({name})'

# Put the package download channels in a specific order
conda config --env --add channels defaults
conda config --env --add channels bioconda
conda config --env --add channels conda-forge

# Download packages flexibly
conda config --env --set channel_priority flexible

# Install the project-specific packages
# in the currently active env
conda install -p ./miniconda_envs/beam_v2.30 -y -c conda-forge python=3.8 pandas numpy python-dotenv python-snappy tensorflow=2.5 apache-beam=2.30 regex spython natsort rtg-tools python-levenshtein
conda install -p ./miniconda_envs/beam_v2.30 -y -c conda-forge matplotlib seaborn

# Deactivate the conda env to continue with build process
conda deactivate

###===== Notes about Beam specific packages =====###
### Python = Apache Beam Python SDK only supports v3.6-3.8
### Scipy = scientific libraries for Python
### DotEnv = enables environment variable configuration across bash and python
### Snappy = A fast compressor/decompressor (required)
### Apache-Beam = unified programming model for batch and stream processes
### Tensorflow = eval metrics visualizations via TensorBoard for CPU, use v2.5.0 for DV v1.4
### Regex = required for update regular expression handling
### Spython = interface between Singularity/Apptainer bash commands and Python
### Natsort = enables sorting of file iterators
### RTG-Tools = required for Mendelian Inhertiance Error calculations performed for summarize
### Levenshtein = required for checking for typos in command line flags, specifically TrioTrain phase namems

### Matplotlib = publication quality visualizations
### Seaborn = statistical visualizations

echo -e "=== scripts/setup/build_beam.sh > end $(date)"
