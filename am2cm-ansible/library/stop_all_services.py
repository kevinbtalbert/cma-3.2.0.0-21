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

    try:
        all_services = cluster.get_all_services()
        running_services = list(service for service in all_services if service.service_state == 'STARTED')
        is_running_services = len(running_services) > 0

        if module.check_mode:
            result['changed'] = is_running_services
            module.exit_json(**result)

        if not is_running_services:
            result['message'] = 'All services have already been stopped!'
            result['changed'] = False
            module.exit_json(**result)

        api_request_success, api_response_message = cluster.stop_all_services()
        if not api_request_success:
            LOG.warning(f"Failed to stop all services by Cluster service! message={api_response_message}")
            LOG.info(f"Stop services one by one")
            for service in running_services:
                LOG.info(f"Stop service {service.name}")
                success, message = cluster.stop_service(service_name=service.name)
                if not success:
                    result['changed'] = False
                    result['message'] = message
                    module.fail_json(msg=f"Failed to stop service {service.name}!", **result)

        result['changed'] = True
        result['message'] = "All HDP services have been stopped successfully!"
        module.exit_json(**result)

    except Exception as e:
        result['changed'] = False
        result['message'] = str(e)
        module.fail_json(msg="Exception when attempting to stop all services", **result)


def main():
    run_module()


if __name__ == '__main__':
    main()
