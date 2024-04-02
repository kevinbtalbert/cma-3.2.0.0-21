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
        role_type=dict(type='str', required=True)
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
    if not result['changed']:
        result['message'] = f"Service {module.params['service_name']} does not exist, " \
                            f"Unable to list role names."
        if module.check_mode:
            module.exit_json(**result)
        else:
            module.fail_json(msg="Failed to find service.", **result)

    if module.check_mode:
        result['message'] = f"Service {module.params['service_name']} exists. " \
                            f"Roles will be queried for type '{module.params['role_type']}'."
        module.exit_json(**result)

    roles = cluster.read_roles(module.params['service_name'])
    role_names = [role.name for role in roles.items if role.type == module.params['role_type']]

    result['role_names'] = role_names
    result['changed'] = True
    result['message'] = ','.join(role_names)
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()