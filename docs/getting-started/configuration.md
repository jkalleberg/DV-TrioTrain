# Configuration

!!! warning
    Steps requiring system-specific edits for your HPC cluster will have a warning label.

All configuration steps described below are included in a helper script, `build.sh`.

??? example "Example | `build.sh`"
    ```
    --8<-- "./scripts/setup/build.sh"
    ```

<a name="interactive"></a>

## 1. Begin an interactive session

!!! warning "Requires Customization"

We request resources in a SLURM "interactive session" to allow us to run code at the command line and avoid running resource-intensive code on the login node, which could negatively impact other users.

<font size= "4"> 
**Option 1: Manual**
</font>

Make edits to the following command template to match your system's resources (i.e., add a valid partition and fair-share account).

```bash title="Run the following at the command line:"
srun --pty -p <partition_name> --time=0-06:00:00 --exclusive --mem=0 -A <account_name> /bin/bash
```

<font size= "4"> 
**Option 2: Automated**
</font>

We use the same syntax as above to repeatedly switch between different resources for interactive sessions within a bash script. Edit the provided template to match your system's resources (i.e., add a valid partition and fair-share account).

```bash title="Run the following at the command line:"
source scripts/start_interactive.sh
```

??? example "Example | `start_interactive.sh`"
    ```
    --8<-- "./scripts/start_interactive.sh"
    ```

<a name="modules"></a>

## 2. Load cluster-specific modules

!!! warning "Requires Customization"

This executable is how TrioTrain finds the [required software](installation.md#system-requirements) on your local HPC. TrioTrain will repeatedly use this script to load all modules and the required custom helper functions. Edit the provided template to match your system (i.e., add valid module names).

```bash title="Run the following at the command line:"
source scripts/setup/modules.sh 
```

??? example "Example | `modules.sh`"
    ```
    --8<-- "./scripts/setup/modules.sh"
    ```

??? note "Alternate Versions of DeepVariant"
    Providing a valid version number as the first argument to `modules.sh` will change the version used. Using any version greater than v1.4.0 is untested!


## 3. Install the Conda environment

!!! warning
    **CAUTION:** TrioTrain and DeepVariant require particular package versions, and TrioTrain assumes that a pre-built conda environment is located here: `./miniconda_envs/beam_v2.30`. We cannot support users who opt to make significant changes or deviate from the conda env path at this time.

This conda environment includes the DeepVariant requirements, such as Apache Beam, Tensorflow, etc. The conda environment can take a while to build. We recommend requesting ample memory during your interactive session before proceeding. 

```bash title="Run the following at the command line:"
source scripts/setup/build_beam.sh

# `source` is used instead of `bash` to by-pass system issues with `conda activate` 
# specific to MU Lewis, which may not be required for your system.
```

??? example "Example | `build_beam.sh`"
    ```
    --8<-- "./scripts/setup/build_beam.sh"
    ```

??? success "Confirming the Conda environment build:"

    After building, activate the new environment automatically with - 
    ```bash title="Run the following at the command line:"
    source scripts/start_conda.sh
    ```

    ```bash title="Expected outputs:"
    (beam_v2.30)[jakth2@lewis4-r630-hpc4-node224 DV-TrioTrain]$ 
    ```

    Then, confirm that the help message prints without errors - 
    ```bash title="Run the following at the command line:"
    python3 triotrain/run_trio_train.py --help
    ```

## 4. Download the Beam shuffling script

TrioTrain requires a local copy of the appropriate shuffling script from Google Genomics Health Group.

```bash title="Run the following at the command line:"
bash scripts/setup/download_shuffle.sh
```

??? example "Example | `download_shuffle.sh`"
    ```
    --8<-- "./scripts/setup/download_shuffle.sh"
    ```

## 5. Install Apptainer/Singularity containers

We need local copies of the two (2) versions of DeepVariant containers and one (1) container for `hap.py`:

1. GPU-specific container used for training
2. CPU-specific container used for all other steps
3. `hap.py` - we strongly recommend using a containerized version. This tool uses the depreciated Python v2.7, making it incompatible with either DeepVariant containers or the TrioTrain conda environment.

??? note "Container Versions"
    The GPU and CPU containers are required since you can't run the GPU version used for training on CPU-only hardware.

```bash title="Run the following at the command line:"
# Install GPU-specific DV apptainer container
bash scripts/setup/build_containers.sh DeepVariant-GPU

# Install CPU-specific DV apptainer container
bash scripts/setup/build_containers.sh DeepVariant-CPU

# Install the happ.py apptainer container
bash scripts/setup/build_happy.sh
```

??? example "Example | `build_containers.sh`"
    ```
    --8<-- "./scripts/setup/build_containers.sh"
    ```

??? example "Example | `build_happy.sh`"
    ```
    --8<-- "./scripts/setup/build_happy.sh"
    ```

---

[:material-arrow-left-box: Install TrioTrain](installation.md){ .md-button } [Complete the Human GIAB Tutorial :material-arrow-right-box:](walk-through.md){ .md-button }
