#!/bin/bash
# NOTE: This is run as a command line script via a SLURM job in the pipeline

echo "=== scripts/run/eval_model.sh > start" $(date) 
echo "### Hostname: $(hostname)"
echo "### Writing temp files here:" $TMPDIR 

#-----------------------------------------------------------------#
#      Test that required environment variables are set           #
#-----------------------------------------------------------------#
# -z means "test if a variable is not set (missing) from the environment"
# therefore, lines 14-44 will exit whenever a required variable is missing.

if [ -z "$TRAIN_DIR" ]; then
  echo -e "$(date '+%Y-%m-%d %H:%M:%S') ERROR: Missing location to write training outputs; required for Apptainer bindings.\nExiting..."
  exit 2
fi

if [ -z "$TRAIN_GENOME" ]; then
  echo -e "$(date '+%Y-%m-%d %H:%M:%S') ERROR: Missing a defined training genome; required for selecting config.pbtxt file.\nExiting..."
  exit 2
fi

if [ -z "$ExamplesDir" ]; then
  echo -e "$(date '+%Y-%m-%d %H:%M:%S') ERROR: Missing location to training inputs; required for Apptainer bindings.\nExiting..."
  exit 2
fi

if [ -z "$BIN_VERSION_DV" ]; then
  # Identify the version of DeepVariant to use
  echo -e "$(date '+%Y-%m-%d %H:%M:%S') ERROR: Missing DeepVariant Version Number; required to use Apptainer.\nExiting..."
  exit 2
fi

if [ -z "$N_Parts" ]; then
  # Identify the number of cores used to create examples
  echo -e "$(date '+%Y-%m-%d %H:%M:%S') ERROR: Missing number of processorys; required to use check number of channels.\nExiting..."
  exit 2
fi

if [ -z "$CONDA_BASE" ]; then
  echo -e "ERROR: Missing base environment path; required to enable 'conda activate'.\nExiting..."
  exit 2
fi

#-----------------------------------------------------------------#
#      Choose container based on hardware (e.g. CPU vs GPU)       #
#-----------------------------------------------------------------#
if [ "$USE_GPU" == true ]; then
  container="deepvariant_${BIN_VERSION_DV}-gpu.sif"
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Using the GPU container | ${container}"
else
  # container="deepvariant_${BIN_VERSION_DV}.sif"
  echo "ERROR: Using the CPU container [${container}] is not advised for model_evaluations"
  exit 2
fi

# #-----------------------------------------------------------------#
# #      Identify if number of channels differ from expectations    #
# #-----------------------------------------------------------------#
# # NOTE: As the PopVCF model does not always exist with every version of DeepVariant,
# #       we need to verify the number of channels in the warm-starting point model
# #       and compare it to the number of channels in the examples given for training.
# # NOTE: Requires a custom checkpoint to be given to identify a channels file!
# if [ -n "$CHKPT_PATH" ] && [ -n "$CHKPT_NAME" ]; then
#   # (^) If checkpoint path & name are a non-empty value, then
  
#   EXPECTED_JSON="$CHKPT_PATH/$CHKPT_NAME.example_info.json"
#   if [ -f $EXPECTED_JSON ]; then
#     # Check for an exisiting example_info.json file 
#     N_CHANNELS_EXPECTED=$(jq '.channels | length' ${EXPECTED_JSON})
#   else
#     echo -e "$(date '+%Y-%m-%d %H:%M:%S') ERROR: Missing a required file | '${EXPECTED_JSON}'.\nExiting..."
#     exit 2
#   fi

#   CREATED_JSON="$ExamplesDir/Child.region1.labeled.tfrecords-00001-of-000${N_Parts}.gz.example_info.json"
#   if [ -f $CREATED_JSON ]; then
#     # Check for an exisiting example_info.json file 
#     N_CHANNELS_MADE=$(jq '.channels | length' ${CREATED_JSON})
#   else
#     echo -e "$(date '+%Y-%m-%d %H:%M:%S') ERROR: Missing a required file | '${EXPECTED_JSON}'.\nExiting..."
#     exit 2
#   fi
  
#   if [ $N_CHANNELS_MADE -eq $N_CHANNELS_EXPECTED ]; then
#     echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: number of channels matches expectations | '${N_CHANNELS_EXPECTED}'"
#     channels_flag=""
#   else
#     echo "$(date '+%Y-%m-%d %H:%M:%S') WARNING: Number of channels created does not match expectations | '${N_CHANNELS_MADE} != ${N_CHANNELS_EXPECTED}'"
#     echo "$(date '+%Y-%m-%d %H:%M:%S') WARNING: Therefore, adding another flag to enable warm-starting | '--allow_warmstart_from_different_num_channels'"  
#     channels_flag="--allow_warmstart_from_different_num_channels"
#   fi
# else
#   channels_flag=""
# fi

#-----------------------------------------------------------------#
#      Determine if evaluations performed after training          #
#-----------------------------------------------------------------#
if [ -z "$PostEval" ]; then
  CkptDir="/train_dir/"
  eval_flag=""
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Model evaluations will be performed simultaneously with model training using:"
else
  mkdir -p "${TRAIN_DIR}/post_eval"
  CkptDir="/train_dir/post_eval/"
  eval_flag="--log_dir=${CkptDir}"
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Model evaluations will be performed after model training using:"
fi

echo -e "$(date '+%Y-%m-%d %H:%M:%S') INFO:\t'${CkptDir}'"

#-----------------------------------------------------------------#
#      Execute evaluation                                         #
#-----------------------------------------------------------------#
# Create a custom bash function for combining words
join_by()
{
    local IFS="$1"; shift; echo "$*";
}
# flag=$(join_by ' \\' ${channels_flag} ${eval_flag})
flag=$(join_by ' \\' ${eval_flag})

if [ ! -z "${flag}" ]; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: ADDITIONAL FLAGS INCLUDE |"
  echo -e "$(date '+%Y-%m-%d %H:%M:%S') INFO:\t'${flag}'"
else
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: NO ADDITIONAL FLAGS TO INCLUDE."
fi
echo -e "$(date '+%Y-%m-%d %H:%M:%S') INFO: Saving evaluation output here | '${TRAIN_DIR}/eval_Child/'" 
echo -e "$(date '+%Y-%m-%d %H:%M:%S') INFO: APPTAINER BINDINGS INCLUDE:\n$(date '+%Y-%m-%d %H:%M:%S') INFO:\t/examples_dir/ : ${ExamplesDir}\n$(date '+%Y-%m-%d %H:%M:%S') INFO:\t/train_dir/ : ${TRAIN_DIR}"

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
