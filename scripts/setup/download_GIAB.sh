#!/bin/bash
# scripts/setup/download_GIAB.sh
echo -e "=== scripts/setup/download_GIAB.sh > start $(date)"

# NOTES --------------------------------------------------------------#
# The DV developers use the following data in their walk-through docs:
# 1) Reference Genome Version: GRCh38_no_alt_analysis_set.fasta
# 2) Benchmark Sample: HGOO3 [AshkenazimTrio-Father], typically only Chr20.
# 3) PopVCF (without genotypes): v3_missing2ref

# However, for a direct comparision between our cattle model and previous models, we need to calculate Mendelian Inheritance Errors (MIE). Therefore, we will be downloading the parents in this trio. We'll also need to download the reference PopVCF used to build the humanWGS_AF model.

# Our GIAB Trio1 Used: ----------------------------------------------------#
# Known as the Ashkenazi Jew Trio
# From Personal Genome Project
# AJ Son = HG002_NA24385_son
# AJ Father = HG003_NA24149_father
# AJ Mother = HG004_NA24143_mother

# Our GIAB Trio2 Used: ----------------------------------------------------#
# Known as the Han Chinese Trio
# From Personal Genome Project
# Chinese Son = HG005_NA24631_son
# Chinese Father = HG006_NA24694_father
# Chinese Mother = HG007_NA24695_mother

# A preprint describing these calls is at https://doi.org/10.1101/2020.07.24.212712.  The paper(s) above can be cited for use of the benchmark, and please cite http://www.nature.com/articles/sdata201625 (doi:10.1038/sdata.2016.25) when using the corresponding sequencing data.

cd triotrain/variant_calling/data/GIAB

#-------- General Reference Files ------------------------------------#
##======= Download Reference Genome =================================##
# NOTES ----
## Files Downloaded Include:
# 1. GRCh38 reference genome [FASTA]
# 2. GRCh38 index [FAI]

# output dir
install --directory --verbose reference

REFDIR=ftp://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.15_GRCh38/seqs_for_alignment_pipelines.ucsc_ids/
REFFILE=GCA_000001405.15_GRCh38_no_alt_analysis_set

if [ ! -f ./reference/md5checksums.txt ]; then
    echo "INFO: Downloading GRCh38 checksum now..."
    curl --continue-at - ${REFDIR}/md5checksums.txt -o ./reference/md5checksums.txt
else
    echo "INFO: file found | './reference/md5checksums.txt'"
fi

# Define the file extensions to be downloaded:
declare -a Ext=(".fna.gz" ".fna.fai")

for e in ${Ext[@]}; do
    if [ -f ./reference/md5checksums.txt ]; then
        echo "INFO: Downloading ${REFFILE}${e} now..."
        curl --continue-at - "${REFDIR}/${REFFILE}${e}" -o "./reference/${REFFILE}${e}" 
        echo "INFO: Checking ${REFFILE}${e} for corruption..."
        check_sum=$(cat ./reference/md5checksums.txt | grep "${REFFILE}${e}")
        old_path="./"
        new_path="./reference/"
        valid_check_sum="${check_sum/$old_path/$new_path}" 
        # echo $check_sum
        # echo $valid_check_sum
        echo "INFO: $(echo $valid_check_sum | md5sum -c)"
    else
        echo "INFO: file found | '${REFFILE}${e}'"
    fi
done

if [ -f "./reference/${REFFILE}.fna.gz" ]; then
    echo "INFO: Unzipping GRCh38 and re-naming reference files now..."
    gunzip -c "./reference/${REFFILE}.fna.gz" > "./reference/GRCh38_no_alt_analysis_set.fasta"
    rm "./reference/${REFFILE}.fna.gz"
    mv "./reference/${REFFILE}.fna.fai" ./reference/GRCh38_no_alt_analysis_set.fasta.fai
else
    echo "INFO: reference re-named already... SKIPPING AHEAD"
fi

##======= Download WGS PopVCF ========================================##
# NOTES ----
## Files Downloaded Include:
# 1. One-thousand genomes (1kGP) allele frequencies [VCF]
# 2. Allele-frequencies index [TBI]

# These data are ~940GiB to download completly.

# The newest version of WGS_AF model can be viewed on GCP here: https://console.cloud.google.com/storage/browser/brain-genomics-public/research/cohort/1KGP/cohort_dv_glnexus_opt/v3_missing2ref?pageState=(%22StorageObjectListTable%22:(%22f%22:%22%255B%255D%22))&prefix=&forceOnObjectsSortingFiltering=false
## THERE ARE TWO PAGES OF FILES!

# output dir
mkdir -p allele_freq

# Define where to get the AF data
AF_DIR="https://storage.googleapis.com/brain-genomics-public/research/cohort/1KGP/cohort_dv_glnexus_opt/v3_missing2ref"

for i in {{1..22},X,Y}
do  
    if [ ! -f ./allele_freq/cohort-chr${i}.release_missing2ref.no_calls.vcf.gz ]; then
        echo "INFO: Downloading chr${i} PopVCF..."
        curl --continue-at - ${AF_DIR}/cohort-chr${i}.release_missing2ref.no_calls.vcf.gz -o ./allele_freq/cohort-chr${i}.release_missing2ref.no_calls.vcf.gz 
    else
        echo "INFO: file found | 'chr${i} PopVCF'"
    fi

    if [ ! -f ./allele_freq/cohort-chr${i}.release_missing2ref.no_calls.vcf.gz.tbi ]; then
        echo "INFO: Downloading chr${i} index ..." 
        curl --continue-at - ${AF_DIR}/cohort-chr${i}.release_missing2ref.no_calls.vcf.gz.tbi -o ./allele_freq/cohort-chr${i}.release_missing2ref.no_calls.vcf.gz.tbi 
    else
        echo "INFO: file found | 'chr${i} index'"
    fi
done

# Merge the chr AF into a genome-wide AF
for i in {{1..22},X,Y}
 do
  echo "./triotrain/variant_calling/data/GIAB/allele_freq/cohort-chr$i.release_missing2ref.no_calls.vcf.gz" >> ./allele_freq/PopVCF.merge.list
done

echo -e "source ./scripts/setup/modules.sh
bcftools concat --file-list triotrain/variant_calling/data/GIAB/allele_freq/PopVCF.merge.list -Oz -o triotrain/variant_calling/data/GIAB/allele_freq/cohort.release_missing2ref.no_calls.vcf.gz
bcftools index triotrain/variant_calling/data/GIAB/allele_freq/cohort.release_missing2ref.no_calls.vcf.gz" > ./allele_freq/concat_PopVCFs.sh


# unable to check for file corruption, lacking a checksum file on GCP

#-------- Trio-Specific Files -------------------------------------------#
# Our GIAB Trio1 ----------------------------------------------------------#
declare -A Trio1=(["HG002"]="HG002_NA24385_son" ["HG003"]="HG003_NA24149_father" ["HG004"]="HG004_NA24143_mother")

# Our GIAB Trio2 ----------------------------------------------------------#
declare -A Trio2=(["HG005"]="HG005_NA24631_son" ["HG006"]="HG006_NA24694_father" ["HG007"]="HG007_NA24695_mother")

##======= Download Trio's GIAB Truth Files =============================##
# NOTES ---- 
# Currently using v4.2.1
## Files Downloaded Include:
# 1. benchmarking region files [BED]
# 2. benchmarking genotypes [VCF]
# 3. benchmarking genotype index [TBI]

# The benchmarking files from NIST can be found here: https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/

# output dir
mkdir -p benchmark

# Define where to get the truth data
TRUTHDIR=https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release

# Our GIAB Trio1 ----------------------------------------------------------#
for t in ${!Trio1[@]}; do
    echo "INFO: Downloading ${t}=${Trio1[${t}]} benchmarking files now..."
    if [ ! -f "./benchmark/${t}_GRCh38_1_22_v4.2_benchmark.bed" ]; then
        curl --continue-at - ${TRUTHDIR}/AshkenazimTrio/${Trio1[${t}]}/NISTv4.2.1/GRCh38/${t}_GRCh38_1_22_v4.2_benchmark.bed -o ./benchmark/${t}_GRCh38_1_22_v4.2_benchmark.bed 
    else
        echo "INFO: file found | '${t}_GRCh38_1_22_v4.2_benchmark.bed'"
    fi

    if [ ! -f "./benchmark/${t}_GRCh38_1_22_v4.2_benchmark.vcf.gz" ]; then 
        curl --continue-at - ${TRUTHDIR}/AshkenazimTrio/${Trio1[${t}]}/NISTv4.2.1/GRCh38/${t}_GRCh38_1_22_v4.2_benchmark.vcf.gz -o ./benchmark/${t}_GRCh38_1_22_v4.2_benchmark.vcf.gz 
    else
        echo "INFO: file found | '${t}_GRCh38_1_22_v4.2_benchmark.vcf.gz'"
    fi

    if [ ! -f "./benchmark/${t}_GRCh38_1_22_v4.2_benchmark.vcf.gz.tbi" ]; then  
        curl --continue-at - ${TRUTHDIR}/AshkenazimTrio/${Trio1[${t}]}/NISTv4.2.1/GRCh38/${t}_GRCh38_1_22_v4.2_benchmark.vcf.gz.tbi -o ./benchmark/${t}_GRCh38_1_22_v4.2_benchmark.vcf.gz.tbi
    else
        echo "INFO: file found | '${t}_GRCh38_1_22_v4.2_benchmark.vcf.gz.tbi'"
    fi

    # Download the README
    if [ ! -f "./benchmark/${t}_README_v4.2.1.txt" ]; then
        curl --continue-at - ${TRUTHDIR}/AshkenazimTrio/${Trio1[${t}]}/NISTv4.2.1/README_v4.2.1.txt -o ./benchmark/${t}_README_v4.2.1.txt 
    else
        echo "INFO: file found | '${t}_README_v4.2.1.txt'"
    fi

    # unable to check for file corruption, lacking a checksum file on ncbi site
done

# Our GIAB Trio2 ----------------------------------------------------------#
for t in ${!Trio2[@]}; do
    echo "INFO: Downloading ${t}=${Trio2[${t}]} benchmarking files now..."
    if [ ! -f "./benchmark/${t}_GRCh38_1_22_v4.2_benchmark.bed" ]; then
        curl --continue-at - ${TRUTHDIR}/ChineseTrio/${Trio2[${t}]}/NISTv4.2.1/GRCh38/${t}_GRCh38_1_22_v4.2.1_benchmark.bed -o ./benchmark/${t}_GRCh38_1_22_v4.2_benchmark.bed
    else
        echo "INFO: file found | '${t}_GRCh38_1_22_v4.2_benchmark.bed'"
    fi
    
    if [ ! -f "./benchmark/${t}_GRCh38_1_22_v4.2_benchmark.vcf.gz" ]; then
        curl --continue-at - ${TRUTHDIR}/ChineseTrio/${Trio2[${t}]}/NISTv4.2.1/GRCh38/${t}_GRCh38_1_22_v4.2.1_benchmark.vcf.gz -o ./benchmark/${t}_GRCh38_1_22_v4.2_benchmark.vcf.gz 
    else
        echo "INFO: file found | '${t}_GRCh38_1_22_v4.2_benchmark.vcf.gz'"
    fi 
    
    if [ ! -f "./benchmark/${t}_GRCh38_1_22_v4.2_benchmark.vcf.gz.tbi" ]; then
        curl --continue-at - ${TRUTHDIR}/ChineseTrio/${Trio2[${t}]}/NISTv4.2.1/GRCh38/${t}_GRCh38_1_22_v4.2.1_benchmark.vcf.gz.tbi -o ./benchmark/${t}_GRCh38_1_22_v4.2_benchmark.vcf.gz.tbi
    else
        echo "INFO: file found | '${t}_GRCh38_1_22_v4.2_benchmark.vcf.gz.tbi'"
    fi
    
    # Download the README
    if [ ! -f "./benchmark/${t}_README_v4.2.1.txt" ]; then
        curl --continue-at - ${TRUTHDIR}/ChineseTrio/${Trio1[${t}]}/NISTv4.2.1/README_v4.2.1.txt -o ./benchmark/${t}_README_v4.2.1.txt 
    else
        echo "INFO: file found | '${t}_README_v4.2.1.txt'"
    fi
    # unable to check for file corruption, lacking a checksum file on ncbi site
done

##======= Download Trio's GIAB Aligned Reads Files =======================##
# NOTES ---- 
## Files Downloaded Include:
# 1. NIST Illumina 2x250bp sequence reads alligned to GRCh38 [BAM]
# 2. Sequence reads index [BAI]
# 3. MD5 checksum [MD5]

# Indexes for various sequencing data and aligned files can be found here: https://github.com/genome-in-a-bottle/giab_data_indexes

# output dir
mkdir -p bam

# Our GIAB Trio1 ----------------------------------------------------------#
# BAM and BAI with MD5 checksums can be found here: https://github.com/genome-in-a-bottle/giab_data_indexes/blob/c4d3b95c2ebf14c175151e4723f82e8980722e90/AshkenazimTrio/alignment.index.AJtrio_Illumina_2x250bps_novoalign_GRCh37_GRCh38_NHGRI_06062016

echo "INFO: Downloading AJ Trio checksum now..."
curl -C - https://raw.githubusercontent.com/genome-in-a-bottle/giab_data_indexes/master/AshkenazimTrio/alignment.index.AJtrio_Illumina_2x250bps_novoalign_GRCh37_GRCh38_NHGRI_06062016 -o ./bam/AJtrio_Illumina_2x250bps_novoaligns_GRCh37_GRCh38.txt 

if [ ! -f ./bam/AJtrio.download ]; then 
    echo "source ./scripts/setup/modules.sh" > ./bam/AJtrio.download

    awk -F '\t' 'NR!=1 { 
        "basename " $1 | getline filename
        close("basename" $1)
        }
        index(filename, "GRCh38") {
            print "echo INFO: downloading ["filename"] now..." 
            print "curl -o triotrain/variant_calling/data/GIAB/bam/"filename" -C - "$1 
            print "echo "$2"\ttriotrain/variant_calling/data/GIAB/bam/"filename" > triotrain/variant_calling/data/GIAB/bam/"filename".md5"
            print "echo INFO: Checking ["filename"] for corruption..."
            print "md5sum -c triotrain/variant_calling/data/GIAB/bam/"filename".md5"
            }' ./bam/AJtrio_Illumina_2x250bps_novoaligns_GRCh37_GRCh38.txt  >> ./bam/AJtrio.download
else
    echo "INFO: file found | 'triotrain/variant_calling/data/GIAB/bam/AJtrio.download'"
fi

if [ ! -f ./bam/AJtrio.run ]; then
    echo "source ./scripts/setup/modules.sh" > ./bam/AJtrio.run
    awk -F '\t' 'NR!=1 { 
        "basename " $1 | getline filename
        close("basename" $1)
        }
        index(filename, "GRCh38") {
            "basename " filename " .bam" | getline label
            close("basename" filename " .bam")
            print "if [ ! -f ./triotrain/variant_calling/data/GIAB/bam/"label".coverage ]; then"
            print "    echo \"INFO: Calculating Coverage for ["label"] now...\"" 
            print "    samtools coverage ./triotrain/variant_calling/data/GIAB/bam/"filename" --output triotrain/variant_calling/data/GIAB/bam/"label".coverage"
            print "else"
            print "    echo \"INFO: file found | ./triotrain/variant_calling/data/GIAB/bam/"label".coverage\""
            print "fi" 
            
            print "if [ ! -f ./triotrain/variant_calling/data/GIAB/bam/$sampleID.avg_coverage.txt ]; then"
            print "    echo \"INFO: Calculating Average Coverage for [$sampleID] now...\"" 
            print "    awk '\''{ total += $6; count++ } END { print \""label" AVERAGE COVERAGE = \" total/count }'\'' triotrain/variant_calling/data/GIAB/bam/"label".coverage > triotrain/variant_calling/data/GIAB/bam/$sampleID.avg_coverage.txt"
            print "else"
            print "    echo \"INFO: file found | ./triotrain/variant_calling/data/GIAB/bam/$sampleID.avg_coverage.txt\""
            print "fi" 
            
            print "echo - - - - - - - - - - - - - - - - - - - - - - - - - - -"
            "basename " $3 | getline secondfile
            close("basename" $3)
            print "curl -o triotrain/variant_calling/data/GIAB/bam/"secondfile" -C - "$3
            print "echo "$4"\ttriotrain/variant_calling/data/GIAB/bam/"secondfile" > triotrain/variant_calling/data/GIAB/bam/"secondfile".md5"
            print "echo INFO: Checking ["secondfile"] for corruption..."
            print "md5sum -c triotrain/variant_calling/data/GIAB/bam/"secondfile".md5"
            print "echo ===================================================="
            } ' ./bam/AJtrio_Illumina_2x250bps_novoaligns_GRCh37_GRCh38.txt >> ./bam/AJtrio.run

    # if running on an interactive session with lots of memory, 
    # uncomment the line below
    # . ./bam/AJtrio.run
else
    echo "INFO: file found | 'triotrain/variant_calling/data/GIAB/bam/AJtrio.run'"
fi

# Our GIAB Trio2 ----------------------------------------------------------#
# BAM and BAI with MD5 checksums can be found here: https://github.com/genome-in-a-bottle/giab_data_indexes/blob/master/ChineseTrio/alignment.index.ChineseTrio_Illumina300X100X_wgs_novoalign_GRCh37_GRCh38_NHGRI_04062016 
# 

echo "INFO: Downloading HC Trio checksum now..."
    curl -C - https://raw.githubusercontent.com/genome-in-a-bottle/giab_data_indexes/master/ChineseTrio/alignment.index.ChineseTrio_Illumina300X100X_wgs_novoalign_GRCh37_GRCh38_NHGRI_04062016 -o ./bam/HCtrio_Illumina300X100X_wgs_novoalign_GRCh37_GRCh38.txt 

if [ ! -f ./bam/HCtrio.download ]; then
    echo "source ./scripts/setup/modules.sh" > ./bam/HCtrio.download

    awk -F '\t' 'NR!=1 { 
        "basename " $1 | getline filename
        close("basename" $1)
        }
        index(filename, "GRCh38") {
            print "echo INFO: downloading ["filename"] now..." 
            print "curl -o triotrain/variant_calling/data/GIAB/bam/"filename" -C - "$1 
            print "echo "$2"\ttriotrain/variant_calling/data/GIAB/bam/"filename" > triotrain/variant_calling/data/GIAB/bam/"filename".md5"
            print "echo INFO: Checking ["filename"] for corruption..."
            print "md5sum -c triotrain/variant_calling/data/GIAB/bam/"filename".md5"
            }' ./bam/HCtrio_Illumina300X100X_wgs_novoalign_GRCh37_GRCh38.txt >> ./bam/HCtrio.download
else
    echo "INFO: file found | 'triotrain/variant_calling/data/GIAB/bam/HCtrio.download'"
fi

if [ ! -f ./bam/HCtrio.run ]; then
    echo "source ./scripts/setup/modules.sh" > ./bam/HCtrio.run
    awk -F '\t' 'NR!=1 { 
        "basename " $1 | getline filename
        close("basename" $1)
        }
        index(filename, "GRCh38") {
            print "sampleID=$(cut -d. -f1 <<< "filename")"
            "basename " filename " .bam" | getline label
            close("basename" filename " .bam")
            print "if [ ! -f ./triotrain/variant_calling/data/GIAB/bam/"label".coverage ]; then"
            print "    echo \"INFO: Calculating Coverage for ["label"] now...\"" 
            print "    samtools coverage ./triotrain/variant_calling/data/GIAB/bam/"filename" --output triotrain/variant_calling/data/GIAB/bam/"label".coverage"
            print "else"
            print "    echo \"INFO: file found | ./triotrain/variant_calling/data/GIAB/bam/"label".coverage\""
            print "fi"  
            print "if [ ! -f ./triotrain/variant_calling/data/GIAB/bam/$sampleID.avg_coverage.txt ]; then"
            print "    echo \"INFO: Calculating Average Coverage for [$sampleID] now...\"" 
            print "    awk '\''{ total += $6; count++ } END { print \""label" AVERAGE COVERAGE = \" total/count }'\'' triotrain/variant_calling/data/GIAB/bam/"label".coverage > triotrain/variant_calling/data/GIAB/bam/$sampleID.avg_coverage.txt"
            print "else"
            print "    echo \"INFO: file found | ./triotrain/variant_calling/data/GIAB/bam/$sampleID.avg_coverage.txt\""
            print "fi" 
            print "echo - - - - - - - - - - - - - - - - - - - - - - - - - - -"
            "basename " $3 | getline secondfile
            close("basename" $3)
            print "curl -o triotrain/variant_calling/data/GIAB/bam/"secondfile" -C - "$3
            print "echo "$4"\ttriotrain/variant_calling/data/GIAB/bam/"secondfile" > triotrain/variant_calling/data/GIAB/bam/"secondfile".md5"
            print "echo INFO: Checking ["secondfile"] for corruption..."
            print "md5sum -c triotrain/variant_calling/data/GIAB/bam/"secondfile".md5"
            print "echo ===================================================="
            } ' ./bam/HCtrio_Illumina300X100X_wgs_novoalign_GRCh37_GRCh38.txt >> ./bam/HCtrio.run

    # if running on an interactive session with lots of memory, 
    # uncomment the line below
    # . ./HCtrio.run

else
    echo "INFO: file found | 'triotrain/variant_calling/data/GIAB/bam/HCtrio.run'"
fi

echo -e "=== scripts/setup/download_humanGIABdata.sh > end $(date)"