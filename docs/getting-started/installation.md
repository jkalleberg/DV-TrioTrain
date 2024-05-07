# Installing TrioTrain

!!! warning
    If you're unfamiliar with SLURM, navigating your computing cluster, or what shared software is available, contact your HPC system's Cluster Administrator for troubleshoot these dependencies.

## Prerequisites

* Unix-like operating system (cannot run on Windows)
* Python 3.8
* Access to a SLURM-based High-Performance Computing Cluster
    - TrioTrain uses both CPU and GPU resources
    - **You must have at least 2 GPU cards on a single compute node to execute re-training effectively!**


<font size= "4"> 
Confirming the availability of GPU resources on a SLURM cluster:
</font>

??? success "Confirming the availability of GPU resources on a SLURM cluster:"

    If GPU resources are within a SLURM partition called `Gpu` - 
    ```bash title="Run the following at the command line:"
    sinfo -o '|%27n|%15C|%8m|%8z|%35G|' -p Gpu
    ```

    ```bash title="Expected outputs:"
    |HOSTNAMES                  |CPUS(A/I/O/T)  |MEMORY  |S:C:T   |GRES                               |
    |lewis4-z10pg-gpu3-node599  |0/0/16/16      |122534  |2:8:1   |gpu:NVIDIA GeForce GTX 1080 Ti:4   |
    |lewis4-r740xd-gpu4-node887 |3/37/0/40      |379240  |2:20:1  |gpu:Tesla V100-PCIE-32GB:3         |
    |lewis4-r740xd-gpu4-node888 |3/37/0/40      |379240  |2:20:1  |gpu:Tesla V100-PCIE-32GB:3         |
    |lewis4-r740xd-gpu4-node913 |3/41/0/44      |379243  |2:22:1  |gpu:Tesla V100-PCIE-32GB:3         |
    |lewis4-r7525-gpu4-node1011 |3/93/0/96      |509326  |2:48:2  |gpu:Tesla V100S-PCIE-32GB:3        |
    |lewis4-r730-gpu4-node426   |0/20/0/20      |122534  |2:10:1  |gpu:Tesla V100-PCIE-32GB:1         |
    |lewis4-r730-gpu4-node434   |0/20/0/20      |122534  |2:10:1  |gpu:Tesla V100-PCIE-32GB:1         |
    |lewis4-r730-gpu4-node476   |0/20/0/20      |122534  |2:10:1  |gpu:Tesla V100-PCIE-32GB:1         |
    ```

    Note - the `:#` output from the GRES column indicates the number of GPU cards on a specific node. If you have heterogeneous resources, specify GPU nodes with 2+ in `train_eval` phase of the `resource_config.json` file. For further details, see [Configuration page](configuration.md).

    To review further details about a specific compute node  - 
    ```bash title="Run the following at the command line:"
    scontrol show node <hostname>
    ```

## System Requirements

!!! warning
    Deviating from these versions will likely cause TrioTrain errors. Proceed with caution! 

!!! warning
    If you have to install any tools manually, add `export PATH=/cluster/path/to/local/software/bin/:$PATH` to your edited `modules.sh` file.

TrioTrain expects the software listed below to be pre-built and available locally on your SLURM-based HPC cluster. The following software versions are expected:

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
