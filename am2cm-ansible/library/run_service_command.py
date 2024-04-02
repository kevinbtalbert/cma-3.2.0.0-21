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
        service_name=dict(type='str', required=True),
        command=dict(type='str', required=True),
        timeout_seconds=dict(type='int', required=False, default=900)
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

    result['changed'] = cluster.is_service_exists(service_name=module.params['service_name'])

    if module.check_mode:
        result['message'] = f"Service {module.params['service_name']} " \
                            f"{'exists' if result['changed'] else 'does not exist'}" \
                            f"Command: {module.params['command']} will {'run' if result['changed'] else 'not run'}"
        module.exit_json(**result)

    if not result['changed']:
        module.fail_json(msg=f"Service {module.params['service_name']} does not exist to run the command "
                             f"{module.params['command']} on", **result)

    result['changed'], result['message'] = cluster.run_service_command(module.params['service_name'],
                                                                       module.params['command'],
                                                                       module.params['timeout_seconds'])

    if result['changed']:
        module.exit_json(**result)
    else:
        module.fail_json(msg="Exception when running 'run service command'", **result)


def main():
    run_module()


if __name__ == '__main__':
    main()
