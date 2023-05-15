# DV-TrioTrain v0.8
DV-TrioTrain is an automated pipeline for extending DeepVariant (DV), a deep learning based variant caller. See the [original DeepVariant github page](https://github.com/google/deepvariant) to learn more.

The DeepVariant-TrioTrain (DV-TT) pipeline is designed for [transfer learning](https://machinelearningmastery.com/transfer-learning-for-deep-learning/), when provided new data sources and context. During model development, DV-TrioTrain iteratively feeds labeled examples from parent-offspring duos, enabling the model to incorporate inheritance expectations. Additionally, the v0.8 DT-TT is the first tool to reproducably expand training DV into non-human, mammalian genomes. Note that DV-TT currently expects short-read (Illumina) Whole Genome Sequence (WGS) data from trio-binned samples for re-training.

However, models built by DV-TrioTrain **do not require trio-binned data for variant calling.** In contrast to the [DeepTrio](https://github.com/google/deepvariant/blob/r1.5/docs/deeptrio-details.md) joint-caller, DV-TT models are trained to prioritize features of inherited variants producing more accurate calls in individual samples. Published DV-TrioTrain models can be used as an alternative checkpoint with DeepVariant's one-step, single-sample variant caller. An index of available models can be found [here](pretrained_models).

## How to customize DeepVariant
We recommend using Apptainer (formerly known as Singularity), for local cluster computing.
```
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

DV-TrioTrain v0.8 currently supports initializing new DV models with the following models:
* the default, human DV v1.4 format (includes the insert size channel)
* the human WGS Allele Frequency model (default + one additional channel)
* any custom model satisfying the channel expectations above

DV-TT produces new DV models for germline variant-calling in diploid organisms. However, there are some species-dependent behaviors in the pipeline. The current species supported include:
* humans
* cows
* mosquitoes
* **(your favorite species could go here)**
  * the DV-TT pipeline can be easily re-configured for your favorite species, assuming your already have the necessary training data.
 

![workflow diagram](docs/images/Workflow_Sm_Horizontal.png)

### Training
For each trio provided, TrioTrain will perform 2 iterations of re-training, one for each parent. The starting parent is a user-specified parameter, either "Mother" or "Father." With the first iteration, an existing DeepVariant model is used to initalize the weights and build upon prior learning. Subsequent iterations begin with a prior iteration's selected checkpoint.

### Evaluation
As a training iteration proceeds, learning is evaluated using labeled examples from the parents' offspring. The same individual's genome is used for both iterations run for a trio. Our assumption is that a model trained on a parent genome will be better at genotyping variants inherited from that parent in the offspring's genome.

### Selection 
Model weights that produce the maximum F1-score are selected for further testing, and to become the starting point for the next iteration. 

### Testing
Testing occurs for all model iterations with a set of genomes previously unseen by the model. Variants are called with the model iterations by providing a custom checkpoint to the single-step variant caller.

### Comparision
Variants produced during a training iteration by a candidate model are compared against a user-defined benchmark set with hap.py, a standardized benchmarking tool recommended by the Global Alliance for Genomic Health (GA4GH). See GA4GH's resources on [Germline Small Variant Benchmarking Tools and Standards](https://github.com/ga4gh/benchmarking-tools), or the [original Illumina hap.py github page](https://github.com/Illumina/hap.py) to learn more.

## Background
Current DeepVariant models were only trained on human data. Our work developing TrioTrain illustrates the limitations of applying models built exclusively with human-genome datasets in other species. Previous work built species-specific DeepVariant models for [mosquito genomes](https://google.github.io/deepvariant/posts/2018-12-05-improved-non-human-variant-calling-using-species-specific-deepvariant-models/), and the [endangered Kākāpō parot](https://www.biorxiv.org/content/10.1101/2022.10.22.513130v1.full). However, previous research has not assessed using DV with other mammalian species. 

We built TrioTrain to enable us to extend DeepVariant with cattle, bison, and yak genomes, and we provide an alternative checkpoint that extends upon v1.4 WGS DeepVariant model for use with the one-step, single-sample variant caller. TrioTrain serves as a template for producing similar research in other domestic animal species. Our work illustrates deep learning opportunities for species without variant reference materials. 
