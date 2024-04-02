#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule


def get_java_family_from_version_and_env(input_family, environment):
    if input_family == 'java':
        return 'oraclejdk'

    if input_family == 'openjdk':
        if 'zulu' in environment.lower():
            return 'azuljdk'
        else:
            return 'openjdk'

    return ''


def get_java_version(version):
    java_version = version.strip('"').split('.')
    if int(java_version[0]) < 9:
        return "jdk" + str(java_version[1])

    return "jdk" + str(java_version[0])


def run_module():
    module_args = dict(
        java_version=dict(type='str', required=True),
        java_environment=dict(type='str', required=True),
        support_matrix=dict(type='dict', required=True)
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

    # ####################################################################

    # list of supported java versions
    supported_java_list = [java_version['description'].lower() for java_version in module.params['support_matrix']['jdks']]
    # input java version
    input_java_family, input_java_version = module.params['java_version'].split(' ')[0], module.params['java_version'].split(' ')[2]

    # java family
    java_family = get_java_family_from_version_and_env(input_java_family, module.params['java_environment'])

    # check if java family is supported
    if not java_family:
        result["message"] = "Unsupported Java version"
        module.fail_json(msg="Current: {}, Supported: {}".format(input_java_family, ", ".join(supported_java_list)), **result)

    # java version
    java = java_family + "-" + get_java_version(input_java_version)

    # check if java version is supported
    if java in supported_java_list:
        result["message"] = "This Java version is supported"
        module.exit_json(**result)
    else:
        result["message"] = "Unsupported Java version"
        module.fail_json(msg="Current: {}, Supported: {}".format(java, ", ".join(supported_java_list)), **result)


def main():
    run_module()


if __name__ == '__main__':
    main()
