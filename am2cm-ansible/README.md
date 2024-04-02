# AM2CM ansible

Please make sure to check the currently supported ansible version in the [python requirements](requirements.txt).

Note: It's recommended to install these requirements into the venv you use for running ansible or your python environment
whichever you prefer
`pip3 install -r requirements.txt`

## How to run post-install step ansible playbook
`ansible-playbook -i inventories/<inventory>.ini site.yml --tags <post-install-step-tag-name>`

### concrete example
`ansible-playbook -i inventories/testing.ini site.yml --tags zookeeper-post-migration`

## How to run a utility ansible playbook
Some roles that can be used as utilities by themselves are provided as separate playbooks.
These can be found under the *utility-playbooks* directory.
Among them, the ones that are parameterized are **recommended** to be used with the **--extra-vars** ansible command line option.

### example 1, restart zookeeper
`ansible-playbook -i am2cm-ansible/inventories/testing.ini am2cm-ansible/utility-playbooks/restart_service.yml --extra-vars="service_name=zookeeper"`

### example 2, query cloudera manager for the configuration 'ranger_kafka_plugin_hdfs_audit_spool_directory' of the 'kafka' service
`ansible-playbook -i am2cm-ansible/inventories/testing.ini am2cm-ansible/utility-playbooks/query_configuration_from_service.yml --extra-vars="service_name=kafka configuration_name=ranger_kafka_plu
gin_hdfs_audit_spool_directory"`

## How to debug custom modules
When adding custom modules or modifying the already existing ones they can be debugged:
- you need a virtual environment setup w/ ansible, or have ansible installed into your local python site-packages
- you need to create a json file containing your input arguments, [see provided example args.json](additional-development-resources/args.json)
- probably the easiest way to debug is to setup a python configuration in your IDE where your single input parameter
will be the above mentioned input parameters json
- See also the [official documentation](https://docs.ansible.com/ansible/latest/dev_guide/developing_modules_general.html#verifying-your-module-code-locally)

## How to configure timeouts of restarting services, services commands, role commands, etc.
Timeout unit: seconds

Location: your `all.yml` or `extra vars` file

**Recommended Usage:**
  - configure service specific command_types and commands in service_specific_timeouts
  - if new command_type (i.e. role) is available for all services, add that to default_timeouts
  - service_specific_timeouts is an optional variable, if deleted all command_types are looked up in default_timeouts
  - customize by setting the `custom_timeout` variable when importing/including the command_type role

###Example - Given the following variables
```yaml
  service_specific_timeouts:
    hdfs:
      restart_service: 1
      run_service_command: 2
    ranger:
      SetupPluginServices: 3
      HdfsFinalizeUpgrade: 4
      run_role_command: 5
   default_timeouts:
     restart_service: 920
     run_role_command: 6920
     run_service_command: 666
```
###End result
```yaml
  timeouts:
    hdfs:
      restart_service: 1
      run_role_command: 6920
      run_service_command: 2
    ranger:
      HdfsFinalizeUpgrade: 4
      restart_service: 920
      run_role_command: 5
      run_service_command: 666
      SetupPluginServices: 3
```

