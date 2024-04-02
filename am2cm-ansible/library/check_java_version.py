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
        supported_java_versions=dict(type='dict', required=True),
        current_java_version_lines=dict(type='list', required=True)
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

    supported_java_versions = module.params["supported_java_versions"]
    current_java_version_lines = module.params["current_java_version_lines"]

    current_java_name = current_java_version_lines[1].split(" ")[0]
    current_java_version = ".".join(current_java_version_lines[0].split(" version ")[1].strip("\"").split(".")[:2])

    if current_java_name not in supported_java_versions.keys():
        result["message"] = "Unsupported Java version"
        hint = "Current: {}, Supported: {}".format(
            current_java_name,
            ", ".join(supported_java_versions.keys())
        )

        module.fail_json(msg=hint, **result)

    if current_java_version not in supported_java_versions[current_java_name]:
        result["message"] = "Unsupported Java version"
        java_versions = [", ".join(
            [" ".join([x, y]) for y in supported_java_versions[x]]
        )
            for x in supported_java_versions
        ]
        hint = "Current: {} {}, Supported: {}".format(current_java_name, current_java_version, java_versions)
        module.fail_json(msg=hint, **result)

    result["message"] = "This java version is supported"
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
