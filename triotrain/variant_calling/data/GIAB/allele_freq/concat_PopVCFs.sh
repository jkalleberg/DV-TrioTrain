source ./scripts/setup/modules.sh
bcftools concat --file-list triotrain/variant_calling/data/GIAB/allele_freq/PopVCF.merge.list -Oz -o triotrain/variant_calling/data/GIAB/allele_freq/cohort.release_missing2ref.no_calls.vcf.gz
bcftools index triotrain/variant_calling/data/GIAB/allele_freq/cohort.release_missing2ref.no_calls.vcf.gz
