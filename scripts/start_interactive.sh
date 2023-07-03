#!/bin/bash
# scripts/start_interactive.sh
# An example script of requesting interactive resources for the Lewis SLURM Cluster
# NOTE: You will need to change this to match your own setup, such as 
# altering the partition name  and qos (i.e. 'Interactive') or,
# altering your account (i.e. 'schnabellab')

# srun --pty -p gpu3 --time=0-04:00:00 -A animalsci /bin/bash
# srun --pty -p hpc6 --time=0-04:00:00 --mem=0 --exclusive -A animalsci /bin/bash
# srun --pty -p Interactive --qos=Interactive --time=0-04:00:00 --mem=0 --exclusive -A animalsci /bin/bash
# srun --pty -p Interactive --qos=Interactive --time=0-04:00:00 --mem=30G -A schnabellab /bin/bash
# srun --pty -p Lewis --time=0-04:00:00 --mem=30G -A schnabellab /bin/bash
srun --pty -p BioCompute --time=0-06:00:00 --exclusive --mem=0 -A schnabellab /bin/bash
