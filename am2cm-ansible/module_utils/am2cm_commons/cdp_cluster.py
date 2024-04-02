import json
import logging
import time
import re
from enum import Enum
from datetime import datetime
from functools import partial
from typing import Union
from importlib.metadata import version  # needs python>=3.8

import cm_client
import requests
import urllib3
from cm_client import ApiService, ApiRoleConfigGroupList, ApiServiceConfig, \
    ApiCommand, ApiParcelList, ApiParcel, ApiConfigList, \
    ApiConfig, ApiBulkCommandList, ApiRoleList, ApiServiceRef, ApiHostList, ApiHost, ApiHealthSummary
from cm_client.rest import ApiException

PARCEL_REPO_URLS = 'REMOTE_PARCEL_REPO_URLS'

urllib3.disable_warnings()

LOG = logging.getLogger(__name__)


class CDPCluster:
    """
    Class to represent a CDP Cluster.
    """

    DEFAULT_SERVICE_COMMAND_TIMEOUT_SECONDS = 900
    DEFAULT_ROLE_COMMAND_TIMEOUT_SECONDS = 900
    DEFAULT_RESTART_SERVICE_TIMEOUT_SECONDS = 900

    def __init__(self, hostname: str, port: int, is_https: bool, verify_ssl: bool,
                 username: str, password: str, cluster_name: str, api_postfix: str = 'api'):
        self.hostname = hostname
        self.port = port
        self.protocol = 'https' if is_https else 'http'
        self.is_https = is_https
        self.verify_ssl = verify_ssl
        self.username = username
        self.password = password
        self.cluster_name = cluster_name
        self.api_postfix = api_postfix or 'api'

        self._set_configuration()

    def _set_configuration(self):
        LOG.debug("Setting Configuration object")
        configuration = cm_client.Configuration()
        input_api_version = self._determine_api_version()[1:]  # e.x. v45 => 45
        max_supported_api_version = re.search(r"(\d+)\.(\d+)\.(\d+)", version('cm_client')).group(1)
        LOG.info(f"Input API version: {input_api_version}")
        LOG.info(f"Max supported API version by cm_client: {max_supported_api_version}")

        api_version = 'v'+str(min(int(max_supported_api_version), int(input_api_version)))
        LOG.info(f"Selected API version: {api_version}")

        configuration.host = "{protocol}://{hostname}:{port}/{api_postfix}/{api_version}".format(protocol=self.protocol,
                                                                                       hostname=self.hostname,
                                                                                       port=self.port,
                                                                                       api_postfix=self.api_postfix,
                                                                                       api_version=api_version)
        configuration.username = self.username
        configuration.password = self.password
        configuration.verify_ssl = self.verify_ssl

    def _determine_api_version(self):
        response = requests.get(url='{protocol}://{hostname}:{port}/{api_postfix}/version'.format(
            protocol=self.protocol, hostname=self.hostname, port=self.port, api_postfix=self.api_postfix),
            headers={'Accept': 'text/plain'},
            auth=(self.username, self.password),
            verify=self.verify_ssl)
        if not response.ok:
            LOG.error("Determining API version failed...")
            response.raise_for_status()

        LOG.info("API version: %s" % response.text.strip())
        return response.text.strip()

    def get_cm_version(self, fallback="0"):
        LOG.info("Trying to get the CM version, fallback value: {}".format(fallback))
        api_instance = cm_client.ClouderaManagerResourceApi(cm_client.ApiClient())

        try:
            api_response = api_instance.get_version()
            LOG.debug("Response: {}".format(api_response))
            return api_response.version
        except ApiException as e:
            LOG.error("Exception when calling ClouderaManagerResourceApi->get_version: %s\n" % e)
            return fallback

    def run_service_command(self, service_name: str, command_name: str,
                            timeout_sec: int = DEFAULT_SERVICE_COMMAND_TIMEOUT_SECONDS):
        LOG.info("Running service command '{command}' for service '{service}'...".format(command=command_name,
                                                                                         service=service_name))
        api_instance = cm_client.ServicesResourceApi(cm_client.ApiClient())
        try:
            api_response: ApiCommand = api_instance.service_command_by_name(self.cluster_name, command_name,
                                                                            service_name)
            LOG.debug("Response: %s" % api_response)
            return self.wait_for_command(api_response, timeout_sec=timeout_sec)
        except ApiException as e:
            LOG.error("Exception when calling ServicesResourceApi->service_command_by_name: %s\n" % e)
            return False, str(e)

    def get_parcel_info(self, parcel_product_name: str, parcel_version: str) -> ApiParcel:
        LOG.debug(f"Trying to get details of '{parcel_product_name}'")
        api_instance = cm_client.ParcelsResourceApi(cm_client.ApiClient())

        try:
            api_response: ApiParcelList = api_instance.read_parcels(self.cluster_name, view='full')
            for parcel in api_response.items:
                if parcel.product == parcel_product_name and parcel.version == parcel_version:
                    return parcel

            return None
        except ApiException as e:
            LOG.error("Exception when calling ParcelsResourceApi->read_parcels: %s\n" % e)
            raise e

    def set_parcel_repo(self, parcel_repo: str):
        LOG.debug(f"Trying to add '{parcel_repo}' parcel repo to CM")
        api_instance = cm_client.ClouderaManagerResourceApi(cm_client.ApiClient())

        try:
            cm_configs = api_instance.get_config(view='full')
            old_parcel_repo_urls = None
            for cm_config in cm_configs.items:
                if cm_config.name == PARCEL_REPO_URLS:
                    old_parcel_repo_urls = cm_config.value
                    break

            # check if the repo has already been added
            for repo in old_parcel_repo_urls.split(','):
                if repo == parcel_repo:
                    LOG.info(f"'{parcel_repo}' has already been added to CM")
                    return

            # value is a comma-separated list
            new_parcel_repo_urls = old_parcel_repo_urls + ", " + parcel_repo
            new_cm_config = cm_client.ApiConfig(name=PARCEL_REPO_URLS, value=new_parcel_repo_urls)
            new_cm_configs = cm_client.ApiConfigList([new_cm_config])
            updated_cm_configs = api_instance.update_config(body=new_cm_configs)

            # wait to make sure parcels are refreshed
            time.sleep(10)

        except ApiException as e:
            LOG.error(f"Exception when adding {parcel_repo} parcel repo to CM: {e}\n")
            raise e

    def download_parcel(self, parcel_info: ApiParcel, timeout_sec: int = 5000):
        api_instance = cm_client.ParcelResourceApi(cm_client.ApiClient())

        current_info = self.get_parcel_info(parcel_info.product, parcel_info.version)
        if current_info.stage != 'AVAILABLE_REMOTELY':
            LOG.info("Parcel is already downloaded, skipping...")
            return True, current_info

        try:
            api_instance.start_download_command(self.cluster_name, parcel_info.product, parcel_info.version)

            success = False
            end_time = time.time() + timeout_sec
            LOG.info(f"Starting download of '{parcel_info.product}' polling...")
            while time.time() < end_time and not success:
                current_stage = self.get_parcel_info(parcel_info.product, parcel_info.version).stage
                LOG.debug(f"Current stage of '{parcel_info.product}': '{current_stage}'")
                if current_stage == 'DOWNLOADED':
                    LOG.info("Download successful...")
                    success = True
                else:
                    time.sleep(30)

            return success, self.get_parcel_info(parcel_info.product, parcel_info.version)
        except ApiException as e:
            LOG.error("Exception when calling ParcelResourceApi->start_download_command: %s\n" % e)
            raise e

    def distribute_parcel(self, parcel_info: ApiParcel, timeout_sec: int = 5000):
        api_instance = cm_client.ParcelResourceApi(cm_client.ApiClient())

        current_info = self.get_parcel_info(parcel_info.product, parcel_info.version)
        if current_info.stage != 'DOWNLOADED':
            LOG.info("Parcel is already distributed, skipping...")
            return True, current_info

        try:
            result: ApiCommand = api_instance.start_distribution_command(
                self.cluster_name, parcel_info.product, parcel_info.version)

            LOG.info(result)

            success = False
            end_time = time.time() + timeout_sec
            LOG.info(f"Starting distribution of '{parcel_info.product}' polling...")
            while time.time() < end_time and not success:
                current_stage = self.get_parcel_info(parcel_info.product, parcel_info.version).stage
                LOG.info(self.get_parcel_info(parcel_info.product, parcel_info.version))
                LOG.info(f"Current stage of '{parcel_info.product}': '{current_stage}'")
                if current_stage == 'DISTRIBUTED':
                    LOG.info("Distribution successful...")
                    success = True
                else:
                    time.sleep(30)

            return success, self.get_parcel_info(parcel_info.product, parcel_info.version)
        except ApiException as e:
            LOG.error("Exception when calling ParcelResourceApi->start_distribution_command: %s\n" % e)
            raise e

    def activate_parcel(self, parcel_info: ApiParcel, timeout_sec: int = 1000):
        api_instance = cm_client.ParcelResourceApi(cm_client.ApiClient())

        current_info = self.get_parcel_info(parcel_info.product, parcel_info.version)
        if current_info.stage != 'DISTRIBUTED':
            LOG.info("Parcel is already activated, skipping...")
            return True, current_info

        try:
            api_instance.activate_command(self.cluster_name, parcel_info.product, parcel_info.version)

            success = False
            end_time = time.time() + timeout_sec
            LOG.info(f"Activating parcel '{parcel_info.product}'.")
            while time.time() < end_time and not success:
                current_stage = self.get_parcel_info(parcel_info.product, parcel_info.version).stage
                LOG.info(f"Current stage of '{parcel_info.product}': '{current_stage}'")
                if current_stage == 'ACTIVATED':
                    LOG.info("Activation successful...")
                    success = True
                else:
                    time.sleep(10)

            return success, self.get_parcel_info(parcel_info.product, parcel_info.version)
        except ApiException as e:
            LOG.error("Exception when calling ParcelResourceApi->activate_parcel: %s\n" % e)
            raise e

    def undistribute_parcel(self, parcel_info: ApiParcel, timeout_sec: int = 5000):
        api_instance = cm_client.ParcelResourceApi(cm_client.ApiClient())

        current_info = self.get_parcel_info(parcel_info.product, parcel_info.version)
        if current_info.stage != 'DISTRIBUTED':
            LOG.info("Parcel is not in distributed state, skipping...")
            return True, current_info

        try:
            api_instance.start_removal_of_distribution_command(
                self.cluster_name, parcel_info.product, parcel_info.version)

            success = False
            end_time = time.time() + timeout_sec
            LOG.info(f"Starting undistribution of '{parcel_info.product}'. Polling...")
            while time.time() < end_time and not success:
                current_stage = self.get_parcel_info(parcel_info.product, parcel_info.version).stage
                LOG.info(self.get_parcel_info(parcel_info.product, parcel_info.version))
                LOG.info(f"Current stage of '{parcel_info.product}': '{current_stage}'")
                if current_stage == 'DOWNLOADED':
                    LOG.info("Undistribution successful...")
                    success = True
                else:
                    time.sleep(15)

            return success, self.get_parcel_info(parcel_info.product, parcel_info.version)
        except ApiException as e:
            LOG.error("Exception when calling ParcelResourceApi->start_removal_of_distribution_command: %s\n" % e)
            raise e

    def deactivate_parcel(self, parcel_info: ApiParcel, timeout_sec: int = 5000):
        api_instance = cm_client.ParcelResourceApi(cm_client.ApiClient())

        current_info = self.get_parcel_info(parcel_info.product, parcel_info.version)
        if current_info.stage != 'ACTIVATED':
            LOG.info("Parcel is not in activated state, skipping...")
            return True, current_info

        try:
            api_instance.deactivate_command(self.cluster_name, parcel_info.product, parcel_info.version)

            success = False
            end_time = time.time() + timeout_sec
            LOG.info(f"Deactivating parcel '{parcel_info.product}'.")
            while time.time() < end_time and not success:
                current_stage = self.get_parcel_info(parcel_info.product, parcel_info.version).stage
                LOG.info(f"Current stage of '{parcel_info.product}': '{current_stage}'")
                if current_stage == 'DISTRIBUTED':
                    LOG.info("Deactivation successful...")
                    success = True
                else:
                    time.sleep(10)

            return success, self.get_parcel_info(parcel_info.product, parcel_info.version)
        except ApiException as e:
            LOG.error("Exception when calling ParcelResourceApi->deactivate_command: %s\n" % e)
            raise e

    def deploy_service_client_configuration(self, service_name: str):
        LOG.info("Deploying service client configuration for service '%s'" % service_name)
        api_instance = cm_client.ServicesResourceApi(cm_client.ApiClient())
        try:
            api_response: ApiCommand = api_instance.deploy_client_config_command(self.cluster_name, service_name)
            LOG.debug("Response %s" % api_response)
            return True, api_response.result_message
        except ApiException as e:
            LOG.error("Exception when calling ServicesResourceApi->deploy_client_config_command: %s\n" % e)
            return False, str(e)

    def start_service(self, service_name: str, timeout_sec: int = 360):
        LOG.info("Starting service '%s'" % service_name)
        api_instance = cm_client.ServicesResourceApi(cm_client.ApiClient())
        try:
            api_response = api_instance.start_command(self.cluster_name, service_name)
            LOG.debug("Response %s" % api_response)
            return self.wait_for_command(api_response, timeout_sec)
        except ApiException as e:
            LOG.error("Exception when calling ServicesResourceApi->start_command: %s\n" % e)
            raise e

    def stop_service(self, service_name: str, timeout_sec: int = 360):
        LOG.info("Stopping service '%s'" % service_name)
        api_instance = cm_client.ServicesResourceApi(cm_client.ApiClient())
        try:
            api_response = api_instance.stop_command(self.cluster_name, service_name)
            LOG.debug("Response %s" % api_response)
            return self.wait_for_command(api_response, timeout_sec)
        except ApiException as e:
            LOG.error("Exception when calling ServicesResourceApi->stop_command: %s\n" % e)
            raise e

    def restart_service(self, service_name: str, timeout_sec: int = DEFAULT_RESTART_SERVICE_TIMEOUT_SECONDS):
        LOG.info("Restarting service '%s'" % service_name)
        if service_name.lower() == 'mgmt':
            return self.restart_cm_management_service()

        api_instance = cm_client.ServicesResourceApi(cm_client.ApiClient())
        try:
            api_response = api_instance.restart_command(self.cluster_name, service_name)
            LOG.debug("Response %s" % api_response)
            return self.wait_for_command(api_response, timeout_sec)
        except ApiException as e:
            LOG.error("Exception when calling ServicesResourceApi->restart_command: %s\n" % e)
            return False, str(e)

    def read_service(self, service_name: str):
        LOG.debug("Reading service '%s'" % service_name)
        if service_name == "mgmt":
            api_instance = cm_client.MgmtServiceResourceApi(cm_client.ApiClient())
            api_response = api_instance.read_service()
        else:
            api_instance = cm_client.ServicesResourceApi(cm_client.ApiClient())
            api_response = api_instance.read_service(self.cluster_name, service_name)
        LOG.debug("Response: %s" % api_response)
        return api_response

    def is_service_exists(self, service_name: str):
        LOG.info(f"Checking whether {service_name} already exists on cluster {self.cluster_name}")
        try:
            return self.read_service(service_name=service_name) is not None
        except ApiException as e:
            constant_error_message = "Service '" + service_name + "' not found in cluster '" + self.cluster_name + "'."
            if constant_error_message in e.body:
                return False
            raise e

    def is_role_exists(self, service_name: str, role_name: str):
        LOG.info(f"Checking whether role '{role_name}' exists"
                 f" for service '{service_name}'"
                 f" on cluster {self.cluster_name}")
        try:
            roles: ApiRoleList = self.read_roles(service_name=service_name)
            next(role for role in roles.items if role.name == role_name)
            return True
        except StopIteration:
            return False

    def list_active_role_commands(self, role_name: str, service_name: str):
        LOG.debug("Listing active commands for role '%s' in service '%s'" % (role_name, service_name))
        api_instance = cm_client.RolesResourceApi(cm_client.ApiClient())
        try:
            api_response = api_instance.list_active_commands(self.cluster_name, role_name, service_name, view='summary')
            LOG.debug("Response: %s" % api_response)
            return api_response
        except ApiException as e:
            LOG.error("Exception when calling RolesResourceApi->list_active_commands: %s\n" % e)

    def list_active_service_commands(self, service_name: str):
        LOG.debug("Listing active commands for service '%s'" % service_name)
        api_instance = cm_client.ServicesResourceApi(cm_client.ApiClient())
        try:
            api_response = api_instance.list_active_commands(self.cluster_name, service_name, view='summary')
            LOG.debug("Response: %s" % api_response)
            return api_response
        except ApiException as e:
            LOG.error("Exception when calling RolesResourceApi->list_active_commands: %s\n" % e)

    def list_active_cloudera_manager_resource_commands(self):
        """
        List active ClouderaManagerResource commands (e.g.: GenerateCredentials)

        :raises ApiException, If a connection issue occurred
        :return: ApiCommandList => A list of ApiCommands that are active currently.
        """
        LOG.debug("Listing active commands for cluster '%s'" % self.cluster_name)
        api_instance = cm_client.ClouderaManagerResourceApi(cm_client.ApiClient())
        try:
            return api_instance.list_active_commands(view='full')
        except ApiException as e:
            LOG.error("Exception when calling ClustersResourceApi->list_active_commands: %s\n" % {e.reason})
            raise e

    def get_service_details(self, service_name: str) -> ApiService:
        return self.read_cm_management_service() if service_name.lower() == 'mgmt' else self.read_service(service_name)

    def wait_for_unnecessary_generate_credentials_commands(self):
        """
        NOTE: This is a workaround mechanism, since Cloudera Manager spawns GenerateCredentials commands
        without treating them as child processes or specifying their parent, thus
        this behaviour causes issues when kerberizing via the API.
        :return (True,message) If all unnecessary generate credentials commands have finished appropriately,
        (False, message) otherwise
        """
        all_active_cloudera_manager_resource_commands = self.list_active_cloudera_manager_resource_commands()
        if all_active_cloudera_manager_resource_commands.items:
            all_active_generate_credentials_commands = list(command for command in
                                                            all_active_cloudera_manager_resource_commands.items
                                                            if command.name == "GenerateCredentials")
            for generate_credentials_command in all_active_generate_credentials_commands:
                success, message = self.wait_for_command(generate_credentials_command)
                LOG.info(message)
                if not success:
                    return False, f"An unnecessary GenerateCredentials command did not finish, details: {message} "
            else:
                return True, "All unnecessary GenerateCredentials commands have finished."
        return True, "There were no unnecessary GenerateCredentials commands active"

    def abort_command(self, command: ApiCommand):
        """
        Tries to abort an ApiCommand.

        :param command: The ApiCommand to be aborted, e.g.: GenerateCredentials
        :return: (True,message) If the returned ApiCommand is inactive and unsuccessful, then it's considered aborted
        (False, message) otherwise
        :raises ApiException, If a connection issue occurred
        """
        try:
            api_instance = cm_client.CommandsResourceApi(cm_client.ApiClient())
            api_response = api_instance.abort_command(command.id)
            if not (api_response.active or api_response.success):
                return True, f"Command ID: {command.id}, name: {command.name} successfully aborted."
            else:
                return False, f"Couldn't abort ID: {command.id}, name: {command.name} command"
        except ApiException as e:
            LOG.info(f"Could not read command from server: {e.reason}")
            raise e

    def wait_for_command(self, command: Union[ApiCommand, ApiBulkCommandList], timeout_sec: int = 360):
        """
        Waits until an ApiCommand has finished or all the ApiCommands in an ApiBulkCommandList have finished

        :param command can be either an ApiCommand or an ApiBulkCommandList
        :param timeout_sec: Maximum timeout in seconds
        :raises ApiException, If a connection issue occurred
        :return: (True , message) if command has succeeded before a timeout (False, message) otherwise
        """
        if isinstance(command, ApiBulkCommandList) and command.items is not None:
            command_message = ""
            for current_command in command.items:
                current_command_success, current_command_message = \
                    self._wait_for_single_command(current_command, timeout_sec=timeout_sec)
                command_message = "\n".join([command_message, current_command_message])
                if not current_command_success:
                    return False, command_message
            else:
                return True, command_message
        else:
            return self._wait_for_single_command(command, timeout_sec=timeout_sec)

    def _wait_for_single_command(self, command: ApiCommand, timeout_sec: int = 360):
        """
        Waits until a command has finished

        :param command An ApiCommand that contains the following useful fields =>
          id: int => The command ID to query
          active: bool => Whether the command is currently active.
          success: bool => If the command is finished, whether it was successful.
        :param timeout_sec: Maximum timeout in seconds
        :raises ApiException, If a connection issue occurred
        :return: (True , message) if command has succeeded before a timeout (False, message) otherwise
        """
        api_instance = cm_client.CommandsResourceApi(cm_client.ApiClient())

        begin_time = time.time()
        timeout = begin_time + timeout_sec
        while time.time() < timeout:
            if command.active:
                time.sleep(10)
                try:  # query command state from API
                    command = api_instance.read_command(command.id)
                except ApiException as e:
                    LOG.info(f"Could not read command from server: {e.reason}")
                    raise e
            else:  # command is inactive
                elapsed_seconds = time.time() - begin_time
                if not command.success:
                    return False, f"Name: {command.name}, ID: {command.id} command has failed." \
                                  f" Elapsed time: {elapsed_seconds:.2f} seconds"
                else:  # command is inactive and has been successful
                    if command.service_ref:  # handle service type commands
                        success, healthcheck_elapsed_seconds = self._wait_for_service_to_become_healthy(
                            command.service_ref, int(timeout_sec - elapsed_seconds))
                        return success, f"Name: {command.name}, ID: {command.id}, " \
                                      f"Service: {command.service_ref.service_name} " \
                                      f"Elapsed time: {elapsed_seconds+healthcheck_elapsed_seconds:.2f} seconds," \
                                      f"Command success: {success}"

                    return True, f"Name: {command.name}, ID: {command.id} command has successfully " \
                                 f"finished in {elapsed_seconds:.2f} seconds"
        return False, f"Name: {command.name}, ID: {command.id} command did not finish in {timeout_sec} seconds"

    def _wait_for_service_to_become_healthy(self, service_reference: ApiServiceRef, timeout_sec: int):
        if service_reference.service_type.lower() == 'mgmt':
            api_instance, kwargs = cm_client.MgmtServiceResourceApi(cm_client.ApiClient()), {'view': 'full'}
        else:
            api_instance, kwargs = cm_client.ServicesResourceApi(cm_client.ApiClient()), \
                                   {'cluster_name': self.cluster_name,
                                    'service_name': service_reference.service_name,
                                    'view': 'full'}
        begin_time = time.time()
        timeout = begin_time + timeout_sec
        while time.time() < timeout:
            service_api_result: ApiService = api_instance.read_service(**kwargs)
            if service_api_result.health_summary != 'BAD':
                return True, time.time() - begin_time
            time.sleep(10)
        return False, timeout_sec

    def update_service_config(self, service_name: str, config_dict: dict):
        LOG.info("Updating configs for '%s' - '%s'" % (service_name, config_dict))
        try:
            api_configs_list = []
            for key, value in config_dict.items():
                api_configs_list.append(cm_client.ApiConfig(name=key, value=value))
            api_service_config = ApiServiceConfig(items=api_configs_list)

            api_instance = cm_client.ServicesResourceApi(cm_client.ApiClient())
            api_response = api_instance.update_service_config(self.cluster_name, service_name, body=api_service_config)
            LOG.debug("Response %s" % api_response)
            return True, f"Service config for '{service_name}' successfully updated with key-values {config_dict}"
        except ApiException as e:
            LOG.error("Exception when calling ServicesResourceApi->service_command_by_name: %s\n" % e)
            return False, str(e)

    def get_current_config_value(self, service_name: str, config_name: str):
        configs = self._read_service_config(service_name)
        LOG.debug(f"get_current_config_value {configs}")
        for config in configs.items:
            if config.name == config_name:
                return config.value if config.value else config.default
        raise StopIteration

    def _read_service_config(self, service_name: str):
        LOG.info("Getting service configurations for '%s'" % service_name)
        api_instance = cm_client.ServicesResourceApi(cm_client.ApiClient())
        try:
            api_response = api_instance.read_service_config(self.cluster_name, service_name, view='full')
            LOG.debug("Response %s" % api_response)
            return api_response
        except ApiException as e:
            LOG.error("Exception when calling ServicesResourceApi->service_command_by_name: %s\n" % e)
            raise e

    def update_cm_config(self, config_dict: dict):
        LOG.info("Attempting to update CM configuration values...")
        config_list = []
        for key, value in config_dict.items():
            config_list.append(cm_client.ApiConfig(name=key, value=value))
        configs = cm_client.ApiConfigList(config_list)

        api_instance = cm_client.ClouderaManagerResourceApi(cm_client.ApiClient())
        try:
            api_response = api_instance.update_config(body=configs)
            LOG.debug("Response %s" % api_response)
            return True, "CM configurations has been updated..."
        except ApiException as e:
            LOG.error("Exception when calling ClouderaManagerResourceApi->update_config: %s\n" % e)
            return False, str(e)

    def get_all_mgmt_role_config_groups(self) -> ApiRoleConfigGroupList:
        api_instance = cm_client.MgmtRoleConfigGroupsResourceApi(cm_client.ApiClient())
        return api_instance.read_role_config_groups()

    def update_mgmt_role_config(self, role_config_group_name: str, config_dict: dict):
        LOG.info(f"Attempting to update CM Management '{role_config_group_name}' Role's config...")
        config_list = []
        for key, value in config_dict.items():
            config_list.append(cm_client.ApiConfig(name=key, value=value))
        configs = cm_client.ApiConfigList(config_list)

        api_instance = cm_client.MgmtRoleConfigGroupsResourceApi(cm_client.ApiClient())
        try:
            api_response = api_instance.update_config(role_config_group_name, body=configs)
            LOG.debug("Response %s" % api_response)
            return True, "CM configurations has been updated..."
        except ApiException as e:
            LOG.error("Exception when calling MgmtRoleConfigGroupsResourceApi->update_config: %s\n" % e)
            return False, str(e)

    def check_if_config_is_present_for_mgmt_role_config_group(self, role_config_group_name: str, config_name: str) \
      -> bool:
        api_instance = cm_client.MgmtRoleConfigGroupsResourceApi(cm_client.ApiClient())
        api_response: ApiConfigList = api_instance.read_config(role_config_group_name, view='full')
        return self._check_if_config_is_present(api_response, config_name)

    def _check_if_config_is_present(self, config_list: ApiConfigList, config_name: str):
        config_items: list[ApiConfig] = config_list.items
        try:
            next(conf for conf in config_items if conf.name == config_name)
            return True
        except StopIteration:
            return False

    def read_roles(self, service_name: str):
        LOG.info("Reading roles for service '%s'" % service_name)
        api_instance = cm_client.RolesResourceApi(cm_client.ApiClient())
        try:
            api_response = api_instance.read_roles(self.cluster_name, service_name)
            LOG.debug("Response %s" % api_response)
            return api_response
        except ApiException as e:
            LOG.error("Exception when calling RolesResourceApi->read_roles: %s\n" % e)

    def run_role_command(self, command_name: str, service_name: str, role_names: list, timeout_sec: int = DEFAULT_ROLE_COMMAND_TIMEOUT_SECONDS):
        LOG.info("Running '%s' role command for service '%s'" % (command_name, service_name))
        api_instance = cm_client.RoleCommandsResourceApi(cm_client.ApiClient())

        body = cm_client.ApiRoleNameList(role_names)
        try:
            api_response = api_instance.role_command_by_name(self.cluster_name, command_name, service_name, body=body)
            LOG.debug("Response %s" % api_response)
            return self.wait_for_command(api_response, timeout_sec)
        except ApiException as e:
            LOG.error("Exception when calling RolesResourceApi->read_roles: %s\n" % e)
            return False, str(e)

    def get_cluster(self, cluster_name: str = None):
        if cluster_name is None:
            cluster_name = self.cluster_name

        api_instance = cm_client.ClustersResourceApi(cm_client.ApiClient())
        try:
            # Reads information about a cluster.
            return api_instance.read_cluster(cluster_name)
        except ApiException as e:
            LOG.error("Exception when calling ClustersResourceApi->read_cluster: %s\n" % e)
        return None

    def is_cluster_exist(self, cluster_name: str = None):
        return self.get_cluster(cluster_name) is not None

    def is_management_service_exists(self):
        api_instance = cm_client.MgmtServiceResourceApi(cm_client.ApiClient())
        LOG.info(f"Checking whether Cloudera Management Service already exists on cluster {self.cluster_name}, on host"
                 f"{self.hostname}")
        try:
            api_instance.read_service(view='summary')
            return True
        except ApiException:
            return False

    def create_cloudera_management_service(self):
        """
        Attempt to create cloudera management service

        :return: Tuple of ( success , message )
        """
        api_instance = cm_client.MgmtServiceResourceApi(cm_client.ApiClient())
        LOG.info(f"Attempting to create empty management service on cluster {self.cluster_name}, on host"
                 f"{self.hostname}")
        try:
            body = cm_client.ApiService(display_name='Cloudera Management Service')
            api_instance.setup_cms(body=body)
            return True, "Cloudera Management Service successfully created."
        except ApiException as e:
            return False, str(e)

    def update_role_config_group_property(self, service_name: str, role_config_group_display_name: str,
                                          configuration_name: str, configuration_value):
        """
        Attempt to update a property to a given value in a role configuration group of a service

        :return: Tuple of ( success , message )
        """
        try:
            role_config_group_name = self. \
                _get_role_config_group_name_from_all_role_config_groups(service_name, role_config_group_display_name)
            message = f"Updated {service_name} service's {role_config_group_display_name}  role configuration group's" \
                      f" {configuration_name} configuration to the following value: '{configuration_value}'"
            config_to_set = {configuration_name: configuration_value}
            self.update_role_config_group_configuration(service_name, role_config_group_name,
                                                        config_to_set, message)
            return True, message
        except ApiException as e:
            return False, str(e)
        except StopIteration:
            return False, "Couldn't find role config group name among role config groups"

    def get_all_services(self) -> list:
        api_instance = cm_client.ServicesResourceApi(cm_client.ApiClient())
        return api_instance.read_services(self.cluster_name).items

    def get_all_services_silently(self):
        try:
            return True, self.get_all_services()
        except ApiException as e:
            return False, str(e)

    def get_role_config_groups_for_service(self, service_name: str) -> ApiRoleConfigGroupList:
        """
        Get all the role configs groups that are associated to a given service

        :param: service_name
        :return: ApiRoleConfigGroupList
        :except: ApiException
        """
        api_instance = cm_client.RoleConfigGroupsResourceApi(cm_client.ApiClient())
        return api_instance.read_role_config_groups(self.cluster_name, service_name)

    def check_if_config_is_present_for_role_config_group(
      self, service_name: str, role_config_group_name: str, config_name: str) -> bool:
        api_instance = cm_client.RoleConfigGroupsResourceApi(cm_client.ApiClient())
        api_response: ApiConfigList = api_instance.read_config(
            self.cluster_name, role_config_group_name, service_name, view='full')
        return self._check_if_config_is_present(api_response, config_name)

    def _get_role_config_group_name_of_role_config_display_name(self, role_config_groups: ApiRoleConfigGroupList,
                                                                display_name: str):
        """
        Find the real role config group name based on the display role config group name

        :param: role_config_groups: The list to search in
        :param: display_name: Filter criteria
        :return: Matching role_config_group.name
        :except: StopException
        """
        return next(role_config_group.name for role_config_group in role_config_groups.items
                    if role_config_group.display_name == display_name)

    def _get_role_config_group_name_from_all_role_config_groups(self, service_name: str, display_name: str):
        role_config_groups = self.get_role_config_groups_for_service(service_name)
        return self._get_role_config_group_name_of_role_config_display_name(role_config_groups,
                                                                            display_name)

    def update_role_config_group_configuration(self, service_name: str, role_config_group_name: str,
                                               config_dict: dict, message: str = ""):
        api_instance = cm_client.RoleConfigGroupsResourceApi(cm_client.ApiClient())
        config_list = []
        for key, value in config_dict.items():
            config_list.append(cm_client.ApiConfig(name=key, value=value))
        body = cm_client.ApiConfigList(config_list)

        api_instance.update_config(self.cluster_name, role_config_group_name,
                                   service_name, message=message, body=body)

    def read_configuration_from_role_config_group(self, service_name: str, role_config_group_display_name: str,
                                                  configuration_name: str):
        try:
            role_config_group_name = self._get_role_config_group_name_from_all_role_config_groups(service_name,
                                                                                                  role_config_group_display_name)
            api_instance = cm_client.RoleConfigGroupsResourceApi(cm_client.ApiClient())
            api_response = api_instance.read_config(self.cluster_name, role_config_group_name,
                                                    service_name, view='full')
            return True, next(config.value if config.value else config.default
                              for config in api_response.items
                              if config.name == configuration_name)
        except ApiException as e:
            return False, str(e)
        except StopIteration:
            return False, "Couldn't find role config group name among role config groups"

    def is_tls_enabled(self):
        """
        API call to CM server whether TLS is enabled.

        :return:  bool
        :except ApiException
        """
        api_instance = cm_client.ClustersResourceApi(cm_client.ApiClient())
        return api_instance.is_tls_enabled(self.cluster_name)

    def get_hostnames_belonging_to_role_group(self, role_group_filter: str):
        try:
            api_instance = cm_client.ClustersResourceApi(cm_client.ApiClient())
            api_response = api_instance.list_hosts(self.cluster_name, view='FULL')
            # get hostname from items whose role_ref's 'role_name' contains 'role_group_filter' as a substring
            return True, json.dumps(list(api_host.hostname
                                         for api_host in api_response.items
                                         if any(role_group_filter in role_ref.role_name
                                                for role_ref in api_host.role_refs)))
        except ApiException as e:
            return False, str(e)

    def query_configuration_value(self, service_name: str, configuration_name: str,
                                  configuration_type: str = 'NOT_SPECIFIED',
                                  role_name_filter: str = None):
        class ConfigurationType(Enum):
            SERVICE = partial(self._query_configuration_query_type_is_service, service_name,
                              configuration_name)
            ROLE = partial(self._query_configuration_query_type_is_role, service_name,
                           configuration_name, role_name_filter)
            NOT_SPECIFIED = partial(self._query_configuration_query_type_is_not_specified, service_name,
                                    configuration_name, role_name_filter)

        try:
            query_function = ConfigurationType[configuration_type].value
            return query_function()
        except ApiException as e:
            return False, str(e)

    def _query_configuration_query_type_is_not_specified(self, service_name, configuration_name: str,
                                                         role_name_filter: str):
        LOG.info("Query type not specified, querying from service configurations first")
        success, configuration_value = self. \
            _query_configuration_query_type_is_service(service_name, configuration_name)

        if success:
            return True, configuration_value

        LOG.info("Trying to query role configurations next")
        return self._query_configuration_query_type_is_role(service_name, configuration_name, role_name_filter)

    def _query_configuration_query_type_is_role(self, service_name, configuration_name,
                                                role_name_filter: str = None):
        api_instance = cm_client.RolesResourceApi(cm_client.ApiClient())
        api_response = api_instance.read_roles(self.cluster_name, service_name)

        if role_name_filter:
            all_roles_for_service = list(item for item in api_response.items if role_name_filter in item.name)
        else:
            all_roles_for_service = api_response.items
        for current_role in all_roles_for_service:
            role_config_api_response = api_instance.read_role_config(self.cluster_name, current_role.name, service_name,
                                                                     view='full')
            try:
                matching_configuration = next(configuration for configuration in role_config_api_response.items
                                              if configuration.name == configuration_name)
                LOG.info(f"Found {configuration_name} in role name: {current_role.name}")
                return True, matching_configuration.value if matching_configuration.value is not None \
                    else matching_configuration.default
            except StopIteration:
                pass
        else:
            return False, f"Couldn't find {configuration_name} in any of the roles for {service_name}"

    def _query_configuration_query_type_is_service(self, service_name, configuration_name):
        service_api_instance = cm_client.ServicesResourceApi(cm_client.ApiClient())
        new_api_response = service_api_instance.read_service_config(self.cluster_name, service_name,
                                                                    view='full')
        try:
            service_configuration = next(config for config in new_api_response.items
                                         if config.name == configuration_name)
            return True, service_configuration.value if service_configuration.value is not None \
                else service_configuration.default
        except StopIteration:
            return False, f"Couldn't find '{configuration_name}' in the service configuration of '{service_name}'"

    def import_kerberos_admin_credentials(self, username: str, password: str):
        LOG.info("Attempting to import kerberos admin credentials to CM...")
        api_instance = cm_client.ClouderaManagerResourceApi(cm_client.ApiClient())

        try:
            success, message = self.wait_for_unnecessary_generate_credentials_commands()
            if success:
                api_response = api_instance.import_admin_credentials(username=username, password=password)
                LOG.debug(f"Response: {api_response}")
                return True, "Imported kerberos admin credentials to CM"
            else:
                return False, message
        except ApiException as e:
            LOG.error("Exception when calling ClouderaManagerResourceApi->import_admin_credentials: %s\n" % e)
            return False, str(e)

    def configure_cluster_for_kerberos(self):
        LOG.info("Calling configure for kerberos API endpoint on CM...")
        api_instance = cm_client.ClustersResourceApi(cm_client.ApiClient())
        body = self.create_configure_kerberos_argument_body()

        try:
            success, message = self.wait_for_unnecessary_generate_credentials_commands()
            if success:
                api_response = api_instance.configure_for_kerberos(self.cluster_name, body=body)
                return self.wait_for_command(api_response)
            else:
                return False, message
        except ApiException as e:
            LOG.error("Exception when calling ClustersResourceApi->configure_for_kerberos: %s\n" % e)
            return False, str(e)

    def create_configure_kerberos_argument_body(self):
        success_transceiver_port, response_transceiver_port = \
            self.read_configuration_from_role_config_group("hdfs", "hdfs-DATANODE", "dfs_datanode_port");
        success_datanode_web_port, response_datanode_web_port = \
            self.read_configuration_from_role_config_group("hdfs", "hdfs-DATANODE", "dfs_datanode_http_port");
        # since ApiConfigureForKerberosArguments doesn't correctly fill out default values,
        # we'll have to do it manually
        datanode_transceiver_port = int(response_transceiver_port) if success_transceiver_port else 1004
        datanode_web_port = int(response_datanode_web_port) if success_datanode_web_port else 1006
        return cm_client.ApiConfigureForKerberosArguments(datanode_transceiver_port=datanode_transceiver_port,
                                                          datanode_web_port=datanode_web_port)

    def delete_kerberos_credentials(self, delete_credentials_mode='all'):
        LOG.info(f"Calling Kerberos credential deletion with mode: {delete_credentials_mode}")
        api_instance = cm_client.ClouderaManagerResourceApi(cm_client.ApiClient())

        try:
            success, message = self.wait_for_unnecessary_generate_credentials_commands()
            if success:
                api_response = api_instance.delete_credentials_command(delete_credentials_mode=delete_credentials_mode)
                LOG.debug(f"Response: {api_response}")
                return self.wait_for_command(api_response)
            else:
                return False, message
        except ApiException as e:
            LOG.error("Exception when calling ClouderaManagerResourceApi->delete_credentials_command: %s\n" % e)
            return False, str(e)

    def generate_missing_kerberos_credentials(self):
        LOG.info("Initiation of Kerberos credential generation...")
        api_instance = cm_client.ClouderaManagerResourceApi(cm_client.ApiClient())

        try:
            success, message = self.wait_for_unnecessary_generate_credentials_commands()
            if success:
                api_response = api_instance.generate_credentials_command()
                LOG.debug(f"Response: {api_response}")
                return self.wait_for_command(api_response)
            else:
                return False, message
        except ApiException as e:
            LOG.error("Exception when calling ClouderaManagerResourceApi->generate_credentials_command: %s\n" % e)
            return False, str(e)

    def read_cm_management_service(self) -> ApiService:
        LOG.info("Read CM Management Service")
        api_instance = cm_client.MgmtServiceResourceApi(cm_client.ApiClient())

        try:
            return api_instance.read_service()
        except ApiException as e:
            LOG.error("Exception when calling MgmtServiceResourceApi->read_service: %s\n" % e)
            raise e

    def stop_cm_management_service(self, timeout_sec: int = 360):
        LOG.info("Initiating STOP command for CM Management Service")
        api_instance = cm_client.MgmtServiceResourceApi(cm_client.ApiClient())

        try:
            api_response = api_instance.stop_command()
            LOG.debug(f"Response: {api_response}")
            return self.wait_for_command(api_response, timeout_sec)
        except ApiException as e:
            LOG.error("Exception when calling MgmtServiceResourceApi->stop_command: %s\n" % e)
            return False, str(e)

    def start_cm_management_service(self, timeout_sec: int = 360):
        LOG.info("Initiating START command for CM Management Service")
        api_instance = cm_client.MgmtServiceResourceApi(cm_client.ApiClient())

        try:
            api_response = api_instance.start_command()
            LOG.debug(f"Response: {api_response}")
            return self.wait_for_command(api_response, timeout_sec)
        except ApiException as e:
            LOG.error("Exception when calling MgmtServiceResourceApi->start_command: %s\n" % e)
            return False, str(e)

    def restart_cm_management_service(self, timeout_sec: int = 360):
        LOG.info("Initiating RESTART command for CM Management Service")
        api_instance = cm_client.MgmtServiceResourceApi(cm_client.ApiClient())

        try:
            api_response = api_instance.restart_command()
            LOG.debug(f"Response: {api_response}")
            return self.wait_for_command(api_response, timeout_sec)
        except ApiException as e:
            LOG.error("Exception when calling MgmtServiceResourceApi->restart_command: %s\n" % e)
            return False, str(e)

    def enable_tls_for_services(self):
        try:
            api_instance = cm_client.ClustersResourceApi(cm_client.ApiClient())
            api_instance.configure_auto_tls_services_command(self.cluster_name)
            return True, f"Successfully enabled auto TLS for services in cluster '{self.cluster_name}'!"
        except ApiException as e:
            return False, str(e)

    def enable_tls(self, remote_username: str, **kwargs):
        """
        Enabling TLS in CM. No Root CA or custom cert is given, CM generates everything in this case.

        :param remote_username: The username to pass to CM server so that it can deploy the certificates to agents
        :param kwargs: can be 'private_key_file' or 'password'
        :return: tuple of success, message
        """
        try:
            if kwargs.get('private_key_file'):
                text_file = open(kwargs.get('private_key_file'))
                private_key = text_file.read()
                text_file.close()
                body = cm_client.ApiGenerateCmcaArguments(user_name=remote_username, private_key=private_key)
            elif 'password' in kwargs:
                body = cm_client.ApiGenerateCmcaArguments(user_name=remote_username, password=kwargs.get('password'))
            else:
                return False, "No private_key_file or password parameter. Please supply one or the other. If both" \
                              "is supplied, private_key_file takes precedence."
            cloudera_manager_resource_api = cm_client.ClouderaManagerResourceApi(cm_client.ApiClient())
            generate_cmca_api_response = cloudera_manager_resource_api.generate_cmca(body=body)
            timeout_seconds = kwargs.get('timeout_seconds', self.DEFAULT_SERVICE_COMMAND_TIMEOUT_SECONDS)
            LOG.info("Generating Certificate by Cloudera Manager")
            command_success, timeout_message = self.wait_for_command(generate_cmca_api_response, timeout_sec=timeout_seconds)
            if command_success:
                LOG.info("Generating Certificate by Cloudera Manager successful!")
                cluster_resource_api = cm_client.ClustersResourceApi(cm_client.ApiClient())
                configure_auto_tls_api_response = cluster_resource_api.configure_auto_tls_services_command(self.cluster_name)
                LOG.info("Configuring Auto-TLS")
                command_success, timeout_message = self.wait_for_command(configure_auto_tls_api_response, timeout_sec=timeout_seconds)

            return command_success, f"Successfully enabled auto TLS for services in cluster '{self.cluster_name}'!" \
                if command_success else timeout_message
        except ApiException as e:
            return False, str(e)

    def start_all_services(self):
        try:
            api_instance = cm_client.ClustersResourceApi(cm_client.ApiClient())
            api_response = api_instance.start_command(self.cluster_name)

            return self.wait_for_command(api_response, timeout_sec=900)
        except ApiException as e:
            return False, str(e)

    def stop_all_services(self):
        try:
            api_instance = cm_client.ClustersResourceApi(cm_client.ApiClient())
            api_response = api_instance.stop_command(self.cluster_name)

            return self.wait_for_command(api_response)
        except ApiException as e:
            return False, str(e)

    def deploy_cluster_client_config(self):
        api_instance = cm_client.ClustersResourceApi(cm_client.ApiClient())
        body = cm_client.ApiHostRefList(items=[])

        try:
            success, message = self.wait_for_unnecessary_generate_credentials_commands()
            if success:
                api_response = api_instance.deploy_cluster_client_config(self.cluster_name, body=body)
                return self.wait_for_command(api_response)
            else:
                return False, message
        except ApiException as e:
            return False, str(e)

    def _read_host_attribute(self, host_id: str, attribute_name: str):
        api_instance = cm_client.HostsResourceApi(cm_client.ApiClient())
        try:
            api_response: ApiHost = api_instance.read_host(host_id=host_id, view='full')
            return getattr(api_response, attribute_name)
        except ApiException as e:
            LOG.error("Exception when calling HostsResourceApi->read_host: %s\n" % e)
            raise e
        except AttributeError as attr_e:
            LOG.error(f"Host with id '{host_id}' has no attribute '{attribute_name}'!")
            raise attr_e

    def read_hosts(self):
        api_instance = cm_client.HostsResourceApi(cm_client.ApiClient())
        try:
            api_response: ApiHostList = api_instance.read_hosts()
            return api_response
        except ApiException as e:
            LOG.error("Exception when calling HostsResourceApi->read_hosts: %s\n" % e)
            raise e

    def wait_for_cm_agent_heartbeat_for_hosts(self, host_list: ApiHostList = None, timeout_sec: int = 150):
        check_start_time = datetime.timestamp(datetime.utcnow())
        timeout = time.time() + timeout_sec
        hosts_still_to_check = host_list.items.copy() if host_list else self.read_hosts().items.copy()
        while time.time() < timeout and len(hosts_still_to_check) > 0:
            host: ApiHost
            for host in hosts_still_to_check:
                last_heartbeat_str = self._read_host_attribute(host.host_id, "last_heartbeat")
                last_heartbeat_time = datetime.timestamp(datetime.strptime(last_heartbeat_str, "%Y-%m-%dT%H:%M:%S.%fZ"))
                LOG.debug(f"Last heartbeat for '{host.hostname}': {last_heartbeat_str} - {last_heartbeat_time}")
                if last_heartbeat_time > check_start_time:
                    LOG.debug(f"Heartbeat for host {host.hostname} successfully arrived")
                    hosts_still_to_check.remove(host)
                else:
                    LOG.debug(f"Heartbeat for host {host.hostname} is old, still waiting...")
                    time.sleep(3)
        if len(hosts_still_to_check) > 0:
            missed_hosts_as_str = ",".join([h.hostname for h in hosts_still_to_check])
            return False, f"Timed out after {timeout_sec} seconds." \
                          f" Heartbeat is still missing from agents on these hosts: {missed_hosts_as_str}"
        else:
            return True, "Heartbeat from all agents have arrived in time!"

    def wait_for_cm_agent_to_be_healthy_on_hosts(self, host_list: ApiHostList = None, timeout_sec: int = 300):
        timeout = time.time() + timeout_sec
        hosts_still_to_check = host_list.items.copy() if host_list else self.read_hosts().items.copy()
        while time.time() < timeout and len(hosts_still_to_check) > 0:
            host: ApiHost
            for host in hosts_still_to_check:
                health_summary = self._read_host_attribute(host.host_id, "health_summary")
                if health_summary == ApiHealthSummary.GOOD:
                    LOG.debug(f"Agent status on {host.hostname} is 'GOOD'!")
                    hosts_still_to_check.remove(host)
                else:
                    LOG.debug(f"Agent status on {host.hostname} is '{health_summary}', still waiting...")
                    time.sleep(3)
        if len(hosts_still_to_check) > 0:
            missed_hosts_as_str = ",".join([h.hostname for h in hosts_still_to_check])
            return False, f"Timed out after {timeout_sec} seconds." \
                          f" Missed to reach 'GOOD' state on these hosts: {missed_hosts_as_str}"
        else:
            return True, "Agent status reached 'GOOD' state on all hosts in time!"

    def read_configuration_from_host(self, host_id: str, configuration_name: str):
        api_instance = cm_client.HostsResourceApi(cm_client.ApiClient())
        try:
            api_response = api_instance.read_host_config(host_id, view='full')
            configuration = next(api_config for api_config in api_response.items
                                 if api_config.name == configuration_name)

            if configuration.value is not None:
                return True, configuration.value

            if configuration.default is not None:
                return True, configuration.default

            return False, f"Couldn't get either configuration value or default " \
                          f"for configuration {configuration_name} on host {host_id}"
        except ApiException as e:
            return False, str(e)
        except StopIteration:
            return False, f"{configuration_name} not found for {host_id}. Available configurations: " + \
                   ", ".join(list(api_config.name for api_config in api_response.items))

    def list_active_cluster_commands(self):
        api_instance = cm_client.ClustersResourceApi(cm_client.ApiClient())
        return api_instance.list_active_commands(self.cluster_name, view='full')

    def deploy_client_configs_and_refresh(self):
        api_instance = cm_client.ClustersResourceApi(cm_client.ApiClient())
        try:
            api_response = api_instance.deploy_client_configs_and_refresh(self.cluster_name)
            LOG.debug("Response: %s" % api_response)
            return self.wait_for_command(api_response, timeout_sec=900)
        except ApiException as e:
            LOG.error("Exception when calling ClustersResourceApi->deploy_client_configs_and_refresh: %s\n" % e)
            return False, str(e)

    def get_role_commands(self, service_name: str, role_name_filter: str):
        role_api = cm_client.RolesResourceApi(cm_client.ApiClient())

        roles = role_api.read_roles(self.cluster_name, service_name)

        role_names = list(item.name for item in roles.items if role_name_filter in item.name)
        LOG.info(f"All roles for service '{service_name}': {role_names}")

        result = []
        for current_role_name in role_names:
            data = role_api.list_commands(self.cluster_name, current_role_name, service_name)
            result.extend(list(item.name for item in data.items))

        return list(set(result))

    def get_cm_truststore(self):
        api_instance = cm_client.CertManagerResourceApi(cm_client.ApiClient())
        return api_instance.get_truststore_password()
