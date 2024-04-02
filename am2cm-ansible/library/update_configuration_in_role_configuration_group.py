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
        cm_configuration=dict(type='dict', required=True),
        service_name=dict(type='str', required=True),
        role_configuration_group_name=dict(type='str', required=True),
        configuration_name=dict(type='str', required=True),
        configuration_value=dict(type='raw', required=True)  # set to 'raw' type so we can accept booleans too
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
    cluster = CDPCluster(
        hostname=module.params['cm_configuration']['cloudera_manager_hostname'],
        port=module.params['cm_configuration']['cloudera_manager_port'],
        is_https=(module.params['cm_configuration']['cloudera_manager_protocol'] == 'https'),
        verify_ssl=False,
        username=module.params['cm_configuration']['cloudera_manager_admin_username'],
        password=module.params['cm_configuration']['cloudera_manager_admin_password'],
        cluster_name=module.params['cm_configuration']['cluster_name'])

    success, returned_value = cluster.read_configuration_from_role_config_group(module.params['service_name'],
                                                                                module.params['role_configuration_group_name'],
                                                                                module.params['configuration_name'])
    if success:
        # for boolean values CM-API always returns lowercase 'true' or 'false'
        # also, regardless of variable type, CM-API returns a string
        # so I opted for turning the module parameter into an appropriate string if it's a boolean
        if isinstance(module.params['configuration_value'], bool):
            module.params['configuration_value'] = str(module.params['configuration_value']).lower()
        if returned_value == module.params['configuration_value']:
            result['changed'] = False
            result['message'] = f"Configuration '{module.params['configuration_name']}' " \
                                f"is already set to the following value: '{module.params['configuration_value']}'"
            module.exit_json(**result)
        else:
            if module.check_mode:
                result['changed'] = True
                result['message'] = "Configuration value will be updated"
    else:
        result['changed'] = False
        result['message'] = returned_value
        module.exit_json(msg="Configuration could not be read from API", **result)

    # if we got this far, then the configuration has been found and needs to be updated
    result['changed'], result['message'] = cluster.update_role_config_group_property(module.params['service_name'],
                                                                 module.params['role_configuration_group_name'],
                                                                 module.params['configuration_name'],
                                                                 module.params['configuration_value'])
    if result['changed']:
        module.exit_json(**result)
    else:
        module.fail_json(msg="Exception when attempting to update configuration", **result)


def main():
    run_module()


if __name__ == '__main__':
    main()
