#!/bin/bash
## copy_happy_metrics.sh

## This script copies the hap.py outputs (*.extended.csv.gz) for each
## iteration, and organizes them into a new directory, depending on model used:

##### TRIO_TRAIN ITERATIONS
##### "../TRIO_TRAINING_OUTPUTS/<EXPERIMENT>/summary/<CHECKPOINT>/<SAMPLE_ID>/happy#.no-flags.extended.csv.gz"

##### BASELINE ITERATIONS
##### ../TRIO_TRAINING_OUTPUTS/summary/<CHECKPOINT>/<SAMPLE_ID>/happy#.no-flags.extended.csv.gz" 

## This format follow the structure of "benchmarking" with trios, which
## expected by "happy_performance.py" script that separates SNV/INDEL and 
## HET/HOM as opposed to "convert_happy" that only does SNV/INDEL.

echo -e "=== triotrain/summarize/copy_happy_metrics.sh > start $(date)"

declare -A SAMPLE_NAMES=( \
["happy1"]="AANUSAM000011750711" \
["happy2"]="BSHUSAM000004081869" \
["happy3"]="CHAUSAM00000M246564" \
["happy4"]="GVHUSAM000000000038" \
["happy5"]="HERUSAF000042190680" \
["happy6"]="JER116M003011609959" \
["happy7"]="LIMUSAM0000000CIM51" \
["happy8"]="RDPUSAM000000000011" \
["happy9"]="SALUSAM000000P31309" \
["happy10"]="SIMUSAM000000000001" \
["happy11"]="UMCUSAM000000196818" \
["happy12"]="UMCUSAU000000194426" \
["happy13"]="UMCUSAU000000204654" \
["happy14"]="UMCUSAM000000341496" \
["happy15"]="UMCUSAF000000341497" \
["happy16"]="UMCUSAM000000341713" \
["happy17"]="UMCUSAM000009341496" \
["happy18"]="UMCUSAF000009341497" \
["happy19"]="UMCUSAM000009341713")

INPUT_PATH="/mnt/pixstor/schnabelr-drii/WORKING/jakth2/TRIO_TRAINING_OUTPUTS"

# Parents
## Note: Father was run first when creating TrioTrain iterations
PARENTS=("Father" "Mother")

# TrioTrain Experiments Only
## These are structured into "TrioName/compare_<parent>"
TRIO_TRAIN_MODELS=("220913_NewTrios" "240724_AA_BR_Only" "240724_YK_HI_Only")

for model in "${TRIO_TRAIN_MODELS[@]}"; do
    echo "--- MODEL NAME: ${model}"
    
    SEARCH_PATH="${INPUT_PATH}/${model}"
    OUTPUT_DIR="${SEARCH_PATH}/summary"
    echo "--- SEARCH_PATH: $SEARCH_PATH" 
    # echo "--- OUTPUT_PATH: $OUTPUT_DIR"
    # Look for exisiting sub-directories, 
    # but skip any sub-sub-directories
    # keep the sub-directories in incremental order
    count=0
    for dir in $(find $SEARCH_PATH -mindepth 1 -maxdepth 1 -type d | sort -V); do
        # Ignore the output directory and the 'envs/'
        if [[ $dir =~ "summary" ]] || [[ $dir =~ "envs" ]]; then
            continue
        else
            echo "------ DIR: ${dir}"
            for parent in ${PARENTS[@]}; do
                echo "--------- PARENT: ${parent}"
                METRICS_DIR="${dir}/compare_${parent}"
                ((count+=1))
                if [ $count -eq 2 ]; then
                    break
                fi
                echo "--------- ITERATION NUMBER: ${count}" 
                CHECKPOINT_DIR="${OUTPUT_DIR}/${count}"
                for file in $(ls $METRICS_DIR | grep extended | sort -V); do
                    # echo "------------ FILE: $file"
                    _file_array=(${file//-/ })
                    _prefix=${_file_array[0]}
                    # echo "------------ PREFIX: $_prefix"
                    NEW_DIR="${CHECKPOINT_DIR}/${SAMPLE_NAMES[$_prefix]}"
                    # echo "------------ CREATING A NEW DIRECTORY | '$NEW_DIR'"
                    mkdir -p $NEW_DIR
                    echo "------------ COPYING A FILE | '${METRICS_DIR}/$file'"
                    cp ${METRICS_DIR}/$file $NEW_DIR 
                    echo "------------ OUTPUT PATH | '$NEW_DIR'"
                done
            done            
        fi
    done
done

# for sample in "${!SAMPLE_NAMES[@]}"; do
#     echo "SAMPLE: ${sample}"
#     test_number=$(echo $sample | tr -cd [:digit:])
#     echo "TEST NUMBER: ${test_number}"
# done

# Baseline/Default DV models
## These have all files in one directory
DEFAULT_MODELS=("baseline-v1.4.0-withIS-noPop" "baseline-v1.4.0-withIS-withPop")
OUTPUT_DIR="${INPUT_PATH}/final_results/summary"
echo "--- OUTPUT_PATH: $OUTPUT_DIR"

for model in "${DEFAULT_MODELS[@]}"; do
    echo "--- MODEL NAME: ${model}"
    SEARCH_PATH="${INPUT_PATH}/${model}"
    echo "--- SEARCH_PATH: $SEARCH_PATH"
    
    _checkpoint="$(basename $SEARCH_PATH)"
    if [[ $_checkpoint =~ "noPop" ]]; then
        alias="DV"
    elif [[ $_checkpoint =~ "withPop" ]]; then
        alias="DV-AF"
    else
        echo -e "ERROR: invalid checkpoint found | '${_checkpoint}'\nExiting..."
        exit 1
    fi

    CHECKPOINT_DIR="${OUTPUT_DIR}/${alias}"
    for file in $(ls $SEARCH_PATH | grep extended | sort -V); do
        # echo "------------ FILE: $file"
        _file_array=(${file//-/ })
        _prefix=${_file_array[0]}
        # echo "------------ PREFIX: $_prefix"
        NEW_DIR="${CHECKPOINT_DIR}/${SAMPLE_NAMES[$_prefix]}"
        echo "------------ CREATING A NEW DIRECTORY | '$NEW_DIR'"
        mkdir -p $NEW_DIR
        echo "------------ COPYING A FILE | '${SEARCH_PATH}/$file'"
        cp ${SEARCH_PATH}/$file $NEW_DIR 
        echo "------------ OUTPUT PATH | '$NEW_DIR'"
    done 
done


echo -e "=== triotrain/summarize/copy_happy_metrics.sh > end $(date)"