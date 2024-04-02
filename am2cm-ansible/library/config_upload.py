#!/usr/bin/python

# << insert correctly modified ansible_preamble here

import json
import logging
import os
import subprocess

from ansible.module_utils.am2cm_commons.cdp_cluster import CDPCluster
from ansible.module_utils.am2cm_commons.logging_utils import configure_logging, get_transition_log_dir
from ansible.module_utils.basic import AnsibleModule

configure_logging(os.path.basename(__file__).replace(".py", "-module.log"))
LOG = logging.getLogger(__name__)


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        cm_configuration=dict(type='dict', required=True),
        config_upload_configuration=dict(type='dict', required=True)
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

    cm_hostname = module.params['cm_configuration']['cloudera_manager_hostname']
    cm_port = module.params['cm_configuration']['cloudera_manager_port']
    cm_protocol = module.params['cm_configuration']['cloudera_manager_protocol']
    is_cm_https = cm_protocol == 'https'
    cm_username = module.params['cm_configuration']['cloudera_manager_admin_username']
    cm_password = module.params['cm_configuration']['cloudera_manager_admin_password']
    cm_cluster_name = module.params['cm_configuration']['cluster_name']

    # check if cm-cluster exists. If not then return error msg
    cluster = CDPCluster(
        hostname=cm_hostname, port=cm_port, is_https=is_cm_https, verify_ssl=False,
        username=cm_username, password=cm_password, cluster_name=cm_cluster_name)

    cluster_exist = cluster.is_cluster_exist()

    # if the user is working with this module in only check mode we do not
    # want to make any changes to the environment, just return the current
    # state with no modifications
    if module.check_mode:
        result['changed'] = cluster_exist
        module.exit_json(**result)

    if not cluster_exist:
        result['changed'] = False
        module.fail_json(msg='CDP cluster does not exist! Please create it first!', **result)

    script_path = module.params['config_upload_configuration']['script_path']
    cluster_topology_file = module.params['config_upload_configuration']['cluster_topology_file']

    args = [f'{script_path}/config-upload.sh',
            '--cluster-topology', cluster_topology_file,
            ]
    os.environ["JAVA_OPTS"] = f"-DlogPath={get_transition_log_dir()}"
    process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate(input=f'{cm_password}\n'.encode())
    rc = process.returncode

    if rc != 0:
        result['stderr'] = stderr
        module.fail_json(msg='Exception when calling config-upload.sh', **result)

    result['stdout'] = stdout

    # use whatever logic you need to determine whether or not this module
    # made any modifications to your target
    result['changed'] = True

    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
