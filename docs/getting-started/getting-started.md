# Getting Started

There are two main audiences of DV-TrioTrain:

1. **[Model users](#model-users)** - call variants using an existing, custom DeepVariant model produced by TrioTrain.

1. **[Model builders](#model-builders)** - build a customized DeepVariant model, by training on either new data, or data from another diploid species.

---

## Model Users

A major benefit of using DeepVariant over alternatives like GATK is that once you've chosen a model checkpoint, you're ready to go! The models created by DV-TrioTrain can be used as an alternative checkpoint with DeepVariant's one-step, single-sample variant caller. An index with descriptions of published models can be found [here](../user-guide/existing_models.md).

### Quick Start

<font size= "4"> 
**Customizing DeepVariant with a TrioTrain model**
</font>

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
  # TODO: fix this command!
  # --custom_model
```

---

## Model Builders

TrioTrain provides a model development framework for DeepVariant, and is therefore compatible with **any diploid species without NIST-GIAB reference materials.** We built the DV-TT pipeline to extend DeepVariant with cattle, bison, and yak genomes.

TrioTrain builds new models by starting with an existing DeepVariant model. Version 0.8 currently uses DV-v1.4's short-read Whole Genome Sequence (WGS) model trained with the human GIAB samples.

TrioTrain can optionally add the allele frequency channel, if given population-level allele frequency data (PopVCF).

### Setup TrioTrain

Getting started with TrioTrain is straight-foward, but requires some configuration to work on your SLURM-based HPC cluster. The user guides below will walk you through what components require tweaking, depending on your system.

First, change directories to your working directory.

```bash
cd /path/to/working_dir
```

Then, complete these guides in order:

1. [Installation Guide](installation.md)
1. [Configuration Guide](configuration.md)
1. [Human GIAB Tutorial](walk-through.md)

### Other Commands and Options

There are various other commands and options available. For a complete list of
commands, use the `--help` flag:

```bash
python3 scripts/model_training/run_trio_train.py --help
```

To view a list of options available on a given command, use the `--help` flag with that command. For example, to get a list of all options available for the `build` command run the following:

```bash
mkdocs build --help
```

<font size= "4"> 
**[Got a question?](../user-guide/get-help.md)** <font size= "4">
