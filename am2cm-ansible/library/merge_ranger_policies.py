#!/usr/bin/python

import json
import logging
import os

import requests
import urllib3
from ansible.module_utils.am2cm_commons.logging_utils import configure_logging
from ansible.module_utils.basic import AnsibleModule
from requests.auth import AuthBase, HTTPBasicAuth

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

configure_logging(os.path.basename(__file__).replace(".py", "-module.log"))
LOG = logging.getLogger(__name__)


class PolicyMerger:
    CREATE_POLICY_PATH = '/service/public/v2/api/policy/apply'
    POLICY_REPO_PATH = '/service/plugins/policies/service/'
    ALL_REPOSITORIES_PATH = '/service/plugins/services'
    INDIVIDUAL_POLICY_PATH = '/service/plugins/policies/'
    UPSERT_PARAMS = {"mergeIfExists": "true"}

    def __init__(self, module: AnsibleModule, result: dict):
        self.module = module
        self.result = result
        self.auth = HTTPBasicAuth(module.params['ranger_admin_user'], module.params['ranger_admin_password'])
        self.verify = module.params['verify_ssl']
        self.get_policy_repo_url_prefix = module.params['ranger_load_balancer_url'] + self.POLICY_REPO_PATH
        self.upsert_policy_url = module.params['ranger_load_balancer_url'] + self.CREATE_POLICY_PATH

    def get_mappings_to_merge(self):
        """
        The goal of this function is to:
            - create a dict which looks like this:
              { <service_name>:
                   { 'latest_policy_repo_id': <id>,
                     'legacy_policy_repo_id': <id>,
                     'legacy_policy_name': <name> },
                ...
              }
            - filter output so that only those elements remain
              which contain both new and legacy keys (there may be services which
              only have one or the other, thus don't have to be merged)
        :return: Mappings between new and legacy policies
        """
        params = self.module.params
        all_ranger_repos = requests.get(params['ranger_load_balancer_url'] + self.ALL_REPOSITORIES_PATH,
                                        auth=self.auth, verify=self.verify).json()
        legacy_to_new_policy_mapping_by_type = {}
        for service in all_ranger_repos['services']:
            if service['type'] not in legacy_to_new_policy_mapping_by_type:
                legacy_to_new_policy_mapping_by_type[service['type']] = {}
            if "cm_" in service['name']:
                legacy_to_new_policy_mapping_by_type[service['type']]['latest_policy_repo_id'] = service['id']
            elif params['legacy_policy_prefix'] in service['name']:
                legacy_to_new_policy_mapping_by_type[service['type']]['legacy_policy_name'] = service['name']
                legacy_to_new_policy_mapping_by_type[service['type']]['legacy_policy_repo_id'] = service['id']

        return dict((k, v) for (k, v) in legacy_to_new_policy_mapping_by_type.items()
                    if 'legacy_policy_repo_id' in v and 'latest_policy_repo_id' in v)

    def get_policy_repo_from_url_by_id(self, repo_id: int):
        download_url = self.get_policy_repo_url_prefix + str(repo_id)
        policy_repo = requests.get(download_url, auth=self.auth, verify=self.verify)  # download new policy json by ID
        if policy_repo.status_code != 200:
            self.module.fail_json(
                msg=f"Could not download ranger policy repositories via: {download_url}", **self.result)
        return policy_repo.json()

    def __toggle_policy_lock(self, lock: bool, policy_list: list):
        directly_modify_policy_url = self.module.params['ranger_load_balancer_url'] + self.INDIVIDUAL_POLICY_PATH
        for policy in policy_list:
            policy['isDenyAllElse'] = lock
            policy_response = requests.put(directly_modify_policy_url+str(policy['id']),
                                                  json=policy, auth=self.auth, verify=self.verify)
            if policy_response.status_code == 200:
                LOG.info(f"Successfully {'enabled' if lock else 'disabled'} isDenyAllElse for policy '{policy['name']}'"
                         f" in service {policy['service']}")
            else:
                self.module.fail_json(msg=f"Couldn't modify policy{policy['name']} "
                                          f"in service {policy['service']}", **self.result)

    def _unlock_policies(self, policy_list: list):
        self.__toggle_policy_lock(False, policy_list)

    def _lock_policies(self, policy_list: list):
        self.__toggle_policy_lock(True, policy_list)

    def merge_policies(self, policy_mapping):
        """
        Merge new policies into legacy policies.
        This is done by taking the new policies jsons, modifying their names to the legacy policy names &
        sending an upsert request to Ranger with a 'mergeIfExists=true' parameter
        :param policy_mapping: Contains mapping between legacy & latest policy IDs and legacy names for the upsert
        :return:
        """
        # Some legacy policies may be locked by the 'isDenyAllElse=true' property. These need to be unlocked first
        legacy_policy_repo = self.get_policy_repo_from_url_by_id(policy_mapping['legacy_policy_repo_id'])
        # The latest policies which contents will be upserted
        new_policy_repo = self.get_policy_repo_from_url_by_id(policy_mapping['latest_policy_repo_id'])

        # make sure that the legacy policies are unlocked to be upsertable
        legacy_policies_with_lock = [policy for policy in legacy_policy_repo['policies'] if policy['isDenyAllElse']]
        self._unlock_policies(legacy_policies_with_lock)

        # do merge/upsert
        self.__merge_latest_policy_repo_into_legacy_repo(new_policy_repo, policy_mapping['legacy_policy_name'])

        # relock after merge/upsert
        self._lock_policies(legacy_policies_with_lock)

    def __merge_latest_policy_repo_into_legacy_repo(self, new_policy_repo, legacy_policy_name):
        for policy in new_policy_repo['policies']:
            upsert_policy = dict(policy)  # copy downloaded new policy into tmp var
            upsert_policy['service'] = legacy_policy_name  # re-write field to legacy policy name

            upsert_response = requests.post(self.upsert_policy_url, json=upsert_policy,
                                            auth=self.auth, verify=self.verify,
                                            params=self.UPSERT_PARAMS)  # POST it w/ mergeIfExists param
            if upsert_response.status_code == 200:
                self.result['message'] += f"Successfully added {policy['name']} policy " \
                                          f"from {policy['service']} to {upsert_policy['service']}\n"
            else:
                self.module.fail_json(msg=f"Couldn't add {policy['name']} policy "
                                          f"from {policy['service']} to {upsert_policy['service']}", **self.result)


def run_module():
    module_args = dict(
        legacy_policy_prefix=dict(type='str', required=True),
        ranger_load_balancer_url=dict(type='str', required=True),
        ranger_admin_user=dict(type='str', required=False, default='admin'),
        ranger_admin_password=dict(type='str', required=True),
        verify_ssl=dict(type='bool', required=False, default=True)
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
    # ####################################################################
    policy_merger = PolicyMerger(module, result)

    mappings_to_merge = policy_merger.get_mappings_to_merge()

    for _, service_policy_mapping in mappings_to_merge.items():
        policy_merger.merge_policies(service_policy_mapping)

    module.exit_json(**result)  # upon reaching this point, we exit without errors


def main():
    run_module()


if __name__ == '__main__':
    main()
