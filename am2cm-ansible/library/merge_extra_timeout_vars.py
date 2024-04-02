#!/usr/bin/python
import json
import logging
import os

from ansible.module_utils.am2cm_commons.logging_utils import configure_logging
from ansible.module_utils.basic import AnsibleModule

configure_logging(os.path.basename(__file__).replace(".py", "-module.log"))
LOG = logging.getLogger(__name__)


def run_module():
    module_args = dict(
        original_timeouts=dict(type='dict', required=True),
        extra_vars_timeouts=dict(type='list', required=True),
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
    # ####################################################################
    result['changed'] = False

    original_timeouts = module.params['original_timeouts']
    extra_timeouts = module.params['extra_vars_timeouts']

    for service_record in extra_timeouts:
        # a service_record in the extra vars is always in the same order:
        # service_record[0] = service name e.g. hdfs/ranger/oozie
        # service_record[1] = command type/name e.g. restart_service/run_role_command/UpgradeHdfsMetadata
        # service_record[2] = timeout value in seconds
        if service_record[0] in original_timeouts:
            original_timeouts[service_record[0]].update(
                {service_record[1]: service_record[2]})
        else:
            original_timeouts[service_record[0]] = {service_record[1]: service_record[2]}

    result['message'] = original_timeouts
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
