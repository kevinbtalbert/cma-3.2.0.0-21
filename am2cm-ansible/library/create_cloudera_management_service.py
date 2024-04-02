#!/usr/bin/python

import json
# << insert correctly modified ansible_preamble here
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
    cluster = CDPCluster(
        hostname=module.params['cm_configuration']['cloudera_manager_hostname'],
        port=module.params['cm_configuration']['cloudera_manager_port'],
        is_https=(module.params['cm_configuration']['cloudera_manager_protocol'] == 'https'),
        verify_ssl=False,
        username=module.params['cm_configuration']['cloudera_manager_admin_username'],
        password=module.params['cm_configuration']['cloudera_manager_admin_password'],
        cluster_name=module.params['cm_configuration']['cluster_name'])

    # Check whether Management Services are already installed
    if cluster.is_management_service_exists():
        result['changed'] = False
        result['message'] = "Management Service already installed"
        module.exit_json(**result)

    # If we're running in check mode, then at this this point we can conclude that
    # management service does NOT exist on the cluster, so the next API call would change state
    if module.check_mode:
        result['changed'] = True
        result['message'] = "Management Service is not currently installed"
        module.exit_json(**result)

    result['changed'], result['message'] = cluster.create_cloudera_management_service()

    if result['changed']:
        module.exit_json(**result)
    else:
        module.fail_json(msg='Exception when calling API', **result)

def main():
    run_module()


if __name__ == '__main__':
    main()
