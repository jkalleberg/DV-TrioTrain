#!/bin/bash
# scripts/start_interactive.sh
# An example script of requesting interactive resources for the Hellbender SLURM Cluster
# NOTE: You will need to change this to match your own setup, such as 
# altering the partition name  and qos (i.e. 'Interactive') or,
# altering your account (i.e. 'schnabelr-lab')

# srun --pty -p schnabelr-umag --time=0-08:00:00 --mem=30G -A schnabelr-umag /bin/bash
# srun --pty -p schnabelr-lab --time=0-08:00:00 --mem=30G -A schnabelr-lab /bin/bash
srun --pty -p general -A schnabelr-lab --time=0-08:00:00 --mem=50G /bin/bash
# srun --pty -p requeue --time=0-06:00:00 --mem=10G /bin/bash
