#!/bin/bash
# scripts/setup/download_GIAB_stratifications.sh
echo -e "=== scripts/setup/download_GIAB_stratifications.sh > start $(date)"

# NOTES --------------------------------------------------------------#

## GitHub describing the contents: https://github.com/genome-in-a-bottle/genome-stratifications
## Reviewers specifically asked about 'segmental duplications' -- defined by GIAB as repeated regions >1kb
## with >90% similarity).

## We will use the latest version of these stratifications: v3.5 (2024-07-18)
### GIAB FTP site link: https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/genome-stratifications/v3.5/ 

## We want the GRCh38 reference genome files. The MD5 checksums are below:

# 72d80c50a92aa67adbae89d697475130  ./GRCh38@all/SegmentalDuplications/GRCh38_notinsegdups.bb
# cb68fc5bed55a446d9d3dbadbef9d735  ./GRCh38@all/SegmentalDuplications/GRCh38_notinsegdups.bed.gz
# 6da75c8fa3c89477b7e2c1c8c95a3716  ./GRCh38@all/SegmentalDuplications/GRCh38_notinsegdups_gt10kb.bb
# 5e92747af6c751e17eb69dbb32bbb1a1  ./GRCh38@all/SegmentalDuplications/GRCh38_notinsegdups_gt10kb.bed.gz
# 3679fc4c03d7aa075241583a5b96447f  ./GRCh38@all/SegmentalDuplications/GRCh38_segdups.bb
# 72ec3f7db18ef9318c64b1df271703fe  ./GRCh38@all/SegmentalDuplications/GRCh38_segdups.bed.gz
# 0ea07e86ef580e3e6a81db39230e7e08  ./GRCh38@all/SegmentalDuplications/GRCh38_segdups_gt10kb.bb
# 747a94ef8f7a15128fb19265f8ecc170  ./GRCh38@all/SegmentalDuplications/GRCh38_segdups_gt10kb.bed.gz
# fd0f5cededa855a700b38988f8d0dc11  ./GRCh38@all/SegmentalDuplications/GRCh38_SegmentalDuplications_README.md

## 'gt10kb' = filtered for regions > 10,000 base pairs

# Change to the correct directory
cd triotrain/variant_calling/data/GIAB/

# Create a SegDup directory
install --directory --verbose stratifications/SegmentalDuplications

# FTP Parent Directory
FTP_DIR="https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/genome-stratifications/v3.5/"
REF_DIR="${FTP_DIR}/GRCh38@all"

# Download the READMEs
if [ ! -f ./stratifications/README.md ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: downloading general README now"
    curl -s --continue-at - ${FTP_DIR}/README.md -o ./stratifications/README.md
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: file found | './stratifications/README.md'"
fi

if [ ! -f ./stratifications/GRCh38-BACKGROUND.md ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: downloading general GRCh38 BACKGROUND now"
    curl -s --continue-at - ${REF_DIR}/GRCh38-BACKGROUND.md -o ./stratifications/GRCh38-BACKGROUND.md
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: file found | './stratifications/GRCh38-BACKGROUND.md'"
fi

if [ ! -f ./stratifications/GRCh38-README.md ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: downloading general GRCh38 README now"
    curl -s --continue-at - ${REF_DIR}/GRCh38-README.md -o ./stratifications/GRCh38-README.md
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: file found | './stratifications/GRCh38-README.md'"
fi

# Download the MD5 checksum file
if [ ! -f ./stratifications/genome-stratifications-md5s.txt ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: downloading GRCh38 checksum now..."
    curl -s --continue-at - ${FTP_DIR}/genome-stratifications-md5s.txt -o ./stratifications/genome-stratifications-md5s.txt
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: file found | './stratifications/genome-stratifications-md5s.txt'"
fi

# Define the file extensions to be downloaded:
declare -a Ext=("_notinsegdups.bed.gz" "_segdups.bed.gz" "_SegmentalDuplications_README.md")

if [ ! -f "./stratifications/SegmentalDuplications/GRCh38_segdups.bed.gz" ]; then 
    for e in ${Ext[@]}; do
        if [ -f ./stratifications/genome-stratifications-md5s.txt ]; then
            echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: downloading GRCh38${e} now..."
            curl -s --continue-at - "${REF_DIR}/SegmentalDuplications/GRCh38${e}" -o "./stratifications/SegmentalDuplications/GRCh38${e}" 
            echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: checking GRCh38${e} for corruption..."
            check_sum=$(cat ./stratifications/genome-stratifications-md5s.txt | grep "GRCh38${e}")
            old_path="./GRCh38@all/"
            new_path="./stratifications/"
            valid_check_sum="${check_sum/$old_path/$new_path}"
            echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: $(echo $valid_check_sum | md5sum -c)"
        else
            echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: file found | 'GRCh38${e}'"
        fi
    done
fi

echo -e "=== scripts/setup/download_GIAB_stratifications.sh > end $(date)"
