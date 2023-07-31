# DV-TrioTrain v0.8

DeepVariant-TrioTrain is an automated pipeline for extending DeepVariant (DV), a deep-learning-based germline variant caller. See the [original DeepVariant github page](https://github.com/google/deepvariant) to learn more.

## Table of Contents

* [Background](#background)  
* [Genotyping Tutorial](#usage)
* [Citation](#citation)

## Background

Default DeepVariant models were only trained on human data. Our work developing DeepVariant-TrioTrain (DV-TT) illustrates the limitations of applying models built exclusively with human-genome datasets in other species. Previous work built species-specific DeepVariant models for [mosquito genomes](https://google.github.io/deepvariant/posts/2018-12-05-improved-non-human-variant-calling-using-species-specific-deepvariant-models/), and the [endangered Kākāpō parot](https://www.biorxiv.org/content/10.1101/2022.10.22.513130v1.full). However, DV-TrioTrain is the first tool to reproducably expand training DV into non-human, mammalian genomes.

DV-TrioTrain v0.8 currently supports initializing a new DV model with one the following:

* the default, human DV v1.4 format (includes the insert size channel)
* the human WGS Allele Frequency model (default + one additional channel)
* any custom model satisfying the channel expectations above

We built the DV-TT pipeline to extend DeepVariant with cattle, bison, and yak genomes. Specifically, TrioTrain builds upon the existing DV model for short-read (Illumina) Whole Genome Sequence (WGS) data, and adds population-level allele frequency data from over 5,500 published cattle samples from SRA. Currently, long-read data is scarce in non-human species, but the DV-TT framework enables continued extension of DV as those data become available.

### Why TrioTrain?

TrioTrain provides a template for model development for any diploid species without NIST-GIAB reference materials. By developing a SLURM-based automated re-training pipeline, we aim to fascilitate adoption of scalable, data-driven variant calling models in domestic animal species. We propose that comparative genomics approaches in deep learning model development offer performance benefits over species-specific models.

DV-TT produces new DV model(s) for germline variant-calling in diploid organisms. The current species supported include:

* humans
* cattle / bison / yak
* *your favorite species could go here* - assuming your already have the necessary training data

During model development, DV-TrioTrain iteratively feeds labeled examples from parent-offspring duos, enabling the model to incorporate inheritance expectations. While the DV-TT pipeline assumes re-training data are from trio-binned samples, **models built by DV-TrioTrain do not require trio-binned data for variant calling.** In contrast to the [DeepTrio](https://github.com/google/deepvariant/blob/r1.5/docs/deeptrio-details.md) joint-caller, DV-TT models are trained to prioritize features of inherited variants to produce fewer Mendelian Inheritance Errors (MIE) in individual samples.

<a name="usage"></a>

## How to customize DeepVariant with a TrioTrain model

Published DV-TrioTrain models can be used as an alternative checkpoint with DeepVariant's one-step, single-sample variant caller. An index of available models can be found [here (fix this link)](pretrained_models).

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

<a name="citation"></a>

## How to cite

> Citation to go here

Please also cite:

> [A universal SNP and small-indel variant caller using deep neural networks. *Nature Biotechnology* 36, 983–987 (2018).](https://rdcu.be/7Dhl) <br/>
Ryan Poplin, Pi-Chuan Chang, David Alexander, Scott Schwartz, Thomas Colthurst, Alexander Ku, Dan Newburger, Jojo Dijamco, Nam Nguyen, Pegah T. Afshar, Sam S. Gross, Lizzie Dorfman, Cory Y. McLean, and Mark A. DePristo.<br/>
doi: <https://doi.org/10.1038/nbt.4235>

### Feedback and technical support

For questions, suggestions, or technical assistance, feel free to [open an issue](https://github.com/jkalleberg/DV-TrioTrain/issues) page or reach out to Jenna Kalleberg at [jakth2@mail.missouri.org](jakth2@mail.missouri.edu)

### Contributing to TrioTrain

Please [open a pull request](https://github.com/jkalleberg/DV-TrioTrain/pulls) if you wish to contribute to TrioTrain.

### License

[GPL-3.0 license](LICENSE)

### Acknowledgements

Many thanks to the developers and contributors of the many open source packages used by TrioTrain:
