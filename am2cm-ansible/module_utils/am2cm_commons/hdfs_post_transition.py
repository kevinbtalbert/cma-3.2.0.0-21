import argparse
import logging
import sys

from ansible.module_utils.am2cm_commons.cdp_cluster import CDPCluster
from cm_client.rest import ApiException

_SERVICE_NAME = 'hdfs'
_FC_INITIALIZE_ZNODE_ROLE_COMMAND_NAME = 'FailoverControllerInitializeZNodeCommand'

LOG = logging.getLogger(__name__)

_DEFAULT_NET_TOPOLOGY_SCRIPT_FILE_NAME = "/etc/hadoop/conf/topology_script.py"


class HdfsPostTransition:

    def __init__(self, hostname: str, port: int, is_https: bool, verify_ssl: bool,
                 username: str, password: str, cluster_name: str, hadoop_rpc_protection: str,
                 net_topology_script_file_name: str, dfs_ha_proxy_provider: str):
        self.cluster = CDPCluster(
            hostname=hostname, port=port, is_https=is_https, verify_ssl=verify_ssl,
            username=username, password=password, cluster_name=cluster_name)
        self.hadoop_rpc_protection = hadoop_rpc_protection
        self.net_topology_script_file_name = net_topology_script_file_name
        self.dfs_ha_proxy_provider = dfs_ha_proxy_provider

    def do_tls_ssl_chapter(self):
        """
        Performs the TLS/SSL chapter based on the documentation
        https://docs.cloudera.com/cdp-private-cloud-upgrade/latest/upgrade-hdp/topics/amb-enable-tls-ssl.html
        """
        configs_to_update = {}
        try:
            if not self.cluster.is_tls_enabled():
                configs_to_update.update(
                    {'dfs_data_transfer_protection': 'authentication', 'hadoop_rpc_protection': 'authentication'})
            else:
                configs_to_update.update(
                    {'hadoop_rpc_protection': self._convert_rpc_protection_value()})
            if len(configs_to_update) > 0:
                return self.cluster.update_service_config(_SERVICE_NAME, configs_to_update)
        except ApiException as e:
            return False, str(e)

    def do_hdfs_ha_chapter(self):
        """
        Performs the HDFS HA chapter based on the documentation
        https://docs.cloudera.com/cdp-private-cloud-upgrade/latest/upgrade-hdp/topics/amb-ha.html
        """
        try:
            if self._is_hdfs_ha_enabled():
                # query hdfs roles, so we can figure out what is the exact name of the first FAILOVERCONTROLLER
                hdfs_roles = self.cluster.read_roles("hdfs")
                # only the first failovercontroller needed, but the input for run_role_command should be a list
                first_failover_controller_role_name = \
                    [next(role.name for role in hdfs_roles.items if "FAILOVERCONTROLLER" in role.name)]
                return self.cluster.run_role_command(
                    _FC_INITIALIZE_ZNODE_ROLE_COMMAND_NAME, _SERVICE_NAME,
                    first_failover_controller_role_name)
            else:
                return True, "HA isn't enabled, so no HA configuration needed"
        except ApiException as e:
            return False, str(e)

    def do_handling_of_missing_blueprint_configs(self):
        """
        Handles configuration parameters, that are not taken care by the tool itself during the migration, so
        it has to be handled post-migration.
        https://docs.cloudera.com/cdp-private-cloud-upgrade/latest/upgrade-hdp/topics/amb-cluster-topology-2.html
        https://docs.cloudera.com/cdp-private-cloud-upgrade/latest/upgrade-hdp/topics/amb-other-review-configurations-for-hdfs.html
        """
        topology_script_value_has_to_be_set = \
            self.net_topology_script_file_name \
            and self.net_topology_script_file_name != _DEFAULT_NET_TOPOLOGY_SCRIPT_FILE_NAME

        if not topology_script_value_has_to_be_set and not self.dfs_ha_proxy_provider:
            return True, "Nothing to do"

        if topology_script_value_has_to_be_set:
            current_success, current_message = self.cluster.update_role_config_group_property(_SERVICE_NAME,
                                                                                              "hdfs-NAMENODE",
                                                                                              "topology_script_file_name",
                                                                                              self.net_topology_script_file_name)
            if not current_success:
                return current_success, current_message

        if self.dfs_ha_proxy_provider:
            topology_config = {'dfs_ha_proxy_provider': self.dfs_ha_proxy_provider}
            current_success, current_message = self.cluster.update_service_config(_SERVICE_NAME, topology_config)
            if not current_success:
                return current_success, current_message
        return True, "Handling of missing blueprint configs chapter successful"

    def do_lzocodec_removal(self):
        """
        Handles the removal of the com.hadoop.compression.lzo.LzoCodec from io_compression_codecs configuration
        """
        try:
            io_compression_codecs_values = self.cluster.get_current_config_value(_SERVICE_NAME, "io_compression_codecs")
            LOG.debug(f"io_compression_codecs_values: {io_compression_codecs_values}")
            config_value_to_remove = 'com.hadoop.compression.lzo.LzoCodec'
            if config_value_to_remove in io_compression_codecs_values:
                io_compression_codecs_values = io_compression_codecs_values.replace(config_value_to_remove, "")
                io_compression_codecs_values = io_compression_codecs_values.replace(',,', ',')
                configs_to_update = {'io_compression_codecs': io_compression_codecs_values}
                return self.cluster.update_service_config(_SERVICE_NAME, configs_to_update)
            return True, f"Nothing to do because '{config_value_to_remove}' cannot be found in config 'io_compression_codecs'"
        except ApiException as e:
            return False, str(e)
        except StopIteration:
            return False, "Couldn't find configuration value in service configurations"

    def _is_hdfs_ha_enabled(self):
        roles = self.cluster.read_roles(_SERVICE_NAME)
        nn_count = 0
        for role in roles.items:
            if role.type == "NAMENODE":
                nn_count += 1
            if nn_count > 1:
                return True
        return False

    def _convert_rpc_protection_value(self):
        """
        As in Ambari, rpc protection can have multiple values, but Cloudera Manager does not allow this, this method,
        based on the original value, figures out the most restrictive setting, and returns with that.
        """
        if ',' in self.hadoop_rpc_protection:
            if 'privacy' in self.hadoop_rpc_protection:
                return 'privacy'
            if 'integrity' in self.hadoop_rpc_protection:
                return 'integrity'

        return self.hadoop_rpc_protection


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hostname", dest="hostname", action="store", required=True)
    parser.add_argument("--port", dest="port", type=int, action="store", required=True)
    parser.add_argument("--username", default="admin", dest="username", action="store")
    parser.add_argument("--password", default="admin", dest="password", action="store")
    parser.add_argument("--cluster-name", dest="cluster_name", action="store", required=True)
    parser.add_argument("--https-enabled", dest="is_https", action="store_true", required=False)
    parser.add_argument("--verify-ssl", dest="verify_ssl", action="store_true")
    parser.add_argument("--hadoop-rpc-protection-value", dest="hadoop_rpc_protection",
                        default="", action="store", required=False)
    parser.add_argument("--net-topology-script-file-name", dest="net_topology_script_file_name",
                        action="store", required=False)
    parser.add_argument("--dfs-ha-proxy-provider",
                        dest="dfs_ha_proxy_provider", action="store", required=False)
    parser.add_argument("--do-tls-ssl-chapter",
                        dest="do_tls_ssl_chapter", action="store", required=False)
    parser.add_argument("--do-hdfs-ha-chapter",
                        dest="do_hdfs_ha_chapter", action="store", required=False)
    parser.add_argument("--do-handling-of-missing-blueprint-configs",
                        dest="do_handling_of_missing_blueprint_configs", action="store", required=False)
    parser.add_argument("--do-lzocodec-removal",
                        dest="do_lzocodec_removal", action="store", required=False)

    args = parser.parse_args()

    all_chapters = not (args.do_tls_ssl_chapter or args.do_hdfs_ha_chapter or
                        args.do_handling_of_missing_blueprint_configs or args.do_lzocodec_removal)

    hdfs_post_transition = HdfsPostTransition(hostname=args.hostname, port=args.port, is_https=args.is_https,
                                              verify_ssl=args.verify_ssl,
                                              username=args.username, password=args.password,
                                              cluster_name=args.cluster_name,
                                              hadoop_rpc_protection=args.hadoop_rpc_protection,
                                              net_topology_script_file_name=args.net_topology_script_file_name,
                                              dfs_ha_proxy_provider=
                                              args.dfs_ha_proxy_provider)

    if all_chapters or args.do_tls_ssl_chapter:
        hdfs_post_transition.do_tls_ssl_chapter()

    if all_chapters or args.do_hdfs_ha_chapter:
        hdfs_post_transition.do_hdfs_ha_chapter()

    if all_chapters or args.do_handling_of_missing_blueprint_configs:
        hdfs_post_transition.do_handling_of_missing_blueprint_configs()

    if all_chapters or args.do_lzocodec_removal:
        hdfs_post_transition.do_lzocodec_removal()

    # TODO missing, if target is not 7.1.7
    #  https://docs.cloudera.com/documentation/enterprise/6/6.3/topics/admin_hdfs_balancer.html

    # TODO: handle "cloud service related configurations" as per doc, if there is any


if __name__ == '__main__':
    sys.exit(main())
