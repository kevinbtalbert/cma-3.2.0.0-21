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
        role_names=dict(type='raw', required=True),
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

    role_names_list = module.params['role_names'] \
        if isinstance(module.params['role_names'], list) \
        else [module.params['role_names']]

    result['changed'] = cluster.is_service_exists(service_name=module.params['service_name'])
    if not result['changed']:
        result['message'] = f"Service {module.params['service_name']} does not exist, " \
                  f"Command: {module.params['command']} will not run"
        if module.check_mode:
            module.exit_json(**result)
        else:
            module.fail_json(msg="Service does not exist!", **result)

    for role in role_names_list:
        result['changed'] = cluster.is_role_exists(service_name=module.params['service_name'], role_name=role)
        if not result['changed']:
            result['message'] = f"Role {role} does not exist for service {module.params['service_name']}, " \
                                f"Command: {module.params['command']} will not run"
            if module.check_mode:
                module.exit_json(**result)
            else:
                module.fail_json(msg="Role does not exist!", **result)

    if module.check_mode:
        result['message'] = f"Service {module.params['service_name']} exists. " \
                            f"Roles '{module.params['service_name']}' exist." \
                            f"Command: {module.params['command']} will run."
        module.exit_json(**result)

    result['changed'], result['message'] = cluster.run_role_command(module.params['command'],
                                                                    module.params['service_name'],
                                                                    role_names_list,
                                                                    module.params['timeout_seconds'])

    if result['changed']:
        module.exit_json(**result)
    else:
        module.fail_json(msg="Exception when running 'run role command'", **result)


def main():
    run_module()


if __name__ == '__main__':
    main()
