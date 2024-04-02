import json
import logging
import time

import requests

LOG = logging.getLogger(__name__)


def current_time_millies():
    return round(time.time() * 1000)


class HDPCluster:
    """
    Class to represent an HDP Cluster.
    """

    headers = {
        'X-Requested-By': 'ambari'
    }

    def __init__(self, hostname: str, port: int, protocol: str, verify_ssl: bool,
                 username: str, password: str, cluster_name: str):
        self.hostname = hostname
        self.port = port
        self.protocol = protocol
        self.verify_ssl = verify_ssl
        self.username = username
        self.password = password
        self.cluster_name = cluster_name
        self.is_https = protocol == "https"
        self.base_url = f'{protocol}://{hostname}:{port}/api/v1'

    def setup_hbase_master_procedure_store_drain(self, check_mode: bool = False):
        LOG.info('setup the procedure store drain for the hbase_master')

        config_type = 'hbase-site'
        configuration = self._get_current_service_configs(service_name='HBASE', config_type=config_type)
        if configuration is None:
            raise Exception(f"Missing {config_type} configuration in the service configurations")

        if "properties" not in configuration:
            raise Exception(f"Missing properties in the {config_type} configuration!")

        property_to_be_added = "hbase.procedure.upgrade-to-2-2"
        if property_to_be_added in configuration["properties"]:
            LOG.info(f"The property {property_to_be_added} has already been added to the hbase-site, "
                     "so nothing to do with ")
            return False

        if check_mode:
            return True

        # add config
        configuration["properties"][property_to_be_added] = True

        # update config
        self._update_configuration(config_type=config_type, properties=configuration["properties"],
                                   change_description='Setup HBase for Master Procedure Store drain')

        return True

    def _get_current_service_configs(self, service_name: str, config_type: str):
        configurations = self._get_all_current_service_configs(service_name)
        for configuration in configurations:
            if configuration["type"] == config_type:
                return configuration
        return None

    def _get_all_current_service_configs(self, service_name: str):
        request_url = f'{self.base_url}/clusters/{self.cluster_name}/configurations/service_config_versions?' \
                      f'is_current=true&service_name={service_name}'
        response = requests.get(url=request_url, auth=(self.username, self.password), verify=self.verify_ssl)

        if not response.ok:
            LOG.error("Getting current service configs failed ...")
            response.raise_for_status()

        data = json.loads(response.text)

        if "items" not in data or len(data["items"]) == 0:
            LOG.warning("Missing items in the service configurations response!!")
            return []

        return data["items"][0]["configurations"]

    def _update_configuration(self, config_type, properties, change_description):

        update_desired_config_body = {
            'Clusters': {
                'desired_config': [{
                    'type': config_type,
                    'tag': f'version{current_time_millies()}',
                    'properties': properties,
                    'service_config_version_note': change_description
                }]
            }
        }

        request_url = f'{self.base_url}/clusters/{self.cluster_name}'
        response = requests.put(url=request_url, data=json.dumps(update_desired_config_body), headers=self.headers,
                                auth=(self.username, self.password), verify=self.verify_ssl)
        LOG.info(f'status_code: {response.status_code}')
        if not response.status_code == 200:
            LOG.error("Updating the configuration failed ...")
            response.raise_for_status()

    def perform_action_on_host_component(self, action, component_name, component_hosts):
        """
        Start, Stop a component on host
        API: PUT /api/v1/clusters/:cluster_name/hosts/:host_name/host_components/:component_name

        :param action: the action to be performed on the component (start,stop)
        :param component_name: the name of the component
        :param component_hosts: the hosts where the coponent is located
        :return: None
        """

        if action == 'start':
            state = "STARTED"
        elif action == 'stop':
            state = "INSTALLED"
        else:
            raise Exception(f"Unknown action: {action}! The action should be start|stop!")

        result = False
        for component_host in component_hosts:
            request = {
                "RequestInfo": {
                    "context": f"{action.capitalize()} {component_name} on {component_host} "
                },
                "Body": {
                    "HostRoles": {
                        "state": state
                    }
                }
            }

            request_url = f'{self.base_url}/clusters/{self.cluster_name}/hosts/{component_host}/host_components/{component_name}'
            response = requests.put(url=request_url, data=json.dumps(request), headers=self.headers,
                                    auth=(self.username, self.password), verify=self.verify_ssl)
            LOG.info(f'status_code: {response.status_code}')
            if not response.ok:
                LOG.error(f"Performing {action} on {component_name} failed ...")
                response.raise_for_status()

            result = result or response.status_code == 202

        return result

    def complete_hbase_master_procedure_store_drain(self, check_mode: bool = False):
        LOG.info('complete the procedure store drain for the hbase_master')

        config_type = 'hbase-site'
        configuration = self._get_current_service_configs(service_name='HBASE', config_type=config_type)
        if configuration is None:
            raise Exception(f"Missing {config_type} configuration in the service configurations")

        if "properties" not in configuration:
            raise Exception(f"Missing properties in the {config_type} configuration!")

        property_to_be_removed = "hbase.procedure.upgrade-to-2-2"
        if property_to_be_removed not in configuration["properties"]:
            LOG.info(f"The property {property_to_be_removed} has already been removed from the hbase-site, "
                     "so nothing to do with ")
            return False

        if check_mode:
            return True

        # update config
        del configuration["properties"][property_to_be_removed]

        self._update_configuration(config_type=config_type, properties=configuration["properties"],
                                   change_description='Complete HBase for Master Procedure Store drain')

        return True

    def is_all_services_stopped(self):
        path = f'{self.base_url}/clusters/{self.cluster_name}/services?fields=ServiceInfo/state'
        response = requests.get(url=path, headers=self.headers,
                                auth=(self.username, self.password), verify=self.verify_ssl)
        if not response.ok:
            LOG.error("Checking if all services are stopped failed ...")
            response.raise_for_status()

        data = json.loads(response.text)
        for item in data["items"]:
            if item["ServiceInfo"]["state"] == "STARTED":
                return False

        return True

    def stop_all_services(self, retry_num=3):
        """
        Stop all HDP services
        """

        path = f'{self.base_url}/clusters/{self.cluster_name}/services'
        payload = {"RequestInfo": {"context": "Stop services by am2cm"},
                   "Body": {"ServiceInfo": {"state": "INSTALLED"}}}

        return self.__perform_and_wait(path, payload, retry_num) < retry_num

    def __perform_and_wait(self, path, payload, retry_num):
        result = self.__perform_request(path, payload, retry_num, wait_for_complete=True)
        return result['retry_count']

    def __perform_request(self, path, payload, retry_num, wait_for_complete=False):
        result = dict()
        retry_count = 0
        while retry_count < retry_num:
            request_status = None
            response = requests.put(url=path, data=json.dumps(payload), headers=self.headers,
                                    auth=(self.username, self.password), verify=self.verify_ssl)
            if response.ok and response.text is not None and len(response.text.strip()) > 0:

                response_json = json.loads(response.text)
                request_id_url = response_json['href']

                if not wait_for_complete:
                    result['tracking_url'] = request_id_url
                    break

                is_completed = False
                while not is_completed:
                    request_status_response = requests.get(url=request_id_url, headers=self.headers,
                                                           auth=(self.username, self.password), verify=self.verify_ssl)
                    request_status_response_json = json.loads(request_status_response.text)
                    if request_status_response_json['Requests']['request_status'] in ['COMPLETED', 'FAILED', 'ABORTED']:
                        is_completed = True
                        request_status = request_status_response_json['Requests']['request_status']
                    else:
                        time.sleep(10)
            if request_status == 'COMPLETED':
                break
            retry_count += 1
        result['retry_count'] = retry_count
        return result

    def is_service_stopped(self, service_name):
        """
        Check whether the given HDP service stopped
        """

        path = f'{self.base_url}/clusters/{self.cluster_name}/services/{service_name.upper()}?fields=ServiceInfo/state'
        response = requests.get(url=path, headers=self.headers,
                                auth=(self.username, self.password), verify=self.verify_ssl)
        if not response.ok:
            LOG.error(f"Checking if {service_name} service is stopped failed ...")
            response.raise_for_status()

        data = json.loads(response.text)
        if data["ServiceInfo"]["state"] == "STARTED":
            return False

        return True

    def stop_service(self, service_name, retry_num=3):
        """
        Stop the given HDP service
        """

        path = f'{self.base_url}/clusters/{self.cluster_name}/services/{service_name.upper()}'
        payload = {"RequestInfo": {"context": f"Stop {service_name.upper()} service by am2cm"},
                   "Body": {"ServiceInfo": {"state": "INSTALLED"}}}

        return self.__perform_and_wait(path, payload, retry_num) < retry_num

    def start_service(self, service_name, retry_num=3):
        """
        Start the given HDP service
        """

        path = f'{self.base_url}/clusters/{self.cluster_name}/services/{service_name.upper()}'
        payload = {"RequestInfo": {"context": f"Start {service_name.upper()} service by am2cm"},
                   "Body": {"ServiceInfo": {"state": "STARTED"}}}

        return self.__perform_and_wait(path, payload, retry_num) < retry_num

    def is_service_started(self, service_name):
        """
        Check whether the given HDP service stopped
        """

        path = f'{self.base_url}/clusters/{self.cluster_name}/services/{service_name.upper()}?fields=ServiceInfo/state'
        response = requests.get(url=path, headers=self.headers,
                                auth=(self.username, self.password), verify=self.verify_ssl)
        if not response.ok:
            LOG.error(f"Checking if {service_name} service is started failed ...")
            response.raise_for_status()

        data = json.loads(response.text)
        if data["ServiceInfo"]["state"] == "INSTALLED":
            return False

        return True

    def start_service_component(self, service_name, component_name, retry_num=3, wait_for_complete=True):
        """
        Start the specified component of the given HDP service
        """

        path = f'{self.base_url}/clusters/{self.cluster_name}/services/{service_name.upper()}/components/{component_name}'
        payload = {
            "RequestInfo": {"context": f"Start {component_name.upper()} in {service_name.upper()} service by am2cm"},
            "Body": {"ServiceComponentInfo": {"state": "STARTED"}}}

        result = self.__perform_request(path, payload, retry_num, wait_for_complete)
        result['success'] = result['retry_count'] < retry_num
        return result

    def is_service_component_started(self, service_name, component_name):
        """
        Check whether the specified component of the given HDP service started
        """

        path = f'{self.base_url}/clusters/{self.cluster_name}/services/{service_name.upper()}/components/{component_name}' \
               f'?fields=ServiceComponentInfo/state'
        response = requests.get(url=path, headers=self.headers,
                                auth=(self.username, self.password), verify=self.verify_ssl)
        if not response.ok:
            LOG.error(f"Checking if {service_name} service is started failed ...")
            response.raise_for_status()

        data = json.loads(response.text)
        if data["ServiceComponentInfo"]["state"] == "STARTED":
            return True

        return False

    def stop_service_component(self, service_name, component_name, retry_num=3, wait_for_complete=True):
        """
        Stop the specified component of the given HDP service
        """

        path = f'{self.base_url}/clusters/{self.cluster_name}/services/{service_name.upper()}/components/{component_name}'
        payload = {
            "RequestInfo": {"context": f"Stop {component_name.upper()} in {service_name.upper()} service by am2cm"},
            "Body": {"ServiceComponentInfo": {"state": "INSTALLED"}}}

        result = self.__perform_request(path, payload, retry_num, wait_for_complete)
        result['success'] = result['retry_count'] < retry_num
        return result

    def regenerate_keytabs(self, retry_num=3):
        path = f'{self.base_url}/clusters/{self.cluster_name}?regenerate_keytabs=all'
        payload = {"Clusters": {"security_type": "KERBEROS"}}

        return self.__perform_and_wait(path, payload, retry_num) < retry_num

    def has_kdc_admin_credential(self):
        path = f'{self.base_url}/clusters/{self.cluster_name}/credentials/kdc.admin.credential'
        response = requests.get(url=path, headers=self.headers,
                                auth=(self.username, self.password), verify=self.verify_ssl)
        if response.status_code == 404:
            return False
        elif response.ok:
            return True

        response.raise_for_status()

    def set_kdc_admin_credential(self, admin_principal, admin_pwd, persist_type="temporary"):
        path = f'{self.base_url}/clusters/{self.cluster_name}/credentials/kdc.admin.credential'
        payload = {"Credential": {"principal": admin_principal, "key": admin_pwd, "type": persist_type}}

        response = requests.post(url=path, headers=self.headers, data=json.dumps(payload),
                                 auth=(self.username, self.password), verify=self.verify_ssl)
        if not response.ok:
            response.raise_for_status()
