#!/usr/bin/python

# << insert correctly modified ansible_preamble here
import json
import logging
import os

from ansible.module_utils.am2cm_commons.logging_utils import configure_logging
from ansible.module_utils.basic import AnsibleModule

configure_logging(os.path.basename(__file__).replace(".py", "-module.log"))
LOG = logging.getLogger(__name__)


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        supported_os_list=dict(type='dict', required=True),
        ansible_facts=dict(type='dict', required=True),
        cm_configuration=dict(type='dict', required=True)
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

    result['original_message'] = json.dumps(module.params)
    LOG.info("inputs: {}".format(result['original_message']))
    # ####################################################################

    cm_version = module.params['cm_configuration']['cloudera_manager_target_version']
    supported_os_list = module.params["supported_os_list"]
    os_name = module.params["ansible_facts"]["distribution"]
    os_version = module.params["ansible_facts"]["distribution_version"]

    # Checking the CM version compatibility (task fails if CM version is unsupported)
    if cm_version not in supported_os_list.keys():
        message = "Unsupported CM version"
        hint = "Current: {}, Supported: {}".format(cm_version, ", ".join(supported_os_list.keys()))
        result["message"] = str(message)

        module.fail_json(msg=hint, **result)

    # Checking the OS name and version compatibility (task will succeed if OS is supported else it will fail)
    if os_name in supported_os_list[cm_version].keys() and os_version in supported_os_list[cm_version][os_name]:
        message = "This OS is supported"
        result["message"] = str(message)

        module.exit_json(**result)
    else:
        message = "Unsupported OS"
        os_list_str = ", ".join(
            [", ".join(
                [" ".join([x, y]) for y in supported_os_list[cm_version][x]]
            )
                for x in supported_os_list[cm_version]]
        )
        hint = "Current: {}, Supported: {}".format(" ".join([os_name, os_version]), os_list_str)
        result["message"] = str(message)

        module.fail_json(msg=hint, **result)


def main():
    run_module()


if __name__ == '__main__':
    main()
