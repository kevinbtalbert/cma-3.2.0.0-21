#!/usr/bin/python

import json
# << insert correctly modified ansible_preamble here
import logging
import os

from ansible.module_utils.am2cm_commons.hdfs_post_transition import HdfsPostTransition
from ansible.module_utils.am2cm_commons.logging_utils import configure_logging
from ansible.module_utils.basic import AnsibleModule

configure_logging(os.path.basename(__file__).replace(".py", "-module.log"))
LOG = logging.getLogger(__name__)


def run_module():
    module_args = dict(
        cm_configuration=dict(type='dict', required=True),
        hadoop_rpc_protection=dict(type='str', required=True),
        net_topology_script_file_name=dict(type='str', required=True),
        dfs_ha_proxy_provider=dict(type='str', required=True)
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
    hdfs_post_transition = HdfsPostTransition(
        hostname=module.params['cm_configuration']['cloudera_manager_hostname'],
        port=module.params['cm_configuration']['cloudera_manager_port'],
        is_https=(module.params['cm_configuration']['cloudera_manager_protocol'] == 'https'),
        verify_ssl=False,
        username=module.params['cm_configuration']['cloudera_manager_admin_username'],
        password=module.params['cm_configuration']['cloudera_manager_admin_password'],
        cluster_name=module.params['cm_configuration']['cluster_name'],
        hadoop_rpc_protection=module.params['hadoop_rpc_protection'],
        net_topology_script_file_name=module.params['net_topology_script_file_name'],
        dfs_ha_proxy_provider=module.params['dfs_ha_proxy_provider']
    )

    # NOTE: This isn't working as a 'true' ansible module yet
    # TODO check if step is already ready (i.e. is there anything that needs to be done)
    # TODO handle module.check_mode

    result['changed'], result['message'] = hdfs_post_transition.do_tls_ssl_chapter()

    if result['changed']:
        module.exit_json(**result)
    else:
        module.fail_json(msg='Exception doing hdfs tls/ssl chapter', **result)


def main():
    run_module()


if __name__ == '__main__':
    main()
