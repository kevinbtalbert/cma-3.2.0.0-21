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
        cm_configuration=dict(type='dict', required=True)
    )

    result = dict(
        changed=False,
        original_message='',
        message=''
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
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

    is_ranger_exists = cluster.is_service_exists(service_name='ranger')

    if module.check_mode:
        result['changed'] = is_ranger_exists
        result['message'] = f"The KafkaRanger plugin will {'' if is_ranger_exists else 'not'} be configured"
        module.exit_json(**result)

    if not is_ranger_exists:
        result['changed'] = False
        module.exit_json(msg="The KafkaRanger plugin is not configured "
                             "because the Ranger service is not installed on the cluster", **result)

    result['changed'], result['message'] = cluster.run_service_command("kafka",
                                                                       "CreateRangerKafkaPluginAuditDirCommand")

    if result['changed']:
        module.exit_json(msg="The KafkaRanger plugin has been configured", **result)
    else:
        module.fail_json(msg="Exception when attempting to configure KafkaRanger plugin", **result)


def main():
    run_module()


if __name__ == '__main__':
    main()
