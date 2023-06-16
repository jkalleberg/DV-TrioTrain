# Software Assumptions

If you're unfamiliar with SLURM, navigating your computing cluster, or what shared software is available to you, reach out to your HPC system's Cluster Administrator.

## Prerequisites

* Unix-like operating system (cannot run on Windows)
* Python 3.8
* Access to a SLURM-based High Performance Computing Cluster that has both CPU and GPU resources

## System Requirements

The following software are required:

| Tool           | Version     | | Tool           | Version     |
| ------         | -------     | | ------         | -------     |
| `gcc`          | 10.2.0      | | `cuda`         | 11.1.0      |
| `curl`         | 7.72.0      | | `picard`       | 2.26.10     |
| `minicoda3`    | 4.9         | | `bcftools`     | 1.14        |
| `java/openjdk` | 17.0.3      | | `htslib`       | 1.14        |
| `apptainer`    | 1.1.7-1.el7 | |`samtools`     | 1.14        |

TrioTrain expects the software listed above (modules) to be pre-built, and available locally on your SLURM-based HPC cluster. For example, on the MU Lewis Computing cluster, we can:

```bash
# Search for modules with:
module avail <tool_search_string>

# or
module spider <tool_search_string>

# After confirming a tool is pre-built,
# these modules are loaded in with:
module load <module_name>
```

These locally-available software are loaded via an executable bash helper script (`modules.sh`).

---

## Install TrioTrain

!!! note
    **TrioTrain assumes that the default `modules.sh` script [(view on GitHub)](https://github.com/jkalleberg/DV-TrioTrain/scripts/setup/modules.sh) works for your cluster.**

    If you're building TrioTrain via Github, you will be able to edit `modules.sh` directly to match your system.
    
    However, if you're building TrioTrain via the Python package, you will need to specify an alternative helper script via  `python3 triotrain/model_train/run_trio_train.py --modules </path/to/your/module.sh>`

There are two supported options for DV-TrioTrain:

1. Clone from Github: `git clone git@github.com:jkalleberg/DV-TrioTrain.git`

2. Install the Python package: `pip install triotrain`

---

<font size= "4"> **[Next: Configure TrioTrain >>>](configuration.md)** </font>
