#!/bin/bash

# Error Handling Routine
error_exit()
{
    status=$?
    if [ $status -ne 0 ]; then
        # echo "Exit Status:" $status
        echo "ERROR: $1" >> $2
        exit $status
    fi
}

# Success Handling Routine
success_exit()
{
    status=$?
    if [ $status -eq 0 ]; then
        echo "SUCCESS: $1" >> $2
        exit 0
    fi
}