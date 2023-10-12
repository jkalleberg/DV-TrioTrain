# Installing TrioTrain

!!! warning
    If you're unfamiliar with SLURM, navigating your computing cluster, or what shared software is available to you, reach out to your HPC system's Cluster Administrator for trouble-shooting these dependencies.
## Prerequisites

* Unix-like operating system (cannot run on Windows)
* Python 3.8
* Access to a SLURM-based High Performance Computing Cluster
    - TrioTrain uses both CPU and GPU resources
    - **You must have at least 2 GPU cards on a single compute node to execute re-training effectively!**

## System Requirements

!!! warning
    Deviating from these versions will likely cause errors with TrioTrain. Proceed with caution! 

!!! warning
    If you have to manually install any tools, be sure to add `export PATH=/cluster/path/to/local/software/bin/:$PATH` to your edited `modules.sh` file.

TrioTrain expects the software listed below to be pre-built, and available locally on your SLURM-based HPC cluster. The following minimum software versions are required:

| Tool           | Version     | | Tool           | Version     |
| ------         | -------     | | ------         | -------     |
| `DeepVariant`  | 1.4.0       | |                |             |
| `gcc`          | 10.2.0      | | `cuda`         | 11.1.0      |
| `curl`         | 7.72.0      | | `picard`       | 2.26.10     |
| `minicoda3`    | 4.9         | | `bcftools`     | 1.14        |
| `java/openjdk` | 17.0.3      | | `htslib`       | 1.14        |
| `apptainer`    | 1.1.7-1.el7 | | `samtools`     | 1.14        |


TrioTrain assumes that the default `modules.sh` script works for your cluster, as this is how the pipeline finds all required software. **YOU WILL NEED TO EDIT THIS FILE TO MATCH YOUR CLUSTER**, or specify an alternative helper script by adding the following flag with your cluster-specific script.

```bash title="Add the following flag whenever you run TrioTrain:"
python3 triotrain/model_train/run_trio_train.py --modules </path/to/your/module.sh> 
```

??? example "Example | `modules.sh`"
    ``` 
    --8<-- "./scripts/setup/modules.sh"
    ```

---

## Install TrioTrain

```bash title="Run the following at the command line:"
git clone git@github.com:jkalleberg/DV-TrioTrain.git
```

---

[Configure TrioTrain :material-arrow-right-box:](configuration.md){ .md-button }
