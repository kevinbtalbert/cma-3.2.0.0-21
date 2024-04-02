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
        service_name=dict(type='str', required=True)
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

    service_name = module.params['service_name']

    is_service_installed = cluster.is_service_exists(service_name=service_name)

    if module.check_mode:
        result['changed'] = is_service_installed
        module.exit_json(**result)

    if not is_service_installed:
        result['changed'] = False
        module.fail_json(msg=f"{service_name} isn't installed, cannot deploy client configurations!", **result)

    deploy_client_config_success, result['message'] = cluster.deploy_service_client_configuration(service_name)
    if not deploy_client_config_success:
        result['changed'] = False
        module.fail_json(msg=f"Deploying {service_name} client configuration has failed!", **result)
    else:
        result['changed'] = True
        result['message'] = f"Deploy Client Configurations for {service_name} is successful!"

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
