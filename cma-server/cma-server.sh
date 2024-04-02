#!/bin/bash

ACTIVE_PROFILE=prod
PYPI_WEBSERVER_PORT=9003

# Local .env
load_env_file() {
  env_file=$1
  if [ -z "$1" ]; then
    env_file=.env
  fi

  if [ -f $env_file ]; then
    # Load Environment Variables
    source $env_file
    echo "$env_file is loaded"
  fi
}

# storing the required variables in an .env file
write_env_file() {
  env_file=$1
  if [ -z "$1" ]; then
    env_file=.env
  fi

  cat >"$env_file" <<EOF
export AM2CM_ROOT="${AM2CM_ROOT}"
export ACTIVE_PROFILE=${ACTIVE_PROFILE}
export PYPI_WEBSERVER_PORT=${PYPI_WEBSERVER_PORT}
export LC_ALL="en_US.UTF-8"
EOF
}


if [[ $(uname) == 'Linux' ]]; then
  export CMA_SERVER_HOME_DIR=$(cd $(dirname "$(readlink -f "$0")")/ && pwd)
else
  readlink_f() {
    local target="$1"
    [ -f "$target" ] || return 1 #no nofile

    while [ -L "$target" ]; do
      target="$(readlink "$target")"
    done
    echo "$(cd "$(dirname "$target")"; pwd -P)"
  }
  export CMA_SERVER_HOME_DIR=$(readlink_f "$0")
fi

ENV_FILE="${CMA_SERVER_HOME_DIR}/.env"
load_env_file "${ENV_FILE}"

for i in "$@"; do
  case $i in
  -rd=* | --am2cm-root-dir=*)
    IN_AM2CM_ROOT=${i#*=}
    ;;
  -p=* | --profile=*)
    ACTIVE_PROFILE=${i#*=}
    ;;
  --pypi-webserver-port=*)
    PYPI_WEBSERVER_PORT=${i#*=}
    ;;
  -d | --debug-mode)
    DEBUG_MODE=true
    ;;
  --start)
    ACTION_START=true
    ;;
  --stop)
    ACTION_STOP=true
    ;;
  --docker-mode)
    DOCKER_MODE=true
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
    --start: Start the cma-server
    --stop: Stop the cma-server
    -rd, --am2cm-root-dir: The root directory of am2cm
    -p, --profile: Set the active profile(s) for the cma-server
    --pypi-webserver-port: Port of local pypi webserver
    -d, --debug-mode: Set the debug option for the cma-server
    -h, --help: Print this help
 "

if [ "${HELP}" = true ]; then
  echo "$__usage"
  exit 0
fi

if [ -z "${AM2CM_ROOT}" ]; then
  while [ -z "${IN_AM2CM_ROOT}" ]; do
    read -p 'Enter the root directory of am2cm: ' IN_AM2CM_ROOT
  done
  export AM2CM_ROOT=${IN_AM2CM_ROOT}
fi

if [ -z "$ACTION_START" ] && [ -z "$ACTION_STOP" ]; then
  ACTION_START=true
fi

if [ "${DEBUG_MODE}" = true ]; then
  export AM2CM_DEBUG_OPTS=-agentlib:jdwp=transport=dt_socket,server=y,suspend=n,address=8000
fi

if [ -n "${ACTIVE_PROFILE}" ]; then
  export CMA_SERVER_PROFILE_OPTS=--spring.profiles.active=${ACTIVE_PROFILE}
fi

PID_FILE=cma-server.pid
PID_FILE_PATH="${CMA_SERVER_HOME_DIR}/${PID_FILE}"
if [ -f "$PID_FILE_PATH" ]; then
  PID=$(cat "${PID_FILE_PATH}")
fi

if [ "${ACTION_STOP}" = true ]; then

  if [ -z "${PID}" ]; then
    echo "Can't stop cma-server because it is not running!"
    exit 1
  fi

  if [ -n "${PID}" ]; then
    if ! ps -p "${PID}" >/dev/null; then
      echo "Can't stop cma-server because it is not running! PID=${PID}"
      exit 1
    fi
  fi

  echo "Stopping cma-server..."
  kill "${PID}"
fi

if [ "${ACTION_START}" = true ]; then

  if [ -n "${PID}" ]; then
    if ps -p "${PID}" >/dev/null; then
      echo "Can't start cma-server because it's running! PID=${PID}"
      exit 1
    fi
  fi

  write_env_file "${ENV_FILE}"

  echo "Starting cma-server..."
  CMA_SERVER_OUT_FILE=${CMA_SERVER_HOME_DIR}/cma-server.out
  export PATH=$JAVA_HOME/bin:$PATH
  export AM2CM_ROOT=$AM2CM_ROOT
  nohup java ${AM2CM_DEBUG_OPTS} -jar -Dloader.path="${CMA_SERVER_HOME_DIR}"/config \
  "${CMA_SERVER_HOME_DIR}"/cma-server.jar "${CMA_SERVER_PROFILE_OPTS}" > "${CMA_SERVER_OUT_FILE}" 2>&1 &
  echo $! > "$PID_FILE_PATH"
  PID=$(cat "$PID_FILE_PATH")
  echo "PID:${PID}"
  if [ "$DOCKER_MODE" = true ]; then
    tail -f "${CMA_SERVER_OUT_FILE}"
  fi
fi


