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
        name=dict(type='str', required=True),
        value=dict(type='raw', required=True),
        state=dict(type='str', required=True, choices=['present', 'absent']),
        service_name=dict(type='str', required=True),
        configuration_type=dict(type='str', required=True, choices=['SERVICE', 'ROLE']),
        configuration_format=dict(type='str', required=True, choices=['XML', 'PROPERTY_FILE']),
        requires_parent_xml_tag=dict(type='bool', required=True),
        role_name=dict(type='str', required=False),
        role_display_name=dict(type='str', required=False),
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
        cluster_name=module.params['cm_configuration']['cluster_name'],
        api_postfix=module.params['cm_configuration'].get('api_postfix'),
    )

    success, returned_value = cluster.query_configuration_value(service_name=module.params['service_name'],
                                                                configuration_name=module.params['name'],
                                                                configuration_type=module.params['configuration_type'],
                                                                role_name_filter=module.params['role_name'])
    updated_dict = {}
    safety_valve_interface = None
    if success:
        if module.params['configuration_format'] == "XML":
            safety_valve_interface: SafetyValveInterface = XmlImplementation()
        elif module.params['configuration_format'] == "PROPERTY_FILE":
            safety_valve_interface: SafetyValveInterface = PropertyFileImplementation()

        original_dict = safety_valve_interface.convert_response_to_dict(returned_value)
        updated_dict = dict(original_dict)

        if module.params['state'] == "present":
            updated_dict.update(module.params['value'])
        elif module.params['state'] == "absent":
            for key_to_delete in module.params['value']:
                updated_dict.pop(key_to_delete, None)

        if original_dict == updated_dict:
            result['changed'] = False
            result['message'] = "No need to do anything, safety valve is up to date"
            module.exit_json(**result)
            print("No need to do anything, safety valve is up to date")
        else:
            if module.check_mode:
                result['changed'] = True
                result['message'] = "Safety valve will be updated"
                module.exit_json(**result)
    else:
        result['changed'] = False
        result['message'] = returned_value
        module.exit_json(msg="Configuration could not be read from API", **result)

    # if we got this far, then the safety valve needs to be updated
    value_to_write_back = safety_valve_interface.convert_dict_to_value_to_write_back(updated_dict)
    if module.params['requires_parent_xml_tag']:
        value_to_write_back = "<configuration>" + value_to_write_back + "</configuration>"
    if module.params['configuration_type'] == 'ROLE':
        role_config_group_display_name = module.params.get('role_display_name') or module.params['role_name']
        result['changed'], result['message'] = cluster.update_role_config_group_property(module.params['service_name'],
                                                                                         role_config_group_display_name,
                                                                                         module.params[
                                                                                             'name'],
                                                                                         value_to_write_back)
    elif module.params['configuration_type'] == 'SERVICE':
        result['changed'], result['message'] = cluster.update_service_config(module.params['service_name'],
                                                                             dict({module.params[
                                                                                  'name']: value_to_write_back}))
    if result['changed']:
        module.exit_json(**result)
    else:
        module.fail_json(msg="Exception when attempting to update configuration", **result)


def main():
    run_module()


if __name__ == '__main__':
    main()
