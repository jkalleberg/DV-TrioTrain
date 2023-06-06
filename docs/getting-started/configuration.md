# Configuration

To ensure reproducibility, all configuration steps described below are included in a helper script, `build.sh`. However, these configuration steps require some system-specific customization for your HPC cluster.

You can view a [template script for automatically building TrioTrain on Github.](https://github.com/jkalleberg/DV-TrioTrain/scripts/setup/build.sh)

Each configuration step during build uses separate helper scripts. Examples these can also found on [Github, under the scripts/ directory](https://github.com/jkalleberg/DV-TrioTrain/scripts/setup/). **Those which require system-specific alterations are bolded.**

## **1. Begin an interactive session first**

!!! note
    You will need to change this bash script to match your own system modules available. Reach out to your cluster's sys admin with any questions.

This will allow you to run command line code from your terminal/screen.

```bash
source scripts/start_interactive.sh
```

## **2. Load cluster-specific modules**

!!! note
    You will need to change this bash script to match your own system modules available. Reach out to your cluster's sys admin with any questions.

This is how TrioTrain finds the system requirements.

```bash
source scripts/setup/modules.sh
```

## 3. Install Apptainer/Singularity containers

Two (2) versions of DeepVariant containers that are used by TrioTrain:

1. GPU-specific container used for training.
2. CPU-specific container used for all other steps.

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

## 4. Install the Conda environment

This conda environment includes the DeepVariant requirements, such as Apache Beam, Tensorflow, etc.

!!! note
    `source` is used instead of `bash` to by-pass system issues with `conda activate` specific to MU Lewis, which may not be required for your system.

```bash
source scripts/setup/build_beam.sh
```

## 5. Download the Beam shuffling script

Create a local copy of the appropriate shuffling script from Google Genomoics Health Group.

```bash
bash scripts/setup/download_shuffle.sh
```

---

<font size= "4"> **[Next: Complete the Human GIAB Demo >>>](walk-through.md)** </font>
