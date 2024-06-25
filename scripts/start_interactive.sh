#!/bin/bash
# scripts/start_interactive.sh
# An example script of requesting interactive resources for the Lewis SLURM Cluster
# NOTE: You will need to change this to match your own setup, such as 
# altering the partition name  and qos (i.e. 'Interactive') or,
# altering your account (i.e. 'schnabellab')

# srun --pty -p gpu3 --time=0-04:00:00 -A animalsci /bin/bash
srun --pty -p schnabelr-umag --time=0-08:00:00 --mem=30G -A schnabelr-umag /bin/bash
# srun --pty -p interactive --time=0-04:00:00 --mem=30G /bin/bash
# srun --pty -p BioCompute --time=0-06:00:00 --exclusive --mem=0 -A schnabellab /bin/bash
