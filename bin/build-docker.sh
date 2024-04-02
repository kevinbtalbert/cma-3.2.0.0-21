#!/usr/bin/env bash

SCRIPT_PATH=$(cd $(dirname "$0")/ && pwd)
ROOT_DIR=$(dirname "$SCRIPT_PATH")

# OS to build on
DOCKER_OS=rhel

DEFAULT_CENTOS_VERSION=7
DEFAULT_CENTOS_IMAGE_VERSION=centos7.9.2009

DEFAULT_RHEL_VERSION=8
DEFAULT_RHEL_IMAGE_VERSION=8.9-1028

DEFAULT_AMAZONLINUX_VERSION=al2023
DEFAULT_AMAZONLINUX_IMAGE_VERSION=2023.3.20231218.0

CMA_SERVER_PROFILE=prod
AM2CM_DOCKER_IMAGE_VERSION=latest

AM2CM_VENV=venv

CMA_EXTRAS_GPL_TAR_LOCATION='cma-extras-gpl.tar.gz'

AIRGAPPED=false

for i in "$@"; do
  case $i in
  -os=* | --docker-os=*)
    DOCKER_OS=${i#*=}
    ;;
  -iv=* | --image-version=*)
    AM2CM_DOCKER_IMAGE_VERSION=${i#*=}
    ;;
  -p=* | --profile=*)
    CMA_SERVER_PROFILE=${i#*=}
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
  -d | --dev-mode)
    DEV_MODE=true
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
    -os, --docker-os: OS to build on (rhel,centos,amazonlinux) (Default: ${DOCKER_OS})
    -iv, --image-version: Set the version tag for the docker image
    -p, --profile: Set the active profile(s) for the cma-server
    --airgapped: Turn on airgapped mode (meaning: install all pypi deps from cma & cma-extras artifact) (Default: $AIRGAPPED)
    --pypi-webserver-port: Port of pypi webserver to install dependencies from
    --cma-extras-gpl-tar-location: Location of GPL extras TAR
    -h, --help: Print this help
 "

if [ "${HELP}" = true ]; then
  echo "$__usage"
  exit 0
fi

if [ -z "${DOCKER_OS}" ]; then
  echo "ERROR: The OS for docker container is not specified!"
  exit 1;
fi

if [ -z "${CMA_SERVER_PROFILE}" ]; then
  echo "ERROR: The profile for the cma-server is not specified!"
  exit 1;
fi

case ${DOCKER_OS} in
  "centos") BUILD_OS=centos BUILD_OS_VERSION=$DEFAULT_CENTOS_VERSION BUILD_IMAGE_VERSION=$DEFAULT_CENTOS_IMAGE_VERSION ;;
  "rhel") BUILD_OS=centos BUILD_OS_VERSION=$DEFAULT_RHEL_VERSION BUILD_IMAGE_VERSION=$DEFAULT_RHEL_IMAGE_VERSION ;;
  "amazonlinux") BUILD_OS=centos BUILD_OS_VERSION=$DEFAULT_AMAZONLINUX_VERSION BUILD_IMAGE_VERSION=$DEFAULT_AMAZONLINUX_IMAGE_VERSION ;;
   *)
     echo "ERROR: ${DOCKER_OS} is unsupported!!"
     exit 1
     ;;
esac

AM2CM_DOCKER_IMAGE=cma-"${DOCKER_OS}"


AM2CM_ROOT_DIR=/$(basename "${ROOT_DIR}")

SRC_CMA_SERVER=cma-server
SRC_AM2CM_ANSIBLE=am2cm-ansible
SRC_AM2CM_TOOL=am2cm-tool
SRC_AM2CM_UPGRADE=am2cm-upgrade
SRC_AM2CM_DIFF=am2cm-diff
SRC_AM2CM_SOLR_CLIENT=am2cm-solr-client
SRC_CMA_PVC_ANSIBLE=cma-pvc-ansible
SRC_CMA_PC_ANSIBLE=cma-pc-ansible
SRC_STARTUP_SCRIPT=docker/startup.sh

if [ "${DEV_MODE}" = true ]; then
  SRC_CMA_SERVER=$SRC_CMA_SERVER/target/$SRC_CMA_SERVER
  SRC_AM2CM_ANSIBLE=$SRC_AM2CM_ANSIBLE/target/$SRC_AM2CM_ANSIBLE
  SRC_AM2CM_TOOL=$SRC_AM2CM_TOOL/target/$SRC_AM2CM_TOOL
  SRC_AM2CM_UPGRADE=am2cm-upgrade-tool/target/$SRC_AM2CM_UPGRADE
  SRC_AM2CM_DIFF=am2cm-diff/target/$SRC_AM2CM_DIFF
  SRC_AM2CM_SOLR_CLIENT=am2cm-solr-client/target/$SRC_AM2CM_SOLR_CLIENT
  SRC_CMA_PVC_ANSIBLE=cma-pvc-ansible/target/cma-pvc-ansible
  SRC_CMA_PC_ANSIBLE=cma-pc-ansible/target/cma-pc-ansible
fi

# It's important to add the docker profile to the end of the active profiles!!!
CMA_SERVER_PROFILE=${CMA_SERVER_PROFILE},docker

if [ "$AIRGAPPED" = true ]; then
  cp $CMA_EXTRAS_GPL_TAR_LOCATION $ROOT_DIR
  CMA_EXTRAS_GPL_TAR=$(basename $CMA_EXTRAS_GPL_TAR_LOCATION)
fi

echo "Calling docker build command..."

docker build -t "${AM2CM_DOCKER_IMAGE}":"${AM2CM_DOCKER_IMAGE_VERSION}" \
  --build-arg BUILD_OS="${BUILD_OS}" --build-arg BUILD_OS_VERSION="${BUILD_OS_VERSION}" \
  --build-arg BUILD_IMAGE_VERSION="${BUILD_IMAGE_VERSION}" \
  --build-arg CMA_ROOT_DIR="/$(basename ${AM2CM_ROOT_DIR})"  --build-arg CMA_SERVER_PROFILE="${CMA_SERVER_PROFILE}" \
  --build-arg SRC_CMA_SERVER=${SRC_CMA_SERVER} --build-arg SRC_AM2CM_ANSIBLE=${SRC_AM2CM_ANSIBLE} \
  --build-arg SRC_AM2CM_TOOL=${SRC_AM2CM_TOOL} --build-arg SRC_AM2CM_UPGRADE=${SRC_AM2CM_UPGRADE} \
  --build-arg SRC_AM2CM_DIFF=${SRC_AM2CM_DIFF} --build-arg SRC_AM2CM_SOLR_CLIENT=${SRC_AM2CM_SOLR_CLIENT} \
  --build-arg SRC_CMA_PVC_ANSIBLE=${SRC_CMA_PVC_ANSIBLE} --build-arg SRC_CMA_PC_ANSIBLE=${SRC_CMA_PC_ANSIBLE} \
  --build-arg AIRGAPPED=${AIRGAPPED} \
  --build-arg CMA_EXTRAS_GPL_TAR="${CMA_EXTRAS_GPL_TAR}" \
  --build-arg INNER_PYPY_WEBSERVER_PORT="${PYPI_WEBSERVER_PORT}" \
  --build-arg SRC_STARTUP_SCRIPT="${SRC_STARTUP_SCRIPT}" \
  -f "${ROOT_DIR}"/docker/Dockerfile "${ROOT_DIR}" \
  --target cma-final

if [ $? -ne 0 ]; then
  echo "Docker build command failed... Exiting..."
  exit 1
fi

docker tag "${AM2CM_DOCKER_IMAGE}":"${AM2CM_DOCKER_IMAGE_VERSION}" "${AM2CM_DOCKER_IMAGE}":latest

if [ $? -ne 0 ]; then
  echo "Docker tag command failed... Exiting..."
  exit 1
fi
