# DV-TrioTrain v0.8

DeepVariant-TrioTrain is an automated pipeline for extending DeepVariant (DV), a deep-learning-based germline variant caller. See the [original DeepVariant GitHub page](https://github.com/google/deepvariant) to learn more.

## Table of Contents

* [Background](#background)
* [Get Started](#user-guide)
* [Citation](#citation)

## Background

The existing DeepVariant models were only trained on human data. Previous work built species-specific DeepVariant models for [mosquito genomes](https://google.github.io/deepvariant/posts/2018-12-05-improved-non-human-variant-calling-using-species-specific-deepvariant-models/) and [the endangered Kākāpō parrot](https://www.biorxiv.org/content/10.1101/2022.10.22.513130v1.full). We built TrioTrain (DV-TT) to enable us to build custom DeepVariant models for cattle, bison, and yak genomes. Our custom models incorporate allele frequency data from over 5,500 published Bovine samples, making DV-TT the first tool to expand [the existing Allele Frequency model](https://doi.org/10.1186/s12859-023-05294-0) into non-human, mammalian genomes. Our work illustrates the limitations of applying models built exclusively with human-genome datasets in other species. Our findings suggest that comparative genomics approaches in deep learning model development offer performance benefits over species-specific models.

### How does TrioTrain work?

DV-TT is a SLURM-based, automated pipeline that produces new DV model(s) for germline variant-calling in any diploid organism, focusing on species without NIST-GIAB reference materials.

![Visual overview of training workflow: TrioTrain begins at an existing checkpoint, then creates labeled, shuffled examples for trio-binned samples before training on a parent and evaluating with the offspring. A new model is selected, which is then used as the starting point for the next iteration while simultaneously used to call variants in a set of test genomes. The resulting VCF from the new model is then compared against a GATK-derrived pseudo-truth VCF to compare model performance changes across training iterations.](https://github.com/jkalleberg/DV-TrioTrain/blob/0c42346a7dee708657358cdacdba298eaa1bfd7b/docs/img/Workflow_Sm_Horizontal.png?raw=true)

Currently, TrioTrain supports initializing training using an existing DV model. [An index of compatible models can be found here.](./docs/user-guide/existing_models.md)

Specifically, TrioTrain builds upon the existing DV model for short-read (Illumina) Whole Genome Sequence (WGS) data and, optionally, adds population-level allele frequency data from published samples. During model development, DV-TrioTrain iteratively feeds labeled examples from parent-offspring duos. Intuitively, a model trained on both parents should better predict inherited variants in the offspring; therefore, two training rounds are performed for each trio. After re-training, any models built with DV-TrioTrain become an alternative checkpoint with DeepVariant's one-step, single-sample variant caller.

**Assuming the necessary training data for your favorite species already exist, TrioTrain automatically enables customizing the DeepVariant model.** [Additional details about the required data can be found here.](./docs/user-guide/usage_guide.md)

### Why TrioTrain?

The unique re-training approach enables the model to incorporate inheritance expectations; **however, models built by DV-TrioTrain do not require trio-binned data for variant calling.**

While the DV-TT pipeline assumes re-training data are from trio-binned samples, models are trained to prioritize features of inherited variants to produce fewer Mendelian Inheritance Errors (MIE) in individual samples, in contrast to the [DeepTrio](https://github.com/google/deepvariant/blob/r1.5/docs/deeptrio-details.md) joint-caller.

<a name="user-guide"></a>

## Get Started

Detailed user guides for installation, configuration, and a tutorial walk-through using the Human GIAB samples are available [here.](./docs/getting-started/getting-started.md)

---

Breeding Insight at Cornell University provided a recording from a brief presentation, which you can watch on YouTube by clicking [here](https://www.youtube.com/watch?v=u8lpZZrt9Zc&list=PLzNvw7rej-RsuMLCQfrH7EKJs7o2og1qp).

<a name="citation"></a>

## How to cite

The TrioTrain manuscript is under review, but, in the meantime, our current pre-print is available on BioRxiv:

> [Overcoming Limitations to Deep Learning in Domesticated Animals with TrioTrain](https://www.biorxiv.org/content/10.1101/2024.04.15.589602v1)
Jenna Kalleberg, Jacob Rissman, Robert D. Schnabel
bioRxiv 2024.04.15.589602; doi: https://doi.org/10.1101/2024.04.15.589602


### Please also cite:

> [A universal SNP and small-indel variant caller using deep neural networks. *Nature Biotechnology* 36, 983–987 (2018).](https://rdcu.be/7Dhl) <br/>
Ryan Poplin, Pi-Chuan Chang, David Alexander, Scott Schwartz, Thomas Colthurst, Alexander Ku, Dan Newburger, Jojo Dijamco, Nam Nguyen, Pegah T. Afshar, Sam S. Gross, Lizzie Dorfman, Cory Y. McLean, and Mark A. DePristo.<br/>
doi: <https://doi.org/10.1038/nbt.4235>

> [Improving variant calling using population data and deep learning. *BMC Bioinformatics* 24, 197 (2023).](https://doi.org/10.1186/s12859-023-05294-0) <br/>
Nae-Chyun Chen, Alexey Kolesnikov, Sidharth Goel, Taedong Yun, Pi-Chuan Chang, and Andrew Carroll.<br/>
doi: <https://doi.org/10.1186/s12859-023-05294-0>

### Feedback and technical support

For questions, suggestions, or technical assistance, feel free to [open an issue](https://github.com/jkalleberg/DV-TrioTrain/issues) page or reach out to Jenna Kalleberg at [jakth2@mail.missouri.org](jakth2@mail.missouri.edu)

### Contributing to TrioTrain

Please [open a pull request](https://github.com/jkalleberg/DV-TrioTrain/pulls) if you wish to contribute to TrioTrain.

### License

[GPL-3.0 license](LICENSE)

### Acknowledgments

Many thanks to the developers and contributors of the many open-source packages used by TrioTrain.
