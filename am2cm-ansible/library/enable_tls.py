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
        cm_configuration=dict(type='dict', required=True),
        ssh_configuration=dict(type='dict', required=True),
        timeout_seconds=dict(type='int', required=False)
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

    if cluster.is_tls_enabled():
        result['changed'] = False
        result['message'] = "TLS is already enabled"
        module.exit_json(**result)

    # If we're running in check mode, then at this this point we can conclude that
    # TLS will be enabled
    if module.check_mode:
        result['changed'] = True
        result['message'] = "TLS will be enabled"
        module.exit_json(**result)

    custom_kwargs = {}
    if 'timeout_seconds' in module.params:
        custom_kwargs['timeout_seconds'] = module.params['timeout_seconds']

    if 'ansible_ssh_private_key_file' in module.params['ssh_configuration'] and\
            module.params['ssh_configuration']['ansible_ssh_private_key_file']:
        custom_kwargs['private_key_file'] = module.params['ssh_configuration']['ansible_ssh_private_key_file']

    elif 'ansible_ssh_pass' in module.params['ssh_configuration']:
        custom_kwargs['password'] = module.params['ssh_configuration']['ansible_ssh_pass']

    else:
        result['changed'] = False
        result['message'] = "Either ansible_ssh_private_key_file or ansible_ssh_pass is missing from" \
                            "all.yml or extra vars configuration"
        module.fail_json(msg='Incorrect parametrization', **result)

    result['changed'], result['message'] = cluster\
        .enable_tls(remote_username=module.params['ssh_configuration']['ansible_user'], **custom_kwargs)
    if result['changed']:
        module.exit_json(**result)
    else:
        module.fail_json(msg='Exception when enabling TLS', **result)


def main():
    run_module()


if __name__ == '__main__':
    main()
