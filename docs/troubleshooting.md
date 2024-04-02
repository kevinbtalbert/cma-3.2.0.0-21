# Troubleshooting
This section provides you a list of possible causes and solutions to debug and resolve issues that you might face while upgrading HDP to CDP Private Cloud Base cluster.

## Accessing CMA root folder in Docker
If you used docker to upgrade, create a bash session inside the container and go to the _am2cm_ folder by running the following command:
```shell
docker exec -it <container_id> bash
```
## Examining CMA Server logs
Access the CMA root folder in docker. The AM2CM (CMA) server logs are in the _$AM2CM_ROOT_ directory with the name _cma-server.log_.

## Examining Transition Data
Access the CMA root folder in docker. Use the transition id of your transition to enter _$AM2CM_ROOT/data/<transition id>_

## Adding or removing transition steps
Access the CMA root folder in docker. Run the following command:
```shell
cd cma-server/config/transitions
```
You will see transition-definition.yml

## Manually editing Ansible input parameters
Access the CMA root folder in docker. Use the _data/\<transition_id\>_ directory within _$AM2CM_ROOT_. 


## Editing transition parameters

* __\<transition id\>-inventory.ini__: Inventory file with the hostnames and roles
* __\<transition id\>-vars.json & group_vars/__: Ansible input that is extracted during the registration process
* __\<transition id\>-user-settings.ini__: Input used by the am2cm tool. For more information, see Transitioning HDP 3.1.5 cluster to CDP Private Cloud Base 7.1.x cluster using the AM2CM tool.
* __conf/__: Other configurations used by the am2cm tool
* __logs/__: Logs from the ansible and tools used during the transition

## Rewriting the Ansible scripts
You can change and add new Ansible scripts. All scripts are located in the folder _am2cm-ansible_. To change the ansible scripts, grep recursively for the tags that you want to change.

