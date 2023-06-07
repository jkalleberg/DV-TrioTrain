#!/bin/bash
# scripts/setup/download_models.sh
"""
NOTES: These model ckpts are only required for warm-starting re-training, and are not used with 'run_deepvariant'

"""
echo -e "=== scripts/setup/download_models.sh > start $(date)"

##======= Downloading default WGS model (without AF channel) ===================##
#   This model allows for ONLY 7 layers in the example images 
#   Meaning, it is NOT compatible examples built with the allele frequency channel!

#   To view in web-browser, execute this to obtain a valid link: 
#       echo "https://console.cloud.google.com/storage/browser/deepvariant/models/DeepVariant/${BIN_VERSION_DV}/DeepVariant-inception_v3-${BIN_VERSION_DV}+data-wgs_standard"

echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Downloading 7-channel WGS model checkpoint (with InsertSize, but without AlleleFreq) - DeepVariant v${BIN_VERSION_DV}"
NO_AF_MODEL_BUCKET="https://storage.googleapis.com/deepvariant/models/DeepVariant/${BIN_VERSION_DV}/DeepVariant-inception_v3-${BIN_VERSION_DV}+data-wgs_standard"

# Use the same file naming convention and enable restarting of any interrupted downloads
curl --create-dirs --continue-at - "${NO_AF_MODEL_BUCKET}/model.ckpt.{data-00000-of-00001,index,example_info.json,meta}" --output "triotrain/model_training/pretrained_models/v${BIN_VERSION_DV}_withIS_noAF/model.ckpt.#1"
echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Done - Downloading 7-channel WGS model checkpoint (with InsertSize, but without AlleleFreq)"
##========================================================================##

##======= Downloading custom WGS model (with Allele Frequency channel) ======================##
#   This model allows for 8 layers in the example images 
#   Meaning, it IS compatible compatible examples built with the allele frequency channel!

#   To view in web-browser, execute this to obtain a valid link:  
#       https://console.cloud.google.com/storage/browser/brain-genomics-public/research/allele_frequency/pretrained_model_WGS/1.4.0;tab=objects?pageState=(%22StorageObjectListTable%22:(%22f%22:%22%255B%255D%22))&prefix=&forceOnObjectsSortingFiltering=false

echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Downloading 8-channel WGS model checkpoint (with InsertSize, with AlleleFreq) - DeepVariant v${BIN_VERSION_DV}"

AF_MODEL_BUCKET="https://storage.googleapis.com/brain-genomics-public/research/allele_frequency/pretrained_model_WGS/${BIN_VERSION_DV}"

# Use the same file naming convention and enable restarting of any interrupted downloads
curl --create-dirs --continue-at - "${AF_MODEL_BUCKET}/model.ckpt.{data-00000-of-00001,index,meta,example_info.json}" --output "triotrain/model_training/pretrained_models/v${BIN_VERSION_DV}_withIS_withAF/wgs_af.model.ckpt.#1"
echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Done - Downloading 8-channel WGS model checkpoint (with InsertSize, with AlleleFreq)"

##========================================================================##

echo -e "=== scripts/setup/download_models.sh > end $(date)"