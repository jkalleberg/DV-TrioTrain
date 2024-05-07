# DV-TrioTrain v0.8

## Background

The existing DeepVariant models were only trained on human data. Species-specific DeepVariant models exist for [mosquito genomes](https://google.github.io/deepvariant/posts/2018-12-05-improved-non-human-variant-calling-using-species-specific-deepvariant-models/), and the [endangered Kākāpō parot](https://www.biorxiv.org/content/10.1101/2022.10.22.513130v1.full). We built TrioTrain (DV-TT) to enable us to create custom DeepVariant models for cattle, bison, and yak genomes. Our custom models incorporate allele frequency data from over 5,500 published Bovine samples, making DV-TT the first tool to expand the existing Allele Frequency model into non-human, mammalian genomes. Our work illustrates the limitations of applying models built exclusively with human-genome datasets in other species. Our findings suggest comparative genomics approaches in deep learning model development offer performance benefits over species-specific models.

---

## How TrioTrain works

DV-TT is a SLURM-based, automated pipeline that produces new DV model(s) for germline variant-calling in any diploid organism, **focusing on species without NIST-GIAB reference materials.**

![workflow diagram](../img/Workflow_Sm_Horizontal.png)

**Assuming the necessary training data for your favorite species already exist, TrioTrain automatically enables customizing the DeepVariant model.** [Additional details about the required data can be found here.](https://github.com/jkalleberg/DV-TrioTrain/blob/62ec43dba06e8004abda1b09242ea4a3450048ad/docs/user-guide/usage_guide.md)

### Initialization

Currently, TrioTrain supports initializing training with weights from an existing DeepVariant model using one of the following options:

* Human WGS DeepVariant-v1.4 formats
    1. Default model - includes the insert size channel
    2. Allele Frequency model - adds one additional channel from a Population VCF
* Any custom model satisfying the channel expectations below

[An index of compatible models can be found here.](https://github.com/jkalleberg/DV-TrioTrain/blob/62ec43dba06e8004abda1b09242ea4a3450048ad/docs/user-guide/existing_models.md)

### Training

For each trio provided, TrioTrain will perform two (2) iterations of re-training, one for each parent. The starting parent is a user-specified parameter, either `Mother` or `Father`. With the first iteration, an existing DeepVariant model is used to initialize the weights and build upon prior learning. Subsequent iterations begin with a previous iteration's selected checkpoint.

### Evaluation

As a training iteration proceeds, learning is evaluated using labeled examples from the parents' offspring. The same individual's genome is used for both iterations run for a trio. We hypothezie that a model trained on a parent genome will be able to genotype variants inherited from that parent in the offspring's genome.

### Selection

The model weights that produce the maximum F1-score in the offspring's genome are selected for further testing, and to become the starting point for the next iteration.

### Testing

Testing occurs for all model iterations with a set of genomes previously unseen by the model. Variants are called with the model iterations by providing a custom checkpoint to the single-step variant caller.

### Comparision

Variants produced during a training iteration by a candidate model are compared against a user-defined benchmark set with hap.py, a standardized benchmarking tool recommended by the Global Alliance for Genomic Health (GA4GH). See GA4GH's resources on [Germline Small Variant Benchmarking Tools and Standards](https://github.com/ga4gh/benchmarking-tools) or the [original Illumina hap.py GitHub page](https://github.com/Illumina/hap.py) to learn more.

## Author

Jenna Kalleberg (<jakth2@mail.missouri.org>)

## Acknowledgements

We thank the developers and contributors to the many open-source packages TrioTrain uses.
