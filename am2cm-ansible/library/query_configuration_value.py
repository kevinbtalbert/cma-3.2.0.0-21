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
        configuration_name=dict(type='str', required=True),
        configuration_type=dict(type='str', required=False, choices=['SERVICE', 'ROLE', 'NOT_SPECIFIED'],
                                default='NOT_SPECIFIED'),
        role_name_filter=dict(type='str', required=False)
    )

    result = dict(
        changed=False,
        original_message='',
        message=''
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
        required_by={
            'role_name_filter': 'configuration_type'
        }
    )
    result['original_message'] = json.dumps(module.params)
    LOG.info("inputs: {}".format(result['original_message']))
    # ####################################################################
    cluster = CDPCluster(
        hostname=module.params['cm_configuration']['cloudera_manager_hostname'],
        port=module.params['cm_configuration']['cloudera_manager_port'],
        is_https=(module.params['cm_configuration']['cloudera_manager_protocol'] == 'https'),
        verify_ssl=False,
        username=module.params['cm_configuration']['cloudera_manager_admin_username'],
        password=module.params['cm_configuration']['cloudera_manager_admin_password'],
        cluster_name=module.params['cm_configuration']['cluster_name'])

    argument_list = [module.params['service_name'], module.params['configuration_name'],
                     module.params['configuration_type'], module.params['role_name_filter']]

    result['changed'], result['message'] = cluster.query_configuration_value(*argument_list)

    if result['changed']:
        module.exit_json(**result)
    else:
        module.fail_json(msg="Exception when looking for service configuration", **result)


def main():
    run_module()


if __name__ == '__main__':
    main()
