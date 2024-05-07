# Getting Started

There are two main audiences of DV-TrioTrain:

1. **[Model users](#model-users)** - those who want to call variants using an existing, custom DeepVariant model produced by TrioTrain.

1. **[Model builders](#model-builders)** - those who want to customize an existing DeepVariant model by extending training on either new data or data from another diploid species.

We used TrioTrain to extend DeepVariant with cattle, bison, and yak genomes. TrioTrain begins with an existing, short-read, Whole Genome Sequencing (WGS) model built with the human GIAB samples. If provided with population-level allele frequency data (PopVCF), TrioTrain can enhance the model by adding the allele frequency channel. For example, the starting point for the model described in the [TrioTrain pre-print](https://www.biorxiv.org/content/10.1101/2024.04.15.589602v1) specifically used version 1.4.0 of DeepVariant *without* the allele frequency channel. However, subsequent bovine-trained iterations relied on allele frequency data from the UMAGv1 callset to reduce coverage bias. The current version of the bovine-trained model checkpoint file can be applied to other domesticated animal species with the required PopVCF.

---

## Model Users

Once you've identified your preferred model checkpoint, you're ready to go! Any model created by DV-TrioTrain can be used as an alternative checkpoint with the one-step, single-sample variant caller. [An index of compatible, published models can be found here](../user-guide/existing_models.md).

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

**We designed TrioTrain to be compatible with any diploid species without NIST-GIAB reference materials.** 

!!! warning
    The tutorial walk-through intentionally uses complete human genomes and will produce **~2 TB of intermediate / output data** within the chosen working directory. However, the last step of the tutorial will clean up any temporary files.

<font size= "5"> 
**TrioTrain Setup**
</font>

Getting started with TrioTrain is straightfoward, but requires careful configuration to work on your SLURM-based HPC cluster. The user guides below will walk you through what components require tweaking, depending on your system.

First, change directories to your working directory, where TrioTrain will be run: `cd /path/to/working_dir`

Then, complete these guides in the following order:

[:material-numeric-1-box: Installation Guide](installation.md){ .md-button .md-button--primary}
[:material-numeric-2-box: Configuration Guide](configuration.md){ .md-button .md-button--primary}
[:material-numeric-3-box: Human GIAB Tutorial](walk-through.md){ .md-button .md-button--primary}

---

<font size= "4"> 
Other Commands and Options
</font>

There are various other commands and options available. For a complete list of
commands, use the `--help` flag:

```bash
python3 triotrain/run_trio_train.py --help
```

[Got a question :octicons-question-16:](../user-guide/get-help.md){ .md-button }
