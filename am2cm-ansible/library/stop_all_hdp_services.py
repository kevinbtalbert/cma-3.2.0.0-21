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

    is_all_service_stopped = cluster.is_all_services_stopped()

    # if the user is working with this module in only check mode we do not
    # want to make any changes to the environment, just return the current
    # state with no modifications
    if module.check_mode:
        result['changed'] = not is_all_service_stopped
        module.exit_json(**result)

    if not is_all_service_stopped:
        is_stopped_successfully = cluster.stop_all_services()
        result['changed'] = is_stopped_successfully
        if not is_stopped_successfully:
            result['message'] = "Failed to stop all HDP services!"
            module.fail_json(**result, msg="Failed to stop all HDP services!")
        else:
            result['message'] = "All HDP services have been stopped successfully!"
    else:
        result['changed'] = False
        result['message'] = "All HDP services have already been stopped!"



    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
