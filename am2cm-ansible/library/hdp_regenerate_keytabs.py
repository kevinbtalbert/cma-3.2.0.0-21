#!/usr/bin/python

# << insert correctly modified ansible_preamble here

import json
import logging
import os

from ansible.module_utils.am2cm_commons.hdp_cluster import HDPCluster
from ansible.module_utils.am2cm_commons.logging_utils import configure_logging
from ansible.module_utils.basic import AnsibleModule

configure_logging(os.path.basename(__file__).replace(".py", "-module.log"))
LOG = logging.getLogger(__name__)


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        ambari_configuration=dict(type='dict', required=True),
        kdc_admin_principal=dict(typ='str', required=True),
        kdc_admin_password=dict(typ='str', required=True),
        kdc_persist_type=dict(typ='str', default="temporary")
    )

    # seed the result dict in the object
    # we primarily care about changed and state
    # change is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = dict(
        changed=False,
        original_message='',
        message=''
    )

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    # if the user is working with this module in only check mode we do not
    # want to make any changes to the environment, just return the current
    # state with no modifications
    if module.check_mode:
        result['changed'] = True
        module.exit_json(**result)

    result['original_message'] = json.dumps(module.params)  # concatenate the params here, if there were any...
    LOG.info("inputs: {}".format(result['original_message']))

    hostname = module.params['ambari_configuration']['hostname']
    port = module.params['ambari_configuration']['port']
    username = module.params['ambari_configuration']['username']
    password = module.params['ambari_configuration']['password']
    cluster_name = module.params['ambari_configuration']['cluster_name']
    protocol = module.params['ambari_configuration']['protocol']

    cluster = HDPCluster(
        hostname=hostname, port=port, protocol=protocol, verify_ssl=False,
        username=username, password=password, cluster_name=cluster_name)

    try:
        if not cluster.has_kdc_admin_credential():
            cluster.set_kdc_admin_credential(admin_principal=module.params['kdc_admin_principal'],
                                             admin_pwd=module.params['kdc_admin_password'],
                                             persist_type=module.params['kdc_persist_type'])

        res = cluster.regenerate_keytabs()
        if not res:
            result['changed'] = False
            module.fail_json(msg="An error occurred while regenerating the keytabs", **result)

        result['changed'] = True

        # in the event of a successful module execution, you will want to
        # simple AnsibleModule.exit_json(), passing the key/value results
        module.exit_json(**result)
    except Exception as e:
        result['stderr'] = e
        result['changed'] = False
        module.fail_json(msg="An error occurred while regenerating the keytabs", **result)


def main():
    run_module()


if __name__ == '__main__':
    main()
