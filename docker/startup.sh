#!/bin/bash

SCRIPT_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1 || exit
  pwd -P
)"

LOG_FILE=$(basename "$0" .sh).log
PYPI_WEBSERVER_LOG=local_pypi_server.log
PYPI_WEBSERVER_PORT=9003
AIRGAPPED=false

for i in "$@"; do
  case $i in
  -p=* | --profile=*)
    CMA_SERVER_PROFILE=${i#*=}
    ;;
  --airgapped=*)
    AIRGAPPED=${i#*=}
    ;;
  --pypi-webserver-port=*)
    PYPI_WEBSERVER_PORT=${i#*=}
    ;;
  -h | --help)
    HELP=true
    ;;

  esac

done

__usage="
 Usage: $(basename "$0") [options]
 Options:
    -iv, --image-version: Set the version tag for the docker image
    -p, --profile: Set the active profile(s) for the cma-server
    --airgapped: Turn on airgapped mode (meaning: install all pypi deps from cma & cma-extras artifact) (Default: $AIRGAPPED)
    --pypi-webserver-port: Port of local pypi webserver
    -h, --help: Print this help
 "

if [ "${HELP}" = true ]; then
  echo "$__usage"
  exit 0
fi

if [ -z "${CMA_SERVER_PROFILE}" ]; then
  echo "--profile must be specified!" | tee -a "$LOG_FILE"
  echo "$__usage" | tee -a "$LOG_FILE"
  exit 1
fi

if [ "$AIRGAPPED" = true ]; then
  # start local python webserver
  nohup python3 -m http.server "${PYPI_WEBSERVER_PORT}" --directory "am2cm-ansible/python_dependencies" > "$PYPI_WEBSERVER_LOG" 2>&1 &
fi

# start server
cma-server.sh --profile="${CMA_SERVER_PROFILE}" --start --docker-mode
