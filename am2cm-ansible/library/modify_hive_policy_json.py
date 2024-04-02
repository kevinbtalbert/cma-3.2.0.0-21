#!/usr/bin/python

import json
import logging
import os
import time

import requests
from ansible.module_utils.am2cm_commons.logging_utils import configure_logging
from ansible.module_utils.basic import AnsibleModule
from requests.auth import HTTPBasicAuth

configure_logging(os.path.basename(__file__).replace(".py", "-module.log"))
LOG = logging.getLogger(__name__)


def run_module():
    module_args = dict(
        hive_policy_json=dict(type='dict', required=True),
        ranger_load_balancer_url=dict(type='str', required=True),
        ranger_policy_url_path=dict(type='str', required=False, default='/service/plugins/policies/'),
        ranger_admin_user=dict(type='str', required=False, default='admin'),
        ranger_admin_password=dict(type='str', required=True),
        verify_ssl=dict(type='bool', required=False, default=True)
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

    result['changed'] = False
    hive_policy_dict = module.params['hive_policy_json']
    for item in hive_policy_dict['policyItems']:
        if "hive" in item['users'] and "hue" not in item['users']:
            item['users'].append("hue")

    hive_policy_dict['updateTime'] = int(time.time())
    ranger_url = module.params['ranger_load_balancer_url'] + module.params['ranger_policy_url_path'] \
                 + str(hive_policy_dict['id'])

    return_val = requests.put(ranger_url, json=hive_policy_dict,
                              auth=HTTPBasicAuth(module.params['ranger_admin_user'], module.params['ranger_admin_password']),
                              verify=module.params['verify_ssl'])
    result['message'] = str(return_val.text)
    if return_val.status_code == 200:
        module.exit_json(**result)
    else:
        module.fail_json(msg="PUT request failed", **result)


def main():
    run_module()


if __name__ == '__main__':
    main()
