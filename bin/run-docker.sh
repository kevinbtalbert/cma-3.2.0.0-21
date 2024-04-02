#!/usr/bin/env bash

script_path="$(
  cd "$(dirname "$0")" >/dev/null 2>&1 || exit
  pwd -P
)"

DOCKER_OS=centos
CMA_DOCKER_IMAGE_VERSION=latest
DOCKER_HOST_PORT=8090

for i in "$@"; do
  case $i in
  -iv=* | --image-version=*)
    CMA_DOCKER_IMAGE_VERSION=${i#*=}
    ;;
  -sp=* | --server-port=*)
    DOCKER_HOST_PORT=${i#*=}
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
    -iv, --image-version: Set the version tag for the docker image ${CMA_DOCKER_IMAGE_VERSION})
    -sp, --server-port: Set the host port to which the container port will be mapped (Default: ${DOCKER_HOST_PORT})
    -h, --help: Print this help
 "

if [ "${HELP}" = true ]; then
  echo "$__usage"
  exit 0
fi


"${script_path}"/cma-docker.sh --start -iv="${CMA_DOCKER_IMAGE_VERSION}" --host-port="${DOCKER_HOST_PORT}"