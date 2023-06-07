#!/bin/bash
# scripts/setup/build_containers.sh

echo "=== scripts/setup/build_containers.sh > start $(date)" $1

echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Creating Apptainer CACHE/ and TMP/, if needed"
install --directory --verbose ${APPTAINER_CACHEDIR}
install --directory --verbose ${APPTAINER_TMPDIR}

# Only want to build these Apptainer Image(s) once!
echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Installing Container Image(s), if necessary"

if [[ $1 == 'DeepVariant-CPU' ]]; then
  version="${BIN_VERSION_DV}"
  image_name="deepvariant_${version}"
  docker_name="${version}"
  command="run_deepvariant"
elif [[ $1 == 'DeepVariant-GPU' ]]; then
  version="${BIN_VERSION_DV}"
  image_name="deepvariant_${version}-gpu"
  docker_name="${version}-gpu"
  command="run_deepvariant"
elif [[ $1 == 'DeepTrio-CPU' ]]; then
  version="${BIN_VERSION_DT}"
  image_name="deepvariant_deeptrio-${version}"
  docker_name="deeptrio-${version}"
  command="deeptrio/run_deeptrio"
elif [[ $1 == 'DeepTrio-GPU' ]]; then
  version="${BIN_VERSION_DT}"
  image_name="deepvariant_deeptrio-${version}-gpu"
  docker_name="deeptrio-${BIN_VERSION_DT}-gpu"
  command="deeptrio/run_deeptrio"
else
  echo -e "$(date '+%Y-%m-%d %H:%M:%S') ERROR: Invalid argument [$1] provided.\n$(date '+%Y-%m-%d %H:%M:%S') INFO: Choices: [ DeepVariant-CPU, DeepTrio-CPU, DeepVariant-GPU, DeepTrio-GPU ]\nExiting... "
  exit 1
fi

if test -x ./${image_name}.sif; then
  echo -e "$(date '+%Y-%m-%d %H:%M:%S') INFO: Image [${image_name}.sif] has already been installed"
  apptainer run -B /usr/lib/locale/:/usr/lib/locale/ ${image_name}.sif /"opt/deepvariant/bin/${command}" --version
else
  echo -e "$(date '+%Y-%m-%d %H:%M:%S') INFO: Image [${image_name}.sif] needs to be installed"
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Apptainer Image will go here: ${PWD}"
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO: Building Apptainer Image now... "
  apptainer pull docker://google/deepvariant:"${docker_name}"
  echo "Done: Building Apptainer Image"
fi

echo "=== scripts/setup/build_containers.sh > end $(date)"