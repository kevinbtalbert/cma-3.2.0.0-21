import argparse
import logging
import sys

from ansible.module_utils.am2cm_commons.cdp_cluster import CDPCluster
from cm_client import ApiRoleConfigGroup
from cm_client.rest import ApiException

LOG = logging.getLogger(__name__)

_CONFIGURATION_NAME = 'process_auto_restart'


class AutoStartHandler:

    def __init__(self, hostname: str, port: int, is_https: bool, verify_ssl: bool,
                 username: str, password: str, cluster_name: str):
        self.cluster = CDPCluster(
            hostname=hostname, port=port, is_https=is_https, verify_ssl=verify_ssl,
            username=username, password=password, cluster_name=cluster_name)

    def _set_auto_start_state_for_mgmt_config_groups(self, set_to_enabled: bool):
        config_dict = {_CONFIGURATION_NAME: str(set_to_enabled).lower()}

        mgmt_role_config_groups: list[ApiRoleConfigGroup] = self.cluster.get_all_mgmt_role_config_groups().items
        for role in [r.name for r in mgmt_role_config_groups]:
            if not self.cluster.check_if_config_is_present_for_mgmt_role_config_group(
              role, _CONFIGURATION_NAME):
                LOG.debug(f"Skipping for '{role}' as it does not have '{_CONFIGURATION_NAME}'")
                continue

            LOG.debug(f"Handling configuration change for CM Management Service "
                      f"- '{role}' role config group")
            self.cluster.update_mgmt_role_config(role, config_dict)

    def _set_auto_start_state_for_service_config_groups(self, set_to_enabled: bool):
        config_to_set = {_CONFIGURATION_NAME: str(set_to_enabled).lower()}

        services = self.cluster.get_all_services()
        for service_name in [s.name for s in services]:
            for role in [r.name for r in self.cluster.get_role_config_groups_for_service(service_name).items]:
                if not self.cluster.check_if_config_is_present_for_role_config_group(
                  service_name, role, _CONFIGURATION_NAME):
                    LOG.debug(f"Skipping for '{service_name}' - '{role}' as it does not have '{_CONFIGURATION_NAME}'")
                    continue

                LOG.debug(f"Handling configuration change for service '{service_name}' - '{role}' role config group")
                self.cluster.update_role_config_group_configuration(service_name, role, config_to_set)

    def set_auto_start_state_for_all(self, set_to_enabled: bool):
        try:
            LOG.info(
                f"Setting auto start state to '{str(set_to_enabled)}' for CM Management Service role config groups")
            self._set_auto_start_state_for_mgmt_config_groups(set_to_enabled)

            LOG.info(f"Setting auto start state to '{str(set_to_enabled)}' for all services' role config groups")
            self._set_auto_start_state_for_service_config_groups(set_to_enabled)
            return True, f"'{_CONFIGURATION_NAME}' has been set to '{str(set_to_enabled)}' everywhere..."
        except ApiException as e:
            return False, str(e)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hostname", dest="hostname", action="store", required=True)
    parser.add_argument("--port", dest="port", type=int, action="store", required=True)
    parser.add_argument("--username", default="admin", dest="username", action="store")
    parser.add_argument("--password", default="admin", dest="password", action="store")
    parser.add_argument("--cluster-name", dest="cluster_name", action="store", required=True)
    parser.add_argument("--https-enabled", dest="is_https", action="store_true", required=False)
    parser.add_argument("--verify-ssl", dest="verify_ssl", action="store_true")
    parser.add_argument("--desired-state", dest="desired_state", action="store",
                        choices=['enabled', 'disabled'], required=True)

    args = parser.parse_args()

    auto_start_handler = AutoStartHandler(hostname=args.hostname, port=args.port, is_https=args.is_https,
                                          verify_ssl=args.verify_ssl,
                                          username=args.username, password=args.password,
                                          cluster_name=args.cluster_name)

    LOG.debug(f"desired_state argument set to: {args.desired_state}")
    if args.desired_state == 'enabled':
        LOG.info("Enabling auto start for all config groups...")
        auto_start_handler.set_auto_start_state_for_all(True)
    else:
        LOG.info("Disabling auto start for all config groups...")
        auto_start_handler.set_auto_start_state_for_all(False)


if __name__ == '__main__':
    sys.exit(main())
