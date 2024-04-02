#!/usr/bin/python
from ansible.module_utils.basic import AnsibleModule
from hurry.filesize import size
import json


def run_module():
    module_args = dict(
        mounts=dict(type='list', required=True),
        space_requirements=dict(type='dict', required=True)
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

    # ####################################################################

    if module.check_mode:
        module.exit_json(**result)

    # mount names and available size
    node_mounts = dict((mount['mount'], int(mount['size_available'])) for mount in module.params['mounts'])
    # space requirements
    space_requirements = dict((mount, int(module.params['space_requirements'][mount])) for mount in module.params['space_requirements'])

    # 1 : check "/var/log"
    if "/var/log" in node_mounts:
        if node_mounts['/var/log'] < space_requirements['/var/log']:
            module.fail_json(
                msg="Available space in \"/var/log\" : {0}\nMinimum space required for storing the logs in "
                    "\"/var/log\" : {1}".format(size(node_mounts['/var/log']),
                                                size(space_requirements['/var/log'])), **result)
    else:
        module.fail_json(msg="\"/var/log\" should not be part of the root OS partition.", **result)

    # 2 : check mounts in space_requirements apart from "/"
    for mount in space_requirements:
        if mount == "/" or mount == "/var/log":  # "/" and "/var/log" are checked separately
            continue
        if mount in node_mounts:
            if node_mounts[mount] < space_requirements[mount]:
                module.fail_json(
                    msg="Available space in \"{0}\" : {1}\nMinimum space required for \"{2}\" is : {3}"
                    .format(mount, size(node_mounts[mount]), mount, size(space_requirements[mount])), **result)
        else:  # if there isn't a separate mount, add space requirement to "/"
            space_requirements['/'] += space_requirements[mount]

    # 3 : check "/"
    if "/" in node_mounts:
        if node_mounts['/'] < space_requirements['/']:
            module.fail_json(msg="Available space in \"/\" : {0}\nMinimum space required for \"/\" is : {1}"
                             .format(size(node_mounts['/']), size(space_requirements['/'])), **result)
    else:
        module.fail_json(msg="Cannot find root partition \"/\".", **result)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
