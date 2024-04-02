#!/usr/bin/python

import json
# << insert correctly modified ansible_preamble here
import logging
import os

from ansible.module_utils.am2cm_commons.auto_start_handler import AutoStartHandler
from ansible.module_utils.am2cm_commons.logging_utils import configure_logging
from ansible.module_utils.basic import AnsibleModule

configure_logging(os.path.basename(__file__).replace(".py", "-module.log"))
LOG = logging.getLogger(__name__)


def run_module():
    module_args = dict(
        cm_configuration=dict(type='dict', required=True),
        autostart_state_enabled=dict(type='bool', required=True)
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
    auto_start_handler = AutoStartHandler(
        hostname=module.params['cm_configuration']['cloudera_manager_hostname'],
        port=module.params['cm_configuration']['cloudera_manager_port'],
        is_https=(module.params['cm_configuration']['cloudera_manager_protocol'] == 'https'),
        verify_ssl=False,
        username=module.params['cm_configuration']['cloudera_manager_admin_username'],
        password=module.params['cm_configuration']['cloudera_manager_admin_password'],
        cluster_name=module.params['cm_configuration']['cluster_name']
    )

    result['changed'], result['message'] = \
        auto_start_handler.set_auto_start_state_for_all(module.params['autostart_state_enabled'])

    if result['changed']:
        module.exit_json(**result)
    else:
        module.fail_json(msg='Error while enabling auto start for all processes', **result)


def main():
    run_module()


if __name__ == '__main__':
    main()
