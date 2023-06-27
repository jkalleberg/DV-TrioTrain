# Configuration

To ensure reproducibility, all configuration steps described below are included in a helper script, `build.sh`. However, these configuration steps require some system-specific customization for your HPC cluster.

You can view a [template script for automatically building TrioTrain on Github.](https://github.com/jkalleberg/DV-TrioTrain/scripts/setup/build.sh)

Each configuration step during the build process uses a separate helper script. Examples these can also found on [Github, under the scripts/ directory](https://github.com/jkalleberg/DV-TrioTrain/scripts/setup/).

## 1. Begin an interactive session first

!!! warning
    You will need to tailor this step to match your HPC cluster. Reach out to your system admin with any questions.

We request resource in a SLURM "interactive session" to allow us to run code at the command line and avoid running resource-intensive code on the login node, which could negatively impact other users.

There are two options:

??? example "Option 1: Manual"
    Edit the following SLURM command to match your system's resources (i.e. add a valid partition and fair-share account), and run at the command line.

    ```bash
    srun --pty -p <partition_name> --time=0-06:00:00 --exclusive --mem=0 -A <account_name> /bin/bash
    ```

??? example "Option 2: Automated"
    Using the same syntax as in Option 1 above, edit the [template script](https://github.com/jkalleberg/DV-TrioTrain/blob/bac33c732065fa7fa1e92097e8f31da383261f4f/scripts/start_interactive.sh) to match your system's resources.

    Then, run the following at the command line:

    ```bash
    source scripts/start_interactive.sh
    ```

## 2. Load cluster-specific modules

!!! warning
    You will need to tailor this step to match your HPC cluster. Reach out to your system admin with any questions.

This executable is how TrioTrain finds the [required software](installation.md#system-requirements) on your local HPC. TrioTrain will repeatedly use this script to load all modules and the required bash helper functions. [You can view the template script on GitHub.](https://github.com/jkalleberg/DV-TrioTrain/blob/bac33c732065fa7fa1e92097e8f31da383261f4f/scripts/setup/modules.sh)

Within the template, edit the lines with `module load <module_name/version>` to match your system (i.e. add a valid module name).

Then, run the following at the command line:

```bash
source scripts/setup/modules.sh 
```

## 3. Install Apptainer/Singularity containers

!!! note
    Both the GPU and CPU containers are required, since you can't run the GPU version used for training on a non-GPU hardware.

TrioTrain uses two (2) versions of DeepVariant containers:

1. GPU-specific container used for training.
2. CPU-specific container used for all other steps.

```bash
# Install GPU-specific apptainer container
bash scripts/setup/build_containers.sh DeepVariant-GPU

# Install CPU-specific apptainer container
bash scripts/setup/build_containers.sh DeepVariant-CPU
```

TrioTrain also uses a third container to run `hap.py`, as it requires the depreciated Python v2.7 making it incompatible with either DeepVariant container and the TrioTrain conda environment.

```bash
# Install the happ.py apptainer container
bash scripts/setup/build_happy.sh
```

## 4. Install the Conda environment

This conda environment includes the DeepVariant requirements, such as Apache Beam, Tensorflow, etc. The conda environment can take awhile to build. We recommend requesting ample memory during your interactive session before proceeding.

??? note
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

[:material-arrow-left-box: Install TrioTrain](installation.md){ .md-button } [Complete the Human GIAB Tutorial :material-arrow-right-box:](walk-through.md){ .md-button }
