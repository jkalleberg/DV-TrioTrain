TrioTrain_README.md was last updated on 2025-04-22 by Jenna Kalleberg.  

--------------------
GENERAL INFORMATION
--------------------

Title of Dataset: Files accompanying the manuscript describing [TrioTrain](https://github.com/jkalleberg/DV-TrioTrain/)

Author Information
- Principal Investigator: Robert D. Schnabel (schnabelr@missouri.edu)  
- Jenna Kalleberg (jenna.kalleberg@missouri.edu)

---------------------------
SHARING/ACCESS INFORMATION
---------------------------

#### Licenses/restrictions placed on the data, or limitations of reuse: CC0
The full UMAG data use policy is included at the end of this document.

#### Recommended citation for the data:  
  Overcoming limitations to customize DeepVariant for domesticated animals with TrioTrain
  Kalleberg et al. bioRxiv 2024.04.15.589602; doi: https://doi.org/10.1101/2024.04.15.589602


#### Links to publicly accessible locations of the data:
https://www.ebi.ac.uk/eva/?eva-study=PRJEB86883


---------------------
DATA OVERVIEW
---------------------

This directory contains most of the ancillary data used to create an alternative, multi-species-trained DV-AF checkpoint for single-sample variant calling. However, due to file size limitations, some intermediate files required by the TrioTrain pipeline can only be made available upon request.

For the 15 bovine trios used in the current study, information about the IDs at UMAG and NCBI's are in the [training data table](./docs/user-guide/training_data), or in the project metadata CSV included with this dataset.

The VCF and BED files we provide are intended to be used as a 'silver-standard', preliminary truth to benchmark the accuracy of small variant calls in bovine genomes.  We strongly recommend reading the information and manuscripts below prior to using these calls to understand how best to use them and their limitations. 


### DATA WE DISTRIBUTE PUBLICLY

We provide a copy of the reference genome that the University of Missouri Animal Genomics group (UMAG) has generally used for mapping reads. This is the same reference genome used by the One Thousand Bull Genomes (1kBulls) project. Briefly, this reference genome has chromosomes 1...29,X,MT,UNMAPPED from L1 Dominette, and the Y chromosome represents the Father/Sire of Dominette. The preferred bovine reference has changed over time, and for different applications you may be familiar with alternative reference assemblies and versions. Additional information summarizing the history of the bovine reference genome can be found [here.](https://bovinegenome.elsiklab.missouri.edu/history)

We provide a per-sample 'ConfidentRegions' BED file which is given to DeepVariant to define truth regions from the autosomes and X chromosome only.

We also provide the population allele frequencies of high-confidence variant calls from the entire UMAGv1 cohort (N=5,612), otherwise known as a PopVCF.

We include the four (4) files that correspond to our customized DV-AF checkpoint created with TrioTrain (aka checkpoint 28).

### PROCESSED DATA TOO LARGE TO EASILY DISTRIBUTE

This directory *does not* contain the processed Illumina short-read WGS in CRAM/BAM format -- the expected input for DeepVariant. However, all of the data used within the current study are publicly available. The original FASTQ files for all bovine samples can be obtained from NCBI's Sequence Read Archive https://www.ncbi.nlm.nih.gov/sra/. A list of all BioSample IDs is included within this dataset as [a CSV file](./project_metadata.csv).

This directory also *does not* contain the high-confidence SNV, small indel, and homozygous reference calls produced with GATK's HaplotypeCaller (v3.8-1-0-gf15c1c3ef). Instead, for each chromosome (1...29,X,MT), the raw, multi-sample, compressed and indexed VCFs are available under EVA project accession [PRJEB86883](https://www.ebi.ac.uk/ena/browser/view/PRJEB86883). These multi-sample VCFs were extracted from the larger cohort (N=5,612) representing multiple bovine species. These data represent *all* genotypes after VQSR-optimization to the larger cohort -- the high-confidence calls plus filtered calls that were excluded prior to re-training with TrioTrain.

---------------------------
METHODOLOGICAL INFORMATION
---------------------------

**Best Practices for Using High-confidence Calls:**
Benchmarking variant calls is a complex process, and we recommend reading and following the best practices published in 2019 by the Global Alliance for Genomics and Health (GA4GH) Benchmarking Team (https://rdcu.be/bqpDT).  An example of NIST's Genome-in-a-bottle (GIAB) benchmark is described in the precisionFDA Truth Challenge V2 manuscript at https://doi.org/10.1101/2020.11.13.380741. Currently, these 7 human genomes are the only official benchmark for variant calling approaches, which includes using the updated GA4GH/GIAB stratifications for genomic repeats. The two human trios from GIAB were used to benchmark the customized checkpoint created with TrioTrain using bovine genomes.

**UMAGv1 Sequence Data Processing:**
Please see the Supplemental Methods (Notes S3 - S17) from the TrioTrain manuscript to learn more. Additionally, we provide a copy of the UMAGv1 SOP used to obtain and process raw FASTQ data from SRA as a [perl script](https://github.com/jkalleberg/DV-TrioTrain/scripts/run/run_sop_v0.7.2.pl). Note that this script is part of a separately maintained pipeline; therefore, this script is not written to be executable within the TrioTrain environment. 

**TrioTrain Truth VCFs:**
Please see the Supplemental Methods (Note S20) from the TrioTrain manuscript to learn more.

**TrioTrain CallableRegion BED files:**
Please see the Supplemental Methods (Note S12) from the TrioTrain manuscript to learn more. These files were created with GATK CallableLoci (version 3.8-1-0-gf15c1c3ef). For 50 individuals, one CallableRegions BED file exists for each BioSample present in the multi-sample raw VCF available under ENA project accession [PRJEB86883](https://www.ebi.ac.uk/ena/browser/view/PRJEB86883). 

For 3 individuals, two CallableRegions BED files exist, where the '-SYNTHETIC' prefix designates which file was used to define CallableRegions for the synthetic Illumina WGS reads created with NEAT (v3.2). These data were created by sampling from the reconstructed, haploid parental assemblies to produce an artificial replicate of each of the three F1 hybrid offspring. Please see the Supplemental Methods (Note S21) from the TrioTrain manuscript to learn more. 

**TrioTrain PopVCF files:**
Please see the Supplemental Methods (Note S12) from the TrioTrain manuscript to learn more.

-----------
FILES LIST
-----------

**Ancillary Data**
- TrioTrain_project_README.md
- TrioTrain_project_metadata.csv

**Reference genome used by UMAG for mapping**
- ARS-UCD1.2_Btau5.0.1Y_autosomes_withX.bed
- ARS-UCD1.2_Btau5.0.1Y.fa
- ARS-UCD1.2_Btau5.0.1Y.fa.fai
- ARS-UCD1.2_Btau5.0.1Y.dict

**Aligned Read files (UMAGv1)**
Due to file size limitations, these intermediate files are available upon request. 

**Benchmarking Variant files (UMAGv1)**
Due to file size limitations, these intermediate files are available upon request.

**Benchmarking Regions files (UMAG v1)**
- <BioSample>.callable.bed.gz
- <BioSample>-SYNTHETIC.callable.bed.gz

**Custom DeepVariant Model Checkpoint files (DeepVariant v1.4)**
- model.ckpt-282383.data-00000-of-00001          
- model.ckpt-282383.example_info.json
- model.ckpt-282383.index 
- model.ckpt-282383.meta

**Population Allele Frequency files (UMAG v1)**
- UMAG1.POP.FREQ.vcf.gz
- UMAG1.POP.FREQ.vcf.gz.tbi


-----------
FILE TYPES
-----------

**Ancillary Data**
* .md5 - md5 checksum for each file
* .md - README file
* .csv - metadata describing the samples used to build the bovine-trained  checkpoint for DeepVariant 

**Reference Genome used by UMAG for mapping**
* .fa - indexed FASTA file 
* .fa.fai - index for FASTA file
* .bed - BED file for masking certain chromosomes in the reference (Y,MT,UNMAPPED) 
* .dict - a sequence dictionary for a specific reference FASTA, created by  Picard CreateSequenceDictionary

**Aligned Read files (UMAG v1)**
* .cram/.bam - indexed CRAM/BAM file
* .cram.crai/.bam.bai - index for CRAM/BAM file

**Benchmarking Variant files (UMAG v1)**
* .vcf.gz - indexed + compressed VCF file
* .vcf.gz.csi - index for compressed VCF file

**Benchmarking Regions files (UMAG v1)**
* .callable.bed.gz - compressed BED file masking regions which are difficult to genotype with GATK

**Custom DeepVariant Model Checkpoint files (DeepVariant v1.4)**
* .data-00000-of-00001 - binary TensorFlow file containing the values of the variables used by the CNN model
* .index - binary TensorFlow file containing the variable names and describes the CNN model
* .meta - binary TensorFlow file containing the graph structure of the CNN model
* .example_info.json - JSON dictionary file describing the version of DeepVariant, the shape expected for tensors (variant examples) along with the compatible channel ids. [See the original documentation for DeepVariant to learn more.](https://google.github.io/deepvariant/posts/2022-06-09-adding-custom-channels/)

**Population Allele Frequency files (UMAG v1)**
* .vcf.gz - indexed + compressed VCF file 
* .vcf.gz.tbi - index for compressed VCF file

---------------------
UMAG Data Use Policy
---------------------

The data/work is provided by UMAG as a public service and is expressly provided
“AS IS.” UMAG MAKES NO WARRANTY OF ANY KIND, EXPRESS, IMPLIED OR STATUTORY,
INCLUDING, WITHOUT LIMITATION, THE IMPLIED WARRANTY OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE, NON-INFRINGEMENT AND DATA ACCURACY. UMAG does
not warrant or make any representations regarding the use of the data or the
results thereof, including but not limited to the correctness, accuracy,
reliability or usefulness of the data. UMAG SHALL NOT BE LIABLE AND YOU HEREBY
RELEASE UMAG FROM LIABILITY FOR ANY INDIRECT, CONSEQUENTIAL, SPECIAL, OR
INCIDENTAL DAMAGES (INCLUDING DAMAGES FOR LOSS OF BUSINESS PROFITS, BUSINESS
INTERRUPTION, LOSS OF BUSINESS INFORMATION, AND THE LIKE), WHETHER ARISING IN
TORT, CONTRACT, OR OTHERWISE, ARISING FROM OR RELATING TO THE DATA (OR THE USE
OF OR INABILITY TO USE THIS DATA), EVEN IF UMAG HAS BEEN ADVISED OF THE
POSSIBILITY OF SUCH DAMAGES.

To the extent that UMAG may hold copyright in countries other than the United
States, you are hereby granted the non-exclusive irrevocable and unconditional
right to print, publish, prepare derivative works and distribute the UMAG data,
in any medium, or authorize others to do so on your behalf, on a royalty-free
basis throughout the world.

You may improve, modify, and create derivative works of the data or any portion
of the data, and you may copy and distribute such modifications or works.
Modified works should carry a notice stating that you changed the data and
should note the date and nature of any such change. Please explicitly
acknowledge the University of Missouri Animal Genomics group (UMAG) as the source of
the data.

Permission to use this data is contingent upon your acceptance of the terms of
this agreement and upon your providing appropriate acknowledgments of UMAG’s
creation of the data/work.