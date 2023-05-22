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
    and a corresponding `.bai` index file . The reads must be aligned to the
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

*  Each `VCF/BED/BAM` file must contain only one sample per file.
*  The `VCF/BED/BAM` files must be sorted and compatible with the reference genome provided to the pipeline.
*  The `VCF` files are bgzipped and tabix indexed.
*  The `BAM` files are tabix indexed.
*  The pipeline will uncompress compressed `BED` files.
*  All files must exist before the execution of the pipeline.

##  Providing input files to TrioTrain

Input files are handled by the primary input file for TrioTrain: a metadata file in `.csv` format. This file contains pedigree and 
file location on disk for each trio is used to retrain DeepVariant.

### Metadata Assumptions

*  Each row corresponds to one complete family trio resulting in two iterations of TrioTrain.
*  Row order determines the sequential order of how trios are used during re-training.

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

### General Note
If the data are available, you can perform additional iterations of TrioTrain by adding rows for additional trio(s) to the metadata `.csv` file. 

Likewise, further test replicates can be achieved by adding columns in sets of three [`BAM,TruthVCF,TruthBED`] for each additional test genome 
to the metadata `.csv` file. Further metadata format details are below.




