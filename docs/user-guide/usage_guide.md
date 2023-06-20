# TrioTrain Data

TrioTrain and DeepVariant use several input file formats; however, all files must:

- exist before the execution of the pipeline
- be compatible with the reference genome provided to the pipeline
- be sorted and indexed
- contain only one sample per file

## Required Raw Data

1. **Reference Genome**
    - must be in [`FASTA`](https://en.wikipedia.org/wiki/FASTA_format)
format
    - includes the corresponding
    [`.fai` index file](http://www.htslib.org/doc/faidx.html) generated with `samtools faidx` and located in the same directory
    - includes the corresponding [`.dict` file](https://gatk.broadinstitute.org/hc/en-us/articles/360036729911-CreateSequenceDictionary-Picard-) generated with `picard` and located in the same directory
    - *(OPTIONALLY)* includes the corresponding [Sequence Data File (SDF)](https://github.com/RealTimeGenomics/rtg-tools) generated with `rtg-tools format` and located at the same path in a sub-directory called "rtg_tools" &mdash; required for calculating Mendelian Inhertiance Errors with testing genomes

1. **Aligned Reads File(s)**
    - must be aligned to the reference genome above
    - can be in either [`BAM`](http://genome.sph.umich.edu/wiki/BAM) format or [`CRAM`](https://www.ga4gh.org/product/cram/) format
    - includes the corresponding `.bai` or `.csi` index file located in the same directory

1. **Benchmarking Variant File(s)**
    - also referred to as  "truth genotypes", or "gold-standard genotypes"
    - must be in in [`VCF`](https://samtools.github.io/hts-specs/VCFv4.3.pdf) format and compressed with `bgzip`
    - includes a corresponding `.tbi` index generated with `tabix` and located in the same directory
    - excludes any homozygous reference genotypes and any sites that violate Mendelian inheritance expectations
  
1. **Benchmarking Region File(s)**
    - also referred to as "callable regions"
    - must be in [`BED`](https://bedtools.readthedocs.io/en/latest/content/general-usage.html) format
    - must be compatible with the specified reference genome
    - compressed files will be decompressed
    - use [0-based coordinates](https://bedtools.readthedocs.io/en/latest/content/overview.html?highlight=0-based#bed-starts-are-zero-based-and-bed-ends-are-one-based)
  
1. **Starting DeepVariant Model Checkpoint**
    - used for warm-start a new model  initializing weights with a previous model
    - can either be downloaded from Google Cloud Platform (GCP) or created previously by a prior TrioTrain iteration
    - Checkpoints consists of four (4) files all located in the same directory:
        1. `.data-00000-of-00001`
        2. `.index`
        3. `.meta`
        4. `.example_info.json` &mdash; defines which features to include as channels within the images given to DeepVariant in [`tfRecord` format](https://www.tensorflow.org/tutorials/load_data/tfrecord)

        !!! note
            Examples made with different channel(s), a different tfRecord shape, or a different DeepVariant version can be incompatible with your chosen starting model. Get details about model features compatible with TrioTrain, such as shape, version and channels [here](existing_models.md).

            *You can check the shape of a model's examples with:*

            `jq '.' <model_name>.example_info.json`.           

1. *(OPTIONAL)* **Population Allele Frequencies**
    - must be in [`VCF`](https://samtools.github.io/hts-specs/VCFv4.3.pdf) format and compressed with `bgzip`
    - includes a corresponding `.tbi` index generated with `tabix` and located in the same directory
    - genotypes should be removed

!!! note
    Our automated, cattle-optimized GATK Best Practices workflow used to generate our input files automatically performs realignment and  recalibration with Base Quality Score Recalibration [(BQSR)](https://gatk.broadinstitute.org/hc/en-us/articles/360035890531-Base-Quality-Score-Recalibration-BQSR-). *BQSR is not required or recommended for using the single-step variant caller from DeepVariant, as it may decrease the accuracy.*
    
    However, re-training involves a small proportion of the total genomes processed by UMAG group (55 of ~6,000). Thus, removing BQSR would  decrease the quality of the entire cohort's GATK genotypes used in other research. The impact of including BQSR in our truth labels was not evaluated further during TrioTrain's development.

## TrioTrain-Specific Inputs

### Configuring SLURM Resources

SLURM resources are handled by TrioTrain via a resource configuration file (`.json`).
#### Resource Config Format

Contains nested dictionaries in the following format:

```json

{"phase_name": {
    "SLURM_SBATCH_PARAMETER": "value",
    "SLURM_SBATCH_PARAMETER": "value",
    "SLURM_SBATCH_PARAMETER": "value",
    }
}
```

There are (8) required phases within TrioTrain's SLURM config file. Valid `phase_names` for these include:

1. `make_examples`
2. `beam_shuffle`
3. `re_shuffle`
4. `train_eval`
5. `select_ckpt`
6. `call_variants`
7. `compare_happy`
8. `convert_happy`

Additionally, there are (3) optional phase names for TrioTrain's supplementary analyes that include:

1. `show_examples` &mdash; for running TrioTrain in 'demo' mode
2. `summary_stats` &mdash; for calculating per-VCF stats for each test genome
3. `mie_summary` &mdash; for calculating Mendelian Inheritance Error rate in trio-binned test genomes

The value for each `phase_name` is a nested dictionary that contains key:value pairs of parameters for running SBATCH job files. [You can view valid SBATCH options in the SLURM documentation.](https://slurm.schedmd.com/sbatch.html)

### Providing required data to TrioTrain

Input files are handled by the primary input file for TrioTrain, a metadata file in `.csv` format. These metadata files are used to define different re-training approaches. For example, you can alter the order in which trios are seen when building a new model between two different metadata files. Metadata includes trio pedigree information, and the absolute file paths for the local data you want to give DeepVariant.

#### Metadata Assumptions

- The first row includes column headers which will become variable names within TrioTrain
- Each row corresponds to one complete family trio resulting in (2) re-training iterations, one for each parent
- Row order determines the sequential order of how trios seen by DeepVariant
- There are **(24) REQUIRED** columns that must be in the order specified in the [Metadata Format section below](#metadata-format)

!!! note
    If the data are available, you can perform additional iterations of TrioTrain by adding rows for each additional trio.

    Likewise, further test replicates can be achieved by adding columns in sets of three [`BAM,TruthVCF,TruthBED`] for each additional test genome.

#### Minimum Data Required

At a minimum, the metadata file must provide absolute paths to the following input files:

1. TrioTrain performs two iterations of re-training, one for each parent in a trio which requires:
    - Three (3) aligned read data `.bam` files, with the corresponding `.bai` index.
    - Three (3) benchmark `.vcf.gz` files, with the corresponding `.vcf.gz.tbi` index.
    - Three (3) benchmark region `.bed` files.

1. TrioTrain tests the model produced for each iteration using a set of genomes previously unseen by the model. Ideally, these testing samples should consist of individuals outside of the family and requires:
    - One or more (1+) aligned read data `.bam` files, with the corresponding `.bai` index.
    - One or more (1+) benchmark `.vcf.gz` files, with the corresponding `.vcf.gz.tbi` index.
    - One or more (1+) benchmark `.bed` files.

---

#### Metadata Format

| Column Number | Column Name      | Description                     | Data Type |
| ------------- | -----------      | ------------------------------- | --------- |
| 1             | RunOrder         | Sequential number for each trio | integer   |
| 2             | RunName          | A unique name of the output directory | string without spaces |
| 3             | ChildSampleID    | A primary, unique identifier for a child; must match the SampleID in the child’s `VCF/BAM/BED` files | alpha-numeric characters |
| 4             | ChildLabID       | A secondary, unique ID for a child ; `default=ChildSampleID` | alpha-numeric characters |
| 5             | FatherSampleID   | A primary, unique identifier for a father; must match the SampleID in the father’s `VCF/BAM/BED` files | alpha-numeric characters |
| 6             | FatherLabID      | A secondary, unique ID for a father; `default=FatherSampleID` | alpha-numeric characters |
| 7             | MotherSampleID   | A primary, unique identifier for a mother; must match the SampleID in the mother’s `VCF/BAM/BED` files | alpha-numeric characters |
| 8             | MotherLabID      | A secondary, unique ID for a mother; `default=MotherSampleID` | alpha-numeric characters |
| 9             | ChildSex         | The sex of the child, where `F=female, M=male, U=unknown` | `F`, `M`, `U` |
| 10            | RefFASTA         | The absolute path to the reference file | `/path/to/file` |
| 11            | PopVCF           | The absolute path to the population allele frequency file; **if blank, allele frequency information will not be included in the TensorFlow records during example image creation** | `/path/to/file` |
| 12            | RegionsFile      | a `.bed` file where each line represents a genomic region for shuffling; each shuffling region produce a set of file shards which depends upon the number of CPUs requested via SLURM; **over-rides RegionShuffling if included** | `/path/to/file` |
| 13            | ChildReadsBAM    | The absolute path to the child's aligned reads | `/path/to/file` |
| 14            | ChildTruthVCF    | The absolute path to the child's truth genotypes | `/path/to/file` |
| 15            | ChildCallableBED | The absolute path to the child's callable regions | `/path/to/file` |
| 16            | FatherReadsBAM   | The absolute path to the fathers's aligned reads | `/path/to/file` |
| 17            | FatherTruthVCF   | The absolute path to the father's truth genotypes | `/path/to/file` |
| 18            | FatherCallableBED| The absolute path to the father's callable regions | `/path/to/file` |
| 19            | MotherReadsBAM   | The absolute path to the mother's aligned reads | `/path/to/file` |
| 20            | MotherVCF        | The absolute path to the mother's truth genotypes | `/path/to/file` |
| 21            | MotherCallableBED| The absolute path to the mother's callable regions | `/path/to/file` |
| 22            | Test1ReadsBAM    | The absolute path to a test genome's aligned reads | `/path/to/file` |
| 23            | Test1TruthVCF    | The absolute path to a test genome's truth genotypes | `/path/to/file` |
| 24            | Test1CallableBED | The absolute path to a test genome's callable regions | `/path/to/file` |

#### Adding more test genomes

Each additional testing genome can be supplied by adding three (3) more columns in the following order:

| Column Number | Column Name      | Description                     | Data Type |
| ------------- | -----------      | ------------------------------- | --------- |
| 25            | Test#ReadsBAM    | The absolute path to a test genome's aligned reads | `/path/to/file` |
| 26            | Test#TruthVCF    | The absolute path to a test genome's truth genotypes | `/path/to/file` |
| 27            | Test#CallableBED | The absolute path to a test genome's callable regions | `/path/to/file` |

!!! note
    The `#` in `Test#` does not correspond to the order each test is performed, as testing is performed in parallel. However, the number for each test genomes must be sequential to provide a unique label for output files.

## TrioTrain Outputs

TODO: add a description here!
