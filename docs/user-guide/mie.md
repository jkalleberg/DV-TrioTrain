# Using Mendenian Inheritance Expectations to Assess Models

If you have trio-binned test genomes, TrioTrain can help calculate Mendelian Inheritance Error rate using `rtg-tools mendelian`. However, you must create a Sequence Data File (SDF) for each reference genome in the same directory as the reference genome in a sub-directory called `rtg_tools/`. Additional details about `rtg-tools` can be [found on GitHub](https://github.com/RealTimeGenomics/rtg-tools), or by [reviewing the PDF documentation here](https://cdn.rawgit.com/RealTimeGenomics/rtg-tools/master/installer/resources/tools/RTGOperationsManual.pdf).

## Create a Reference Sequence Data File

!!! warning
    This step is specific to the Human reference genome GRCh38. Cattle-specific input files are packaged with TrioTrain. **If you are working with a new species, you will need to create this file for your reference genome.**

After completing the tutorial walk-through, create the Human reference SDF by running the following at the command line:

```bash

source ./scripts/start_conda.sh     # Ensure the previously built conda env is active
bash scripts/setup/setup_rtg_tools.sh
```

For other species, use the following template:

??? example "Example | Creating the SDF"
    ```bash title="./scripts/setup/setup_rtg_tools.sh"
    --8<-- "scripts/setup/setup_rtg_tools.sh"
    ```

## Merge Results from each test genome

Creating per-iteration results by merging the per-test results from the baseline DeepVariant WGS.AF model, and the two iterations completed during the GIAB tutorial:

```bash
for start_i in $(seq 0 1); do
    echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: merging processed results from hap.py for GIAB run#${start_i}"
    python3 triotrain/summarize/merge_results.py --env ../TUTORIAL/GIAB_Trio/envs/run${start_i}.env -g Father
    echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: finished merging processed results from hap.py for GIAB run#${start_i}"
done
```

Creating results for all iterations by merging the per-iteration results created above:

```bash
python3 triotrain/summarize/merge_results.py --env ../TUTORIAL/GIAB_Trio/envs/run1.env --merge-all -m triotrain/summarize/data/tutorial_metadata.csv --dry-run
```
