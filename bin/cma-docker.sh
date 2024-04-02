#!/usr/bin/env bash

SCRIPT_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1 || exit
  pwd -P
)"
source "$SCRIPT_PATH"/common.sh # load commons

ENV_FILE="$SCRIPT_PATH"/$(basename "$0" .sh).env
LOG_FILE="$LOGS_DIR"/$(basename "$0" .sh).log

DOCKER_OS=rhel
CMA_DOCKER_IMAGE_VERSION=latest
DOCKER_HOST_PORT=8090
PYPI_WEBSERVER_PORT=9003
DOCKER_CONTAINER_NAME=cma-server
DOCKER_EXTRA_ARGS=

DEFAULT_CMA_SERVER_PROFILE=prod
CMA_SERVER_PROFILE=${DEFAULT_CMA_SERVER_PROFILE}

CMA_EXTRAS_GPL_TAR_LOCATION=$(ls "${ROOT_DIR}/.."/cma-extras-gpl-*.tar.gz 2>/dev/null | tail -n1)

AIRGAPPED=false

for i in "$@"; do
  case $i in
  --start)
    ACTION_START=true
    ;;
  --stop)
    ACTION_STOP=true
    ;;
  --restart)
    ACTION_STOP=true
    ACTION_START=true
    ;;
  --rebuild)
    ACTION_REBUILD=true
    ;;
  -os=* | --docker-os=*)
    DOCKER_OS=${i#*=}
    ;;
  -iv=* | --image-version=*)
    CMA_DOCKER_IMAGE_VERSION=${i#*=}
    ;;
  -P=* | --host-port=*)
    DOCKER_HOST_PORT=${i#*=}
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
  -n=* | --container-name=*)
    DOCKER_CONTAINER_NAME=${i#*=}
    ;;
  -p=* | --profile=*)
    CMA_SERVER_PROFILE=${i#*=}
    ;;
  --env-file=*)
    DOCKER_CONTAINER_ENV_FILE=${i#*=}
    ;;
  --user=*)
    DOCKER_USER=${i#*=}
    ;;
  --network=*)
    CUSTOM_DOCKER_NETWORK=${i#*=}
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
    --start: Start the container
    --stop: Stop the docker container
    --restart: Restart the docker container
    --rebuild: Rebuild the docker image
    -os, --docker-os: OS to build on (rhel,centos,amazonlinux) (Default: ${DOCKER_OS})
    -iv, --image-version: Set the version tag for the docker image ${CMA_DOCKER_IMAGE_VERSION})
    -P, --host-port: Set the host port to which the container port will be mapped (Default: ${DOCKER_HOST_PORT})
                     Special values:
                                     * 0 - in this case, random available port will be selected on host
                                     * -1 - no port publishing will be set up at all
    --airgapped: Turn on airgapped mode (meaning: install all pypi deps from cma & cma-extras artifact) (Default: $AIRGAPPED)
    --pypi-webserver-port: Set the host port of the webserver running pypi in the container
    --cma-extras-gpl-tar-location: Location of GPL extras TAR (Default: ROOT_DIR/..) NOTE: this a requirement for airgapped mode!!
    -n, --container-name: Set the name of the container (Default: ${DOCKER_CONTAINER_NAME})
    -p, --profile: Set the active profile(s) for the cma-server (Default: $DEFAULT_CMA_SERVER_PROFILE)
        --env-file: Set a file of environment variables for the docker container
        --user: Set the docker user by providing uid:gid
        --network: Name of the docker network to connect the container into (Default: Not specified)
    -h, --help: Print this help
 "

if [ "${HELP}" = true ]; then
  echo "$__usage"
  exit 0
fi

if [ -z "${ACTION_START}" -a -z "${ACTION_STOP}" -a -z "${ACTION_REBUILD}" ]; then
  ACTION_START=true
fi

echo "#################################################################################################################" >>"$LOG_FILE"
echo "Actions: ACTION_START: ${ACTION_START:-false}, ACTION_STOP: ${ACTION_STOP:-false}, ACTION_REBUILD: ${ACTION_REBUILD:-false}" >>"$LOG_FILE"

if ! docker info >/dev/null 2>&1; then
  echo "This script uses docker, and it isn't running - please start docker and try again!" | tee -a "$LOG_FILE"
  exit 1
fi

CMA_DOCKER_IMAGE_BASE=cma-${DOCKER_OS}
CMA_DOCKER_IMAGE=${CMA_DOCKER_IMAGE_BASE}:${CMA_DOCKER_IMAGE_VERSION}

stop_container() {
  if [ "$(docker ps -q -f name="${DOCKER_CONTAINER_NAME}")" ]; then
    echo "Stopping the ${DOCKER_CONTAINER_NAME} container... " | tee -a "${LOG_FILE}"
    docker stop "${DOCKER_CONTAINER_NAME}" >>"${LOG_FILE}" 2>&1

    if docker ps | grep "${DOCKER_CONTAINER_NAME}" >/dev/null 2>&1; then
      echo "Failed." | tee -a "$LOG_FILE"
      exit 1
    else
      echo "Removing ${ROOT_DIR}/cma-server/cma-server.pid" | tee -a "$LOG_FILE"
      rm -f "${ROOT_DIR}/cma-server/cma-server.pid"
      echo "Done." | tee -a "$LOG_FILE"
    fi
  fi
}

delete_container() {
  if docker container inspect "${DOCKER_CONTAINER_NAME}" >/dev/null 2>&1; then

    echo -n "Deleting the ${DOCKER_CONTAINER_NAME} container... " | tee -a "$LOG_FILE"
    docker rm "${DOCKER_CONTAINER_NAME}" >>"$LOG_FILE" 2>&1

    if ! docker container inspect "${DOCKER_CONTAINER_NAME}" >/dev/null 2>&1; then
      echo "Done." | tee -a "$LOG_FILE"
    else
      echo "Failed." | tee -a "$LOG_FILE"
      exit 1
    fi
  fi
}

delete_image() {
  if docker image inspect "${CMA_DOCKER_IMAGE}" >/dev/null 2>&1; then

    echo -n "Deleting the ${CMA_DOCKER_IMAGE} image... " | tee -a "$LOG_FILE"
    docker rmi "${CMA_DOCKER_IMAGE}" >>"$LOG_FILE" 2>&1

    if ! docker image inspect "${CMA_DOCKER_IMAGE}" >/dev/null 2>&1; then
      echo "Done." | tee -a "$LOG_FILE"
    else
      echo "Failed." | tee -a "$LOG_FILE"
      exit 1
    fi
  fi
}

build_image() {
  if ! docker image inspect "${CMA_DOCKER_IMAGE}" >/dev/null 2>&1; then
    echo "The ${CMA_DOCKER_IMAGE} image is missing!" | tee -a "$LOG_FILE"
    if [ "$AIRGAPPED" = true ]; then
      "$SCRIPT_PATH"/setup.sh --docker -os="${DOCKER_OS}" -iv="${CMA_DOCKER_IMAGE_VERSION}" --profile="${CMA_SERVER_PROFILE}" --cma-extras-gpl-tar-location="${CMA_EXTRAS_GPL_TAR_LOCATION}" --pypi-webserver-port="${PYPI_WEBSERVER_PORT}" --airgapped
    else
      "$SCRIPT_PATH"/setup.sh --docker -os="${DOCKER_OS}" -iv="${CMA_DOCKER_IMAGE_VERSION}" --profile=${CMA_SERVER_PROFILE}
    fi
    if [ $? -ne 0 ]; then
      exit 1
    fi

    LAST_CMA_DOCKER_IMAGE="${CMA_DOCKER_IMAGE}"
  fi
}

rebuild_image() {
  if docker image inspect "${CMA_DOCKER_IMAGE}" >/dev/null 2>&1; then
    stop_container
    delete_container
    delete_image
  fi
  build_image
}

# get container ID and store in LAST_DOCKER_CONTAINER_ID variable
get_container_id() {
  docker ps -aq -f name=${DOCKER_CONTAINER_NAME}
}

run_container() {
  echo -n "Starting the ${DOCKER_CONTAINER_NAME} container... " | tee -a "$LOG_FILE"
  AM2CM_ROOT_DIR=/$(basename "${ROOT_DIR}")


  if [ -n "${DOCKER_CONTAINER_ENV_FILE}" ]; then
    DOCKER_EXTRA_ARGS+="--env-file ${DOCKER_CONTAINER_ENV_FILE} "
  fi

  if [ -n "${DOCKER_USER}" ]; then
    DOCKER_EXTRA_ARGS+="--user ${DOCKER_USER} "
  fi

  if [ -n "${CUSTOM_DOCKER_NETWORK}" ]; then
    DOCKER_EXTRA_ARGS+="--network ${CUSTOM_DOCKER_NETWORK} "
  fi

  DOCKER_PORT_ARGS=""
  # If a negative number, start without port publishing at all
  if [ "${DOCKER_HOST_PORT}" -gt "-1" ]; then
    if [ "${DOCKER_HOST_PORT}" == "0" ]; then
      # Random port will be selected
      DOCKER_PORT_ARGS+="-p 8090"
    else
      # Normal port publishing
      DOCKER_PORT_ARGS+="-p ${DOCKER_HOST_PORT}:8090"
    fi
  fi

  if [ "$AIRGAPPED" = true ]; then
    DOCKER_PORT_ARGS+=" "
    if [ "${PYPI_WEBSERVER_PORT}" -gt "-1" ]; then
      # since inner & outer port may be configured differently, acquire inner port from the image
      INNER_PYPY_WEBSERVER_PORT=$(docker image inspect "${CMA_DOCKER_IMAGE}" | grep -m1 "INNER_PYPY_WEBSERVER_PORT=" | grep -o "[0-9][0-9]*")
      if [ "${PYPI_WEBSERVER_PORT}" == "0" ]; then
        # Random port will be selected
        DOCKER_PORT_ARGS+="-p $INNER_PYPY_WEBSERVER_PORT"
      else
        # Normal port publishing
        DOCKER_PORT_ARGS+="-p ${PYPI_WEBSERVER_PORT}:${INNER_PYPY_WEBSERVER_PORT}"
      fi
    fi
  fi

  CMA_HOME="/$(basename $AM2CM_ROOT_DIR)"
  # NOTE: do NOT quote DOCKER_PORT_ARGS here, since then bash will pass it as a single string to the docker command, instead of expanding it with the spaces
  # i.e. with quotes, it DOES NOT work
  docker run -d --name "${DOCKER_CONTAINER_NAME}" ${DOCKER_PORT_ARGS} -v "${ROOT_DIR}":"${CMA_HOME}" ${DOCKER_EXTRA_ARGS} "${CMA_DOCKER_IMAGE}" 2>&1 >> "$LOG_FILE"

  LAST_DOCKER_CONTAINER_ID=$(get_container_id)
  if [ -z "${LAST_DOCKER_CONTAINER_ID}" ]; then
    echo "Failed."
  else
    echo "Done."
  fi
}

rebuild_container() {
  stop_container
  delete_container
  run_container
}

start_container() {
  docker start "${DOCKER_CONTAINER_NAME}" >>"$LOG_FILE" 2>&1
  LAST_DOCKER_CONTAINER_ID=$(get_container_id)
}

print_container_info() {
  if docker ps -q -f name="${DOCKER_CONTAINER_NAME}" >/dev/null 2>&1; then
    echo "Container-name: ${DOCKER_CONTAINER_NAME}" | tee -a "$LOG_FILE"
    echo "Container-id: ${LAST_DOCKER_CONTAINER_ID}" | tee -a "$LOG_FILE"
    if [ "${DOCKER_HOST_PORT}" == "-1" ]; then
    # Start without port publishing at all
      echo "The cma-server will be available in about 30 seconds. No port publishing has been set up." | tee -a "$LOG_FILE"
    elif [ "${DOCKER_HOST_PORT}" == "0" ]; then
    # Publish to random port
      echo "The cma-server will be available in about 30 seconds on a random port. Check 'docker ps' output for info." | tee -a "$LOG_FILE"
    else
    # Normal port publishing
      echo "The cma-server will be available at http://localhost:${DOCKER_HOST_PORT} in about 30 seconds " | tee -a "$LOG_FILE"
    fi
  else
    echo "The container failed to start!" | tee -a "$LOG_FILE"
    exit 1
  fi
}

# storing the required variables in an .env file
write_env_file() {
  env_file=${1:-.env}
  cat >"$env_file" <<EOF
export LAST_CMA_DOCKER_IMAGE="${LAST_CMA_DOCKER_IMAGE}"
export LAST_DOCKER_CONTAINER_ID="${LAST_DOCKER_CONTAINER_ID}"
EOF
}

load_env_file "${ENV_FILE}"

if [ "${ACTION_STOP}" = true ]; then
  stop_container
fi

if [ "${ACTION_REBUILD}" = true ]; then
  rebuild_image
fi

# check if image exists otherwise generate one

if [ "${ACTION_START}" = true ]; then

  if ! docker image inspect "${CMA_DOCKER_IMAGE}" >/dev/null 2>&1; then
    build_image
  else
    if [ "${LAST_CMA_DOCKER_IMAGE}" != "${CMA_DOCKER_IMAGE}" ]; then
      while true; do
        if [ -z "${LAST_CMA_DOCKER_IMAGE}" ]; then
          BUILD_CMA_IMAGE=r
        else
          read -r -p "There is a ${CMA_DOCKER_IMAGE_BASE} image with the ${CMA_DOCKER_IMAGE_VERSION} tag. Do you want to [c]ontinue or [r]ebuild? [c]:" BUILD_CMA_IMAGE
        fi
        BUILD_CMA_IMAGE=${BUILD_CMA_IMAGE:-c}
        case $BUILD_CMA_IMAGE in
        [rR])
          rebuild_image
          break
          ;;
        [cC])
          echo "Continue with the existing image..."
          break
          ;;
        *) echo invalid response ;;
        esac
      done
    fi
  fi

  # check if $DOCKER_CONTAINER_NAME exists. Ask the user whether to continue or recreate it.
  if [ ! "$(docker ps -q -f name="${DOCKER_CONTAINER_NAME}")" ]; then
    if docker container inspect "${DOCKER_CONTAINER_NAME}" >/dev/null 2>&1; then
      while true; do
        if [ "${LAST_DOCKER_CONTAINER_ID}" != $(get_container_id) ]; then
          read -r -p "The container ${DOCKER_CONTAINER_NAME} exists. Do you want to [c]ontinue or [r]ebuild? [c]:" BUILD_CMA_CONTAINER
        fi
        BUILD_CMA_CONTAINER=${BUILD_CMA_CONTAINER:-c}
        case $BUILD_CMA_CONTAINER in
        [rR])
          echo "Rebuilding the ${DOCKER_CONTAINER_NAME} container..."
          rebuild_container
          break
          ;;
        [cC])
          echo "Continue with the existing container..."
          start_container
          break
          ;;
        *) echo invalid response ;;
        esac
      done
    else
      run_container
    fi
  fi

  print_container_info
fi

write_env_file "${ENV_FILE}"
