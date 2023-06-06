# Human GIAB Demo

This demo will enable you to confirm setup worked correctly, and provide you with an example of how to run DV-TrioTrain.

## 1. Download pre-trained models

Running a local copy of a container requires us to create a local copy of the `model.ckpt` files.

```bash
bash scripts/setup/download_models.sh
```

!!! note
    These models are the human-trained models produced by Google Genomics Health Group. An index of the models used can be found [here](existing_models.md).

## 2. Download GIAB data

Create a local copy of the GIAB trio data v4.2.1 for benchmarking.

```bash
# Download the checksums and intermediate files
bash scripts/setup/download_GIAB.sh

# Submit SLURM jobs for downloading large files
bash triotrain/variant_calling/data/GIAB/bam/AJtrio.download 
bash triotrain/variant_calling/data/GIAB/bam/HCtrio.download 
```

## 3. Create supplmentary reference files

After the Human reference genome is downloaded, supplementary files must also be created.

### Reference dictionary file with `picard`

MISSING: ADD THIS IN!

### Files for `rtg-tools`

These files are required by `rtg-tools mendelian`. This step is specific to the Human reference genome GRCh38.

```bash
bash scripts/setup/setup_rtg_tools.sh
```
