!#/bin/bash
# template for how to run the scripts created during setup

# merge the PopVCF
sbatch -n1 -t 10:00:00 -p BioCompute --mem=10G -A biocommunity --job-name concat_PopVCF --output triotrain/variant_calling/data/GIAB/allele_freq/%j_concat_PopVCF.out --mail-user=jakth2@mail.missouri.edu --mail-type=FAIL,END,TIME_LIMIT --wrap="bash triotrain/variant_calling/data/GIAB/allele_freq/concat_PopVCFs.sh"

# download the AJtrio BAMs
sbatch -n1 -t 10:00:00 -p BioCompute --mem=0 --exclusive -A biocommunity --job-name AJtrio --output triotrain/variant_calling/data/GIAB/bam/%j_download_AJtrio.out --mail-user=jakth2@mail.missouri.edu --mail-type=FAIL,END,TIME_LIMIT --wrap="bash triotrain/variant_calling/data/GIAB/bam/AJtrio.download"

# download the HCtrio BAMs
sbatch -n1 -t 10:00:00 -p BioCompute --mem=0 --exclusive -A biocommunity --job-name HCtrio --output triotrain/variant_calling/data/GIAB/bam/%j_download_HCtrio.out --mail-user=jakth2@mail.missouri.edu --mail-type=FAIL,END,TIME_LIMIT --wrap="bash triotrain/variant_calling/data/GIAB/bam/HCtrio.download"
