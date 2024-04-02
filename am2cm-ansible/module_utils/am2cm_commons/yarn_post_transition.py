import argparse
import logging
import sys

from ansible.module_utils.am2cm_commons.cdp_cluster import CDPCluster

_SERVICE_NAME = 'yarn'
_CREATE_JOB_HISTORY_DIR_SERVICE_COMMAND = 'CreateHistoryDir'
_INSTALL_YARN_MAPREDUCE_FRAMEWORK_JARS_COMMAND = 'YarnInstallMrFrameworkJars'
_YARN_RESET_ZNODE_ACLS_COMMAND = 'YarnZkAclResetCommand'

LOG = logging.getLogger(__name__)


class YarnPostTransition:

    def __init__(self, hostname: str, port: int, is_https: bool, verify_ssl: bool,
                 username: str, password: str, cluster_name: str):
        self.cluster = CDPCluster(
            hostname=hostname, port=port, is_https=is_https, verify_ssl=verify_ssl,
            username=username, password=password, cluster_name=cluster_name)

    def do_start_job_history_chapter(self):
        """
        Performs job history startup based on documentation.
        https://docs.cloudera.com/cdp-private-cloud-upgrade/latest/upgrade-hdp/topics/amb-job-yarn.html
        """

        return self.cluster.run_service_command(_SERVICE_NAME, _CREATE_JOB_HISTORY_DIR_SERVICE_COMMAND)

    def do_install_mapreduce_framework_jars_chapter(self):
        """
        Performs jar deployment action based on documentation.
        https://docs.cloudera.com/cdp-private-cloud-upgrade/latest/upgrade-hdp/topics/amb-yarn-restart.html
        """

        return self.cluster.run_service_command(_SERVICE_NAME, _INSTALL_YARN_MAPREDUCE_FRAMEWORK_JARS_COMMAND)

    def do_yarn_nodemanager_chapter(self):
        """
        Perform reset of configuration 'yarn.nodemanager.linux-container-executor.group' to default, when needed.
        Based on documentation.
        https://docs.cloudera.com/cdp-private-cloud-upgrade/latest/upgrade-hdp/topics/amb-yarn-nodemanager.html
        """

        cm_config_key = 'container_executor_group'
        role_config_group_display_name = 'yarn-NODEMANAGER'
        new_cm_config_value = 'yarn'
        success, current_value = self.cluster.query_configuration_value(_SERVICE_NAME, cm_config_key, 'ROLE',
                                                                        role_config_group_display_name)
        if success and current_value == 'hadoop':
            return self.cluster.update_role_config_group_property(_SERVICE_NAME,
                                                                  role_config_group_display_name,
                                                                  cm_config_key,
                                                                  new_cm_config_value)
        else:
            return True, "Nothing to do..."

    def do_reset_znode_acls_chapter(self):
        """
        Performs the Reset ZNode ACLs chapter based on the documentation.
        https://docs.cloudera.com/cdp-private-cloud-upgrade/latest/upgrade-hdp/topics/amb-yarn-znode_acls.html
        """
        return self.cluster.run_service_command(_SERVICE_NAME, _YARN_RESET_ZNODE_ACLS_COMMAND)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hostname", dest="hostname", action="store", required=True)
    parser.add_argument("--port", dest="port", type=int, action="store", required=True)
    parser.add_argument("--username", default="admin", dest="username", action="store")
    parser.add_argument("--password", default="admin", dest="password", action="store")
    parser.add_argument("--cluster-name", dest="cluster_name", action="store", required=True)
    parser.add_argument("--https-enabled", dest="is_https", action="store_true", required=False)
    parser.add_argument("--verify-ssl", dest="verify_ssl", action="store_true")
    parser.add_argument("--start-job-history", dest="start_job_history", action="store_true")
    parser.add_argument("--install-mapreduce-framework-jars",
                        dest="install_mapreduce_framework_jars", action="store_true")
    parser.add_argument("--yarn-nodemanager", dest="yarn_nodemanager", action="store_true")
    parser.add_argument("--reset-znode-acls", dest="reset_znode_acls", action="store_true")

    args = parser.parse_args()

    all_chapters = not (args.start_job_history or args.install_mapreduce_framework_jars or args.yarn_nodemanager or
                        args.reset_znode_acls)

    yarn_post_transition = YarnPostTransition(args.hostname, args.port, args.is_https, args.verify_ssl,
                                              args.username, args.password, args.cluster_name)

    if all_chapters or args.start_job_history:
        yarn_post_transition.do_start_job_history_chapter()

    if all_chapters or args.install_mapreduce_framework_jars:
        yarn_post_transition.do_install_mapreduce_framework_jars_chapter()

    if all_chapters or args.yarn_nodemanager:
        yarn_post_transition.do_yarn_nodemanager_chapter()

    if all_chapters or args.reset_znode_acls:
        yarn_post_transition.do_reset_znode_acls_chapter()


if __name__ == '__main__':
    sys.exit(main())
