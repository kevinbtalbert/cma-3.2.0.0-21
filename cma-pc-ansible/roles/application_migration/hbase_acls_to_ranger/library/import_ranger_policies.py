import os
import logging
import json
import requests
from requests.auth import HTTPBasicAuth

from ansible.module_utils.am2cm_commons.logging_utils import configure_logging
from ansible.module_utils.basic import AnsibleModule

configure_logging(os.path.basename(__file__).replace(".py", "-module.log"))
LOG = logging.getLogger(__name__)


def import_ranger_policies(ranger_url, jwt_data_lake_knox_token, ranger_policy_json_file):
    with open(ranger_policy_json_file) as fp:
        data = fp.read()

    files = {
        'file': ('policies.json', data, 'application/json'),
        'servicesMapJson': ('blob', '{"cm_hbase":"cm_hbase"}', 'application/json')
    }

    response = requests.post(
        '{}/service/plugins/policies/importPoliciesFromFile'.format(ranger_url),
        auth=HTTPBasicAuth('Token', jwt_data_lake_knox_token),
        files=files,
        verify=False,
    )

    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        raise requests.HTTPError('{} - Response Body: {}'.format(e, response.text))



def run_module():
    module_args = dict(
        ranger_admin_url=dict(type='str', required=True),
        jwt_data_lake_knox_token=dict(type='str', required=True),
        ranger_policy_json_file=dict(type='str', required=True),
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
    result['original_message'] = json.dumps(module.params)  # concatenate the params here, if there were any...
    LOG.info("inputs: {}".format(result['original_message']))

    ranger_admin_url = module.params['ranger_admin_url']
    jwt_data_lake_knox_token = module.params['jwt_data_lake_knox_token']
    ranger_policy_json_file = module.params['ranger_policy_json_file']

    if not os.path.exists(ranger_policy_json_file):
        module.fail_json(msg="input_hbase_acls_file {} does not exist".format(ranger_policy_json_file))

    import_ranger_policies(ranger_admin_url, jwt_data_lake_knox_token, ranger_policy_json_file)

    result['changed'] = True
    result["message"] = "Results saved to {}".format(ranger_policy_json_file)
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
