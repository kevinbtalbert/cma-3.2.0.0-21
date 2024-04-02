#!/bin/bash

if [[ $(uname) == 'Linux' ]]; then
  export AM2CM_DIFF_HOME_DIR=$(cd $(dirname "$(readlink -f "$0")")/ && pwd)
else
  readlink_f() {
    local target="$1"
    [ -f "$target" ] || return 1 #no nofile

    while [ -L "$target" ]; do
      target="$(readlink "$target")"
    done
    echo "$(cd "$(dirname "$target")"; pwd -P)"
  }
  export AM2CM_DIFF_HOME_DIR=$(readlink_f "$0")
fi

export PATH=$JAVA_HOME/bin:$PATH
CLASSPATH=$AM2CM_DIFF_HOME_DIR/conf:$AM2CM_DIFF_HOME_DIR/lib/*:$AM2CM_DIFF_HOME_DIR/*:.:
java -Xms2G -cp $CLASSPATH com.cloudera.migration.diff.ConfigDiff "$@"