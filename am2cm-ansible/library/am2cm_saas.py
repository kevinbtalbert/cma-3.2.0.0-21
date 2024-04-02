#!/usr/bin/python

# << insert correctly modified ansible_preamble here

import json
import logging
import os
import subprocess

from ansible.module_utils.am2cm_commons.logging_utils import configure_logging, get_transition_log_dir
from ansible.module_utils.basic import AnsibleModule

configure_logging(os.path.basename(__file__).replace(".py", "-module.log"))
LOG = logging.getLogger(__name__)


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        am2cm_saas_configuration=dict(type='dict', required=True)
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

    # if the user is working with this module in only check mode we do not
    # want to make any changes to the environment, just return the current
    # state with no modifications
    if module.check_mode:
        result['changed'] = True
        module.exit_json(**result)

    script_path = module.params['am2cm_saas_configuration']['script_path']
    source_version = module.params['am2cm_saas_configuration']['source_version']
    target_version = module.params['am2cm_saas_configuration']['target_version']
    user_setting_file = module.params['am2cm_saas_configuration']['user_setting_file']
    config_path = module.params['am2cm_saas_configuration']['config_path']
    am_blueprint_file = module.params['am2cm_saas_configuration']['ambari_blueprint_file']
    cm_blueprint_file = module.params['am2cm_saas_configuration']['cm_blueprint_file']

    args = [f'{script_path}/am2cm-saas.sh',
            '--source-version', source_version,
            '--target-version', target_version,
            '--blueprint-file', am_blueprint_file,
            '--cm-template-file', cm_blueprint_file,
            '--silent',
            ]
    if len(user_setting_file) > 0:
        args.append('--user-setting-file')
        args.append(user_setting_file)

    if len(config_path) > 0:
        args.append('--config-path')
        args.append(config_path)

    os.environ["JAVA_OPTS"] = f"-DlogPath={get_transition_log_dir()}"
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    rc = process.returncode

    if rc != 0:
        result['stderr'] = stderr
        module.fail_json(msg='Exception when calling am2cm-saas.sh', **result)

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
