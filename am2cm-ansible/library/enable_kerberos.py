#!/usr/bin/python

import json
# << insert correctly modified ansible_preamble here
import logging
import os

from ansible.module_utils.am2cm_commons.cdp_cluster import CDPCluster
from ansible.module_utils.am2cm_commons.kerberos_handler import KerberosHandler
from ansible.module_utils.am2cm_commons.logging_utils import configure_logging
from ansible.module_utils.basic import AnsibleModule

configure_logging(os.path.basename(__file__).replace(".py", "-module.log"))
LOG = logging.getLogger(__name__)


def run_module():
    module_args = dict(
        cm_configuration=dict(type='dict', required=True),
        kdc_server_configuration=dict(type='dict', required=True),
        os_type=dict(type='str', required=True)
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
        cluster_name=module.params['cm_configuration']['cluster_name']
    )
    kerberos_handler = KerberosHandler(
        cluster=cluster,
        use_ad=module.params['cm_configuration']['kerberos_configuration']['use_ad'],
        kdc_host=module.params['kdc_server_configuration']['kdc_host'],
        realm_name=module.params['cm_configuration']['kerberos_configuration']['realm_name'],
        ad_domain=module.params['cm_configuration']['kerberos_configuration']['ad_domain'],
        kerberos_admin_user=module.params['cm_configuration']['kerberos_configuration']['kerberos_admin_user'],
        kerberos_admin_password=module.params['cm_configuration']['kerberos_configuration']['kerberos_admin_password'],
        os_type=module.params['os_type']
    )

    result['changed'], result['message'] = kerberos_handler.set_kerberos_configurations()
    if not result['changed']:
        module.fail_json(msg='Exception while setting kerberos configurations for Cloudera Manager', **result)

    result['changed'], result['message'] = kerberos_handler.configure_cm_for_kerberos()
    if result['changed']:
        module.exit_json(**result)
    else:
        module.fail_json(msg='Exception while enabling kerberos in Cloudera Manager', **result)


def main():
    run_module()


if __name__ == '__main__':
    main()
