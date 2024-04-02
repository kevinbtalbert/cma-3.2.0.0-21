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
    # ####################################################################
    cluster = CDPCluster(
        hostname=module.params['cm_configuration']['cloudera_manager_hostname'],
        port=module.params['cm_configuration']['cloudera_manager_port'],
        is_https=(module.params['cm_configuration']['cloudera_manager_protocol'] == 'https'),
        verify_ssl=False,
        username=module.params['cm_configuration']['cloudera_manager_admin_username'],
        password=module.params['cm_configuration']['cloudera_manager_admin_password'],
        cluster_name=module.params['cm_configuration']['cluster_name'])

    all_services, started_services_names = exit_module_if_all_services_are_already_started(cluster, module, result)

    if module.check_mode:
        handle_check_mode(all_services, module, result, started_services_names)

    result['changed'], result['message'] = cluster.start_all_services()
    if result['changed']:
        module.exit_json(**result)
    else:
        module.fail_json(msg="Exception when attempting to restart service", **result)


def handle_check_mode(all_services, module, result, started_services_names):
    result['changed'] = True
    all_service_names = list(service.name for service in all_services)
    not_started_service_names = list(set(all_service_names) - set(started_services_names))
    result['message'] = "Not all services are running, start_all_service command will run. " \
                        "Currently not started services are: " + ",".join(not_started_service_names)
    module.exit_json(**result)


def exit_module_if_all_services_are_already_started(cluster, module, result):
    not_na_state_services = []
    started_services_names = []

    api_request_success, api_response_message = cluster.get_all_services_silently()
    if api_request_success:
        all_services = api_response_message
        not_na_state_services = list(service for service in all_services if service.service_state != 'NA')
        started_services_names = list(service.name for service in all_services if service.service_state == 'STARTED')
        if len(started_services_names) == len(not_na_state_services):
            result['changed'] = False
            result['message'] = "All services are in STARTED state, nothing to do"
            module.exit_json(**result)
    else:
        result['changed'] = False
        result['message'] = api_response_message
        module.fail_json(msg="Exception when querying API for services", **result)
    return not_na_state_services, started_services_names


def main():
    run_module()


if __name__ == '__main__':
    main()
