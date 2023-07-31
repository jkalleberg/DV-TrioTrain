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

For SLURM-based HPC clusters, we recommend using Apptainer (formerly known as Singularity).

```bash
BIN_VERSION_DV="1.4.0"
  apptainer run \
    -B /usr/lib/locale/:/usr/lib/locale/,\
      ${YOUR_INPUT_DIR}/DV-TrioTrain/:/run_dir/,\
      ${YOUR_REF_DIR}:/ref_dir/,\
      ${YOUR_BAM_DIR}:/bam_dir/,\
      ${YOUR_OUTPUT_DIR}:/out_dir/,\
      ${CUSTOM_MODEL_DIR}:/start_dir/,\
      ${YOUR_POPVCF_DIR}:/popVCF_dir/ \
    deepvariant_${BIN_VERSION_DV}.sif \
    /opt/deepvariant/bin/run_deepvariant \
    --model_type=WGS \
    --ref=/ref_dir/${YOUR_REFERENCE} \
    --reads=/bam_dir/${YOUR_BAM} \
    --output_vcf=/out_dir/${YOUR_OUTPUT_VCF} \
    --intermediate_results_dir=/out_dir/tmp/ \
    --num_shards=$(nproc) \ **This will use all your cores to run make_examples. Feel free to change.**
    --customized_model=/start_dir/${YOUR_CKPT_NAME} \
    --make_examples_extra_args="use_allele_frequency=true,population_vcfs=/popVCF_dir/${YOUR_POP_VCF}" \
    --dry_run=false **Default is false. If set to true, commands will be printed out but not executed.
```

---

## Model Builders

TrioTrain provides a model development framework for DeepVariant, and is therefore compatible with **any diploid species without NIST-GIAB reference materials.** The current version of DV-TT extends DeepVariant for use with cattle, bison, and yak genomes. Future versions of TrioTrain will hopefully support other domesticated animal species with the requisite data.

TrioTrain builds new models by starting with an existing DeepVariant model. The current version of TT uses DV-v1.4's short-read Whole Genome Sequence (WGS) model trained with the human GIAB samples. TrioTrain can optionally add the allele frequency channel, if given population-level allele frequency data (PopVCF).

### Setup TrioTrain

Getting started with TrioTrain is straight-foward, but requires some configuration to work on your SLURM-based HPC cluster. The user guides below will walk you through what components require tweaking, depending on your system.

First, change directories to your working directory.

```bash
cd /path/to/working_dir
```

Then, complete these guides in the following order:

1. [Installation Guide](installation.md)
1. [Configuration Guide](configuration.md)
1. [Human GIAB Tutorial](walk-through.md)

### Other Commands and Options

There are various other commands and options available. For a complete list of
commands, use the `--help` flag:

```bash
python3 triotrain/run_trio_train.py --help
```

To view a list of options available on a given command, use the `--help` flag with that command. For example, to get a list of all options available for the `build` command run the following:

```bash
mkdocs build --help
```

[Got a question :octicons-question-16:](../user-guide/get-help.md){ .md-button }
