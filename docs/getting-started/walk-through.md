# Human GIAB Demo

This demo will enable you to confirm setup worked correctly, and provide you with an example of how to run DV-TrioTrain.

After correctly installing DV-TrioTrain, run the following command at the command line:

```bash
cd DV-TrioTrain
ls
```

You should see the following in this directory:

```bash
APPTAINER_CACHE   deepvariant_1.4.0-gpu.sif  docs    hap.py_v0.3.12.sif  miniconda_envs  README.md  triotrain
APPTAINER_TMPDIR  deepvariant_1.4.0.sif      errors  LICENSE             mkdocs.yml      scripts
```

## **1. Begin an interactive session first**

!!! note
    You will need to change this bash script to match your own system modules available. Reach out to your cluster's sys admin with any questions.

This will allow you to run command line code from your terminal/screen. When running `start_interactive.sh`, an entire compute node was requested for adequate memory of large files:

```bash
source scripts/start_interactive.sh
# srun --pty -p BioCompute --time=0-06:00:00 --exclusive --mem=0 -A schnabellab /bin/bash
# scontrol show node lewis4-r630-htc4-node329
NodeName=lewis4-r630-htc4-node329 Arch=x86_64 CoresPerSocket=28
   CPUAlloc=56 CPUErr=0 CPUTot=56 CPULoad=0.68
   AvailableFeatures=(null)
   ActiveFeatures=(null)
   Gres=(null)
   NodeAddr=lewis4-r630-htc4-node329 NodeHostName=lewis4-r630-htc4-node329 Version=17.02
   OS=Linux RealMemory=509577 AllocMem=509577 FreeMem=256579 Sockets=2 Boards=1
   State=ALLOCATED ThreadsPerCore=2 TmpDisk=0 Weight=1 Owner=N/A MCS_label=N/A
   Partitions=r630-htc4,htc4,BioCompute,General 
   BootTime=2023-05-09T10:44:41 SlurmdStartTime=2023-05-09T10:45:14
   CfgTRES=cpu=56,mem=509577M
   AllocTRES=cpu=56,mem=509577M
   CapWatts=n/a
   CurrentWatts=0 LowestJoules=0 ConsumedJoules=0
   ExtSensorsJoules=n/s ExtSensorsWatts=0 ExtSensorsTemp=n/s
```

## **2. Load cluster-specific modules**

!!! note
    You will need to change this bash script to match your own system modules available. Reach out to your cluster's sys admin with any questions.

This is how TrioTrain finds the system requirements.

```bash
source scripts/setup/modules.sh
```

## 3. Download pre-trained models

Running a local copy of a container requires us to create a local copy of the `model.ckpt` files. Run the following command at the command line:

```bash
bash scripts/setup/download_models.sh
```

You should see the following directories created:

```bash
# ls triotrain/model_training/pretrained_models/
v1.4.0_withIS_noAF  v1.4.0_withIS_withAF
```

The directory contents should include:

```bash
# ls triotrain/model_training/pretrained_models/v1.4.0_withIS_noAF/
model.ckpt.data-00000-of-00001  model.ckpt.example_info.json  model.ckpt.index  model.ckpt.meta
```

```bash
# ls triotrain/model_training/pretrained_models/v1.4.0_withIS_withAF/
wgs_af.model.ckpt.data-00000-of-00001  wgs_af.model.ckpt.index
wgs_af.model.ckpt.example_info.json    wgs_af.model.ckpt.meta
```

!!! note
    These models are the human-trained models produced by Google Genomics Health Group. An index of the models used can be found [here](existing_models.md).

## 4. Download Intermediate GIAB data

Create a local copy of the GIAB trio data v4.2.1 for benchmarking. Run the following command at the command line:

```bash
# Download the checksums and intermediate files
bash scripts/setup/download_GIAB.sh
```

### Expected Intermediate Data Outputs

After completing, you should see the following directories:

```bash
# ls triotrain/variant_calling/data/GIAB
allele_freq  bam  benchmark  reference
```

The contents of the directories BEFORE running SLURM jobs includes:

**1. `allele_freq/`**

```bash
# ls triotrain/variant_calling/data/GIAB/allele_freq/
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
```

**2. `bam/`**

```bash
# ls triotrain/variant_calling/data/GIAB/bam/
AJtrio.download                                        HCtrio.download  HCtrio.run
AJtrio_Illumina_2x250bps_novoaligns_GRCh37_GRCh38.txt  HCtrio_Illumina300X100X_wgs_novoalign_GRCh37_GRCh38.txt
AJtrio.run                                             HG002_corrected_md5sums.feb19upload.txt  
```

**3. `benchmark/`**

```bash
# ls triotrain/variant_calling/data/GIAB/benchmark/
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
```

**4. `reference/`**

```bash
# ls triotrain/variant_calling/data/GIAB/reference/
GRCh38_no_alt_analysis_set.fasta  GRCh38_no_alt_analysis_set.fasta.fai  md5checksums.txt
```

## 5. Download Raw GIAB data

The following commands can either be wrapped with SBATCH, or run interactively at the command line if you have enough memory.

```bash
# Downloading raw data files for each GIAB trio
# ensure you're in the DV-TrioTrain directory!
bash scripts/start_interactive.sh
. scripts/setup/modules.sh

bash triotrain/variant_calling/data/GIAB/allele_freq/concat_PopVCFs.sh
bash triotrain/variant_calling/data/GIAB/bam/AJtrio.download 
bash triotrain/variant_calling/data/GIAB/bam/HCtrio.download
```

### Expected Raw Data Outputs

**1. `allele_freq/`**

```bash
# ls triotrain/variant_calling/data/GIAB/allele_freq/
```

**2. `bam/`**

```bash
# ls triotrain/variant_calling/data/GIAB/bam/

```

## 6. Submit SLURM job to calculate coverage as a sanity check

```bash
bash scripts/start_interactive.sh
. scripts/setup/modules.sh

bash triotrain/variant_calling/data/GIAB/bam/AJtrio.run
bash triotrain/variant_calling/data/GIAB/bam/HCtrio.run
```

## 6. Create supplmentary reference files

After the Human reference genome is downloaded, supplementary files must also be created.

### Reference dictionary file with `picard`

MISSING: ADD THIS IN!

### Files for `rtg-tools`

These files are required by `rtg-tools mendelian`. This step is specific to the Human reference genome GRCh38.

```bash
bash scripts/setup/setup_rtg_tools.sh
```

## 7. Create the demo metadata file

```bash
# ensure you're running from the DV-TrioTrain directory!
bash scripts/start_interactive.sh
. scripts/setup/modules.sh
. scripts/start_conda.sh
python triotrain/model_training/demo/create_metadata.py
```