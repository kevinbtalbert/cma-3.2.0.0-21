#!/usr/bin/python

# << insert correctly modified ansible_preamble here

import json
import logging
import os
import subprocess

from ansible.module_utils.am2cm_commons.cdp_cluster import CDPCluster
from ansible.module_utils.am2cm_commons.logging_utils import configure_logging, get_transition_log_dir
from ansible.module_utils.basic import AnsibleModule

configure_logging(os.path.basename(__file__).replace(".py", "-module.log"))
LOG = logging.getLogger(__name__)


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        ambari_configuration=dict(type='dict', required=False),
        cm_configuration=dict(type='dict', required=True),
        am2cm_configuration=dict(type='dict', required=True)
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
    LOG.info("inputs: {}".format(result['original_message']))

    cm_hostname = module.params['cm_configuration']['cloudera_manager_hostname']
    cm_port = module.params['cm_configuration']['cloudera_manager_port']
    cm_username = module.params['cm_configuration']['cloudera_manager_admin_username']
    cm_password = module.params['cm_configuration']['cloudera_manager_admin_password']
    cm_protocol = module.params['cm_configuration']['cloudera_manager_protocol']
    cm_cluster_name = module.params['cm_configuration']['cluster_name']
    is_cm_https = cm_protocol == 'https'

    # check if cm-cluster exists. If so then return error msg
    cluster = CDPCluster(
        hostname=cm_hostname, port=cm_port, is_https=is_cm_https, verify_ssl=False,
        username=cm_username, password=cm_password, cluster_name=cm_cluster_name)

    cluster_exist = cluster.is_cluster_exist()

    # if the user is working with this module in only check mode we do not
    # want to make any changes to the environment, just return the current
    # state with no modifications
    if module.check_mode:
        result['changed'] = not cluster_exist
        module.exit_json(**result)

    if cluster_exist:
        result['changed'] = False
        module.fail_json(msg='CDP cluster exists! Please delete it first!', **result)

    script_path = module.params['am2cm_configuration']['script_path']
    source_version = module.params['am2cm_configuration']['source_version']
    deployment_template_file = module.params['am2cm_configuration']['deployment_template_file']
    skip_pre_upgrade = module.params['am2cm_configuration']['skip_pre_upgrade']
    user_setting_file = module.params['am2cm_configuration']['user_setting_file']
    config_path = module.params['am2cm_configuration']['config_path']
    role_groups_enabled = module.params['am2cm_configuration']['role_groups_enabled']

    args = [f'{script_path}/am2cm.sh',
            '--source-version', source_version,
            '--deployment-template-file', deployment_template_file,
            '--silent',
            '--skip-pre-upgrade' if skip_pre_upgrade else '',
            '--cm-server', cm_hostname,
            '--cm-port', str(cm_port),
            '--cm-username', cm_username,
            '--cm-password', cm_password,
            '--cm-is-https' if is_cm_https else '',
            '--user-setting-file', user_setting_file,
            '--config-path', config_path,
            '--enable-role-groups', role_groups_enabled
            ]

    if 'target_version' in module.params['am2cm_configuration']:
        target_version = module.params['am2cm_configuration']['target_version']
        args.extend(['--target-version', target_version])

    if 'ambari_blueprint_file' in module.params['am2cm_configuration']:
        am_blueprint_file = module.params['am2cm_configuration']['ambari_blueprint_file']
        args.extend(['--blueprint-file', am_blueprint_file])

    if module.params['ambari_configuration']:
        ambari_hostname = module.params['ambari_configuration']['hostname']
        ambari_port = module.params['ambari_configuration']['port']
        ambari_username = module.params['ambari_configuration']['username']
        ambari_password = module.params['ambari_configuration']['password']
        ambari_cluster_name = module.params['ambari_configuration']['cluster_name']
        ambari_protocol = module.params['ambari_configuration']['protocol']
        args.extend([
            '--ambari-server', ambari_hostname,
            '--ambari-port', str(ambari_port),
            '--ambari-username', ambari_username,
            '--ambari-password', ambari_password,
            '--ambari-cluster-name', ambari_cluster_name,
            '--ambari-is-https' if ambari_protocol == 'https' else ''
        ])

    try:
        cm_version = cluster.get_cm_version()
        if cm_version != "0" and is_enable_hdfs_compatibility(cm_version):
            args.extend(['--enable-hdfs-compatibility'])
    except Exception as e:
        result['stderr'] = str(e)
        module.fail_json(msg='Exception when processing cm version', **result)

    os.environ["JAVA_OPTS"] = f"-DlogPath={get_transition_log_dir()}"
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    rc = process.returncode

    if rc != 0:
        result['stderr'] = stderr
        module.fail_json(msg='Exception when calling am2cm.sh', **result)

    result['stdout'] = stdout

    # use whatever logic you need to determine whether or not this module
    # made any modifications to your target
    result['changed'] = True

    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    module.exit_json(**result)


def is_enable_hdfs_compatibility(cm_version):
    # If cm version is 7.7.1 or later

    version_chars = cm_version.split(".")

    if len(version_chars) < 3:
        raise Exception("Version string format error. Version was: %s" % cm_version)

    if int(version_chars[0]) > 7:
        return True
    elif int(version_chars[0]) == 7:
        if int(version_chars[1]) > 7:
            return True
        elif int(version_chars[1]) == 7:
            if int(version_chars[2]) >= 1:
                return True
    return False


def main():
    run_module()


if __name__ == '__main__':
    main()
