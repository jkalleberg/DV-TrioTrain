#!/usr/bin/bash
## scripts/setup/modules.sh

echo "=== scripts/setup/modules.sh start > $(date)"

echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Wipe Lewis Modules... "
module purge
echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Done Wipe Lewis Modules"

echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Loading Lewis Modules... "

# Enable loading of pkgs from prior manager
module load rss/rss-2020

# Update to a newer, but still old, version of Curl
module load curl/7.72.0

# Update to a newer version of git,
# Required for Git extensions on VSCode
module load git/2.29.0

# Enable "conda activate" rather than,
# using "source activate"
module load miniconda3/4.9
export CONDA_BASE=$(conda info --base)

# System Requirement to use 'conda activate' 
source ${CONDA_BASE}/etc/profile.d/conda.sh
conda deactivate

# Modules required for re-training
module load java/openjdk/java-1.8.0-openjdk
module load singularity/singularity
module load picard/2.26.10

# Modules required for post-procesing variants
module load cuda/11.1.0
module load bcftools/1.14
module load htslib/1.14
module load samtools/1.14
module load gcc/10.2.0

echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Done Loading Lewis Modules"

echo -e "$(date '+%Y-%m-%d %H:%M:%S') INFO: Conda Base Environment:\n${CONDA_BASE}"
echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Python Version:"
python3 --version
echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Java Version:"
java -version
echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Apptainer Version:"
apptainer --version

# Source DeepVariant version and CACHE Dir
echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Adding Apptainer variables... "
echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: This step is required to build DeepVariant image(s)"

if [ -z "$1" ]
then
    echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Using defaults, DeepVariant version 1.4.0"
    export BIN_VERSION_DV="1.4.0"
    export BIN_VERSION_DT="1.4.0"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Using inputs, DeepVariant version $1"
    export BIN_VERSION_DV="$1"
    export BIN_VERSION_DT="$1"
fi

export APPTAINER_CACHEDIR="${PWD}/APPTAINER_CACHE"
export APPTAINER_TMPDIR="${PWD}/APPTAINER_TMPDIR"
echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Done adding Apptainer variables"

# Confirm that it worked
echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: DeepVariant Version: ${BIN_VERSION_DV}"
echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Apptainer Cache: ${APPTAINER_CACHEDIR}"
echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Apptainer Tmp: ${APPTAINER_TMPDIR}"

# Activating the Bash Sub-Routine to handle errors
echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Loading bash helper functions... "
source scripts/setup/helper_functions.sh
echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Done Loading bash helper functions"

echo "=== scripts/setup/modules.sh > end $(date)"