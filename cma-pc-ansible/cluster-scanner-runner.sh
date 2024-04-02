#
# Copyright (c) 2023, Cloudera, Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

TAGS="scan-cluster"
DISCOVERY_MODULES="hdfs_report,hive_metastore"

__usage="
Usage: $(basename "$0") [options]
Options:
   --data-scan: generate the data report (hdfs, hive)
   --hdfs-data-scan: generate the hdfs data report
   --hive-data-scan: generate the full hive data report (table scan + check)
   --hive-table-scan: generate the table scan report
   --hive-table-check: generate the hive table check report
   --hbase-table-scan: generate the table scan report for hbase
   --workload-scan: generate the workload report
   --hive-workload-scan: generate the hive-sql report
   -i, --inventory: the inventory file
   -e, --extra-vars: the extra-vars file
   -t, --tags: only run plays and tasks tagged with these values (default=${TAGS})
   -o, --output-dir: the output dir
   -h, --help: Print this help
"

while test $# -gt 0; do
  case $1 in
  --data-scan)
    DISCOVERY_MODULES="hdfs_report,hive_metastore"
    TAGS="scan-cluster"
    shift
    ;;
  --hdfs-data-scan)
    DISCOVERY_MODULES=hdfs_report
    TAGS="download-discovery-bundle"
    shift
    ;;
  --hive-data-scan)
    DISCOVERY_MODULES=hive_metastore
    TAGS="download-discovery-bundle,hive-sre-pre-check"
    shift
    ;;
  --hive-table-scan)
    DISCOVERY_MODULES=hive_metastore
    TAGS="download-discovery-bundle"
    shift
    ;;
  --hive-table-check)
    TAGS="hive-sre-pre-check"
    shift
    ;;
  --hbase-table-scan)
      TAGS="scan-hbase-tables"
      shift
      ;;
  --workload-scan)
      TAGS="scan-cluster-workload"
      shift
      ;;
  --hive-workload-scan)
      TAGS="scan-hive-queries"
      shift
      ;;
  --oozie-data-scan)
      TAGS="scan-oozie-jobs"
      shift
      ;;
  -i | --inventory)
    shift
    INVENTORY=$1
    shift
    ;;
  -e | --extra-vars)
    shift
    EXTRA_VARS=$1
    shift
    ;;
  -t | --tags)
    shift
    TAGS=$1
    shift
    ;;
  -o | --output-dir)
    shift
    OUTPUT_DIR_PATH=$1
    shift
    ;;
  -h | --help)
    HELP=true
    shift
    ;;
  *)
    echo "Unknown option: $1"
    HELP=true
    break
    ;;
  esac
done

if [ "${HELP}" = true ]; then
  echo "$__usage"
  exit 0
fi

if [ -z ${INVENTORY} ]; then
  echo "ERROR: Make sure the inventory file is specified"
  exit 1
fi

if [ -z ${EXTRA_VARS} ]; then
  echo "ERROR: Make sure the extra-vars file is specified"
  exit 2
fi

if [ -n "${DISCOVERY_MODULES}" ]; then
  ADDITIONAL_EXTRA_VARS="-e discovery_bundle_module=${DISCOVERY_MODULES}"
fi

if [ -n "${OUTPUT_DIR_PATH}" ]; then
  ADDITIONAL_EXTRA_VARS="${ADDITIONAL_EXTRA_VARS} -e cluster_scan_dir=${OUTPUT_DIR_PATH}"
fi

echo "inventory: ${INVENTORY}"
echo "extra-vars: ${EXTRA_VARS}"
echo "tags: ${TAGS}"
echo "additional-extra-vars: ${ADDITIONAL_EXTRA_VARS}"

ansible-playbook -i ${INVENTORY} site.yml --tags ${TAGS} --extra-vars "@${EXTRA_VARS}" ${ADDITIONAL_EXTRA_VARS}