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
        timeout_seconds=dict(type='int', required=False, default=300)
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

    if module.check_mode:
        result['changed'] = True
        result['message'] = f"Will wait until heartbeat is received from all CM agents" \
                            f" and CM agent health status is 'GOOD' on all hosts"
        module.exit_json(**result)

    result['changed'], result['message'] = \
        cluster.wait_for_cm_agent_heartbeat_for_hosts(timeout_sec=module.params['timeout_seconds'])
    if not result['changed']:
        module.fail_json(msg="Failure while waiting for heartbeats from agents...", **result)

    LOG.info("Heartbeat from all hosts have arrived successfully. Waiting for agents to become healthy again.")
    result['changed'], result['message'] = \
        cluster.wait_for_cm_agent_to_be_healthy_on_hosts(timeout_sec=module.params['timeout_seconds'])
    if result['changed']:
        LOG.info("All agents are healthy.")
        module.exit_json(**result)
    else:
        module.fail_json(msg="Failure while waiting for agents to become 'GOOD'...", **result)


def main():
    run_module()


if __name__ == '__main__':
    main()
