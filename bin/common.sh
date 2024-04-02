
ROOT_DIR=$(dirname $(cd $(dirname $(readlink -f "$0"))/ && pwd))
VENV_DIR="${ROOT_DIR}"/venv
LOGS_DIR="${ROOT_DIR}"/logs

mkdir -p "${LOGS_DIR}"

# Local .env
load_env_file() {
  env_file=${1:-.env1}
  if [ -f "${env_file}" ]; then
    # Load Environment Variables
    source "${env_file}"
    echo "${env_file} is loaded"
  fi
}

# $1 the default python executable. Defaults to 'python3'
get_python_executable() {
  local default_python_executable=${1:-python3}
  read -r -p "Enter the path for python3 executable [${default_python_executable}]:" python_executable
  python_executable=${python_executable:-${default_python_executable}}
  echo "${python_executable}"
}

delete_virtual_env()
{
  echo "Deleting virtualenv in ${VENV_DIR}"
  if ! rm -rf "${VENV_DIR}"; then
    echo "Failed to delete ${VENV_DIR}"
    return 1
  fi
  return 0
}

function wait_for_pid() {

  local pid=$1
  while kill -0 "${pid}" >/dev/null 2>&1; do
    printf '.' > /dev/tty
    sleep 2
  done

}

function xtimeout {
  timeout=$1
  shift
  command=("$@")
  (
    "${command[@]}" &
    runner_pid=$!
    trap -- '' SIGTERM
    ( # killer job
      sleep "$timeout"
      if ps -p $runner_pid > /dev/null; then
        kill -SIGKILL $runner_pid 2>/dev/null 2>&1
      fi
    ) &
    killer_pid=$!
    wait_for_pid $runner_pid 2> /dev/null
    kill -SIGKILL $killer_pid >/dev/null 2>&1
  )
}

wait_for_file() {
  local file="$1"; shift
  local wait_seconds="${1:-10}"; shift # 10 seconds as default timeout

  until test $((wait_seconds--)) -eq 0 -o -f "$file" ; do
    printf '.' > /dev/tty;
    sleep 2;
  done

  if [ "$wait_seconds" -le 0 ]; then
    return 1
  fi
  return 0
}