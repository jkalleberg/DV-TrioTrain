#!/usr/bin/bash
## scripts/run/environment.sh

echo -e "=== scripts/run/environment.sh > start $(date)\n$(date '+%Y-%m-%d %H:%M:%S') INFO: EnvFile -- ${1}"

if [ $# -lt 1 ]; then
  echo 1>&2 "$0: provide inputs for: EnvFile"
  exit 2
elif [ $# -gt 1 ]; then
  echo 1>&2 "$0: provide only EnvFile"
  exit 2
fi
# The ModelName argument is available as "$1"

# Activate the Environment variables
export EnvFile=${1}
echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Activating analysis environment:"
. ${EnvFile}

echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Current Environment loaded: ${RunName}-Run${RunOrder} Trio=${ChildLabID}:${FatherLabID}:${MotherLabID}"
echo -e "=== scripts/run/environment.sh > end $(date)"
