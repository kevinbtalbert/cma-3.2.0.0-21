#!/usr/bin/env bash

SCRIPT_PATH=$(cd $(dirname "$(readlink -f "$0")")/ && pwd)
source "$SCRIPT_PATH"/common.sh # load commons

LOG_FILE="$LOGS_DIR"/$(basename "$0" .sh).log

DEFAULT_DOCKER_OS=rhel
DEFAULT_AM2CM_DOCKER_IMAGE_VERSION=latest
DEFAULT_CMA_SERVER_PROFILE=prod
DEFAULT_PYTHON_EXECUTABLE=python3

DOCKER_OS=${DEFAULT_DOCKER_OS}
AM2CM_DOCKER_IMAGE_VERSION=${DEFAULT_AM2CM_DOCKER_IMAGE_VERSION}
CMA_SERVER_PROFILE=${DEFAULT_CMA_SERVER_PROFILE}
PYPI_WEBSERVER_PORT=9003
AIRGAPPED=false

for i in "$@"; do
  case $i in
  --local)
    SETUP_LOCAL=true
    ;;
  --docker)
    SETUP_DOCKER=true
    ;;
  -os=* | --docker-os=*)
    DOCKER_OS=${i#*=}
    ;;
  -iv=* | --image-version=*)
    AM2CM_DOCKER_IMAGE_VERSION=${i#*=}
    ;;
  -p=* | --profile=*)
    CMA_SERVER_PROFILE=${i#*=}
    ;;
  -py=* | --python-executable=*)
    PYTHON_EXECUTABLE=${i#*=}
    ;;
  --airgapped)
    AIRGAPPED=true
    ;;
  --pypi-webserver-port=*)
    PYPI_WEBSERVER_PORT=${i#*=}
    ;;
  --cma-extras-gpl-tar-location=*)
    CMA_EXTRAS_GPL_TAR_LOCATION=${i#*=}
    ;;
  -h | --help)
    HELP=true
    ;;
  *)
    echo "Unknown option: $i"
    HELP=true
    ;;
  esac
done

__usage="
 Usage: $(basename "$0") [options]
 Options:
    --local: Install am2cm on the local machine
    --docker: Install am2cm in a docker container
    -os, --docker-os: the OS of the docker container (Default: $DEFAULT_DOCKER_OS)
    -p, --profile: Set the active profile(s) for the cma-server (Default: $DEFAULT_CMA_SERVER_PROFILE)
    -py, --python-executable: Path to python3 executable
    --airgapped: Turn on airgapped mode (meaning: install all pypi deps from cma & cma-extras artifact) (Default: $AIRGAPPED)
    --pypi-webserver-port: Port of pypi webserver to install dependencies from (Default: $PYPI_WEBSERVER_PORT)
    --cma-extras-gpl-tar-location: Location of GPL extras TAR (Default: ROOT_DIR/..) NOTE: this a requirement for airgapped mode!!
    -h, --help: Print this help
 "

if [ "$AIRGAPPED" = true ]; then
  echo "CMA_EXTRAS_GPL_TAR_LOCATION: $CMA_EXTRAS_GPL_TAR_LOCATION"
  if [ ! -f "$CMA_EXTRAS_GPL_TAR_LOCATION" ]; then
    echo "CMA extras gpl tar is missing, please provide as follows: --cma-extras-gpl-tar-location=<location>"
    echo "or place it next to your CMA root dir"
    exit 1
  fi
fi


if [ "${HELP}" = true ]; then
  echo "$__usage"
  exit 0
fi

while [ -z "${SETUP_LOCAL}" ] && [ -z "${SETUP_DOCKER}" ]; do
  read -r -p "Select the type of installation ([l]ocal|[d]ocker):" INSTALL_TYPE
  case  $INSTALL_TYPE in
    l | local) SETUP_LOCAL=true;;
    d | docker) SETUP_DOCKER=true;;
    *) echo "ERROR: The '${INSTALL_TYPE}' is not a valid installation type! Please select one of the following options [l]ocal or [d]ocker"
      ;;
  esac
done

if [ "${SETUP_DOCKER}" = true ]; then
  if [ -z "${DOCKER_OS}" ]; then
    read -r -p "Enter the OS of the docker container [${DEFAULT_DOCKER_OS}]:" DOCKER_OS
    DOCKER_OS=${DOCKER_OS:-${DEFAULT_DOCKER_OS}}
  fi
  if [ -z "${AM2CM_DOCKER_IMAGE_VERSION}" ]; then
    read -r -p "Enter the version for the docker image [${DEFAULT_AM2CM_DOCKER_IMAGE_VERSION}]:" AM2CM_DOCKER_IMAGE_VERSION
    AM2CM_DOCKER_IMAGE_VERSION=${AM2CM_DOCKER_IMAGE_VERSION:-${DEFAULT_AM2CM_DOCKER_IMAGE_VERSION}}
  fi
fi

if [ -z "${CMA_SERVER_PROFILE}" ]; then
  read -r -p "Enter the active profile for the cma-server [${DEFAULT_CMA_SERVER_PROFILE}]:" CMA_SERVER_PROFILE
  CMA_SERVER_PROFILE=${CMA_SERVER_PROFILE:-$DEFAULT_CMA_SERVER_PROFILE}
fi

if [ "${SETUP_DOCKER}" = true ]; then
  echo "Building docker image..." | tee -a "$LOG_FILE"
  if [ "$AIRGAPPED" = true ]; then
    "$SCRIPT_PATH"/build-docker.sh $DEV_OPTS -os="${DOCKER_OS}" -iv="${AM2CM_DOCKER_IMAGE_VERSION}" --profile="${CMA_SERVER_PROFILE}" --cma-extras-gpl-tar-location="${CMA_EXTRAS_GPL_TAR_LOCATION}" --pypi-webserver-port="${PYPI_WEBSERVER_PORT}" --airgapped | tee -a "$LOG_FILE"
  else
    "$SCRIPT_PATH"/build-docker.sh $DEV_OPTS -os="${DOCKER_OS}" -iv="${AM2CM_DOCKER_IMAGE_VERSION}" --profile="${CMA_SERVER_PROFILE}" | tee -a "$LOG_FILE"
  fi

  if [ "${PIPESTATUS[0]}" -ne "0" ]; then
    echo "Building the image has failed..." | tee -a "$LOG_FILE"
    exit 1
  fi
fi

if [ "${SETUP_LOCAL}" = true ]; then

  cleanup() {
    if ! delete_virtual_env; then
      echo "The ${VENV_DIR} must be deleted manually!"
    fi
    exit 1
  }

  download_software_dependencies_for_offline_use() {
    source "${VENV_DIR}"/bin/activate
    if [ "$VIRTUAL_ENV" = "" ]; then
      echo "Virtualenv could not be activated in ${VENV_DIR}" | tee -a "$LOG_FILE"
      exit 1;
    fi
    dependency_install_playbooks=( download_jdbc_drivers download_atlas_migration_tool_for_offline_use )
    cd "${ROOT_DIR}"/am2cm-ansible || exit 1
    for i in "${dependency_install_playbooks[@]}"
    do
     echo "Running playbook $i" | tee -a "$LOG_FILE"
     ansible-playbook -e "@inventories/group_vars/all.yml" -e "cma_root_dir=$ROOT_DIR" "playbooks/install/$i.yml" | tee -a "$LOG_FILE"
     if [ "${PIPESTATUS[0]}" -ne "0" ]; then
       echo "Failed to download dependencies! Exiting..." | tee -a "$LOG_FILE"
       deactivate
       exit 1
     fi
    done
    deactivate
  }

  trap cleanup SIGINT

  if [ -z "${PYTHON_EXECUTABLE}" ]; then
    PYTHON_EXECUTABLE=$(get_python_executable $DEFAULT_PYTHON_EXECUTABLE)
  fi

  echo "Creating virtualenv in ${VENV_DIR} ..." | tee -a "$LOG_FILE"
  "${PYTHON_EXECUTABLE}" -m venv "${VENV_DIR}" | tee -a "$LOG_FILE"
  if [ "${PIPESTATUS[0]}" -ne "0" ]; then
    echo "Setting up virtualenv has failed! Exiting..." | tee -a "$LOG_FILE"
    exit 1
  fi

  echo "Installing requirements for am2cm-ansible in ${VENV_DIR} ..." | tee -a "$LOG_FILE"
  source "${VENV_DIR}"/bin/activate
  if [ "$AIRGAPPED" = true ]; then
    echo "Unarchiving CMA extras GPL tar" | tee -a "$LOG_FILE"
    tar -xzf "$CMA_EXTRAS_GPL_TAR_LOCATION" --directory "${ROOT_DIR}"/am2cm-ansible/python_dependencies
    # requirements for the control node now have the format: control_node_PYTHON_VERSION_requirements.txt
    REQUIREMENTS="${ROOT_DIR}/am2cm-ansible/python_requirements/control_node_${USER_PYTHON_VERSION}_requirements.txt"
    echo "Using requirements file: $REQUIREMENTS" | tee -a "$LOG_FILE"
    pip install -r "${REQUIREMENTS}" -i "http://localhost:${PYPI_WEBSERVER_PORT}/" --trusted-host localhost | tee -a "$LOG_FILE"
  else
    pip install -r "${ROOT_DIR}"/am2cm-ansible/requirements.txt  | tee -a "$LOG_FILE"
  fi

  if [ "${PIPESTATUS[0]}" -ne "0" ]; then
    echo "Installing pip requirements have failed! Exiting..." | tee -a "$LOG_FILE"
    deactivate
    exit 1
  fi
  deactivate

  echo "Download software dependencies for offline use.." | tee -a "${LOG_FILE}"
  download_software_dependencies_for_offline_use

  echo 'Configure cma-server ...' | tee -a "$LOG_FILE"
  cat >"${ROOT_DIR}"/cma-server/.env <<EOF
export AM2CM_ROOT="${ROOT_DIR:-$PWD}"
export ACTIVE_PROFILE=${CMA_SERVER_PROFILE}
export PYPI_WEBSERVER_PORT=${PYPI_WEBSERVER_PORT}
EOF
fi

echo "Setup completed!" | tee -a "$LOG_FILE"
