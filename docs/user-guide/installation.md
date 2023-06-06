# Cofiguring DV-TrioTrain for Your System

## Prerequisites

* Unix-like operating system (cannot run on Windows)
* Python 3.8
* Access to a SLURM-based High Performance Computing Cluster that has both CPU and GPU resources

## System Requirements

If you're unfamiliar with SLURM, navigating your computing cluster, or what shared-software is available to you, reach out to your system's Cluster Administrator.

You can view a template script, `modules.sh`, that is required by TrioTrain on [Github](https://github.com/jkalleberg/DV-TrioTrain/scripts/setup/modules.sh). This helper script is how TrioTrain finds the required software described below. The following HPC modules are required:

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

These are pre-built software packages available locally on the MU Lewis Computing Cluster, loaded in with:

```bash
module load <module_name>
```

On our cluster, we can search for modules with:

```bash
module avail <tool_name>

# or

module spider <tool_name>
```

---

## Install TrioTrain

There are two supported options for DV-TrioTrain:

1. Clone from Github

```bash
git clone git@github.com:jkalleberg/DV-TrioTrain.git
```

1. Install the `triotrain` Python package

```bash
pip install triotrain
```

TrioTrain assumes that modules listed in `scripts/setup/modules.sh` are available. If you're building TrioTrain via Github, you will be able to edit the `modules.sh` file directly to match your system. However, if you're building TrioTrain via the Python package, you will need to specify an alternative `modules.sh` file.

Example:
``` bash
python3 triotrain/model_train/run_trio_train.py --module-file </path/to/your/module.sh>
```

---

## Configuration Walk-Through

To ensure reproducibility, all configuration steps described below are included in a helper script, `build.sh`. However, these configuration steps require some system-specific customization for your HPC cluster. You can view a template of the `build.sh` script used by TrioTrain on [Github](https://github.com/jkalleberg/DV-TrioTrain/scripts/setup/build.sh).

Each configuration step below uses a helper script, examples of which can also found on [Github, under the scripts/ directory](https://github.com/jkalleberg/DV-TrioTrain/scripts/setup/). The ones which require system-specific alterations are bolded.

### **1. Begin an interactive session first**

This will allow you to run command line code from your terminal/screen.

```bash
source scripts/start_interactive.sh
```

### **2. Load cluster-specific modules**

This is how TrioTrain finds the system requirements described above.

```bash
source scripts/setup/modules.sh
```

!!! note
    You will need to change this bash script to match your own system modules available. Reach out to your cluster's sys admin for installation guidelines.


### 3. Install Apptainer/Singularity containers

Two (2) versions of DeepVariant containers that are used by TrioTrain, the DV-GPU for training, and the DV-CPU for all other DV-specific steps.

```bash
# Install GPU-specific apptainer container
bash scripts/setup/build_containers.sh DeepVariant-GPU

# Install CPU-specific apptainer container
bash scripts/setup/build_containers.sh DeepVariant-CPU
```

!!! note
    Both the GPU and CPU containers are required, since you can't run the GPU version used for training on a non-GPU hardware.

A third container is used by TrioTrain, specifically for `hap.py` which currently still uses the depreciated Python v2.7 that makes it incompatible with DeepVariant.

```bash
# Install the happ.py apptainer container
bash scripts/setup/build_happy.sh
```

### 4. Install the Conda environment

This conda environment includes the DeepVariant requirements, such as Apache Beam, Tensorflow, etc.

!!! note
    `source` is used instead of `bash` to by-pass system issues with `conda activate` specific to MU Lewis, which may not be required for your system.

```bash
source scripts/setup/build_beam.sh
```

### 5. Download the Beam shuffling script

Create a local copy of the appropriate shuffling script from Google Genomoics Health Group.

```bash
bash scripts/setup/download_shuffle.sh
```

### 6. Download pre-trained models

Create a local copy of the model.ckpt files, as required by Apptainer. These models are the human-trained models produced by Google Genomics Health Group which are described in detail [here](existing_models.md).

```bash
bash scripts/setup/download_models.sh
```

### 7. Download GIAB data

Create a local copy of the GIAB trio data v4.2.1 for benchmarking.

```bash
bash scripts/setup/download_GIAB.sh
bash triotrain/variant_calling/data/GIAB/bam/AJtrio.download 
bash triotrain/variant_calling/data/GIAB/bam/HCtrio.download 
```

### 8. Create the `rtg-tools` reference files

These files are required by `rtg-tools mendelian`. This step is specific to the Human reference genome GRCh38.

```bash
bash scripts/setup/setup_rtg_tools.sh
```