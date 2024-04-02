#!/usr/bin/env bash

"${@:2}" &
pid=$!
# shellcheck disable=SC2064
trap "kill ${pid}" SIGINT EXIT
wait ${pid}
echo "$?" > "${1}"
