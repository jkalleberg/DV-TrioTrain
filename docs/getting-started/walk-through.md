# Human GIAB Tutorial

After completing this demo, you'll know that DV-TrioTrain has been setup correctly on your HPC cluster. This tutorial completes one round of re-training with a Human trio as an example of how to run DV-TrioTrain.

**Again, the bolded items may require tweaking for your specific HPC cluster.
**

## 1. Confirm setup worked

Once you've finished with both the [Installation Guide](installation.md) and the [Configuration Guide](configuration.md), run the following at the command line:

```bash
# Change the working directory
cd DV-TrioTrain

ls

# Output ---------
APPTAINER_CACHE   deepvariant_1.4.0-gpu.sif  docs    hap.py_v0.3.12.sif  miniconda_envs  README.md  triotrain
APPTAINER_TMPDIR  deepvariant_1.4.0.sif      errors  LICENSE             mkdocs.yml      scripts
```

* All executables expect to be run from this `DV-TrioTrain/` directory
* `triotrain/` directory contains Python modules for the DV-TrioTrain package
* `scripts/` directory contains Bash helper scripts and functions that can be used as templates

## **2. Begin an interactive session**

An interactive session ensures you do not run resource-intensive code on the login node, which could negatively impact other users. [You can view the default script on Github.](https://github.com/jkalleberg/DV-TrioTrain/blob/bac33c732065fa7fa1e92097e8f31da383261f4f/scripts/start_interactive.sh)

!!! note
    You will need to change this bash script to match your own system resources. Reach out to your cluster's sys admin with any questions.

    For example, on the MU Lewis Research Compute Cluster, the default `start_interactive.sh` requests an entire compute node with: `srun --pty -p <partition_name> --time=0-06:00:00 --exclusive --mem=0 -A <account_name> /bin/bash`

Assuming you've already edited this script to request the appropriate partition/resources/account for your HPC cluster, run the following at the command line:

```bash
source scripts/start_interactive.sh
```

The GIAB raw data used in this tutorial is relatively large, and thus needs ample memory for downloading and processing. Details about the memory/CPUs available on compute node requested are below:

```bash
# Check the resources for a specific node
scontrol show node <node_name>

# Output ---------
NodeName=<node_name> Arch=x86_64 CoresPerSocket=28
    CPUAlloc=56 CPUErr=0 CPUTot=56 CPULoad=0.68
    AvailableFeatures=(null)
    ActiveFeatures=(null)
    Gres=(null)
    NodeAddr=<node_name> NodeHostName=<node_name> Version=17.02
    OS=Linux RealMemory=509577 AllocMem=509577 FreeMem=256579 Sockets=2 Boards=1
    State=ALLOCATED ThreadsPerCore=2 TmpDisk=0 Weight=1 Owner=N/A MCS_label=N/A
    Partitions=<partition_name>,General  
    CfgTRES=cpu=56,mem=509577M
    AllocTRES=cpu=56,mem=509577M
    CapWatts=n/a
    CurrentWatts=0 LowestJoules=0 ConsumedJoules=0
    ExtSensorsJoules=n/s ExtSensorsWatts=0 ExtSensorsTemp=n/s
```

## **3. Load cluster-specific modules**

The module executable is how TrioTrain finds the system requirements. [You can view the default script on Github.](https://github.com/jkalleberg/DV-TrioTrain/blob/bac33c732065fa7fa1e92097e8f31da383261f4f/scripts/setup/modules.sh)

!!! note
    You will need to change this bash script to match your own system. Reach out to your cluster's sys admin with any questions.

    For example, on the MU Lewis Research Computing Cluster, local software is loaded with `module load <module_name/version>`.

Assuming you've already edited this script to load the [required software](installation.md#system-requirements) that is available on your HPC cluster, run the following at the command line:

```bash
source scripts/setup/modules.sh
```

## 4. Download pre-trained models

Running a local copy of a container requires us to create a local copy of the `model.ckpt` files. [You can view this script on Github.](https://github.com/jkalleberg/DV-TrioTrain/blob/bac33c732065fa7fa1e92097e8f31da383261f4f/scripts/setup/download_models.sh)

Run the following commands at the command line:

```bash
# Downloads both v1.4 default human model, and the v1.4 WGS.AF human model
bash scripts/setup/download_models.sh
```

```bash
# Check the outputs for the v1.4 default human model
ls triotrain/model_training/pretrained_models/v1.4.0_withIS_noAF/

# Output ---------
model.ckpt.data-00000-of-00001  model.ckpt.example_info.json  model.ckpt.index  model.ckpt.meta
```

```bash
# Check the outputs for the v1.4 WGS.AF human model
ls triotrain/model_training/pretrained_models/v1.4.0_withIS_withAF/

# Output ---------
wgs_af.model.ckpt.data-00000-of-00001  wgs_af.model.ckpt.index
wgs_af.model.ckpt.example_info.json    wgs_af.model.ckpt.meta
```

!!! note
    These models are the human-trained models produced by Google Genomics Health Group. An index of the compatible models can be found [here](../user-guide/existing_models.md).

## 5. Download Intermediate GIAB data

Benchmarking requires us to create a local copy of the GIAB trio data v4.2.1.
[You can view this script on Github.](https://github.com/jkalleberg/DV-TrioTrain/blob/bac33c732065fa7fa1e92097e8f31da383261f4f/scripts/setup/download_GIAB.sh)

Run the following command at the command line:

```bash
# Downloads the checksums and intermediate files:
bash scripts/setup/download_GIAB.sh
```

```bash
# Check that GIAB data exist
ls triotrain/variant_calling/data/GIAB

# Output ---------
allele_freq  bam  benchmark  reference
```

Check contents of each of these directories:

```bash
# =====================================================================
# allele_freq/
ls triotrain/variant_calling/data/GIAB/allele_freq/

# Output ---------
cohort-chr10.release_missing2ref.no_calls.vcf.gz      cohort-chr21.release_missing2ref.no_calls.vcf.gz.tbi
cohort-chr10.release_missing2ref.no_calls.vcf.gz.tbi  cohort-chr22.release_missing2ref.no_calls.vcf.gz
cohort-chr11.release_missing2ref.no_calls.vcf.gz      cohort-chr22.release_missing2ref.no_calls.vcf.gz.tbi
cohort-chr11.release_missing2ref.no_calls.vcf.gz.tbi  cohort-chr2.release_missing2ref.no_calls.vcf.gz
cohort-chr12.release_missing2ref.no_calls.vcf.gz      cohort-chr2.release_missing2ref.no_calls.vcf.gz.tbi
cohort-chr12.release_missing2ref.no_calls.vcf.gz.tbi  cohort-chr3.release_missing2ref.no_calls.vcf.gz
cohort-chr13.release_missing2ref.no_calls.vcf.gz      cohort-chr3.release_missing2ref.no_calls.vcf.gz.tbi
cohort-chr13.release_missing2ref.no_calls.vcf.gz.tbi  cohort-chr4.release_missing2ref.no_calls.vcf.gz
cohort-chr14.release_missing2ref.no_calls.vcf.gz      cohort-chr4.release_missing2ref.no_calls.vcf.gz.tbi
cohort-chr14.release_missing2ref.no_calls.vcf.gz.tbi  cohort-chr5.release_missing2ref.no_calls.vcf.gz
cohort-chr15.release_missing2ref.no_calls.vcf.gz      cohort-chr5.release_missing2ref.no_calls.vcf.gz.tbi
cohort-chr15.release_missing2ref.no_calls.vcf.gz.tbi  cohort-chr6.release_missing2ref.no_calls.vcf.gz
cohort-chr16.release_missing2ref.no_calls.vcf.gz      cohort-chr6.release_missing2ref.no_calls.vcf.gz.tbi
cohort-chr16.release_missing2ref.no_calls.vcf.gz.tbi  cohort-chr7.release_missing2ref.no_calls.vcf.gz
cohort-chr17.release_missing2ref.no_calls.vcf.gz      cohort-chr7.release_missing2ref.no_calls.vcf.gz.tbi
cohort-chr17.release_missing2ref.no_calls.vcf.gz.tbi  cohort-chr8.release_missing2ref.no_calls.vcf.gz
cohort-chr18.release_missing2ref.no_calls.vcf.gz      cohort-chr8.release_missing2ref.no_calls.vcf.gz.tbi
cohort-chr18.release_missing2ref.no_calls.vcf.gz.tbi  cohort-chr9.release_missing2ref.no_calls.vcf.gz
cohort-chr19.release_missing2ref.no_calls.vcf.gz      cohort-chr9.release_missing2ref.no_calls.vcf.gz.tbi
cohort-chr19.release_missing2ref.no_calls.vcf.gz.tbi  cohort-chrX.release_missing2ref.no_calls.vcf.gz
cohort-chr1.release_missing2ref.no_calls.vcf.gz       cohort-chrX.release_missing2ref.no_calls.vcf.gz.tbi
cohort-chr1.release_missing2ref.no_calls.vcf.gz.tbi   cohort-chrY.release_missing2ref.no_calls.vcf.gz
cohort-chr20.release_missing2ref.no_calls.vcf.gz      cohort-chrY.release_missing2ref.no_calls.vcf.gz.tbi
cohort-chr20.release_missing2ref.no_calls.vcf.gz.tbi  concat_PopVCFs.sh
cohort-chr21.release_missing2ref.no_calls.vcf.gz      PopVCF.merge.list
# =====================================================================

# bam/ 
ls triotrain/variant_calling/data/GIAB/bam/

# Output ---------
AJtrio.download                                        HCtrio.download  HCtrio.run
AJtrio_Illumina_2x250bps_novoaligns_GRCh37_GRCh38.txt  HCtrio_Illumina300X100X_wgs_novoalign_GRCh37_GRCh38.txt
AJtrio.run                                             HG002_corrected_md5sums.feb19upload.txt  

# =====================================================================

# benchmark/
ls triotrain/variant_calling/data/GIAB/benchmark/

# Output ---------
HG002_GRCh38_1_22_v4.2_benchmark.bed         HG005_GRCh38_1_22_v4.2_benchmark.bed
HG002_GRCh38_1_22_v4.2_benchmark.vcf.gz      HG005_GRCh38_1_22_v4.2_benchmark.vcf.gz
HG002_GRCh38_1_22_v4.2_benchmark.vcf.gz.tbi  HG005_GRCh38_1_22_v4.2_benchmark.vcf.gz.tbi
HG002_README_v4.2.1.txt                      HG005_README_v4.2.1.txt
HG003_GRCh38_1_22_v4.2_benchmark.bed         HG006_GRCh38_1_22_v4.2_benchmark.bed
HG003_GRCh38_1_22_v4.2_benchmark.vcf.gz      HG006_GRCh38_1_22_v4.2_benchmark.vcf.gz
HG003_GRCh38_1_22_v4.2_benchmark.vcf.gz.tbi  HG006_GRCh38_1_22_v4.2_benchmark.vcf.gz.tbi
HG003_README_v4.2.1.txt                      HG006_README_v4.2.1.txt
HG004_GRCh38_1_22_v4.2_benchmark.bed         HG007_GRCh38_1_22_v4.2_benchmark.bed
HG004_GRCh38_1_22_v4.2_benchmark.vcf.gz      HG007_GRCh38_1_22_v4.2_benchmark.vcf.gz
HG004_GRCh38_1_22_v4.2_benchmark.vcf.gz.tbi  HG007_GRCh38_1_22_v4.2_benchmark.vcf.gz.tbi
HG004_README_v4.2.1.txt                      HG007_README_v4.2.1.txt
# =====================================================================

# reference/
ls triotrain/variant_calling/data/GIAB/reference/

# Output ---------
GRCh38_no_alt_analysis_set.fasta  GRCh38_no_alt_analysis_set.fasta.fai  md5checksums.txt
# =====================================================================
```

## 6. Download Raw GIAB data

The following bash scripts are created by `download_GIAB.sh`. They can either be wrapped with SBATCH, or run interactively at the command line if you have enough memory.

```bash
# Merge the per-chr PopVCFs into one PopVCF
bash triotrain/variant_calling/data/GIAB/allele_freq/concat_PopVCFs.sh

# Downloading raw data files for each GIAB trio
bash triotrain/variant_calling/data/GIAB/bam/AJtrio.download 
bash triotrain/variant_calling/data/GIAB/bam/HCtrio.download
```

Check for new outputs in each of these directories:

```bash
# =====================================================================
# allele_freq/
ls triotrain/variant_calling/data/GIAB/allele_freq/ | grep cohort.release

# Output ---------
cohort.release_missing2ref.no_calls.vcf.gz
cohort.release_missing2ref.no_calls.vcf.gz.csi
# =====================================================================

# bam/
ls triotrain/variant_calling/data/GIAB/bam/ | grep HG002

# Output ---------
HG002_corrected_md5sums.feb19upload.txt
HG002.GRCh38.2x250.bam
HG002.GRCh38.2x250.bam.bai
HG002.GRCh38.2x250.bam.bai.md5
HG002.GRCh38.2x250.bam.md5
HG002.GRCh38.2x250.coverage.out

# ---------------------------------------------------------------------
ls triotrain/variant_calling/data/GIAB/bam/ | grep HG003

# Output ---------
HG003.GRCh38.2x250.bam
HG003.GRCh38.2x250.bam.bai
HG003.GRCh38.2x250.bam.bai.md5
HG003.GRCh38.2x250.bam.md5

# ---------------------------------------------------------------------
ls triotrain/variant_calling/data/GIAB/bam/ | grep HG004

# Output ---------
HG004.GRCh38.2x250.bam
HG004.GRCh38.2x250.bam.bai
HG004.GRCh38.2x250.bam.bai.md5
HG004.GRCh38.2x250.bam.md5

# ---------------------------------------------------------------------
ls triotrain/variant_calling/data/GIAB/bam/ | grep HG005

# Output ---------
HG005.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.300x.bam
HG005.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.300x.bam.bai
HG005.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.300x.bam.bai.md5
HG005.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.300x.bam.md5

# ---------------------------------------------------------------------
ls triotrain/variant_calling/data/GIAB/bam/ | grep HG006

# Output ---------
HG006.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.100x.bam
HG006.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.100x.bam.bai
HG006.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.100x.bam.bai.md5
HG006.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.100x.bam.md5

# ---------------------------------------------------------------------
ls triotrain/variant_calling/data/GIAB/bam/ | grep HG007

# Output ---------
HG007.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.100x.bam
HG007.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.100x.bam.bai
HG007.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.100x.bam.bai.md5
HG007.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.100x.bam.md5

# =====================================================================
```

## 7. Sanity Check: calculate average coverage

```bash
bash scripts/start_interactive.sh
. scripts/setup/modules.sh

bash triotrain/variant_calling/data/GIAB/bam/AJtrio.run
bash triotrain/variant_calling/data/GIAB/bam/HCtrio.run
```

## 8. Create supplmentary reference files

After the Human reference genome is downloaded, supplementary files must also be created.

### Reference dictionary file with `picard`

TODO: ADD THIS IN!

### Files for `rtg-tools`

These files are required by `rtg-tools mendelian`. This step is specific to the Human reference genome GRCh38.

```bash
bash scripts/setup/setup_rtg_tools.sh
```

## 9. Create the demo metadata file

```bash
# ensure you're running from the DV-TrioTrain directory!
bash scripts/start_interactive.sh
. scripts/setup/modules.sh
. scripts/start_conda.sh
python triotrain/model_training/demo/create_metadata.py
```
