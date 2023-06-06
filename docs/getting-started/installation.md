# Software Assumptions

## Prerequisites

* Unix-like operating system (cannot run on Windows)
* Python 3.8
* Access to a SLURM-based High Performance Computing Cluster that has both CPU and GPU resources

## System Requirements

If you're unfamiliar with SLURM, navigating your computing cluster, or what shared-software is available to you, reach out to your system's Cluster Administrator.

The following software are required:

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

TrioTrain expects these software packages, referred to as "modules", to be pre-built, and available locally on your SLURM-based HPC cluster. For example, on the MU Lewis Computing cluster, we can:

```bash
# Search for modules with:
module avail <tool_search_string>

# or
module spider <tool_search_string>

# After confirming a tool is pre-build,
# these modules are loaded in with:
module load <module_name>
```

!!! note
    TrioTrain requires a bash helper script, `modules.sh` to find and load the locally-available software.
    
    You can view the [default script on Github.](https://github.com/jkalleberg/DV-TrioTrain/scripts/setup/modules.sh)

    TrioTrain assumes that default `modules.sh` works for your cluster. If you're building TrioTrain via Github, you will be able to edit the `modules.sh` file directly to match your system. However, if you're building TrioTrain via the Python package, you will need to specify an alternative helper script.

    Example:

    ``` bash
    python3 triotrain/model_train/run_trio_train.py --modules </path/to/your/module.sh>
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

---

<font size= "4"> **[Next: Configure TrioTrain >>>](configuration.md)** </font>