#!/usr/bin/python
import json
import logging
import os

from ansible.module_utils.am2cm_commons.cdp_cluster import CDPCluster
from ansible.module_utils.am2cm_commons.logging_utils import configure_logging
from ansible.module_utils.am2cm_commons.safety_valve_formats import SafetyValveInterface
from ansible.module_utils.am2cm_commons.safety_valve_formats import XmlImplementation
from ansible.module_utils.am2cm_commons.safety_valve_formats import PropertyFileImplementation
from ansible.module_utils.basic import AnsibleModule

configure_logging(os.path.basename(__file__).replace(".py", "-module.log"))
LOG = logging.getLogger(__name__)


def run_module():
    module_args = dict(
        cm_configuration=dict(type='dict', required=True),
        valve_name=dict(type='str', required=True),
        valve_value=dict(type='str', required=True),
        service_name=dict(type='str', required=True),
        configuration_type=dict(type='str', required=True, choices=['SERVICE', 'ROLE']),
        configuration_format=dict(type='str', required=True, choices=['XML', 'PROPERTY_FILE']),
        role_name=dict(type='str', required=False)
    )

    result = dict(
        changed=False,
        original_message='',
        message=''
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
        required_if=[
            ('configuration_type', 'ROLE', ['role_name'], False)
        ]  # if configuration_type == 'ROLE', then 'role_name' param must be specified
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

    success, returned_value = cluster.query_configuration_value(service_name=module.params['service_name'],
                                                                configuration_name=module.params['valve_name'],
                                                                configuration_type=module.params['configuration_type'],
                                                                role_name_filter=module.params['role_name'])
    safety_valve_interface = None
    result['changed'] = True
    LOG.info("Success: {}".format(str(success)))
    LOG.info("Returned value: {}".format(str(returned_value)))
    if success:
        if module.params['configuration_format'] == "XML":
            safety_valve_interface: SafetyValveInterface = XmlImplementation()
        elif module.params['configuration_format'] == "PROPERTY_FILE":
            safety_valve_interface: SafetyValveInterface = PropertyFileImplementation()

        original_dict = safety_valve_interface.convert_response_to_dict(returned_value)

        LOG.info("Name: {}".format(str(module.params['valve_name'])))
        LOG.info("Value: {}".format(str(module.params['valve_value'])))
        LOG.info("Original dict: {}".format(str(original_dict)))
        if module.params['valve_value'] in original_dict:
            result['message'] = original_dict[module.params['valve_value']]
            module.exit_json(**result)
        else:
            result['message'] = None
            module.exit_json(**result)
    else:
        result['changed'] = False
        result['message'] = returned_value
        module.exit_json(msg="Configuration could not be read from API", **result)

    if result['changed']:
        module.exit_json(**result)
    else:
        module.fail_json(msg="Exception when looking for safety valve value", **result)


def main():
    run_module()


if __name__ == '__main__':
    main()
