# Cofiguring DV-TrioTrain for your system

## Prerequisites

* Unix-like operating system (cannot run on Windows)
* Python 3.8
* Access to a SLURM-based High Performance Computing Cluster

### System Requirements

The following HPC modules are required:

| Tool           | Version     |
| ------         | -------     |
| `gcc`          | 10.2.0      |
| `curl`         | 7.72.0      |
| `minicoda3`    | 4.9         |
| `java/openjdk` | 17.0.3      |
| `apptainer`    | 1.1.7-1.el7 |
| `picard`       | 2.26.10     |
| `cuda`         | 11.1.0      |
| `bcftools`     | 1.14        |
| `htslib`       | 1.14        |
| `samtools`     | 1.14        |

These are pre-built software packages available locally on the MU Lewis Computing Cluster, loaded in with `module load <module_name>`. On our cluster, we can search for modules with `module avail <tool_name>` or `module spider <tool_name>`. If you're unfamiliar with SLURM, navigating your computing cluster, or what shared-software is available, reach out to your system's Cluster Administrator.

You can view a template of this `modules.sh` on [Github](https://github.com/jkalleberg/DV-TrioTrain/scripts/setup/modules.sh).

TrioTrain assumes that modules listed in `scripts/setup/modules.sh` are available. If you're building TrioTrain via Github, you will be able to edit the `modules.sh` file directly to match your system. However, if you're building TrioTrain via the Python package, you will need to specify an alternative `modules.sh` file.

Example:
``` bash
python3 triotrain/model_train/run_trio_train.py --module-file </path/to/your/module.sh
```

## Configuration Walk-through

```bash
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

# Install the conda env needed for python package 'triotrain'
source scripts/setup/build_beam.sh

# Download the appropriate shuffling script from Google Genomoics Health Group
bash scripts/setup/download_shuffle.sh

# Download pre-trained models
bash scripts/setup/download_models.sh

# Download GIAB trio data v4.2.1 for benchmarking
bash scripts/setup/download_GIAB.sh

# Create the rtg-tools reference files for the Human ref genome GRCh38
# NOTE: this must be run after download_GIAB!
bash scripts/setup/setup_rtg_tools.sh

echo -e "=== scripts/setup/build.sh > end $(date)"
```