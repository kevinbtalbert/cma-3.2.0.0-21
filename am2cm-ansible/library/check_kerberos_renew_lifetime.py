#!/usr/bin/python
import json
import logging
import os

from ansible.module_utils.am2cm_commons.logging_utils import configure_logging
from ansible.module_utils.am2cm_commons.time_utils import convert_time_to_seconds
from ansible.module_utils.basic import AnsibleModule

configure_logging(os.path.basename(__file__).replace(".py", "-module.log"))
LOG = logging.getLogger(__name__)


def run_module():
    module_args = dict(
        renew_lifetime=dict(type='str', required=True),
        target=dict(type='str', required=True)
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

    if module.check_mode:
        module.exit_json(**result)

    try:
        renew_lifetime = convert_time_to_seconds(module.params['renew_lifetime'])
        target = convert_time_to_seconds(module.params['target'])
    except Exception as e:
        result['stderr'] = str(e)
        module.fail_json(msg=str(e), **result)

    if renew_lifetime < target:
        module.fail_json(msg="Kerberos Renew Lifetime ({0}) is less than the recommended value ({1})"
                         .format(module.params['renew_lifetime'], module.params['target']), **result)
    else:
        module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()

