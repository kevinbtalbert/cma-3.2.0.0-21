#!/bin/bash

export PATH=$JAVA_HOME/bin:$PATH
export AM2CM_HOME_DIR=$(cd $(dirname $0)/ && pwd)
CLASSPATH=$AM2CM_HOME_DIR/conf:$AM2CM_HOME_DIR/lib/*:$AM2CM_HOME_DIR/*:.:
java -Xms2G -cp $CLASSPATH $JAVA_OPTS com.cloudera.migration.CMClusterScanner "$@"