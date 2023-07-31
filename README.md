# DV-TrioTrain v0.8

DeepVariant-TrioTrain is an automated pipeline for extending DeepVariant (DV), a deep-learning-based germline variant caller. See the [original DeepVariant github page](https://github.com/google/deepvariant) to learn more.

## Table of Contents

* [Background](#background)
* [Get Started](#user-guide)
* [Citation](#citation)

## Background

Default DeepVariant models were only trained on human data. Our work developing DeepVariant-TrioTrain (DV-TT) illustrates the limitations of applying models built exclusively with human-genome datasets in other species. Previous work built species-specific DeepVariant models for [mosquito genomes](https://google.github.io/deepvariant/posts/2018-12-05-improved-non-human-variant-calling-using-species-specific-deepvariant-models/), and the [endangered Kākāpō parot](https://www.biorxiv.org/content/10.1101/2022.10.22.513130v1.full). However, DV-TrioTrain is the first tool to reproducably expand training into non-human, mammalian genomes.

### How does TrioTrain work?

DV-TT is a SLURM-based, automated pipeline that produces new DV model(s) for germline variant-calling in any diploid organism, with a focus on species without NIST-GIAB reference materials.

![Visual overview of training workflow, starting at an existing checkpoint, then proceeding to re-train and evaluate with trio-binned examples. A new model is selected, which is then used as the starting point for the next iteration while simultaneously used to call variants in a set of test genomes. The resulting VCF from the new model is then compared against a GATK-derrived pseudo-truth VCF to compare model performance changes across training iterations.](https://github.com/jkalleberg/DV-TrioTrain/blob/0c42346a7dee708657358cdacdba298eaa1bfd7b/docs/img/Workflow_Sm_Horizontal.png?raw=true)

Currently, TrioTrain supports initializing training using an existing DV. An index of compatible models can be found [here.](./docs/user-guide/existing_models.md) Specifically, TrioTrain builds upon the existing DV model for short-read (Illumina) Whole Genome Sequence (WGS) data, and adds population-level allele frequency data from over 5,500 published cattle samples from SRA. During model development, DV-TrioTrain iteratively feeds labeled examples from parent-offspring duos. Intuitively, a model trained on both parents, should be better at predicting inherited variants in the offspring; therefore, two rounds of training are peformed for each trio. After re-training, any models built with DV-TrioTrain become an alternative checkpoint with DeepVariant's one-step, single-sample variant caller.

We built the DV-TT pipeline to extend DeepVariant with cattle, bison, and yak genomes. **However, assuming your already have the necessary training data for your favorite species, TrioTrain enables you to create a custom model automatically.** Additional details about the required data can be found [here.](./docs/user-guide/usage_guide.md)

### Why TrioTrain?

Our findings suggest that comparative genomics approaches in deep learning model development offer performance benefits over species-specific models.



, enabling the model to incorporate inheritance expectations. While the DV-TT pipeline assumes re-training data are from trio-binned samples, **models built by DV-TrioTrain do not require trio-binned data for variant calling.** In contrast to the [DeepTrio](https://github.com/google/deepvariant/blob/r1.5/docs/deeptrio-details.md) joint-caller, DV-TT models are trained to prioritize features of inherited variants to produce fewer Mendelian Inheritance Errors (MIE) in individual samples.

<a name="user-guide"></a>
## Get started with TrioTrain

Detailed user guides for installation, configuration and a tutorial walk-through using the Human GIAB samples are available [here.](./docs/getting-started/getting-started.md)

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
