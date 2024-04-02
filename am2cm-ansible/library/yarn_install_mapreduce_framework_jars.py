#!/usr/bin/python

# << insert correctly modified ansible_preamble here
import json
import logging
import os

from ansible.module_utils.am2cm_commons.logging_utils import configure_logging
from ansible.module_utils.am2cm_commons.yarn_post_transition import YarnPostTransition
from ansible.module_utils.basic import AnsibleModule

configure_logging(os.path.basename(__file__).replace(".py", "-module.log"))
LOG = logging.getLogger(__name__)


def run_module():
    module_args = dict(
        cm_configuration=dict(type='dict', required=True)
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
    yarn_post_transition = YarnPostTransition(
        hostname=module.params['cm_configuration']['cloudera_manager_hostname'],
        port=module.params['cm_configuration']['cloudera_manager_port'],
        is_https=(module.params['cm_configuration']['cloudera_manager_protocol'] == 'https'),
        verify_ssl=False,
        username=module.params['cm_configuration']['cloudera_manager_admin_username'],
        password=module.params['cm_configuration']['cloudera_manager_admin_password'],
        cluster_name=module.params['cm_configuration']['cluster_name']
    )

    # NOTE: This isn't working as a 'true' ansible module yet
    # TODO check if step is already ready (i.e. is there anything that needs to be done)
    # TODO handle module.check_mode

    result['changed'], result['message'] = yarn_post_transition.do_install_mapreduce_framework_jars_chapter()

    if result['changed']:
        module.exit_json(**result)
    else:
        module.fail_json(msg='Exception doing YARN installing MapReduce Framework JARs', **result)


def main():
    run_module()


if __name__ == '__main__':
    main()
