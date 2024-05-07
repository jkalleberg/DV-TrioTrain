# Handling SLURM Job Failure

SLURM job resubmission works on (1) TrioTrain iteration at a time to prevent duplication of currently running jobs from other iterations.

## Resubmit Existing SBATCH

Occasionally, a SLURM job may fail randomly. For example, you may get an email with the following subject line:

`SLURM Job_id=27671698 Name=examples-parallel-Father1-region4 Failed, Run time 00:20:27, NODE_FAIL`

Individual SLURM jobs can be resubmitted using a previously made SBATCH file by adding the following flags:

* `--start-itr`: tells TrioTrain which specific iteration to restart (i.e. Father1 = 1, Mother1 = 2, etc.)
* `--restart-jobs`: tells TrioTrain which job(s) to restart for a particular phase by providing a JSON-format string in `'{"phase_name<:genome>": [job_index, job_index]}'` format. If the list of job indexes includes a 0, TrioTrain will correct this by using 1-based indexing to ensure that region1 or test1 jobs correspond to the first job index.

!!! note
    Resubmitting an upstream job will resubmit all downstream jobs for that iteration. Resubmitting `make_examples` for Father-region1 will re-run nearly the entire iteration as the initial job will also trigger TrioTrain to resubmit `beam_shuffle` for Father-region1 followed by `re_shuffle` for Father. Re-shuffling will trigger `train_eval`, `select_ckt`, and `call_variants`, which then triggers `compare_happy` and `convert_happy`.

    For the above example, run the following at the command line:

    ```bash
    python3 triotrain/run_trio_train.py                                         \
        -g Father                                                               \
        --unmapped-reads chrUn                                                  \
        --est-examples 1                                                        \
        -m triotrain/model_training/tutorial/GIAB.Human_tutorial_metadata.csv   \
        -n GIAB_Trio                                                            \
        -r triotrain/model_training/tutorial/resources_used.json                \
        --num-tests 3                                                           \
        --output ../TUTORIAL                                                    \
        --start-itr 1                                                           \
        --stop-itr 2                                                            \
        --restart-jobs '{"make_examples:Father": [4]}'                          \
        --dry-run                                                               \
        --custom-checkpoint triotrain/model_training/pretrained_models/v1.4.0_withIS_withAF/wgs_af.model.ckpt
    ```

## Resubmit a New SBATCH

SLURM jobs may also fail due to insufficient resource requests, particularly the `beam_shuffle` or `re_shuffle` jobs. These jobs require you to overwrite the existing SBATCH job file with new resources.

Individual SLURM jobs can be resubmitted easily using the two flags above with an additional flag:

* `--overwrite`: tells TrioTrain to re-write a new SBATCH file and replace existing results files.

!!! warning
    Using this flag for any upstream job will replace all exising downstream results. Use the `--dry-run` flag to confirm how this flag will behave before re-running any jobs.

```bash
python3 triotrain/run_trio_train.py                                         \
    -g Father                                                               \
    --unmapped-reads chrUn                                                  \
    --est-examples 1                                                        \
    -m triotrain/model_training/tutorial/GIAB.Human_tutorial_metadata.csv   \
    -n GIAB_Trio                                                            \
    -r triotrain/model_training/tutorial/resources_used.json                \
    --num-tests 3                                                           \ 
    --output ../TUTORIAL                                                    \
    --start-itr 1                                                           \
    --restart-jobs '{"make_examples:Father": [4]}'                          \
    --overwrite                                                             \
    --dry-run                                                               \
    --custom-checkpoint triotrain/model_training/pretrained_models/v1.4.0_withIS_withAF/wgs_af.model.ckpt
```

## Including Currently Running Jobs

If you need to restart a downstream job that needs to be contingent upon a currently running job, you can edit the `--restart-jobs` flag to include existing SLURM job numbers. For example, the following would resubmit `compare_happy` for `test1`, and create new SBATCH files for `test2` and `test3`:

```bash
python3 triotrain/run_trio_train.py                                         \
    -g Father                                                               \
    --unmapped-reads chrUn                                                  \
    --est-examples 1                                                        \
    -m triotrain/model_training/tutorial/GIAB.Human_tutorial_metadata.csv   \
    -n GIAB_Trio                                                            \
    -r triotrain/model_training/tutorial/resources_used.json                \
    --num-tests 3                                                           \
    --custom-checkpoint triotrain/model_training/pretrained_models/v1.4.0_withIS_withAF/wgs_af.model.ckpt \
    --output ../TUTORIAL                                                    \
    --start-itr 1                                                           \
    --stop-itr 2                                                            \
    --restart-jobs '{"call_variants": [27669522, 2, 3]}'                    \
    --overwrite                                                             \
    --dry-run                                                               \
    --custom-checkpoint triotrain/model_training/pretrained_models/v1.4.0_withIS_withAF/wgs_af.model.ckpt
```
