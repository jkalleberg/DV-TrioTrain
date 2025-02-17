#!/bin/bash
# NOTE: This is run as a command line script via a SLURM job in the pipeline

echo "=== scripts/run/train_model.sh > start" $(date) 
echo "### Hostname: $(hostname)"
echo "### Writing temp files here:" $TMPDIR 

#-----------------------------------------------------------------#
#      Test that required environment variables are set           #
#-----------------------------------------------------------------#
# -z means "test if a variable is not set (missing) from the environment"
# therefore, lines 14-59 will exit whenever a required variable is missing.

if [ -z "$TRAIN_DIR" ]; then
  echo -e "$(date '+%Y-%m-%d %H:%M:%S') ERROR: Missing location to write training outputs; required for Apptainer bindings.\nExiting..."
  exit 2
fi

if [ -z "$TRAIN_GENOME" ]; then
  echo -e "$(date '+%Y-%m-%d %H:%M:%S') ERROR: Missing a defined training genome; required for selecting config.pbtxt file.\nExiting..."
  exit 2
fi

if [ -z "$NUM_STEPS" ]; then
  echo -e "$(date '+%Y-%m-%d %H:%M:%S') ERROR: Missing training length (steps to perform); required.\nExiting..."
  exit 2
fi

if [ -z "$BatchSize" ]; then
  echo -e "$(date '+%Y-%m-%d %H:%M:%S') ERROR: Missing number of examples to use per step; required.\nExiting..."
  exit 2
fi

if [ -z "$LearnRate" ]; then
  echo -e "$(date '+%Y-%m-%d %H:%M:%S') ERROR: Missing adjustment to CNN weights upon error calculation; required.\nExiting..."
  exit 2
fi

if [ -z "$ExamplesDir" ]; then
  echo -e "$(date '+%Y-%m-%d %H:%M:%S') ERROR: Missing location to training inputs; required for Apptainer bindings.\nExiting..."
  exit 2
fi

if [ -z "$CodePath" ]; then
  echo -e "$(date '+%Y-%m-%d %H:%M:%S') ERROR: Missing location of container; required for Apptainer bindings.\nExiting..."
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

#-----------------------------------------------------------------#
#      Choose container based on hardware (e.g. CPU vs GPU)       #
#-----------------------------------------------------------------#
if [ "$USE_GPU" == true ]; then
  container="deepvariant_${BIN_VERSION_DV}-gpu.sif"
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Using the GPU container | ${container}"
else
  # container="deepvariant_${BIN_VERSION_DV}.sif"
  echo -e "$(date '+%Y-%m-%d %H:%M:%S') ERROR: Using the CPU container [${container}] is not advised for model_training.\nExiting..."
  exit 2
fi

#-----------------------------------------------------------------#
#      Identify what parts of the training genome to use          #
#-----------------------------------------------------------------#
# NOTE: the Y chromosome and any unmapped reads are excluded 
#       with re-training by default during make_examples.
if [ -z "$RegionsFile_Path" ]; then
  if [ -z "$RegionsFile_File" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Missing a region file; all examples will be used"
    region_file_used=""
    region_path=""
    region_flag=""
  fi
else
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO:\t/region_dir/ : ${RegionsFile_Path}"
  region_file_used="${RegionsFile_Path}/${RegionsFile_File}"
  region_path="${RegionsFile_Path}:/region_dir/,"
  region_flag="--regions=\"/region_dir/${RegionsFile_File}\""
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Using a region file | '${region_file_used}'"
fi

#-----------------------------------------------------------------#
#      Identify if weights are initalized from previous model     #
#-----------------------------------------------------------------#
# NOTE: passing --start_from_checkpoint="default_model" does not work with a local container
#       the "default_model" weights are thus downloaded locally and used as the initial weights
#       for the first round of re-training
if [ -z "$CHKPT_PATH" ]; then
  if [ -z "$CHKPT_NAME" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') WARNING: Initializing new model with random weights"
    model_used="Default-${BIN_VERSION_DV}"
    base="/usr/lib/locale/:/usr/lib/locale/,"
    model_flag="--start_from_checkpoint=None"
  fi
else
  test_ckpt="${CHKPT_PATH}/${CHKPT_NAME}"
  model_used="${test_ckpt}"
  base="/usr/lib/locale/:/usr/lib/locale/,${CHKPT_PATH}:/start_dir/,"
  model_flag="--start_from_checkpoint=/start_dir/${CHKPT_NAME}"
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Initializing new model with weights from a previous model | '${CHKPT_PATH}/${CHKPT_NAME}'"
fi

#-----------------------------------------------------------------#
#      Identify if number of channels differ from expectations    #
#-----------------------------------------------------------------#
# NOTE: As the PopVCF model does not always exist with every version of DeepVariant,
#       we need to verify the number of channels in the warm-starting point model
#       and compare it to the number of channels in the examples given for training.
# NOTE: Requires a custom checkpoint to be given to identify a channels file!
if [ ! -z "$CHKPT_PATH" ] && [ ! -z "$CHKPT_NAME" ]; then
  # (^) If checkpoint path & name are NOT empty values, then
  EXPECTED_JSON="$CHKPT_PATH/$CHKPT_NAME.example_info.json"
  if [ -f $EXPECTED_JSON ]; then
    # Check for an exisiting example_info.json file 
    N_CHANNELS_EXPECTED=$(jq '.channels | length' ${EXPECTED_JSON})
  else
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') ERROR: Missing a required file | '${EXPECTED_JSON}'.\nExiting..."
    exit 2
  fi

  CREATED_JSON="$ExamplesDir/$TRAIN_GENOME.region1.labeled.tfrecords-00001-of-000${N_Parts}.gz.example_info.json"
  if [ -f $CREATED_JSON ]; then
    # Check for an exisiting example_info.json file 
    N_CHANNELS_MADE=$(jq '.channels | length' ${CREATED_JSON})
  else
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') ERROR: Missing a required file | '${EXPECTED_JSON}'.\nExiting..."
    exit 2
  fi
  
  if [ $N_CHANNELS_MADE -eq $N_CHANNELS_EXPECTED ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: number of channels matches expectations | '${N_CHANNELS_EXPECTED}'"
    channels_flag=""
  else
    echo "$(date '+%Y-%m-%d %H:%M:%S') WARNING: Number of channels created does not match expectations | '${N_CHANNELS_MADE} != ${N_CHANNELS_EXPECTED}'"
    echo "$(date '+%Y-%m-%d %H:%M:%S') WARNING: Therefore, adding another flag to enable warm-starting | '--allow_warmstart_from_different_num_channels'"  
    channels_flag="--allow_warmstart_from_different_num_channels"
  fi
else
  channels_flag=""
fi

#-----------------------------------------------------------------#
#      Determine if PopVCF will be used to create a channel       #
#-----------------------------------------------------------------#
# NOTE: If PopVCF variables exist and are not empty
#       include the appropriate path in the Apptainer bindings
if [[ $PopVCF_Path && ${PopVCF_Path-x} && $PopVCF_File && ${PopVCF_File-x} ]]
then
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: \$PopVCF_Path and \$PopVCF_File are set and NOT empty"
  bindings="${base}${region_path}${ExamplesDir}/:/examples_dir/,${TRAIN_DIR}/:/train_dir/,${CodePath}/:/run_dir/,${PopVCF_Path}/:/popVCF_dir/"
  echo -e "$(date '+%Y-%m-%d %H:%M:%S') INFO: APPTAINER BINDINGS INCLUDE:\n$(date '+%Y-%m-%d %H:%M:%S') INFO:\t/examples_dir/ : ${ExamplesDir}\n$(date '+%Y-%m-%d %H:%M:%S') INFO:\t/train_dir/ : ${TRAIN_DIR}\n$(date '+%Y-%m-%d %H:%M:%S') INFO:\t/popVCF_dir/ : ${PopVCF_Path}"
  # echo $bindings\
else
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Either \$PopVCF_Path or \$PopVCF_File are unset or empty"
  bindings="${base}${region_path}${ExamplesDir}/:/examples_dir/,${TRAIN_DIR}/:/train_dir/,${CodePath}/:/run_dir/"
  
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Determining if missing all PopVCF variables... "
  echo ${PopVCF?Error \$PopVCF is not defined. Exiting.}                    
  # ^ WILL STOP SCRIPT EXECUTION IF VARIABLE IS NOT SET
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: 'PopVCF' variable exists, but is empty, so those flag(s) will not be included"
  echo -e "$(date '+%Y-%m-%d %H:%M:%S') INFO: APPTAINER BINDINGS INCLUDE:\n$(date '+%Y-%m-%d %H:%M:%S') INFO:\t/examples_dir/ : ${ExamplesDir}\n$(date '+%Y-%m-%d %H:%M:%S') INFO:\t/train_dir/ : ${TRAIN_DIR}"
fi

#-----------------------------------------------------------------#
#      Execute training                                           #
#-----------------------------------------------------------------#

# Create a custom bash function for combining words
join_by()
{
  local d=${1-} f=${2-}
  if shift 2; then
    printf %s "$f" "${@/#/$d}"
  fi
}
flag=$(join_by \\n\\t ${region_flag} ${model_flag} ${channels_flag})

if [ ! -z "${flag}" ]; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: ADDITIONAL FLAGS INCLUDE:"
  echo -e "\t'${flag}'"
else
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: NO ADDITIONAL FLAGS TO INCLUDE."
fi

echo -e "$(date '+%Y-%m-%d %H:%M:%S') INFO: Saving re-training output here | '${TRAIN_DIR}'" 
echo -e "$(date '+%Y-%m-%d %H:%M:%S') INFO: One Epoch of re-training = ${NUM_STEPS} steps"

time apptainer run --nv -B ${bindings} \
  "${container}" \
  /opt/deepvariant/bin/model_train \
  --dataset_config_pbtxt="/examples_dir/${TRAIN_GENOME}.labeled.shuffled.merged.dataset_config.pbtxt" \
  --train_dir="/train_dir/" \
  --model_name="inception_v3" \
  --number_of_steps=${NUM_STEPS} \
  --save_interval_secs=300 \
  --batch_size=${BatchSize} \
  --learning_rate=${LearnRate} \
  ${model_flag} \
  ${channels_flag} \
  ${region_flag}

echo -e "=== scripts/run/train_model.sh > end $(date)"
