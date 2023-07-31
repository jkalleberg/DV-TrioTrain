# Installing TrioTrain

## Prerequisites

* Unix-like operating system (cannot run on Windows)
* Python 3.8
* Access to a SLURM-based High Performance Computing Cluster that has both CPU and GPU resources
    - If you're unfamiliar with SLURM, navigating your computing cluster, or what shared software is available to you, reach out to your HPC system's Cluster Administrator.

## System Requirements

The following software are required:

| Tool           | Version     | | Tool           | Version     |
| ------         | -------     | | ------         | -------     |
| `gcc`          | 10.2.0      | | `cuda`         | 11.1.0      |
| `curl`         | 7.72.0      | | `picard`       | 2.26.10     |
| `minicoda3`    | 4.9         | | `bcftools`     | 1.14        |
| `java/openjdk` | 17.0.3      | | `htslib`       | 1.14        |
| `apptainer`    | 1.1.7-1.el7 | |`samtools`     | 1.14        |

TrioTrain expects the software listed above, referred to as modules, to be pre-built, and available locally on your SLURM-based HPC cluster.

For example, on the MU Lewis Computing cluster, we can:

```bash
# Search for modules with:
module avail <tool_search_string>

# or
module spider <tool_search_string>

# After confirming a tool is pre-built,
# these modules are loaded in with:
module load <module_name>
```

These locally-available software are loaded by TrioTrain via an executable bash helper script, referred to as `modules.sh`.

!!! warning
    TrioTrain assumes that the default `modules.sh` script works for your cluster.

---

## Install TrioTrain

Install  DV-TrioTrain by cloning from GitHub:

```bash
git clone git@github.com:jkalleberg/DV-TrioTrain.git
```

Then, either edit [the default modules script](https://github.com/jkalleberg/DV-TrioTrain/blob/f54f83be2aee1b6a39d8e6ca7b2b02dd0e1fa6eb/scripts/setup/modules.sh), or specify an alternative helper script by adding the following flag with need to specify an alternative helper script using:

```bash
python3 triotrain/model_train/run_trio_train.py --modules </path/to/your/module.sh> 
```

---

[Configure TrioTrain :material-arrow-right-box:](configuration.md){ .md-button }
