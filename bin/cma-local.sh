#!/usr/bin/env bash

SCRIPT_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1 || exit
  pwd -P
)"

source "$SCRIPT_PATH"/common.sh # load commons

LOG_FILE="$LOGS_DIR"/$(basename "$0" .sh).log

CMA_SERVER_HOME_DIR="${ROOT_DIR}/cma-server"
CMA_SERVER_PID_FILE="${CMA_SERVER_HOME_DIR}/cma-server.pid"
CMA_SERVER_LOG_FILE=cma-server.log

PYPI_PID_FILE="${ROOT_DIR}/.pypi_server.pid"
PYPI_WEBSERVER_PORT=9003

DEFAULT_CMA_SERVER_START_TIMEOUT=60
CMA_SERVER_START_TIMEOUT="${DEFAULT_CMA_SERVER_START_TIMEOUT}"
DEFAULT_CMA_SERVER_STOP_TIMEOUT=60
CMA_SERVER_STOP_TIMEOUT="${DEFAULT_CMA_SERVER_STOP_TIMEOUT}"

DEFAULT_CMA_SERVER_PROFILE=prod
CMA_SERVER_PROFILE="${DEFAULT_CMA_SERVER_PROFILE}"

SETUP_CMA_SERVER=false
VERBOSE=false
AIRGAPPED=false

# newer ansible needs locale to be set
export LC_ALL="en_US.UTF-8"

CMA_EXTRAS_GPL_TAR_LOCATION=$(ls "${ROOT_DIR}/.."/cma-extras-gpl-*.tar.gz 2>/dev/null | tail -n1)

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
  --start-timeout=*)
    CMA_SERVER_START_TIMEOUT=${i#*=}
    ;;
  --stop-timeout=*)
    CMA_SERVER_STOP_TIMEOUT=${i#*=}
    ;;
  -h | --help)
    HELP=true
    ;;
  -v | --verbose)
    VERBOSE=true
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
    --start: Start the CMA server
    --stop: Stop the CMA server
    --restart: Restart the CMA server
    --rebuild: Reinstall the CMA server
    -p, --profile: Set the active profile(s) for the cma-server (Default: $DEFAULT_CMA_SERVER_PROFILE)
    -py, --python-executable: Path to python3 executable
    --airgapped: Turn on airgapped mode (meaning: install all pypi deps from cma & cma-extras artifact) (Default: $AIRGAPPED)
    --pypi-webserver-port: Port of local pypi webserver
    --cma-extras-gpl-tar-location: Location of GPL extras TAR (Default: ROOT_DIR/..) NOTE: this a requirement for airgapped mode!!
    --start-timeout: Set timeout for server start (Default: $DEFAULT_CMA_SERVER_START_TIMEOUT seconds)
    --stop-timeout: Set timeout for server stop (Default: $DEFAULT_CMA_SERVER_STOP_TIMEOUT seconds)
    -v, --verbose: Print verbose log
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

load_PYTHON_EXECUTABLE_variable() {
  if [ -z "${PYTHON_EXECUTABLE}" ]; then
    PYTHON_EXECUTABLE=$(get_python_executable)
  fi
}

get_pypi_server_pid() {
  if [ ! -f "${PYPI_PID_FILE}" ]; then
    echo ''
  else
    cat "${PYPI_PID_FILE}"
  fi
}

is_pypi_server_running() {
  local pid=$(get_pypi_server_pid)
  if [ -z "${pid}" -o "${pid}" = '' ]; then
    return 1
  fi
  kill -0 "$pid" >/dev/null 2>&1
}

start_pypi_server() {
  stop_pypi_server
  echo "Starting Local PyPi server"
  load_PYTHON_EXECUTABLE_variable
  nohup "${PYTHON_EXECUTABLE}" -m http.server "${PYPI_WEBSERVER_PORT}" --directory "$ROOT_DIR"/am2cm-ansible/python_dependencies > "$LOGS_DIR/local_pypi_server.log" 2>&1 &
  echo $! > "$PYPI_PID_FILE"
  if ! is_pypi_server_running; then
    echo "Failed to start Local PyPi server - Exiting..." | tee -a "$LOG_FILE"
    exit 1
  fi
  echo "Started Local PyPi server! Logging into $LOGS_DIR/local_pypi_server.log" | tee -a "$LOG_FILE"
}

stop_pypi_server() {
  echo "Stopping Local PyPi server"
  if is_pypi_server_running; then
    local pypi_pid=$(get_pypi_server_pid)
    kill "$pypi_pid"
    if [ "$?" -eq 0 ]; then
      rm $PYPI_PID_FILE
    else
      echo "Failed to stop Local PyPi server - Exiting..." | tee -a "$LOG_FILE"
      exit 1
    fi
  fi
}

cleanup_pypi_server () {  # this method is expected to be called only from a trap on EXIT
  if [ "$?" -ne 0 ]; then
    stop_pypi_server
  fi
}


get_cma_server_pid() {
  if [ ! -f "${CMA_SERVER_PID_FILE}" ]; then
    echo ''
  else
    cat "${CMA_SERVER_PID_FILE}"
  fi
}

is_cma_server_running() {
  local pid=$(get_cma_server_pid)
  if [ -z "${pid}" -o "${pid}" = '' ]; then
    return 1
  fi
  kill -0 "$pid" >/dev/null 2>&1
}

cleanup() {
  echo -e '\n'
  if [ "${SETUP_CMA_SERVER}" = true ]; then
    if ! delete_virtual_env; then
      echo 'Next time the script should be called with the --rebuild option'
    fi
  fi
  echo 'The script is terminated'
  exit 1
}

execute_command() {
  if [ "${VERBOSE}" = true ]; then
    printf "\n" > /dev/tty
    "$@" | tee -a "$LOG_FILE"
    if [ "${PIPESTATUS[0]}" -ne "0" ]; then
      echo "Command execution has failed! Exiting..." | tee -a "$LOG_FILE"
      exit 1
    fi
  else
    "$SCRIPT_PATH"/capture_exit_code.sh "${LOGS_DIR}/command_exit_code.txt" "${@}" >>"$LOG_FILE" 2>&1 &

    local pid=$!
    trap "kill ${pid}; cleanup" SIGINT

    wait_for_pid ${pid} 2> /dev/null
    if [ "$(head -n 1 "${LOGS_DIR}"/command_exit_code.txt)" != "0" ]; then
      echo "Command execution has failed! Exiting..." | tee -a "$LOG_FILE"
      exit 1
    fi
  fi
}

setup_cma_server() {

  load_PYTHON_EXECUTABLE_variable 
  SETUP_CMA_SERVER=true
  if [ "$AIRGAPPED" = true ]; then
    if ! is_pypi_server_running; then
      start_pypi_server
    fi
  fi

  echo -n "Installing the CMA server.." | tee -a "$LOG_FILE"
  if [ "$AIRGAPPED" = true ]; then
    execute_command "$SCRIPT_PATH"/setup.sh --local --profile="${CMA_SERVER_PROFILE}" --python-executable="${PYTHON_EXECUTABLE}" --pypi-webserver-port="${PYPI_WEBSERVER_PORT}" --cma-extras-gpl-tar-location="${CMA_EXTRAS_GPL_TAR_LOCATION}"
  else
    execute_command "$SCRIPT_PATH"/setup.sh --local --profile="${CMA_SERVER_PROFILE}" --python-executable="${PYTHON_EXECUTABLE}"
  fi

  if [ -d "${VENV_DIR}" ]; then
    echo "Done." | tee -a "$LOG_FILE"
  else
    echo "Failed." | tee -a "$LOG_FILE"
    exit 1
  fi
}

wait_str() {
  local file="$1"; shift
  local initial_term="$1"; shift
  local search_term="$1"; shift
  local wait_time="${1:-5}"; shift # 5 minutes as default timeout

  if ! wait_for_file "$file"; then
    echo "Failed!"
    echo "ERROR: $file is missing!" > /dev/tty
    exit 1
  fi

  # Check for the last occurrence of the initial term, or default to 1 (1st line) if it's not found
  #
  # Default scenario can happen if the file has been created already, but the initial term would be on the 1st line
  # which has not yet been written into the file.
  local initial_line_number=$(grep -n "${initial_term}" "$file" | tail -n1 | cut -d: -f1)
  initial_line_number=${initial_line_number:-1}

  (xtimeout "$wait_time" tail -F -n +"$initial_line_number" "$file") | grep -q "$search_term" && echo "Done!" && return 0

  echo "Failed!"
  echo "Timeout of $wait_time reached. Unable to find '$search_term' in '$file'"
  echo "Please check the $file for more details!"
  return 1
}

stop_cma_server() {
  if is_cma_server_running; then
    echo -n "Stopping the CMA server.." | tee -a "$LOG_FILE"
    execute_command "$ROOT_DIR"/cma-server/cma-server.sh --stop

    # check if cma_server stopped
    if ! wait_str $CMA_SERVER_LOG_FILE "Started Application\|lastSseEvent is NULL" "Shutdown completed" $CMA_SERVER_STOP_TIMEOUT; then
      exit 1
    fi
    if [ "$AIRGAPPED" = true ]; then
      stop_pypi_server
    fi
  else
    echo "CMA server is not running!"
  fi
}

start_cma_server() {
  if [ "$AIRGAPPED" = true ]; then
    if ! is_pypi_server_running; then
      start_pypi_server
    fi
  fi
  if ! is_cma_server_running; then
    echo -n "Starting the CMA server.." | tee -a "$LOG_FILE"
    if [ "$AIRGAPPED" = true ]; then
      execute_command "$ROOT_DIR"/cma-server/cma-server.sh --start --am2cm-root-dir="${ROOT_DIR}" --pypi-webserver-port="${PYPI_WEBSERVER_PORT}"
    else
      execute_command "$ROOT_DIR"/cma-server/cma-server.sh --start --am2cm-root-dir="${ROOT_DIR}"
    fi

    # check if cma_server started
    if ! wait_str $CMA_SERVER_LOG_FILE "Starting Application" "Started Application" $CMA_SERVER_START_TIMEOUT; then
      exit 1
    fi

  else
    echo "CMA server is running!"
  fi
}

reinstall() {
  # stop cma-server if running
  if is_cma_server_running; then
    stop_cma_server
  fi

  # delete virtual env
  if ! delete_virtual_env; then
    exit 1
  fi
  setup_cma_server
}

if [ "$AIRGAPPED" = true ]; then
  trap "cleanup_pypi_server" EXIT
fi

if [ "${ACTION_STOP}" = true ]; then
  stop_cma_server
fi

if [ "${ACTION_REBUILD}" = true ]; then
  reinstall
fi

if [ "${ACTION_START}" = true ]; then
  if [ ! -d "${VENV_DIR}" ]; then
    setup_cma_server
    sleep 1
  fi
  start_cma_server
fi
