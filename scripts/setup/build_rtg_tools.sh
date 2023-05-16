##======= Create RTG-TOOLS SDF file ==================================##
# required for using rtg-tools 'mendelian'
# if [ ! -f ../rtg_tools/human_reference/reference.txt ]; then
#     source ./scripts/setup/modules.sh
#     conda activate /storage/hpc/group/UMAG_test/WORKING/jakth2/deep-variant/miniconda_envs/beam_v2.30
#     rtg format -o /storage/hpc/group/UMAG_test/WORKING/jakth2/deep-variant/rtg_tools/human_reference /storage/hpc/group/UMAG_test/WORKING/jakth2/230105_humanGIAB/reference/GRCh38_no_alt_analysis_set.fasta
# else
#     echo "INFO: RTG-TOOLS SDF file already exists... SKIPPING AHEAD"
# fi