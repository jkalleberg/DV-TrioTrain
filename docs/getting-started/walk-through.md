# Human GIAB Tutorial

After completing this demo, you'll know that DV-TrioTrain has been setup correctly on your HPC cluster. This tutorial completes one round of re-training with a Human trio as an example of how to run DV-TrioTrain. If you haven't already, go back and complete the previous two guides:  
  
[:material-numeric-1-box: Installation Guide](installation.md){ .md-button }
[:material-numeric-2-box: Configuration Guide](configuration.md){ .md-button }

## 1. Confirm setup worked

Run the following at the command line:

```bash
cd DV-TrioTrain
ls
```

??? success "Expected Output"
    ```bash
    APPTAINER_CACHE   deepvariant_1.4.0-gpu.sif  docs    hap.py_v0.3.12.sif  miniconda_envs  README.md  triotrain
    APPTAINER_TMPDIR  deepvariant_1.4.0.sif      errors  LICENSE             mkdocs.yml      scripts
    ```

    * `triotrain/` directory contains Python modules for the DV-TrioTrain package

    * `scripts/` directory contains Bash helper scripts and functions that can be used as templates

## 2. Begin an interactive session

!!! warning
    You will need to tailor this step to match your HPC cluster. Reach out to your system admin with any questions.

The GIAB raw data we will be using for this tutorial is relatively large, and thus needs ample memory. We request these resource in a SLURM "interactive session" to allow us to run code at the command line and avoid running resource-intensive code on the login node, which could negatively impact other users. Details about the memory/CPUs requested for this tutorial when run on the MU Lewis Computing Cluster can be found in the [User Guide](../user-guide/compute.md).

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

## 3. Load cluster-specific modules

!!! warning
    You will need to tailor this step to match your HPC cluster. Reach out to your system admin with any questions.

This executable is how TrioTrain finds the [required software](installation.md#system-requirements) on your local HPC. TrioTrain will repeatedly use this script to load all modules and the required bash helper functions. [You can view the template script on GitHub.](https://github.com/jkalleberg/DV-TrioTrain/blob/bac33c732065fa7fa1e92097e8f31da383261f4f/scripts/setup/modules.sh)

Within the template, edit the lines with `module load <module_name/version>` to match your system (i.e. add a valid module name).

Then, run the following at the command line:

```bash
source scripts/setup/modules.sh 
```

## 4. Download pre-trained models

Running a local copy of a container requires us to create a local copy of the `model.ckpt` files from v1.4 of DeepVariant. These checkpoints are the human-trained models produced by Google Genomics Health Group. An index with source links for the published models compatible with TrioTrain can be found [here](../user-guide/existing_models.md).

We are downloading two model checkpoints:

* the default human model
* the WGS.AF human model

All the steps to download these data are contained in a single script, which [you can view on Github.](https://github.com/jkalleberg/DV-TrioTrain/blob/bac33c732065fa7fa1e92097e8f31da383261f4f/scripts/setup/download_models.sh)

Run the following at the command line:

```bash
bash scripts/setup/download_models.sh
```

??? success "Expected Output: Default human model"
    ```bash title="Run at the command line"
    ls triotrain/model_training/pretrained_models/v1.4.0_withIS_noAF/
    ```

    ```bash title="Check outputs"
    model.ckpt.data-00000-of-00001  model.ckpt.example_info.json  model.ckpt.index  model.ckpt.meta
    ```

??? success "Expected Output: WGS.AF human model"
    ```bash title="Run at the command line"
    ls triotrain/model_training/pretrained_models/v1.4.0_withIS_withAF/
    ```

    ```bash title="Check outputs"
    wgs_af.model.ckpt.data-00000-of-00001  wgs_af.model.ckpt.index
    wgs_af.model.ckpt.example_info.json    wgs_af.model.ckpt.meta
    ```

## 5. Download Raw Data

We will be using two Human trios from the v4.2.1 GIAB benchmarking data.

| TrioNumber | TrioName     | CommonID | SampleID | Relationship |
| ---------- | ------------ | -------- | -------- | ------------ |
| 1          | AshkenaziJew | HG002    | NA24385  | Son          |
|            |              | HG003    | NA24149  | Father       |
|            |              | HG004    | NA24143  | Mother       |
| 2          | HanChinese   | HG005    | NA24631  | Son          |
|            |              | HG006    | NA24694  | Father       |
|            |              | HG007    | NA24695  | Mother       |

We will be downloading (5) types of raw data:

1. the per-chromosome 1kGP Population Allele Frequency (`.vcf.gz`) with corresponding index file (`.tbi`)
2. sequence data &mdash; checksums (`.md5`) and index files (`.txt`) containing the download paths for:
    1. the aligned reads files (`.bam`)
    1. the corresponding index file (`.bai`)
3. a benchmarking callset (`.vcf.gz`) with corresponding index file (`.tbi`), for each sample
4. a benchmarking regions file (`.bed`) for each sample
5. the GRCh38 reference genome (`.fasta`), with corresponding index file (`.fai`)

All the steps to download these data are contained in a single script, which [you can view on Github.](https://github.com/jkalleberg/DV-TrioTrain/blob/bac33c732065fa7fa1e92097e8f31da383261f4f/scripts/setup/download_GIAB.sh)

Run the following at the command line:

```bash
bash scripts/setup/download_GIAB.sh
```

??? success "Expected Output: GIAB Directories"

    ```bash title="Run at the command line"
    ls triotrain/variant_calling/data/GIAB
    ```

    ```bash title="Check output directories"
    allele_freq  bam  benchmark  reference
    ```

??? success "Expected Raw Data: `allele_freq/`"

    ```bash title="Run at the command line"
    ls triotrain/variant_calling/data/GIAB/allele_freq/
    ```

    ```bash title="Check outputs"
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

??? success "Expected Raw Data: `bam/`"

    ```bash title="Run at the command line"
    ls triotrain/variant_calling/data/GIAB/bam
    ```

    ```bash title="Check outputs"
    AJtrio.download                                        HCtrio.download  
    AJtrio_Illumina_2x250bps_novoaligns_GRCh37_GRCh38.txt  HCtrio_Illumina300X100X_wgs_novoalign_GRCh37_GRCh38.txt
    HG002_corrected_md5sums.feb19upload.txt
    ```

??? success "Expected Raw Data: `benchmark/`"

    ```bash title="Run at the command line"
    ls triotrain/variant_calling/data/GIAB/benchmark/
    ```

    ```bash title="Check outputs"
    HG002_GRCh38_1_22_v4.2.1_benchmark.bed         HG005_GRCh38_1_22_v4.2.1_benchmark.vcf.gz
    HG002_GRCh38_1_22_v4.2.1_benchmark.vcf.gz      HG005_GRCh38_1_22_v4.2.1_benchmark.vcf.gz.tbi
    HG002_GRCh38_1_22_v4.2.1_benchmark.vcf.gz.tbi  HG005_README_v4.2.1.txt
    HG002_README_v4.2.1.txt                      HG006_benchmark.md5
    HG003_GRCh38_1_22_v4.2.1_benchmark.bed         HG006_GRCh38_1_22_v4.2.1_benchmark.bed
    HG003_GRCh38_1_22_v4.2.1_benchmark.vcf.gz      HG006_GRCh38_1_22_v4.2.1_benchmark.vcf.gz
    HG003_GRCh38_1_22_v4.2.1_benchmark.vcf.gz.tbi  HG006_GRCh38_1_22_v4.2.1_benchmark.vcf.gz.tbi
    HG003_README_v4.2.1.txt                      HG006_README_v4.2.1.txt
    HG004_GRCh38_1_22_v4.2.1_benchmark.bed         HG007_benchmark.md5
    HG004_GRCh38_1_22_v4.2.1_benchmark.vcf.gz      HG007_GRCh38_1_22_v4.2.1_benchmark.bed
    HG004_GRCh38_1_22_v4.2.1_benchmark.vcf.gz.tbi  HG007_GRCh38_1_22_v4.2.1_benchmark.vcf.gz
    HG004_README_v4.2.1.txt                      HG007_GRCh38_1_22_v4.2.1_benchmark.vcf.gz.tbi
    HG005_benchmark.md5                          HG007_README_v4.2.1.txt
    HG005_GRCh38_1_22_v4.2.1_benchmark.bed
    ```

??? success "Expected Raw Data: `reference/`"

    ```bash title="Run at the command line"
    ls triotrain/variant_calling/data/GIAB/reference/
    ```

    ```bash title="Check outputs"
    GRCh38_no_alt_analysis_set.fasta  GRCh38_no_alt_analysis_set.fasta.fai  md5checksums.txt
    ```

## 6. Process Raw Data

!!! note
    These scripts can either be wrapped with SBATCH, or run interactively at the command line if you have enough memory. However, each script can take awhile to complete, particularly the `.download` scripts (1hr+). 

In addition to the raw data, `download_GIAB.sh` also creates (3) bash scripts to process raw data into the formats expected by the tutorial:

1. `concat_PopVCFs.sh` + input file `PopVCF.merge.list` &mdash; merges the per-chr VCFs into a single file
2. `AJtrio.download` &mdash; downloads GIAB Trio1
3. `HCtrio.download` &mdash; downloads GIAB Trio2

### a. Merge the PopVCF

We need to create a single, genome-wide PopVCF from the raw per-chromosome PopVCF files. The per-chr Population VCFs were produced by the One Thousand Genomes Project (1kGP) and used to train the Human WGS.AF model. [You can view the raw files on Google Cloud Platform.](https://console.cloud.google.com/storage/browser/brain-genomics-public/research/cohort/1KGP/cohort_dv_glnexus_opt/v3_missing2ref?pageState=(%22StorageObjectListTable%22:(%22f%22:%22%255B%255D%22))&prefix=&forceOnObjectsSortingFiltering=false)

Run the following at the command line:

```bash
bash triotrain/variant_calling/data/GIAB/allele_freq/concat_PopVCFs.sh
```

??? success "Expected Intermediate Data: `allele_freq/`"

    ```bash title="Run at the command line"
    ls triotrain/variant_calling/data/GIAB/allele_freq/ | grep cohort.release
    ```

    ```bash title="Check outputs"
    cohort.release_missing2ref.no_calls.vcf.gz
    cohort.release_missing2ref.no_calls.vcf.gz.csi
    ```

### b. Download GIAB Sequence Data

!!! warning
    The NIST FTP server runs slowly, causing `curl` to timeout. **You may need to run these scripts repeatedly until all data is transfered.**

We need to download the large sequence data files, and confirm they are not corrupted by checking the MD5 checksums, where available. These BAM/BAI files orginate from the GIAB FTP site. [An index of GIAB data created with these samples can be found on GitHub.](https://github.com/genome-in-a-bottle/giab_data_indexes)

Run the following at the command line:

```bash
bash triotrain/variant_calling/data/GIAB/bam/AJtrio.download
```

??? success "Expected Raw Data | HG002:"
    ```bash title="Run at the command line"
    ls triotrain/variant_calling/data/GIAB/bam/ | grep HG002
    ```

    ```bash title="Check outputs"
    HG002_corrected_md5sums.feb19upload.txt
    HG002.GRCh38.2x250.bam
    HG002.GRCh38.2x250.bam.bai
    HG002.GRCh38.2x250.bam.bai.md5
    HG002.GRCh38.2x250.bam.md5
    ```

??? success "Expected Raw Data | HG003:"
    ```bash title="Run at the command line"
    ls triotrain/variant_calling/data/GIAB/bam/ | grep HG003
    ```

    ```bash title="Check outputs"
    HG003.GRCh38.2x250.bam
    HG003.GRCh38.2x250.bam.bai
    HG003.GRCh38.2x250.bam.bai.md5
    HG003.GRCh38.2x250.bam.md5
    ```

??? success "Expected Raw Data | HG004:"
    ```bash title="Run at the command line"
    ls triotrain/variant_calling/data/GIAB/bam/ | grep HG004
    ```

    ```bash title="Check outputs"
    HG004.GRCh38.2x250.bam
    HG004.GRCh38.2x250.bam.bai
    HG004.GRCh38.2x250.bam.bai.md5
    HG004.GRCh38.2x250.bam.md5
    ```

And, run the following at the command line:

```bash
bash triotrain/variant_calling/data/GIAB/bam/HCtrio.download
```

??? success "Expected Raw Data | HG005:"
    ```bash title="Run at the command line"
    ls triotrain/variant_calling/data/GIAB/bam/ | grep HG005
    ```

    ```bash title="Check outputs"
    HG005.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.300x.bam
    HG005.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.300x.bam.bai
    HG005.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.300x.bam.bai.md5
    HG005.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.300x.bam.md5
    ```
??? success "Expected Raw Data | HG006:"
    ```bash title="Run at the command line"
    ls triotrain/variant_calling/data/GIAB/bam/ | grep HG006
    ```

    ```bash title="Check outputs"
    HG006.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.100x.bam
    HG006.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.100x.bam.bai
    HG006.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.100x.bam.bai.md5
    HG006.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.100x.bam.md5
    ```

??? success "Expected Raw Data | HG007:"
    ```bash title="Run at the command line"
    ls triotrain/variant_calling/data/GIAB/bam/ | grep HG007
    ```

    ```bash title="Check outputs"
    HG007.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.100x.bam
    HG007.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.100x.bam.bai
    HG007.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.100x.bam.bai.md5
    HG007.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.100x.bam.md5
    ```

## 7. Create TrioTrain Inputs

There are (3) required input files we must create before we can run TrioTrain. [Complete details about all required data can be found in the TrioTrain User Guide.](../user-guide/usage_guide.md#assumptions)

### a. [Reference Dictionary File (`.dict`)](../user-guide/usage_guide.md#required-raw-data)

!!! warning
    This step is specific to the Human reference genome GRCh38 as cattle-specific input files are packaged with TrioTrain. **If you are working with a new species, you will need to create this file for your reference genome.**

We need a reference dictionary file in the same directory as the reference genome. This file defines the genomic co-ordinates possible with TrioTrain's region shuffling. By default, region shuffling will only use the autosomes and X chromosome. However, you can expand or contract the shuffling area by providing an alternative region file (`.bed`) in the [metadata file (`.csv`).](#b-metadata-file-csv)

Run at the command line:

```bash
picard CreateSequenceDictionary \
    --REFERENCE ./triotrain/variant_calling/data/GIAB/reference/GRCh38_no_alt_analysis_set.fasta \
    --OUTPUT ./triotrain/variant_calling/data/GIAB/reference/GRCh38_no_alt_analysis_set.dict \
    --SPECIES human
```

??? success "Expected Output:"
    ```bash title="Run at the command line"
    ls triotrain/variant_calling/data/GIAB/reference/ | grep .dict
    ```

    ```bash title="Check output"
    GRCh38_no_alt_analysis_set.dict
    ```

### b. [Metadata file (`.csv`)](../user-guide/usage_guide.md#providing-required-data-to-triotrain)

We also need a metadata file to tell TrioTrain where to find all of previously downloaded Human GIAB data. This file contains pedigree information, and the absolute paths for file inputs. Absolute paths are required to help the Apptainer/Singularity containers identify local files. [Formatting specifications for this required input can be found in the TrioTrain User Guide.](../user-guide/usage_guide.md#metadata-format)

For the tutorial, we've created a helper script to automatically create an example of this file. This script uses expectations of where the tutorial data are stored to add local paths. However, outside of the tutorial, the metadata file is a user-created input.

Run the following at the command line:

```bash
source ./scripts/start_conda.sh                 # Ensure the previously built conda env is active
python triotrain/model_training/tutorial/create_metadata.py
```

??? success "Expected Output:"
    ```bash title="Run at the command line"
    ls triotrain/model_training/tutorial
    ```

    ```bash title="Check output"
    create_metadata.py  GIAB.Human_tutorial_metadata.csv  __init__.py  resources_used.json
    ```

### c. [SLURM Resource Config File (`.json`)](../user-guide/usage_guide.md#configuring-slurm-resources)

The last required input we need for TrioTrain is the SLURM resource config file (`.json`). This file tells TrioTrain what resources to request from your HPC cluster when submitting SLURM jobs. [Formatting specifications for this required input can be found in the TrioTrain User Guide.](../user-guide/usage_guide.md#resource-config-format)

??? example "Example | Resource Config File"
    ``` title="triotrain/model_training/tutorial/resources_used.json"
    --8<-- "./triotrain/model_training/tutorial/resources_used.json"
    ```

The hardware listed for each phase in the above example (e.g. mem, ntasks, gpus, etc.) are provided to illustrate which phases are memory intensive, but should not be interpretedate as the minimum or the optimum resources required for each phase. The MU Lewis Research Computing Cluster is heterogenous, so several of the example phases request resources to maximize the number of compute nodes possible.

For the tutorial, copy the above example into a new file, and manually edit the SBATCH parameters to match your HPC cluster (i.e. changing the partition list, account, and email address).

```bash
cp ./triotrain/model_training/tutorial/resources_used.json </path/to/new_file.json>
vi </path/to/new_file.json>     # update resources manually 
```

### d. *(OPTIONAL)* Reference Sequence Data File

!!! warning
    This step is specific to the Human reference genome GRCh38. Cattle-specific input files are packaged with TrioTrain. **If you are working with a new species, you will need to create this file for your reference genome.**

If you have trio-binned test genomes, TrioTrain can help calculate Mendelian Inheritance Error rate using `rtg-tools mendelian`. However, you must create a Sequence Data File (SDF) for each reference genome in the same directory as the reference genome in a sub-directory called `rtg_tools/`. Additional details about `rtg-tools` can be [found on GitHub](https://github.com/RealTimeGenomics/rtg-tools), or by [reviewing the PDF documentation here](https://cdn.rawgit.com/RealTimeGenomics/rtg-tools/master/installer/resources/tools/RTGOperationsManual.pdf).

To create the Human reference SDF, run the following at the command line:

```bash

source ./scripts/start_conda.sh     # Ensure the previously built conda env is active
bash scripts/setup/setup_rtg_tools.sh
```

Use the following template 

??? example "Example | Creating the SDF"
    ```bash title="./scripts/setup/setup_rtg_tools.sh"
    --8<-- "scripts/setup/setup_rtg_tools.sh"
    ```

---

## 8. Run Shuffling Demo

```bash
python3 triotrain/run_trio_train.py                                         \
    -g Father                                                               \
    -m triotrain/model_training/tutorial/GIAB.Human_tutorial_metadata.csv   \
    -n demo                                                                 \
    -r triotrain/model_training/tutorial/resources_used.json                \
    --demo-mode                                                             \
    --demo-chr 21                                                           \
    --num-tests 3                                                           \
    --custom-checkpoint triotrain/model_training/pretrained_models/v1.4.0_withIS_withAF/wgs_af.model.ckpt \
    --output ../TUTORIAL                                                    \
    --dry-run                                                               
```

