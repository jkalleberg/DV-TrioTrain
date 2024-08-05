#!/bin/bash
#================================================================
# HEADER
#================================================================
#% SYNOPSIS
#+    helper_functions.sh args ...
#%
#% DESCRIPTION
#%    These functions capture the error codes of a sub-process,
#%    to have the SLURM SBATCH keep the status of the tasks.
#%
#% REQUIRED ARGS
#%    $1 [str]    Message to be printed into a new file
#%    $2 [str]    Path to a new file
#%
#% EXAMPLES
#%    export STATUS_FILE=/path/to/output.txt
#%    export MESSAGE='"statement to be printed after execution"'
#%    bash /script/to/execute.sh
#%    capture_status $MESSAGE $STATUS_FILE
#%
#  DEBUG OPTION
#    set -n  # Uncomment to check your syntax, without execution.
#    set -x  # Uncomment to debug this shell script
#
#================================================================
# END_OF_HEADER
#================================================================

# Error Handling Routine
capture_status()
{
    status=$?
    if [ $status -ne 0 ]; then
        # echo "Exit Status:" $status
        echo "ERROR: $1" >> $2
        exit $status
    elif [ $status -eq 0 ]; then
        echo "SUCCESS: $1" >> $2
        # exit 0        Uncomment this line to have the main proces terminate even if sub process worked
    fi
}

# # Error Handling Routine
# error_exit()
# {
#     status=$?
#     if [ $status -ne 0 ]; then
#         # echo "Exit Status:" $status
#         echo "ERROR: $1" >> $2
#         exit $status
#     fi
# }

# # Success Handling Routine
# success_exit()
# {
#     status=$?
#     if [ $status -eq 0 ]; then
#         echo "SUCCESS: $1" >> $2
#         exit 0
#     fi
# }