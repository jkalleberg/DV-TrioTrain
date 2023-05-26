# Getting Started

There are two main audiences of DV-TrioTrain:

1. **Model builders** - those who want to customize a new DeepVariant model, either with new data or in a new species.

2. **Model users** - those who have an existing, custom DeepVariant model they'd like to use to call variants.

---

## Model Users

A major benefit of using DeepVariant, over alternatives like GATK, is that once you've chosen a model checkpoint, you're ready to go! Published DV-TrioTrain models can be used as an alternative checkpoint with DeepVariant's one-step, single-sample variant caller. An index of available models can be found [here](../user-guide/existing_models.md).

### How to customize DeepVariant with an existing TrioTrain model



We recommend using Apptainer (a.k.a. Singularity), for local cluster computing.

```bash
BIN_VERSION="1.4.0"
docker run \
  -v "YOUR_INPUT_DIR":"/input" \
  -v "YOUR_OUTPUT_DIR:/output" \
  google/deepvariant:"${BIN_VERSION}" \
  /opt/deepvariant/bin/run_deepvariant \
  --model_type=WGS \
  --ref=/input/YOUR_REF \
  --reads=/input/YOUR_BAM \
  --output_vcf=/output/YOUR_OUTPUT_VCF \
  --output_gvcf=/output/YOUR_OUTPUT_GVCF \
  --num_shards=$(nproc) \ **This will use all your cores to run make_examples. Feel free to change.**
  --dry_run=false **Default is false. If set to true, commands will be printed out but not executed.
```

---

## Model Builders

**TrioTrain provides a model development template for any diploid species without NIST-GIAB reference materials.**

TrioTrain builds upon the existing DV model for short-read (Illumina) Whole Genome Sequence (WGS) data, while adding population-level allele frequency data from published samples from SRA.

We built the DV-TT pipeline to extend DeepVariant with cattle, bison, and yak genomes.

---

## Installation

To install DV-TrioTrain, run the following command from the command line:

```bash
pip install dv_triotrain
```

For more details, see the [Installation Guide](user-guilde/installation.md).

## Running the Demo

Getting started is super easy. To create a new project, run the following command from the command line:

```bash
mkdocs new my-project
cd my-project
```

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

## [Got a question?](../user-guide/get-help.md)
