#!/usr/bin/python

# << insert correctly modified ansible_preamble here

import json
import os
import subprocess

from ansible.module_utils.basic import AnsibleModule


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        am2cm_solr_client_configuration=dict(type='dict', required=True),
        solr_collection=dict(type='str', required=True),
        solr_action=dict(type='str', required=True),
        log_file_path=dict(type='str', required=True),
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
    result['original_message'] = json.dumps(module.params)  # concatenate the params here, if there were any...

    script_path = module.params['am2cm_solr_client_configuration']['script_path']
    zk_connect = module.params['am2cm_solr_client_configuration']['zookeeper_connect_string']
    backup_dir = module.params['am2cm_solr_client_configuration']['backup_dir']
    is_kerberized_cluster = module.params['am2cm_solr_client_configuration']['is_kerberized_cluster']

    collection = module.params['solr_collection']
    solr_action = module.params['solr_action']
    log_file_path = module.params['log_file_path']

    args = ['{0}/am2cm-solr-client.sh'.format(script_path),
            '--zookeeper-connect-string', zk_connect,
            '--collection', collection
            ]
    if is_kerberized_cluster:
        jaas_file = module.params['am2cm_solr_client_configuration']['jaas_file']
        args.extend(['--jaas-file', jaas_file])

    if 'trust_store_location' in module.params['am2cm_solr_client_configuration']:
        trust_store_location = module.params['am2cm_solr_client_configuration']['trust_store_location']
        trust_store_type = module.params['am2cm_solr_client_configuration']['trust_store_type']
        trust_store_password = module.params['am2cm_solr_client_configuration']['trust_store_password']
        args.extend(['--trust-store-type', trust_store_type,
                     '--trust-store-location', trust_store_location,
                     '--trust-store-password', trust_store_password])

    if 'key_store_location' in module.params['am2cm_solr_client_configuration']:
        key_store_location = module.params['am2cm_solr_client_configuration']['key_store_location']
        key_store_type = module.params['am2cm_solr_client_configuration']['key_store_type']
        key_store_password = module.params['am2cm_solr_client_configuration']['key_store_password']
        args.extend(['--key-store-type', key_store_type,
                     '--key-store-location', key_store_location,
                     '--key-store-password', key_store_password])

    if solr_action == 'backup':
        args.extend(['--dump-documents', '--output', backup_dir])
    elif solr_action == 'restore':
        args.extend(['--upload-documents', '--input', backup_dir])

    try:
        os.environ['AM2CM_SOLR_CLIENT_OPTS'] = '-DlogFilePath=' + log_file_path
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        rc = process.returncode

        result['stdout'] = stdout

        if rc != 0:
            result['stderr'] = stderr
            module.fail_json(msg='Exception when calling am2cm-solr-client.sh', **result)

        # use whatever logic you need to determine whether or not this module
        # made any modifications to your target
        result['changed'] = True

        # in the event of a successful module execution, you will want to
        # simple AnsibleModule.exit_json(), passing the key/value results
        module.exit_json(**result)
    except Exception as e:
        result['stderr'] = e
        result['changed'] = False
        module.fail_json(msg='Exception when calling am2cm-solr-client.sh', **result)


def main():
    run_module()


if __name__ == '__main__':
    main()
