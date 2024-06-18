#!/bin/bash
# NOTE: This is run as a command line script via a SLURM job in the pipeline

echo "=== scripts/run/train_model.sh > start" $(date) 
echo "### Hostname: $(hostname)"
echo "### Writing temp files here:" $TMPDIR 

#--- TEST THAT ENV VARIABLES ARE SET ---#
if [ -z "$TRAIN_DIR" ]; then
  echo "ERROR: Missing location to write training outputs; required for Apptainer bindings"
  exit 2
fi

if [ -z "$TRAIN_GENOME" ]; then
  echo "ERROR: Missing a defined training genome; required for selecting config.pbtxt file"
  exit 2
fi

if [ -z "$NUM_STEPS" ]; then
  echo "ERROR: Missing training length (steps to perform); required"
  exit 2
fi

if [ -z "$BatchSize" ]; then
  echo "ERROR: Missing number of examples to use per step; required"
  exit 2
fi

if [ -z "$LearnRate" ]; then
  echo "ERROR: Missing adjustment to CNN weights upon error calculation; required"
  exit 2
fi

if [ -z "$ExamplesDir" ]; then
  echo "ERROR: Missing location to training inputs; required for Apptainer bindings"
  exit 2
fi

if [ -z "$CodePath" ]; then
  echo "ERROR: Missing location of container; required for Apptainer bindings"
  exit 2
fi

#---- Identify the version of DeepVariant to use and hardward options -----#
if [ -z "$BIN_VERSION_DV" ]; then
  echo "ERROR: Missing DeepVariant Version Number; required to use Apptainer"
  exit 2
fi

if [ "$USE_GPU" == true ]; then
  container="deepvariant_${BIN_VERSION_DV}-gpu.sif"
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Using the GPU container | ${container}"
else
  # container="deepvariant_${BIN_VERSION_DV}.sif"
  echo "ERROR: Using the CPU container [${container}] is not advised for model_training"
  exit 2
fi

#---- Identify the initial weights to be used -----#
# NOTE: passing --start_from_checkpoint="default_model" does not work with a local container
#       the "default_model" weights are thus downloaded locally and used as the initial weights
#       for the first round of re-training
if [ -z "$CHKPT_PATH" ] ; then
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
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Initializing new model with weights from a previous model | '${CHKPT_PATH}${CHKPT_NAME}'"
fi

#---- Identify if additional channel will be added -----#
# NOTE: If PopVCF variables exist and are not empty
#       include the appropriate path in the Apptainer bindings
if [[ $PopVCF_Path && ${PopVCF_Path-x} && $PopVCF_File && ${PopVCF_File-x} ]]
then
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: \$PopVCF_Path and \$PopVCF_File are set and NOT empty"
  bindings="${base}${region_path}${ExamplesDir}/:/examples_dir/,${TRAIN_DIR}/:/train_dir/,${CodePath}/:/run_dir/,${PopVCF_Path}/:/popVCF_dir/"
  echo -e "$(date '+%Y-%m-%d %H:%M:%S') INFO: APPTAINER BINDINGS:\n$(date '+%Y-%m-%d %H:%M:%S') INFO:\t/examples_dir/ : ${ExamplesDir}\n$(date '+%Y-%m-%d %H:%M:%S') INFO:\t/train_dir/ : ${TRAIN_DIR}\n$(date '+%Y-%m-%d %H:%M:%S') INFO:\t/popVCF_dir/ : ${PopVCF_Path}"
  echo $bindings
  flag="${region_flag}${model_flag}" 
  
else
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Either \$PopVCF_Path or \$PopVCF_File are unset or empty"
  bindings="${base}${region_path}${ExamplesDir}/:/examples_dir/,${TRAIN_DIR}/:/train_dir/,${CodePath}/:/run_dir/"
  flag="${region_flag}${model_flag}"
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Determining if missing all PopVCF variables... "
  echo ${PopVCF?Error \$PopVCF is not defined. Exiting.}                    
  # ^ WILL STOP SCRIPT EXECUTION IF VARIABLE IS NOT SET
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: 'PopVCF' variable exists, but is empty, so those flag(s) will not be included"
  echo -e "$(date '+%Y-%m-%d %H:%M:%S') INFO: APPTAINER BINDINGS:\n$(date '+%Y-%m-%d %H:%M:%S') INFO:\t/examples_dir/ : ${ExamplesDir}\n$(date '+%Y-%m-%d %H:%M:%S') INFO:\t/train_dir/ : ${TRAIN_DIR}"
fi

#---- Identify what parts of the training genome are used -----#
# NOTE: the Y chromosome and any unmapped reads are excluded 
#       with re-training by default.
# NOTE: assumes that the total number of chromosomes are based 
#       on the bovid genome.
if [ -z "$REGION_PATH" ] ; then
  if [ -z "$REGION_FILE" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Missing a region file; all examples will be used"
    region_file_used=""
    region_path=""
    region_flag=""
  fi
else
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO:\t/region_dir/ : ${REGION_PATH}"
  region_file_used="${REGION_PATH}/${REGION_FILE}"
  region_path="${REGION_PATH}:/region_dir/,"
  region_flag="--regions=\"/region_dir/${REGION_FILE}\""
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Using a region file | '${region_file_used}'"
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Additional flags include:"
echo $flag
echo -e "$(date '+%Y-%m-%d %H:%M:%S') INFO: One Epoch of re-training = ${NUM_STEPS} steps"
echo -e "$(date '+%Y-%m-%d %H:%M:%S') INFO: Saving re-training output here | '${TRAIN_DIR}'" 

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
  ${flag}

echo -e "=== scripts/run/train_model.sh > end $(date)"
