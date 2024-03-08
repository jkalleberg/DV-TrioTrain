# Human GIAB Tutorial

<font size= "4"> 
**This tutorial completes one round of re-training with a Human trio from GIAB.**
</font>

!!! warning "Warning | Storage Needs"
    Completing this tutorial will produce ~2T of intermediate and output data. Ensure you  have sufficient space before proceeding!

## 1. Confirm Successful Configuration

??? success "Check | Installation"
    ```bash title="Run the following at the command line:"
    cd DV-TrioTrain
    ls
    ```

    ```bash title="Expected outputs:"
    deepvariant_1.4.0-gpu.sif  docs    hap.py_v0.3.12.sif  miniconda_envs  README.md  triotrain
    deepvariant_1.4.0.sif      errors  LICENSE             mkdocs.yml      scripts
    ```

    * `triotrain/` directory contains Python modules for the DV-TrioTrain package

    * `scripts/` directory contains Bash helper scripts and functions that can be used as templates

## 2. Activate Environment

Repeat the first two steps of Configuration:

- [Step 1: Interactive Session](configuration.md#interactive)
- [Step 2: Load Modules](configuration.md#modules)


## 4. Download pre-trained models

!!! warning "Warning | Download Size"

Running a local copy of a container requires us to create a local copy of the `model.ckpt` files from v1.4.0 of DeepVariant. These checkpoints are the human-trained models produced by Google Genomics Health Group. [Details about published models compatible with TrioTrain can be found here](../user-guide/existing_models.md).

We need to download (2) two model checkpoints:

* the default human model
* the WGS.AF human model


```bash title="Run the following at the command line:"
bash scripts/setup/download_models.sh
```

??? example "Example | `download_models.sh`"
    ```
    --8<-- "./scripts/setup/download_models.sh"
    ```

??? success "Check | Default human model"
    ```bash title="Run the following at the command line:"
    ls triotrain/model_training/pretrained_models/v1.4.0_withIS_noAF/
    ```

    ```bash title="Expected outputs:"
    model.ckpt.data-00000-of-00001  model.ckpt.example_info.json  model.ckpt.index  model.ckpt.meta
    ```

??? success "Check | WGS.AF human model"
    ```bash title="Run the following at the command line:"
    ls triotrain/model_training/pretrained_models/v1.4.0_withIS_withAF/
    ```

    ```bash title="Expected outputs:"
    wgs_af.model.ckpt.data-00000-of-00001  wgs_af.model.ckpt.index
    wgs_af.model.ckpt.example_info.json    wgs_af.model.ckpt.meta
    ```

## 5. Download Raw Data

!!! warning "Warning | Download Size"

We are using two Human trios from the v4.2.1 GIAB benchmarking data.

| TrioNumber | TrioName     | CommonID | SampleID | Relationship |
| ---------- | ------------ | -------- | -------- | ------------ |
| 1          | AshkenaziJew | HG002    | NA24385  | Son          |
|            |              | HG003    | NA24149  | Father       |
|            |              | HG004    | NA24143  | Mother       |
| 2          | HanChinese   | HG005    | NA24631  | Son          |
|            |              | HG006    | NA24694  | Father       |
|            |              | HG007    | NA24695  | Mother       |

We need (5) types of raw data:

| Number | Description | Extension | 
| ------ | ----------- | --------- |
| 1.     | the GRCh38 reference genome | `.fasta`, `.fai` | 
| 2.     | 1kGP Population Allele Frequency, with index file | `.vcf.gz`, `vcf.gz.tbi` | 
| 3.     | benchmarking files | |
|        | per-genome truth callsets, with index files | `.vcf.gz`, `vcf.gz.tbi` | 
|        | per genome truth regions file | `.bed` |
| 4.     | sample metadata | |
|        | checksums file  | `.md5` |
|        | index files | `.txt` | 
| 5.     | the aligned reads files, with index file | `.bam`, `.bai` |


```bash title="Run the following at the command line:"
bash scripts/setup/download_GIAB.sh
```

??? example "Example | `download_GIAB.sh`"
    ```
    --8<-- "./scripts/setup/download_GIAB.sh"
    ```

??? success "Check | Data Directories"

    ```bash title="Run the following at the command line:"
    ls triotrain/variant_calling/data/GIAB
    ```

    ```bash title="Expected new directories:"
    allele_freq  bam  benchmark  reference
    ```

??? success "Check | `allele_freq/`"

    ```bash title="Run the following at the command line:"
    ls triotrain/variant_calling/data/GIAB/allele_freq/
    ```

    ```bash title="Expected outputs:"
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

??? success "Check | `bam/`"

    ```bash title="Run the following at the command line:"
    ls triotrain/variant_calling/data/GIAB/bam
    ```

    ```bash title="Expected outputs:"
    AJtrio.download                                        HCtrio.download  
    AJtrio_Illumina_2x250bps_novoaligns_GRCh37_GRCh38.txt  HCtrio_Illumina300X100X_wgs_novoalign_GRCh37_GRCh38.txt
    HG002_corrected_md5sums.feb19upload.txt
    ```

??? success "Check | `benchmark/`"

    ```bash title="Run the following at the command line:"
    ls triotrain/variant_calling/data/GIAB/benchmark/
    ```

    ```bash title="Expected outputs:"
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

??? success "Check | `reference/`"

    ```bash title="Run the following at the command line:"
    ls triotrain/variant_calling/data/GIAB/reference/
    ```

    ```bash title="Expected outputs:"
    GRCh38_no_alt_analysis_set.fasta  GRCh38_no_alt_analysis_set.fasta.fai  md5checksums.txt
    ```

??? success "Check | Processing Raw Data Scripts"
    In addition to the raw data, `download_GIAB.sh` also creates (3) bash scripts to process raw data into the formats expected by the tutorial:

    1. `concat_PopVCFs.sh` + input file `PopVCF.merge.list` &mdash; merges the per-chr VCFs into a single file
    2. `AJtrio.download` &mdash; downloads GIAB Trio1
    3. `HCtrio.download` &mdash; downloads GIAB Trio2

## 6. Process Raw Data

!!! note
    These scripts can either be wrapped with SBATCH, or run interactively at the command line if you have enough memory. However, each script can take awhile to complete, particularly the `.download` scripts (1hr+).

### a. Merge the PopVCF

!!! warning "Warning | Download Size"

We need to create a single, genome-wide PopVCF from the raw per-chromosome PopVCF files. The per-chr Population VCFs were produced by the One Thousand Genomes Project (1kGP) and used to train the Human WGS.AF model. [You can view the raw files on Google Cloud Platform.](https://console.cloud.google.com/storage/browser/brain-genomics-public/research/cohort/1KGP/cohort_dv_glnexus_opt/v3_missing2ref?pageState=(%22StorageObjectListTable%22:(%22f%22:%22%255B%255D%22))&prefix=&forceOnObjectsSortingFiltering=false)


```bash title="Run the following at the command line:"
bash triotrain/variant_calling/data/GIAB/allele_freq/concat_PopVCFs.sh
```

??? example "Example | `concat_PopVCFs.sh`"
    ```
    --8<-- "./triotrain/variant_calling/data/GIAB/allele_freq/concat_PopVCFs.sh"
    ```

??? success "Check Intermediate Data | `allele_freq/`"

    ```bash title="Run the following at the command line:"
    ls triotrain/variant_calling/data/GIAB/allele_freq/ | grep cohort.release
    ```

    ```bash title="Expected outputs:"
    cohort.release_missing2ref.no_calls.vcf.gz
    cohort.release_missing2ref.no_calls.vcf.gz.csi
    ```

### b. Download Sequence Data

!!! warning "Warning | Download Size"

!!! warning
    Given the large file size, the NIST FTP server runs slowly causing `curl` to timeout. **You may need to run these scripts repeatedly until all data is transfered completely.**

We need to download the large sequence data files, and confirm they are not corrupted by checking the MD5 checksums. These `BAM/BAI` files orginate from the GIAB FTP site. [An index of GIAB data created with these samples can be found on GitHub.](https://github.com/genome-in-a-bottle/giab_data_indexes)

```bash title="1. Run the following at the command line:"
bash triotrain/variant_calling/data/GIAB/bam/AJtrio.download
```

??? example "Example | `AJtrio.download`"
    ```
    --8<-- "./triotrain/variant_calling/data/GIAB/bam/AJtrio.download"
    ```

??? success "Check Intermediate Data | HG002:"
    ```bash title="Run the following at the command line:"
    ls triotrain/variant_calling/data/GIAB/bam/ | grep HG002
    ```

    ```bash title="Expected outputs:"
    HG002_corrected_md5sums.feb19upload.txt
    HG002.GRCh38.2x250.bam
    HG002.GRCh38.2x250.bam.bai
    HG002.GRCh38.2x250.bam.bai.md5
    HG002.GRCh38.2x250.bam.md5
    ```

??? success "Check Intermediate Data | HG003:"
    ```bash title="Run the following at the command line:"
    ls triotrain/variant_calling/data/GIAB/bam/ | grep HG003
    ```

    ```bash title="Expected outputs:"
    HG003.GRCh38.2x250.bam
    HG003.GRCh38.2x250.bam.bai
    HG003.GRCh38.2x250.bam.bai.md5
    HG003.GRCh38.2x250.bam.md5
    ```

??? success "Check Intermediate Data | HG004:"
    ```bash title="Run the following at the command line:"
    ls triotrain/variant_calling/data/GIAB/bam/ | grep HG004
    ```

    ```bash title="Expected outputs:"
    HG004.GRCh38.2x250.bam
    HG004.GRCh38.2x250.bam.bai
    HG004.GRCh38.2x250.bam.bai.md5
    HG004.GRCh38.2x250.bam.md5
    ```

```bash title="2. Run the following at the command line:"
bash triotrain/variant_calling/data/GIAB/bam/HCtrio.download
```

??? example "Example | `HCtrio.download`"
    ```
    --8<-- "./triotrain/variant_calling/data/GIAB/bam/HCtrio.download"
    ```

??? success "Check Intermediate Data | HG005:"
    ```bash title="Run the following at the command line:"
    ls triotrain/variant_calling/data/GIAB/bam/ | grep HG005
    ```

    ```bash title="Expected outputs:"
    HG005.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.300x.bam
    HG005.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.300x.bam.bai
    HG005.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.300x.bam.bai.md5
    HG005.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.300x.bam.md5
    ```

??? success "Check Intermediate Data | HG006:"
    ```bash title="Run the following at the command line:"
    ls triotrain/variant_calling/data/GIAB/bam/ | grep HG006
    ```

    ```bash title="Expected outputs:"
    HG006.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.100x.bam
    HG006.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.100x.bam.bai
    HG006.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.100x.bam.bai.md5
    HG006.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.100x.bam.md5
    ```

??? success "Check Intermediate Data | HG007:"
    ```bash title="Run the following at the command line:"
    ls triotrain/variant_calling/data/GIAB/bam/ | grep HG007
    ```

    ```bash title="Expected outputs:"
    HG007.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.100x.bam
    HG007.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.100x.bam.bai
    HG007.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.100x.bam.bai.md5
    HG007.GRCh38_full_plus_hs38d1_analysis_set_minus_alts.100x.bam.md5
    ```

## 7. Create TrioTrain Inputs

There are (3) required input files we must create before we can run TrioTrain. [Complete details about all required data can be found in the TrioTrain User Guide.](../user-guide/usage_guide.md#assumptions)

### a. [Reference Dictionary File (`.dict`)](../user-guide/usage_guide.md#reference)

!!! warning
    This step is specific to the Human reference genome GRCh38 since cattle-specific input files are pre-packaged with TrioTrain. **If you are working with a new species, you will need to create this file for your reference genome.**

We need a reference dictionary file in the same directory as the reference genome. This file defines the valid genomic coordinates for TrioTrain's region shuffling. 

By default, region shuffling will only use the autosomes and X chromosome. However, you can expand or contract the shuffling area by providing an alternative region file for a particular trio by providing an existing `BED` file under the `RegionsFile` column within the [metadata file (`.csv`).](#b-metadata-file-csv)

```bash title="Run the following at the command line:"
picard CreateSequenceDictionary \
    --REFERENCE ./triotrain/variant_calling/data/GIAB/reference/GRCh38_no_alt_analysis_set.fasta \
    --OUTPUT ./triotrain/variant_calling/data/GIAB/reference/GRCh38_no_alt_analysis_set.dict \
    --SPECIES human
```

??? success "Check | Dictionary File "
    ```bash title="Run the following at the command line:"
    ls triotrain/variant_calling/data/GIAB/reference/ | grep .dict
    ```

    ```bash title="Expected output:"
    GRCh38_no_alt_analysis_set.dict
    ```

### b. [Metadata file (`.csv`)](../user-guide/usage_guide.md#providing-required-data-to-triotrain)

We also need a metadata file to tell TrioTrain where to find all of previously downloaded Human GIAB data. This file contains pedigree information, and the absolute paths for file inputs. Absolute paths are required to help the Apptainer/Singularity containers identify local files. [Formatting specifications for this required input can be found in the TrioTrain User Guide.](../user-guide/usage_guide.md#metadata-format)

For the tutorial, we've created a helper script to automatically create an example of this file. This script uses expectations of where the tutorial data are stored to add local paths. **However, outside of the tutorial this file is a user-created input.**

```bash title="Run the following at the command line:"
source ./scripts/setup/modules.sh
source ./scripts/start_conda.sh                 # Ensure the previously built conda env is active
python3 ./triotrain/model_training/tutorial/create_metadata.py
```

??? example "Example | `create_metadata.py`"
    ```
    --8<-- "./triotrain/model_training/tutorial/create_metadata.py"
    ```

??? success "Check | Tutorial Metadata File"
    ```bash title="Run the following at the command line:"
    ls triotrain/model_training/tutorial
    ```

    ```bash title="Expected output:"
    create_metadata.py  estimate.py  GIAB.Human_tutorial_metadata.csv  __init__.py  resources_used.json
    ```

### c. [SLURM Resource Config File (`.json`)](../user-guide/usage_guide.md#resource-config-format)

The last required input we need for TrioTrain is the SLURM resource config file (`.json`). This file tells TrioTrain what resources to request from your HPC cluster when submitting SLURM jobs. [

??? example "Example | Resource Config File"
    ``` title="triotrain/model_training/tutorial/resources_used.json"
    --8<-- "./triotrain/model_training/tutorial/resources_used.json"
    ```

The hardware listed above for each phase (e.g. `mem`, `ntasks` , `gpus`, etc.) vary, as some phases are memory intensive. These values should not be interpreted as the minimum or the optimum resources required for each phase. The MU Lewis Research Computing Cluster is heterogenous, the example config file requests resources to maximize the number of compute nodes when running memory-intensive phases.

For the tutorial, copy the above example into a new file, and manually edit the SBATCH parameters to match your HPC cluster (i.e. changing the partition list, account, and email address). This new resource config file is passed to TrioTrain via `-r </path/to/new_file.json>`

---

## 8. Run Shuffling Demo

**Shuffling the labeled examples is a critical step to re-training DeepVariant because the model assumes successive training images are independent of one another.** DeepVariant includes an Apache Beam pipeline that puts training examples in random genomic order. However, in our experience, getting the Python SDK for Beam, Apache Spark and SLURM to cooperate is a dependency nightmare.

Our alternative approach, referred to as "Region Shuffling", splits the autosomes and the X chromosome into subset regions before making the labeled examples. Using the previously created `.dict` file created for the reference, TrioTrain will determine how many regions are required automatically.

!!! warning
    For our analyses in bovine genomes, we exclude parts of the genome from our region shuffling, including:

    1. the Y chromosome and the Mitochondrial genome &mdash; due to limitations with the `ARS-UCD1.2_Btau5.0.1Y` reference genome

    2. the unmapped reads &mdash;  due to a large volume of contigs containing a small amount of variants that can not be easily distributed across 60-150+ shuffling regions

    TrioTrain will automatically search the reference genome `.dict` file for contigs labeled with `Y` and `M/MT` and will ignore them prior to defining shuffling regions.
    
    Use the `--unmapped-reads` flag to provide a contig prefix pattern to exclude. The default value (NKLS) is approprate for the `ARS-UCD1.2_Btau5.0.1Y` reference genome.

??? note "Note | Identifying Contig Labels"
    ```bash title="Run the following at the command line:"
    cat ARS-UCD1.2_Btau5.0.1Y.dict | awk '{if($1 ~ "@SQ") print $2}' | cut -c4-7 | sort | uniq -c | sort -k1
    ```

    ```bash title="Check output"
        1 1
        1 10
        1 11
        1 12
        1 13
        1 14
        1 15
        1 16
        1 17
        1 18
        1 19
        1 2
        1 20
        1 21
        1 22
        1 23
        1 24
        1 25
        1 26
        1 27
        1 28
        1 29
        1 3
        1 4
        1 5
        1 6
        1 7
        1 8
        1 9
        1 MT
        1 X
        1 Y
        2180 NKLS
    ```

---

A shuffling region is defined in a non-overlapping, 0-based `BED` file. The goal is to create a subset of labeled examples which are representative of the whole genome, yet small enough to be shuffled within the memory of a single compute node. After defining the shuffling regions, labeled and shuffled examples are created by running parallel SLURM jobs. In our testing with bovine genomes, constraining each region to produce ~200,000 labeled examples works well.

In our experience, numerous small jobs running quickly minimizes wall time between phases. We also priorize a large number of regions, as this further increases the randomness during the final `re_shuffle` processes that randomizes the order regions are given to the model.

??? example "Example | Computing Power"
    Given ~370G mem across 40 cores, DeepVariant will shuffle each region's examples in around 6 minutes, which can be submitted in parallel to reduce wall time.

??? note "Note | Output Volume"
    A typical cattle genome with ~8 million variants results in around ~65 regions, resulting in (65 regions x 40 cores) tfrecord output files. TrioTrain repeats this process for shuffling, resulting in another (65 regions x 40 cores) shuffled tfrecord output files. This is repeated for all 3 genomes within a trio resulting in a large volume of individual files (65 regions x 40 cores x 2 phases per genome).
    
    The final step of our approach, referrred to as `re_shuffle`, condenses the 40 tfrecord files for a region, reducing the number of files fed to DeepVariant per genome back down to 65. To further improve shuffling, we randomize the order regions are provided to DeepVariant.

    **If your species of interest produces a large volume of variants (> 8 million / genome), TrioTrain can easily overload your cluster's I/O capabilities, or write more than 10,000 files to a directory, or overwhelm the SLURM scheduler by submitting thousands of jobs simultaneously.** Future versions of TrioTrain will address these challenges, but proceed with caution; your cluster's SysAdmin will thank you!

**This shuffling demo enables you to adjust TrioTrain's parameters for estimating how many shuffling regions to use for each genome.** The two primary flags which control Region Shuffling are:

1. `--max-examples` &mdash; defines the upper limit of total number of examples to produce for each region; values greater than the default (200,000) will increase the wall time.

2. `--est-examples` &mdash; defines expectations of the number of examples DeepVariant produces per genomic variant; the default value (1.5) is appropriate for bovine genomes, but with the human GIAB samples, we found a value of 1 to be more appropriate.

Additionally, TrioTrain bases the Region Shuffling calculations on the total number of variants found in each genome. This value can vary drastically across training genomes, so TrioTrain uses the number of PASS variants within the corresponding TruthVCF. A larger number of truth variants results in more regions made per region.

**Before running TrioTrain in a new mamalian genome or on a new HPC cluster, we strongly recommend completing the region shuffling demo using the smallest chromosome possible using the `--demo-chr=<region_literal>` flag.**

??? note "Note | Working in Other Species"
    The appropriate values for `max-examples` and `est-examples` may vary widely across species, as the number of examples DeepVariant produces depends on several factors including:

    * genome size

    * the reference genome used
    
    * how many variants are identified in an individual genome

    For example, the F1-hybrid offspring in cattle are crosses between diverent lineages, resulting in an abnormal amount heterzygous genotypes compared to typical cattle genomes. Instead of typical 8 million variants per genome, these samples produced 20+ million variants per genome.

---

For this tutorial, complete the demo for Human genomes by **editing the following at the command to include your new SLURM config file**:

```bash title="Run the following at the command line:"
# You can add the --dry-run flag to this command to confirm the TrioTrain pipeline runs smoothly before submitting jobs to the queue
source ./scripts/setup/modules.sh
source ./scripts/start_conda.sh                 # Ensure the previously built conda env is active
python3 triotrain/run_trio_train.py                                                                         \
    -g Father                                                                                               \
    --unmapped-reads chrUn                                                                                  \
    -m triotrain/model_training/tutorial/GIAB.Human_tutorial_metadata.csv                                   \
    -n demo                                                                                                 \
    --demo-mode                                                                                             \
    --demo-chr chr21                                                                                        \
    --num-tests 3                                                                                           \
    --custom-checkpoint triotrain/model_training/pretrained_models/v1.4.0_withIS_withAF/wgs_af.model.ckpt   \
    --output ../TUTORIAL                                                                                    \
    -r </path/to/new_file.json>
```

---

This demo will produce and submit the following SLURM jobs:

1. `make_examples` &mdash; for both Father & Child
2. `beam_shuffle` &mdash; for both Father & Child
3. `re_shuffle` &mdash; for both Father & Child
4. `call_variants` &mdash; for just the Father

---

There are (6) types of output files from running the demo:

| File Extension          | Number of Files (Shards) | Genome Used   |
| ----------------------- | --------------- | ------------- |
| `labeled.tfrecords*.gz` | N               | Father, Child |
| `labeled.tfrecords*.gz.example_info.json` | N               | Father, Child |
| `labeled.shuffled*.tfrecord.gz` | N               | Father, Child |
| `labeled.shuffled.dataset_config.pbtxt` | 1       | Father, Child |
| `labeled.shuffled.merged.dataset_config.pbtxt` | 1       | Father, Child |
| `labeled.shuffled.merged.tfrecord.gz` | 1        | Father, Child |
| *N = number of CPUs requested in your `resources_used.json` file, shards are numbered 0 &mdash; (N - 1).* | |

??? success "Expected Output | Father Shuffling:"
    ```bash title="Run the following at the command line:"
    ls ../TUTORIAL/demo/Human_tutorial/examples/ | grep Father
    ```

    ```bash title="Check output"
    Father.chr21.labeled.shuffled-00000-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00001-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00002-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00003-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00004-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00005-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00006-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00007-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00008-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00009-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00010-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00011-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00012-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00013-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00014-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00015-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00016-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00017-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00018-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00019-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00020-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00021-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00022-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00023-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00024-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00025-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00026-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00027-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00028-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00029-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00030-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00031-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00032-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00033-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00034-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00035-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00036-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00037-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00038-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled-00039-of-00040.tfrecord.gz
    Father.chr21.labeled.shuffled.dataset_config.pbtxt
    Father.chr21.labeled.tfrecords-00000-of-00040.gz
    Father.chr21.labeled.tfrecords-00000-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00001-of-00040.gz
    Father.chr21.labeled.tfrecords-00001-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00002-of-00040.gz
    Father.chr21.labeled.tfrecords-00002-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00003-of-00040.gz
    Father.chr21.labeled.tfrecords-00003-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00004-of-00040.gz
    Father.chr21.labeled.tfrecords-00004-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00005-of-00040.gz
    Father.chr21.labeled.tfrecords-00005-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00006-of-00040.gz
    Father.chr21.labeled.tfrecords-00006-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00007-of-00040.gz
    Father.chr21.labeled.tfrecords-00007-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00008-of-00040.gz
    Father.chr21.labeled.tfrecords-00008-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00009-of-00040.gz
    Father.chr21.labeled.tfrecords-00009-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00010-of-00040.gz
    Father.chr21.labeled.tfrecords-00010-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00011-of-00040.gz
    Father.chr21.labeled.tfrecords-00011-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00012-of-00040.gz
    Father.chr21.labeled.tfrecords-00012-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00013-of-00040.gz
    Father.chr21.labeled.tfrecords-00013-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00014-of-00040.gz
    Father.chr21.labeled.tfrecords-00014-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00015-of-00040.gz
    Father.chr21.labeled.tfrecords-00015-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00016-of-00040.gz
    Father.chr21.labeled.tfrecords-00016-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00017-of-00040.gz
    Father.chr21.labeled.tfrecords-00017-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00018-of-00040.gz
    Father.chr21.labeled.tfrecords-00018-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00019-of-00040.gz
    Father.chr21.labeled.tfrecords-00019-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00020-of-00040.gz
    Father.chr21.labeled.tfrecords-00020-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00021-of-00040.gz
    Father.chr21.labeled.tfrecords-00021-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00022-of-00040.gz
    Father.chr21.labeled.tfrecords-00022-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00023-of-00040.gz
    Father.chr21.labeled.tfrecords-00023-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00024-of-00040.gz
    Father.chr21.labeled.tfrecords-00024-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00025-of-00040.gz
    Father.chr21.labeled.tfrecords-00025-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00026-of-00040.gz
    Father.chr21.labeled.tfrecords-00026-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00027-of-00040.gz
    Father.chr21.labeled.tfrecords-00027-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00028-of-00040.gz
    Father.chr21.labeled.tfrecords-00028-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00029-of-00040.gz
    Father.chr21.labeled.tfrecords-00029-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00030-of-00040.gz
    Father.chr21.labeled.tfrecords-00030-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00031-of-00040.gz
    Father.chr21.labeled.tfrecords-00031-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00032-of-00040.gz
    Father.chr21.labeled.tfrecords-00032-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00033-of-00040.gz
    Father.chr21.labeled.tfrecords-00033-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00034-of-00040.gz
    Father.chr21.labeled.tfrecords-00034-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00035-of-00040.gz
    Father.chr21.labeled.tfrecords-00036-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00037-of-00040.gz
    Father.chr21.labeled.tfrecords-00037-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00038-of-00040.gz
    Father.chr21.labeled.tfrecords-00038-of-00040.gz.example_info.json
    Father.chr21.labeled.tfrecords-00039-of-00040.gz
    Father.chr21.labeled.tfrecords-00039-of-00040.gz.example_info.json
    ```

    **Confirm that SLURM jobs completed successfully**
    ```bash title="Run the following at the command line:"
    cat ../TUTORIAL/demo/Human_tutorial/logs/tracking-Baseline-v1.4.0.log | grep SUCCESS | grep Father | wc -l
    ```

    ```bash title="Check output"
    41
    ```

??? success "Expected Output | Child Shuffling:"
    ```bash title="Run the following at the command line:"
    ls ../TUTORIAL/demo/Human_tutorial/examples/ | grep Child
    ```

    ```bash title="Check output"
    Child.chr21.labeled.shuffled-00000-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00001-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00002-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00003-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00004-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00005-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00006-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00007-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00008-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00009-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00010-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00011-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00012-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00013-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00014-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00015-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00016-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00017-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00018-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00019-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00020-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00021-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00022-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00023-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00024-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00025-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00026-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00027-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00028-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00029-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00030-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00031-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00032-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00033-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00034-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00035-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00036-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00037-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00038-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled-00039-of-00040.tfrecord.gz
    Child.chr21.labeled.shuffled.dataset_config.pbtxt
    Child.chr21.labeled.tfrecords-00000-of-00040.gz
    Child.chr21.labeled.tfrecords-00000-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00001-of-00040.gz
    Child.chr21.labeled.tfrecords-00001-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00002-of-00040.gz
    Child.chr21.labeled.tfrecords-00002-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00003-of-00040.gz
    Child.chr21.labeled.tfrecords-00003-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00004-of-00040.gz
    Child.chr21.labeled.tfrecords-00004-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00005-of-00040.gz
    Child.chr21.labeled.tfrecords-00005-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00006-of-00040.gz
    Child.chr21.labeled.tfrecords-00006-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00007-of-00040.gz
    Child.chr21.labeled.tfrecords-00007-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00008-of-00040.gz
    Child.chr21.labeled.tfrecords-00008-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00009-of-00040.gz
    Child.chr21.labeled.tfrecords-00009-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00010-of-00040.gz
    Child.chr21.labeled.tfrecords-00010-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00011-of-00040.gz
    Child.chr21.labeled.tfrecords-00011-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00012-of-00040.gz
    Child.chr21.labeled.tfrecords-00012-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00013-of-00040.gz
    Child.chr21.labeled.tfrecords-00013-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00014-of-00040.gz
    Child.chr21.labeled.tfrecords-00014-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00015-of-00040.gz
    Child.chr21.labeled.tfrecords-00015-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00016-of-00040.gz
    Child.chr21.labeled.tfrecords-00016-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00017-of-00040.gz
    Child.chr21.labeled.tfrecords-00017-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00018-of-00040.gz
    Child.chr21.labeled.tfrecords-00018-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00019-of-00040.gz
    Child.chr21.labeled.tfrecords-00019-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00020-of-00040.gz
    Child.chr21.labeled.tfrecords-00020-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00021-of-00040.gz
    Child.chr21.labeled.tfrecords-00021-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00022-of-00040.gz
    Child.chr21.labeled.tfrecords-00022-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00023-of-00040.gz
    Child.chr21.labeled.tfrecords-00023-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00024-of-00040.gz
    Child.chr21.labeled.tfrecords-00024-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00025-of-00040.gz
    Child.chr21.labeled.tfrecords-00025-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00026-of-00040.gz
    Child.chr21.labeled.tfrecords-00026-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00027-of-00040.gz
    Child.chr21.labeled.tfrecords-00027-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00028-of-00040.gz
    Child.chr21.labeled.tfrecords-00028-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00029-of-00040.gz
    Child.chr21.labeled.tfrecords-00029-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00030-of-00040.gz
    Child.chr21.labeled.tfrecords-00030-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00031-of-00040.gz
    Child.chr21.labeled.tfrecords-00031-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00032-of-00040.gz
    Child.chr21.labeled.tfrecords-00032-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00033-of-00040.gz
    Child.chr21.labeled.tfrecords-00033-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00034-of-00040.gz
    Child.chr21.labeled.tfrecords-00034-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00035-of-00040.gz
    Child.chr21.labeled.tfrecords-00035-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00036-of-00040.gz
    Child.chr21.labeled.tfrecords-00036-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00037-of-00040.gz
    Child.chr21.labeled.tfrecords-00037-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00038-of-00040.gz
    Child.chr21.labeled.tfrecords-00038-of-00040.gz.example_info.json
    Child.chr21.labeled.tfrecords-00039-of-00040.gz
    Child.chr21.labeled.tfrecords-00039-of-00040.gz.example_info.json
    ```

    **Confirm that SLURM jobs completed successfully**
    ```bash title="Run the following at the command line:"
    cat ../TUTORIAL/demo/Human_tutorial/logs/tracking-Baseline-v1.4.0.log | grep SUCCESS | grep Child | wc -l
    ```

    ```bash title="Check output"
    41
    ```

??? success "Expected Output | Benchmarking:"
    ```bash title="Run the following at the command line:"
    less ../TUTORIAL/demo/summary/Human_tutorial.SLURM.job_numbers.csv
    ```

    ```bash title="Check output"
    AnalysisName,RunName,Parent,Phase,JobList
    Baseline-v1.4.0,Human_tutorial,Father,make_examples,27669522
    Baseline-v1.4.0,Human_tutorial,Father,beam_shuffle,27669523
    Baseline-v1.4.0,Human_tutorial,Father,make_examples,27669524
    Baseline-v1.4.0,Human_tutorial,Father,beam_shuffle,27669525
    # The JobList column will differ based on SLURM job numbers
    ```

**The following will provide a conservative estimate for the `--max-examples` and `--est-examples` parameters to ensure shuffling easily fits within your available memory.**

```bash title="Run the following at the command line:"
source ./scripts/setup/modules.sh
source ./scripts/start_conda.sh                 # Ensure the previously built conda env is active
python3 triotrain/model_training/tutorial/estimate.py                           \
    --vcf-file ../TUTORIAL/demo/Human_tutorial/test_Father/test1_chr21.vcf.gz   \
    -g Father                                                                   \
    --demo-mode                                                                 \
    --env-file ../TUTORIAL/demo/envs/run1.env
```

??? success "Expected Output | Estimating TrioTrain Parameters:"
    ```bash
    ===== start of triotrain/model_training/tutorial/estimate.py @ 2023-06-29  11:25:27 =====
    2023-06-29 11:25:27 AM - [INFO] - [DEMO] - [TRIO1] - [count_variants] - [Father]: number of REF/REF variants found | 44,452
    2023-06-29 11:25:27 AM - [INFO] - [DEMO] - [TRIO1] - [count_variants] - [Father]: number of PASS variants found | 114,332
    2023-06-29 11:25:28 AM - [INFO] - [DEMO] - [TRIO1] - [count_variants] - [Father]: default maximum examples per region | 200,000
    2023-06-29 11:25:28 AM - [INFO] - [DEMO] - [TRIO1] - [count_variants] - [Father]: default value for --max-examples is appropriate
    2023-06-29 11:25:28 AM - [INFO] - adding Demo_TotalVariants='114332'
    2023-06-29 11:25:28 AM - [INFO] - [DEMO] - [TRIO1] - [count_variants] - [Father]: added 'Demo_TotalVariants=114332' to env file
    2023-06-29 11:25:28 AM - [INFO] - [DEMO] - [TRIO1] - [count_variants] - [Father]: number of examples made | 75,902
    2023-06-29 11:25:28 AM - [INFO] - [DEMO] - [TRIO1] - [count_variants] - [Father]: calculated examples per variant | 0.664
    2023-06-29 11:25:28 AM - [INFO] - [DEMO] - [TRIO1] - [count_variants] - [Father]: prevent underestimating which creates too many examples per region by rounding up to the nearest 0.5 | 1.0
    2023-06-29 11:25:28 AM - [INFO] - [DEMO] - [TRIO1] - [count_variants] - [Father]: default examples per variant | 1.5
    2023-06-29 11:25:28 AM - [INFO] - [DEMO] - [TRIO1] - [count_variants] - [Father]: difference between default and calculated examples per variant | 0.836
    2023-06-29 11:25:28 AM - [INFO] - [DEMO] - [TRIO1] - [count_variants] - [Father]: when running TrioTrain outside of this tutorial, please use '--est-examples=1.0'
    2023-06-29 11:25:28 AM - [INFO] - adding Est_Examples='1.0'
    2023-06-29 11:25:28 AM - [INFO] - [DEMO] - [TRIO1] - [count_variants] - [Father]: added 'Est_Examples=1.0' to env file
    ===== end of triotrain/model_training/tutorial/estimate.py @ 2023-06-29  11:25:28 =====
    ```

## 9. Run TrioTrain with a Human Trio

Now that we know how to tailor TrioTrain for our non-bovine species (human), we can move forward with starting the re-training pipeline.

Complete the GIAB TrioTrain by **editing the following at the command to include your new SLURM config file**:

```bash title="Run the following at the command line:"
# You can add the --dry-run flag to this command to confirm the TrioTrain pipeline runs smoothly prior to submitting jobs to the queue
source ./scripts/setup/modules.sh
source ./scripts/start_conda.sh                 # Ensure the previously built conda env is active
python3 triotrain/run_trio_train.py                                                                         \
    -g Father                                                                                               \
    --unmapped-reads chrUn                                                                                  \
    --est-examples 1                                                                                        \
    -m triotrain/model_training/tutorial/GIAB.Human_tutorial_metadata.csv                                   \
    -n GIAB_Trio                                                                                            \
    --num-tests 3                                                                                           \
    --custom-checkpoint triotrain/model_training/pretrained_models/v1.4.0_withIS_withAF/wgs_af.model.ckpt   \
    --output ../TUTORIAL                                                                                    \
    --benchmark                                                                                             \
    -r </path/to/new_file.json>
```

[Need to Re-Submit a SLURM job :octicons-question-16:](../user-guide/resubmit.md){ .md-button }

??? success "Check | Baseline WGS.AF:"
    ```bash title="Run the following at the command line:"
    ls ../TUTORIAL/baseline_v1.4.0_withIS_withAF/ | grep total | grep total
    ```

    ```bash title="Expected outputs:"
    Test1.total.metrics.csv
    Test2.total.metrics.csv
    Test3.total.metrics.csv
    ```

??? success "Check | Father:"
    ```bash title="Run the following at the command line:"
    ls ../TUTORIAL/GIAB_Trio/Human_tutorial/compare_Father/ | grep total
    ```

    ```bash title="Expected outputs:"
    Test1.total.metrics.csv
    Test2.total.metrics.csv
    Test3.total.metrics.csv
    ```

??? success "Check | Mother:"
    ```bash title="Run the following at the command line:"
    ls ../TUTORIAL/GIAB_Trio/Human_tutorial/compare_Mother/ | grep total
    ```

    ```bash title="Expected outputs:"
    Test1.total.metrics.csv
    Test2.total.metrics.csv
    Test3.total.metrics.csv
    ```

## Merge Results | Per-Iteration

Each `Test#.total.metrics.csv` output file should contain 57 rows and 2 columns. The metrics within are the raw and proprotional performance metrics from hap.py. After all `convert_happy` jobs complete, we will separately merge the results from running the baseline iteration, and both training iterations completed during the GIAB tutorial:

```bash title="Run the following at the command line:"
source ./scripts/setup/modules.sh
source ./scripts/start_conda.sh                 # Ensure the previously built conda env is active
for start_i in $(seq 0 1); do
    echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: merging processed results from hap.py for GIAB run#${start_i}"
    python3 triotrain/summarize/merge_results.py --env ../TUTORIAL/GIAB_Trio/envs/run${start_i}.env -g Father -m triotrain/summarize/data/tutorial_metadata.csv
    echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: finished merging processed results from hap.py for GIAB run#${start_i}"
done
```

??? success "Check | Baseline WGS.AF"
    ```bash title="Run the following at the command line:"
    ls ../TUTORIAL/baseline_v1.4.0_withIS_withAF/ | grep All
    ```

    ```bash title="Expected outputs:"
    DV1.4_WGS.AF_human.AllTests.total.metrics.csv
    ```

??? success "Check | GIAB Trio1"
    ```bash title="Run the following at the command line:"
    ls ../TUTORIAL/GIAB_Trio/summary | grep All
    ```

    ```bash title="Expected outputs:"
    Trio1.AllTests.total.metrics.csv
    ```

## Clean Up Directories | Per-Iteration

Running TrioTrain produces a large volume of temporary files. Run the following at the command line to free up space:

```bash title="Run the following at the command line:"
source ./scripts/setup/modules.sh
source ./scripts/start_conda.sh                 # Ensure the previously built conda env is active
for start_i in $(seq 0 1); do
    echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: removing temp files for GIAB run#${start_i}"
    python3 triotrain/model_training/slurm/clean_tmp.py --env ../TUTORIAL/GIAB_Trio/envs/run${start_i}.env
    echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: finished removing temp files for GIAB run#${start_i}"
done
```

??? success "Check | Baseline WGS.AF"
    ```bash title="Run the following at the command line:"
    du -h ../TUTORIAL/baseline_v1.4.0_withIS_withAF/
    ```

    ```bash title="Expected outputs:"
    700M    ../TUTORIAL/baseline_v1.4.0_withIS_withAF/
    ```

??? success "Check | GIAB Trio1"
    ```bash title="Run the following at the command line:"
    du -h ../TUTORIAL/GIAB_Trio
    ``

    ```bash title="Expected outputs:"
    141M    ../TUTORIAL/GIAB_Trio/Human_tutorial/logs
    402M    ../TUTORIAL/GIAB_Trio/Human_tutorial/compare_Mother
    1.1M    ../TUTORIAL/GIAB_Trio/Human_tutorial/train_Mother/eval_Child
    23G     ../TUTORIAL/GIAB_Trio/Human_tutorial/train_Mother
    394M    ../TUTORIAL/GIAB_Trio/Human_tutorial/test_Father
    298M    ../TUTORIAL/GIAB_Trio/Human_tutorial/compare_Father
    1.1M    ../TUTORIAL/GIAB_Trio/Human_tutorial/train_Father/eval_Child
    23G     ../TUTORIAL/GIAB_Trio/Human_tutorial/train_Father
    243G    ../TUTORIAL/GIAB_Trio/Human_tutorial/examples
    391M    ../TUTORIAL/GIAB_Trio/Human_tutorial/test_Mother
    3.1M    ../TUTORIAL/GIAB_Trio/Human_tutorial/jobs
    290G    ../TUTORIAL/GIAB_Trio/Human_tutorial
    100K    ../TUTORIAL/GIAB_Trio/summary
    50K     ../TUTORIAL/GIAB_Trio/envs
    290G    ../TUTORIAL/GIAB_Trio/
    ```


[Next - Comparing Models :material-arrow-right-box:](../user-guide/mie.md){ .md-button }
