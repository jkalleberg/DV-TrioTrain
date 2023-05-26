# DV-TrioTrain v0.8

DeepVariant-TrioTrain (DV-TT) is an automated pipeline for extending DeepVariant (DV), a deep-learning-based germline variant caller. See the [original DeepVariant github page](https://github.com/google/deepvariant) to learn more about DeepVariant.

<a name="background"></a>

## Background

Default DeepVariant models were only trained on human data. Our work developing DeepVariant-TrioTrain (DV-TT) illustrates the limitations of applying models built exclusively with human-genome datasets in other species. Species-specific DeepVariant models exist for [mosquito genomes](https://google.github.io/deepvariant/posts/2018-12-05-improved-non-human-variant-calling-using-species-specific-deepvariant-models/), and the [endangered Kākāpō parot](https://www.biorxiv.org/content/10.1101/2022.10.22.513130v1.full). However, DV-TrioTrain is the first tool to reproducably expand training DV into non-human, mammalian genomes from multiple species.

We built the DV-TT pipeline to extend DeepVariant with cattle, bison, and yak genomes. Specifically, TrioTrain builds upon the existing DV model for short-read (Illumina) Whole Genome Sequence (WGS) data, while adding population-level allele frequency data from over 5,500 published cattle samples from SRA. Currently, population-scale, long-read data is scarce in non-human species, but the DV-TT framework enables continued extension of DV as those data become available.

**TrioTrain provides a model development template for any diploid species without NIST-GIAB reference materials.** Our goal is to motivate adoption of scalable, data-driven variant calling models in domestic animal species. We propose that comparative genomics approaches in deep learning model development offers performance benefits over species-specific models.

!!! note
    DV-TT produces new DV model(s) for germline variant-calling in diploid organisms. However, there are some species-dependent behaviors in the pipeline.  

    **The current species supported include:**

    * humans
    * cows
    * mosquitoes
    * *your favorite species could go here!*
        * The DV-TT pipeline can be easily re-configured for your favorite species, assuming the necessary training data exist.
        * See the [User Guide] for more details.

DV-TrioTrain is designed for [transfer learning](https://machinelearningmastery.com/transfer-learning-for-deep-learning/), relying on new data sources and context to expand on prior experience. During model development, DV-TrioTrain iteratively feeds labeled examples from parent-offspring duos, enabling the model to incorporate inheritance expectations.

While the DV-TT pipeline assumes re-training data are from trio-binned samples, models built by DV-TrioTrain **do not require trio-binned data for variant calling.** In contrast to the [DeepTrio](https://github.com/google/deepvariant/blob/r1.5/docs/deeptrio-details.md) joint-caller, DV-TT models are trained to prioritize features of inherited variants to produce fewer Mendelian Inheritance Errors (MIE) in individual samples.

---

## How TrioTrain works

![workflow diagram](img/Workflow_Sm_Horizontal.png)

### Initialization

TrioTrain begins by initalizing with weights from an exisiting DeepVariant Model, using one of the following options:

* Human WGS DeepVariant-v1.4 formats
    1. Default model - includes the insert size channel
    2. Allele Frequency model - adds one additional channel from a Population VCF
* Any custom model satisfying the channel expectations below

### Training

For each trio provided, TrioTrain will perform 2 iterations of re-training, one for each parent. The starting parent is a user-specified parameter, either `Mother` or `Father`. With the first iteration, an existing DeepVariant model is used to initalize the weights and build upon prior learning. Subsequent iterations begin with a prior iteration's selected checkpoint.

### Evaluation

As a training iteration proceeds, learning is evaluated using labeled examples from the parents' offspring. The same individual's genome is used for both iterations run for a trio. Our assumption is that a model trained on a parent genome will be better at genotyping variants inherited from that parent in the offspring's genome.

### Selection

Model weights that produce the maximum F1-score in the offspring's genomeare selected for further testing, and to become the starting point for the next iteration.

### Testing

Testing occurs for all model iterations with a set of genomes previously unseen by the model. Variants are called with the model iterations by providing a custom checkpoint to the single-step variant caller.

### Comparision

Variants produced during a training iteration by a candidate model are compared against a user-defined benchmark set with hap.py, a standardized benchmarking tool recommended by the Global Alliance for Genomic Health (GA4GH). See GA4GH's resources on [Germline Small Variant Benchmarking Tools and Standards](https://github.com/ga4gh/benchmarking-tools), or the [original Illumina hap.py github page](https://github.com/Illumina/hap.py) to learn more.

[User Guide]: user-guide/README.md