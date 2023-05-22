#!/bin/bash
# NOTE: This is run as a command line script via a SLURM job in the pipeline
echo "=== scripts/run/eval_model.sh > start" $(date) 
echo "### Hostname: $(hostname)"
echo "### Writing temp files here:" $TMPDIR 

#--- CHECK THAT ENV VARIABLES ARE DEFINED ---#
if [ -z "$BIN_VERSION_DV" ]; then
  echo "ERROR: Missing DeepVariant Version Number; required to use Apptainer"
  exit 2
fi

if [ -z "$CONDA_BASE" ]; then
  echo "ERROR: Missing base environment path; required to enable 'conda activate'"
  exit 2
fi

if [ -z "$TRAIN_DIR" ]; then
  echo "ERROR: Missing location where training outputs were written; required for Apptainer bindings"
  exit 2
fi

if [ -z "$TRAIN_GENOME" ]; then
  echo "ERROR: Missing label for current training iteration; required for parsing evaluation metrics"
  exit 2
fi

if [ -z "$EnvFile" ]; then
  echo "ERROR: Missing analysis environment file; required for parsing evaluation metrics"
  exit 2
fi

if [ -z "$ExamplesDir" ]; then
  echo "ERROR: Missing location to training inputs; required for Apptainer bindings"
  exit 2
fi

if [ "$USE_GPU" == true ]; then
  container="deepvariant_${BIN_VERSION_DV}-gpu.sif"
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Using the GPU container | ${container}"
else
  # container="deepvariant_${BIN_VERSION_DV}.sif"
  echo "ERROR: Using the CPU container [${container}] is not advised for model_evaluations"
  exit 2
fi

if [ -z "$PostEval" ]; then
  CkptDir="/train_dir/"
  flag=""
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Model evaluations will be performed simultaneously with model training using:"
else
  mkdir -p "${TRAIN_DIR}/post_eval"
  CkptDir="/train_dir/post_eval/"
  flag="--log_dir=${CkptDir}"
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Model evaluations will be performed after model training using:"
fi

echo -e "$(date '+%Y-%m-%d %H:%M:%S') INFO:\t'${CkptDir}'"

echo -e "$(date '+%Y-%m-%d %H:%M:%S') INFO: Apptainer BINDINGS:\n$(date '+%Y-%m-%d %H:%M:%S') INFO:\t/examples_dir/ : ${ExamplesDir}\n$(date '+%Y-%m-%d %H:%M:%S') INFO:\t/train_dir/ : ${TRAIN_DIR}"

time apptainer run --nv -B /usr/lib/locale/:/usr/lib/locale/,"${ExamplesDir}/":/examples_dir/,"${TRAIN_DIR}/":/train_dir/ \
  "${container}" \
  /opt/deepvariant/bin/model_eval \
  --dataset_config_pbtxt="/examples_dir/Child.labeled.shuffled.merged.dataset_config.pbtxt" \
  --checkpoint_dir="${CkptDir}" \
  --eval_name='Child' \
  --save_interval_secs=-1 \
  --save_interval_steps=2000 \
  --eval_timeout=3600 \
  --batch_size=512  \
  "${flag}"

echo "=== scripts/run/eval_model.sh > end $(date)" 
