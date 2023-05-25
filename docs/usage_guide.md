# TrioTrain Usage Guide

TrioTrain is a pipeline to automate re-training of DeepVariant models. Visit the DeepVariant 
[usage guide](https://github.com/google/deepvariant/blob/r1.5/docs/deepvariant-details.md) to 
learn more in-depth details about how DeepVariant works. 

## Overview
TrioTrain and DeepVariant use several input file formats:

1.  A reference genome in [FASTA](https://en.wikipedia.org/wiki/FASTA_format)
    format and a corresponding
    [`.fai` index file](http://www.htslib.org/doc/faidx.html) generated using the
    `samtools faidx` command.

1.  Aligned reads file(s) in [BAM](http://genome.sph.umich.edu/wiki/BAM) format
    and a corresponding `.bai` index file **OR** in [CRAM](https://www.ga4gh.org/product/cram/)
    format with a corresponding `.csi` index file. The reads must be aligned to the
    reference genome described above.

1. Benchmarking variant file(s), or "truth genotypes," in [VCF](https://samtools.github.io/hts-specs/VCFv4.3.pdf) format 
   and a corresponding `.tbi` index file generated with `tabix`. Each sample should have its own benchmark VCF file, meaning
   no multi-sample VCFs.
  
1. Benchmarking region file(s), or "callable regions," in [BED](https://bedtools.readthedocs.io/en/latest/content/general-usage.html) format. 
   The regions provided must match the reference genome described above.
  
1.  A model checkpoint for DeepVariant, used a warm-start for retraining. Pre-trained checkpoints can either downloaded from
    Google Cloud Platform (GCP), or were created previously by a prior TrioTrain iteration.
    A checkpoint consists of four (4) file formats:
    * `.data-00000-of-00001`
    * `.index`
    * `.meta`
    * `.example_info.json` - defines the channels to include in the variant examples in TensorFlow Record 
       [(tfRecord)](https://www.tensorflow.org/tutorials/load_data/tfrecord) format. 
       Note that examples made with channel(s), tfRecord shape, or DeepVariant version can be incompatible with alternative DV models.

1.  *(OPTIONAL)* Population Allele Frequencies in [VCF](https://samtools.github.io/hts-specs/VCFv4.3.pdf) format 
   and a corresponding `.tbi` index file generated with `tabix`. Genotypes should be removed from this VCF. 

### General Note
Our automated, cattle-optimized GATK Best Practices workflow used to generate our input files automatically performs realignment and 
recalibration with Base Quality Score Recalibration 
[(BQSR)](https://gatk.broadinstitute.org/hc/en-us/articles/360035890531-Base-Quality-Score-Recalibration-BQSR-). 
Note that **BQSR is not required**, or recommended for using the single-step variant caller from DeepVariant, as it may decrease the accuracy. 
However, re-training involves a small proportion of the total genomes processed by UMAG group (55 of ~6,000). Thus, removing BQSR would 
decrease the quality of the entire cohort's GATK genotypes used in other research. The impact of including BQSR in our truth labels 
was not evaluated further during TrioTrain's development.

### Input Assumptions

*  All files must exist before the execution of the pipeline.
*  `VCF/BED/BAM/CRAM`
    *  Each file must contain only one sample per file.
    *  The files must be sorted and indexed.
    *  All must be compatible with the reference genome `FASTA` provided to the pipeline.
    *  `VCF` files
        *  These files should be compressed with `bgzip`
        *  Benchmark `VCF` files used as truth labels:
            *  Excludes any homozygous reference genotypes.
            *  Excludes any sites that violate Mendelian inheritance expectations.
    * `BED` files
        * Compressed files will be decompressed automatically.
        * These files use [0-based coordinates](https://bedtools.readthedocs.io/en/latest/content/overview.html?highlight=0-based#bed-starts-are-zero-based-and-bed-ends-are-one-based) 
    *  `BAM/CRAM` files
        * Either file type can be provided to TrioTrain.


##  Providing input files to TrioTrain

Input files are handled by the primary input file for TrioTrain: a metadata file in `.csv` format. This file contains pedigree and 
file locations saved to disk for each trio is used to re-train DeepVariant.

### Metadata Assumptions

*  Each row corresponds to one complete family trio resulting in two iterations of TrioTrain.
*  Row order determines the sequential order of how trios are used during re-training.
*  There are 24 **REQUIRED** columns with headers that must be in the order described in detail
in the [Metadata Format](#metadata-format) section.

At a minimum, this metadata file must provide
absolute paths to the following input files:

1.  TrioTrain performs two iterations of re-training, one for each parent in a trio. The following genomic data 
    are **REQUIRED** for the entire family trio:
    
    * Three (3) aligned read data `.bam` files, with the corresponding `.bai` index. 
    * Three (3) benchmark `.vcf.gz` files, with the corresponding `.vcf.gz.tbi` index.
    * Three (3) benchmark region `.bed.gz` files.

1.  TrioTrain tests the model produced for each iteration using a set of genomes previously unseen by the model. 
    The following genomic data are **REQUIRED** from individual(s) outside of the family trio:
    * One or more (1+) aligned read data `.bam` files, with the corresponding `.bai` index.
    * One or more (1+) benchmark `.vcf.gz` files, with the corresponding `.vcf.gz.tbi` index.
    * One or more (1+) benchmark `.bed.gz` files.

### General Notes
If the data are available, you can perform additional iterations of TrioTrain by adding rows for additional trio(s) to the metadata `.csv` file. 

Likewise, further test replicates can be achieved by adding columns in sets of three [`BAM,TruthVCF,TruthBED`] for each additional test genome 
to the metadata `.csv` file. Further metadata format details are below.

## Metadata Format

| Column Number | Column Name      | Description                     | Data Type | 
| ------------- | -----------      | ------------------------------- | --------- |
| 1             | RunOrder         | Sequential number for each trio | integer   |
| 2             | RunName          | The name of the output directory to be created; a unique memo/note for the analysis | string without spaces |
| 3             | ChildSampleID    | A primary, unique identifier for a child; must match the SampleID in the child’s VCF/BAM/BED files | alpha-numeric characters |
| 4             | ChildLabID       | A secondary, unique ID for a child ; defaults to ChildSampleID | alpha-numeric characters |
| 5             | FatherSampleID   | A primary, unique identifier for a father; must match the SampleID in the father’s VCF/BAM/BED files | alpha-numeric characters |
| 6             | FatherLabID      | A secondary, unique ID for a father; defaults to  to FatherSampleID | alpha-numeric characters |
| 7             | MotherSampleID   | A primary, unique identifier for a mother; must match the SampleID in the mother’s VCF/BAM/BED files | alpha-numeric characters |
| 8             | MotherLabID      | A secondary, unique ID for a mother; defaults to  to MotherSampleID | alpha-numeric characters |
| 9             | ChildSex         | The sex of the child, where F=female, M=male, and U=unknown | `F`, `M`, `U` |
| 10            | RefFASTA         | The absolute path to the reference file | `/path/to/file` |
| 11            | PopVCF           | The absolute path to the population allele frequency file; if blank, allele frequency information will not be included in the TensorFlow records during example image creation | `/path/to/file` |
| 12            | RegionsFile      | **over-rides RegionShuffling if included**; a `.bed` file where each line represents a genomic region for shuffling; each shuffling region produce a set of file shards which depends upon the number of CPUs requested via SLURM | `/path/to/file` |
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

### Adding more test genomes
Each additional testing genome can be supplied by adding three (3) more columns in the following order:
| Column Number | Column Name      | Description                     | Data Type | 
| ------------- | -----------      | ------------------------------- | --------- |
| 25            | Test#ReadsBAM    | The absolute path to a test genome's aligned reads | `/path/to/file` |
| 26            | Test#TruthVCF    | The absolute path to a test genome's truth genotypes | `/path/to/file` |
| 27            | Test#CallableBED | The absolute path to a test genome's callable regions | `/path/to/file` |

**NOTE:** The `#` in `Test#` does not correspond to the order each test is performed, as testing is performed in parallel. However, the number for each test genomes must be sequential to provide a unique label for output files.

## TrioTrain Outputs
<add a description here!>
