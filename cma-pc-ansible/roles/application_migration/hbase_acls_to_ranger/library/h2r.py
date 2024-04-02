#!/usr/bin/env python
import os
import sys
import re
import itertools
import json
import logging
from datetime import datetime

from ansible.module_utils.am2cm_commons.logging_utils import configure_logging, get_transition_log_dir
from ansible.module_utils.basic import AnsibleModule

configure_logging(os.path.basename(__file__).replace(".py", "-module.log"))
LOG = logging.getLogger(__name__)

def get_acls_from_file(hbase_file):
    acls = []
    with open(hbase_file) as f:
        for line in f:
           acl = extract_params(line)
           if acl:
              acls.append(acl)
           else:
               print("WARN: could not parse line {}:".format(hbase_file))
               print(line)
    return acls

def extract_params(s):
    m = re.search(r"([\w:@]+)\s*column=l:(.+), timestamp=[\d\-T:.+]+, value=([ARWXC]+)", s)
    if m:
        resource = m.group(1)
        identity = m.group(2)
        permissions = m.group(3)
        return (resource, identity, permissions)
    else:
        return None

def unfold_accesses(s):
    accesses = []
    for a in s:
        if a == 'R':
            accesses.append({ "type": "read" , "isAllowed": True })
        if a == 'W':
            accesses.append({ "type": "write" , "isAllowed": True })
        if a == 'C':
            accesses.append({ "type": "create" , "isAllowed": True })
        if a == 'X':
            accesses.append({ "type": "execute" , "isAllowed": True })
        if a == 'A':
            accesses.append({ "type": "admin" , "isAllowed": True })
    return accesses

def get_policy_items(acls):
    policy_items = []
    for acl in acls:
         identity = acl[1]
         access_str = acl[2]
         accesses = unfold_accesses(acl[2])
         users = []
         groups = []
         is_delegate_admin = 'A' in access_str
         if identity.startswith('@'):
             groups.append(identity.lstrip('@'))
         else:
             users.append(identity)

         policy_item = {
             "accesses": accesses,
             "users": users,
             "groups": groups,
             "roles": [],
             "conditions": [],
             "delegateAdmin": is_delegate_admin
         }
         policy_items.append(policy_item)
    return policy_items

def get_policies(acls, today):
    policies = []
    count=0
    for key, group in itertools.groupby(acls, lambda x: x[0]):
        count += 1
        policy_items = get_policy_items(group)
        table = key
        if table.startswith('@'):
            table = table.lstrip('@') + ":*"
        resource = {
            "table": { "values": [ table ] },
            "column-family": { "values": [ "*" ] },
            "column": { "values": [ "*" ] }
        }
        labels = [ "h2r", "generated:"+today ]
        policy = {
            "serviceType": "hbase",
            "service": "cm_hbase",
            "name": table + " imported acl# " + str(count),
            "policyLabels": labels,
            "resources": resource,
            "policyItems" : policy_items
        }
        policies.append(policy)
    return policies

def write_json(ranger_dict, ranger_file):
    with open(ranger_file, "w") as f:
        json.dump(ranger_dict, f, indent=2)
        print("{} file generated".format(ranger_file))


def run_module():
    module_args = dict(
        input_hbase_acls_file=dict(type='str', required=True),
        output_ranger_policy_file=dict(type='str', required=True),
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
    result['original_message'] = json.dumps(module.params)  # concatenate the params here, if there were any...
    LOG.info("inputs: {}".format(result['original_message']))

    input_hbase_acls_file = module.params['input_hbase_acls_file']
    output_ranger_policy_file = module.params['output_ranger_policy_file']

    if not os.path.exists(input_hbase_acls_file):
        module.fail_json(msg="input_hbase_acls_file {} does not exist".format(input_hbase_acls_file))

    today = datetime.today().strftime('%Y-%m-%d_%H:%M')

    acls = get_acls_from_file(input_hbase_acls_file)
    policies = get_policies(acls, today)
    ranger_dict = {"policies" : policies}
    if not policies:
        LOG.warn("No policies were generated! Maybe something went wrong")
    write_json(ranger_dict, output_ranger_policy_file)

    result['changed'] = True
    result["message"] = "Results saved to {}".format(output_ranger_policy_file)
    module.exit_json(**result)


def main():
  run_module()


if __name__ == '__main__':
  main()
