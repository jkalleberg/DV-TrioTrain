#!/bin/bash
# build_happy.sh

echo "=== scripts/setup/build_happy.sh > start $(date)"

echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Creating Apptainer CACHE/ and TMP/, if needed"
install --directory --verbose ${APPTAINER_CACHEDIR}
install --directory --verbose ${APPTAINER_TMPDIR}

# Only want to build these Apptainer Image(s) once!
echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Installing Hap.py Container Image(s), if necessary..."

if test -x ./hap.py_v0.3.12.sif; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Image [hap.py_v0.3.12.sif] has already been installed"
  apptainer run -B /usr/lib/locale/:/usr/lib/locale/ hap.py_v0.3.12.sif /opt/hap.py/bin/hap.py --help
else
  echo "$(date '+%Y-%m-%d %H:%M:%S')INFO: Image [hap.py_v0.3.12.sif] needs to be installed"
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Apptainer Image will go here: ${PWD}"
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Building Apptainer Image now... "
  apptainer pull docker://jmcdani20/hap.py:v0.3.12
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Done Building Hap.py Apptainer Image"
fi

echo "=== scripts/setup/build_happy.sh > end $(date)"