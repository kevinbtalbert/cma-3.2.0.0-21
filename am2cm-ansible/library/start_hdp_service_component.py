#!/usr/bin/python

# << insert correctly modified ansible_preamble here

import json
import logging
import os

from ansible.module_utils.am2cm_commons.hdp_cluster import HDPCluster
from ansible.module_utils.am2cm_commons.logging_utils import configure_logging
from ansible.module_utils.basic import AnsibleModule

configure_logging(os.path.basename(__file__).replace(".py", "-module.log"))
LOG = logging.getLogger(__name__)


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        ambari_configuration=dict(type='dict', required=True),
        service_name=dict(type='str', required=True),
        component_name=dict(type='str', required=True),
        wait_for_complete=dict(type='bool', required=False, default=True)
    )

    # seed the result dict in the object
    # we primarily care about changed and state
    # change is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = dict(
        changed=False,
        original_message='',
        message=''
    )

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )
    result['original_message'] = json.dumps(module.params)  # concatenate the params here, if there were any...
    LOG.info("inputs: {}".format(result['original_message']))

    hostname = module.params['ambari_configuration']['hostname']
    port = module.params['ambari_configuration']['port']
    username = module.params['ambari_configuration']['username']
    password = module.params['ambari_configuration']['password']
    cluster_name = module.params['ambari_configuration']['cluster_name']
    protocol = module.params['ambari_configuration']['protocol']

    cluster = HDPCluster(
        hostname=hostname, port=port, protocol=protocol, verify_ssl=False,
        username=username, password=password, cluster_name=cluster_name)

    service_name = module.params['service_name']
    component_name = module.params['component_name']
    is_component_started = cluster.is_service_component_started(service_name, component_name)

    result['tracking_url'] = ''

    # if the user is working with this module in only check mode we do not
    # want to make any changes to the environment, just return the current
    # state with no modifications
    if module.check_mode:
        result['changed'] = not is_component_started
        module.exit_json(**result)

    if not is_component_started:
        wait_for_complete = module.params['wait_for_complete']
        start_result = cluster.start_service_component(service_name=service_name,
                                                       component_name=component_name,
                                                       wait_for_complete=wait_for_complete)
        result['changed'] = start_result['success']
        if not start_result['success']:
            error_message = f"Failed to start {component_name} in {service_name} HDP service!"
            result['message'] = error_message
            module.fail_json(**result, msg=error_message)
        else:
            if not wait_for_complete:
                result['tracking_url'] = start_result['tracking_url']
            result['message'] = f"The {component_name} in {service_name} HDP service has been started successfully!"
    else:
        result['changed'] = False
        result['message'] = f"The {component_name} in {service_name} HDP service has already been started!"

    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
