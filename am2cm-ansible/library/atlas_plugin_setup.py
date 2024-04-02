#!/usr/bin/python

import json
import logging
import os

from ansible.module_utils.am2cm_commons.cdp_cluster import CDPCluster
from ansible.module_utils.am2cm_commons.logging_utils import configure_logging
from ansible.module_utils.basic import AnsibleModule

configure_logging(os.path.basename(__file__).replace(".py", "-module.log"))
LOG = logging.getLogger(__name__)


def run_module():
    module_args = dict(
        cm_configuration=dict(type='dict', required=True),
        create_hbase_tables=dict(type='bool', default=False, required=False),
        create_kafka_topics=dict(type='bool', default=False, required=False)
    )

    result = dict(
        changed=False,
        original_message='',
        message=''
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=False
    )
    result['original_message'] = json.dumps(module.params)
    LOG.info("inputs: {}".format(result['original_message']))
    # ####################################################################
    # ####################################################################
    cluster = CDPCluster(
        hostname=module.params['cm_configuration']['cloudera_manager_hostname'],
        port=module.params['cm_configuration']['cloudera_manager_port'],
        is_https=(module.params['cm_configuration']['cloudera_manager_protocol'] == 'https'),
        verify_ssl=False,
        username=module.params['cm_configuration']['cloudera_manager_admin_username'],
        password=module.params['cm_configuration']['cloudera_manager_admin_password'],
        cluster_name=module.params['cm_configuration']['cluster_name'])

    final_success_message = "Successfully executed plugins: "

    is_atlas_installed = cluster.is_service_exists(service_name="atlas")

    if not is_atlas_installed:
        result['changed'] = False
        module.fail_json(msg="Atlas isn't installed, cannot run InitializeAtlas", **result)

    initialize_atlas_success, result['message'] = cluster.run_service_command("atlas", "InitializeAtlas")
    if not initialize_atlas_success:
        result['changed'] = False
        module.fail_json(msg="InitializeAtlas command failed", **result)
    else:
        final_success_message += " InitializeAtlas"

    is_ranger_installed = cluster.is_service_exists(service_name="ranger")
    if is_ranger_installed:
        create_ranger_atlas_plugin_success, result['message'] = cluster. \
            run_service_command("atlas", "CreateRangerAtlasPluginAuditDirCommand")
        if not create_ranger_atlas_plugin_success:
            module.fail_json(msg="Create ranger atlas plugin failed", **result)
        else:
            final_success_message += " CreateRangerAtlasPluginAuditDirCommand"

    if module.params['create_hbase_tables']:
        create_hbase_atlas_tables_success, result['message'] = \
            cluster.run_service_command("atlas", "CreateHBaseTablesForAtlas")
        if not create_hbase_atlas_tables_success:
            module.fail_json(msg="CreateHBaseTablesForAtlas command failed", **result)
        else:
            final_success_message += " CreateHBaseTablesForAtlas"

    if module.params['create_kafka_topics']:
        create_kafka_atlas_topics_success, result['message'] = \
            cluster.run_service_command("atlas", "CreateKafkaTopicsForAtlas")
        if not create_kafka_atlas_topics_success:
            module.fail_json(msg="CreateKafkaTopicsForAtlas command failed", **result)
        else:
            final_success_message += " CreateKafkaTopicsForAtlas"

    result['message'] = final_success_message
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
