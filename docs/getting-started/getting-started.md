# Getting Started

There are two main audiences of DV-TrioTrain:

1. Model builders - for those who want to customize a new DeepVariant model, either with new data or in a new species.

2. Model users - for those who want to call variants with an existing, custom DeepVariant model.

---

## Model users

A major benefit of using DeepVariant over alternatives like GATK is that non-human genomics researchers do not have to become model builders to enable them to be model users. Once you've chosen a model checkpoint, you're ready to go!

### How to customize DeepVariant with an existing TrioTrain model

Published DV-TrioTrain models can be used as an alternative checkpoint with DeepVariant's one-step, single-sample variant caller. An index of available models can be found [here](../user-guide/existing_models.md).

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

## Installation

To install DV-TrioTrain, run the following command from the command line:

```bash
pip install dv_triotrain
```

For more details, see the [Installation Guide](user-guilde/installation.md).


## Creating a new project

Getting started is super easy. To create a new project, run the following
command from the command line:

```bash
mkdocs new my-project
cd my-project
```


## Other Commands and Options

There are various other commands and options available. For a complete list of
commands, use the `--help` flag:

```bash
mkdocs --help
```

To view a list of options available on a given command, use the `--help` flag
with that command. For example, to get a list of all options available for the
`build` command run the following:

```bash
mkdocs build --help
```

## Getting help

See the [User Guide](user-guide/usage_guide.md) for more complete documentation of all of TrioTrain's features.

To get help with TrioTrain, please use the [GitHub discussions (fix this link)]() or [GitHub issues (fix this link)]().
