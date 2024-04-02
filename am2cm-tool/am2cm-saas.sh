#!/bin/bash

export PATH=$JAVA_HOME/bin:$PATH
export AM2CM_HOME_DIR=$(cd $(dirname $0)/ && pwd)
if [ -z "${AM2CM_WORKDIR}" ]; then
  export AM2CM_WORKDIR=$(pwd)
fi

echo "am2cm-workdir: ${AM2CM_WORKDIR}"
CLASSPATH=$AM2CM_HOME_DIR/conf:$AM2CM_HOME_DIR/lib/*:$AM2CM_HOME_DIR/*:.:
java -Xms2G -cp $CLASSPATH $JAVA_OPTS com.cloudera.migration.CMMigrationSaas "$@"