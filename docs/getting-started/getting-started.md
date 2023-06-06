# Getting Started

There are two main audiences of DV-TrioTrain:

1. **Model builders** - those who want to customize a new DeepVariant model, either with new data or in a new species.

2. **Model users** - those who have an existing, custom DeepVariant model they'd like to use to call variants.

---

## Model Builders

**TrioTrain provides a model development template for any diploid species without NIST-GIAB reference materials.**

TrioTrain builds upon the existing DV model for short-read (Illumina) Whole Genome Sequence (WGS) data, while optionally adding population-level allele frequency data. We built the DV-TT pipeline to extend DeepVariant with cattle, bison, and yak genomes.

Get started by following the steps below.

---

## Model Users

A major benefit of using DeepVariant over alternatives like GATK is that once you've chosen a model checkpoint, you're ready to go!

Published DV-TrioTrain models can be used as an alternative checkpoint with DeepVariant's one-step, single-sample variant caller. The model checkpoints used by DV-TT are downloaded from Google Health Genomics from GCP. An index with descriptions of available models can be found [here](../user-guide/existing_models.md).

---

## Quick Start

Getting started is super easy. First, change directories to your working directory. Then, follow along with these guides:

1. [Installation Guide](installation.md)
1. [Configuration Guide](../user-guide/installation.md)
1. [Demo Walk-Through](../user-guide/installation.md)

## Other Commands and Options

There are various other commands and options available. For a complete list of
commands, use the `--help` flag:

```bash
python3 scripts/model_training/run_trio_train.py --help
```

To view a list of options available on a given command, use the `--help` flag with that command. For example, to get a list of all options available for the `build` command run the following:

```bash
mkdocs build --help
```

---

### **How to customize DeepVariant with an existing TrioTrain model**

We recommend using Apptainer (a.k.a. Singularity), for local cluster computing.

```bash
BIN_VERSION="1.4.0"

# Pull the image.
singularity pull docker://google/deepvariant:"${BIN_VERSION}-gpu"

# Run a Custom DeepVariant.
singularity run -B /usr/lib/locale/:/usr/lib/locale/ \
  "YOUR_INPUT_DIR":"/input" \
  "YOUR_OUTPUT_DIR:/output" \
  docker://google/deepvariant:"${BIN_VERSION}" \
  /opt/deepvariant/bin/run_deepvariant \
  --model_type=WGS \
  --ref="${INPUT_DIR}"/ucsc.hg19.chr20.unittest.fasta \
  --reads="${INPUT_DIR}"/NA12878_S1.chr20.10_10p1mb.bam \
  --regions "chr20:10,000,000-10,010,000" \
  --output_vcf="${OUTPUT_DIR}"/output.vcf.gz \
  --output_gvcf="${OUTPUT_DIR}"/output.g.vcf.gz \
  --intermediate_results_dir "${OUTPUT_DIR}/intermediate_results_dir" \ **Optional.
  --num_shards=1 \ **How many cores the `make_examples` step uses. Change it to the number of CPU cores you have.**
  --dry_run=false **Default is false. If set to true, commands will be printed out but not executed.  
```

---

<font size= "4"> **[Got a question?](../user-guide/get-help.md)** </font>
