# Rollback HDP services 3.1.5 from CDP 7.1.x

To roll back you must first back up before starting the transition process, either manually or using the automated backup procedure.
.

The rollback restores your HDP cluster to the state it was in before the upgrade, including Kerberos and TLS/SSL configurations.

Before you start rolling back the CDP Private Cloud Base 7 to HDP, review the following information.

### Caveats

* Any data created after the backup is lost.
* Follow all the steps in the order presented in this topic. Cloudera recommends that you read through the backup and rollback steps before starting the backup process. You may want to create a detailed plan to help you anticipate potential problems.
* You can roll back to HDP  after upgrading to CDP Private Cloud Base 7 only if the HDFS upgrade has __not__ been finalized. The rollback restores your HDP cluster to the state it was in before the upgrade, including Kerberos and TLS/SSL configurations.
* These rollback steps depend on completed backups taken before upgrading to CDP. For steps where you need to restore the contents of a directory, clear the contents of the directory before copying the backed-up files to the directory. If you fail to do this, artifacts from the original upgrade can cause problems if you attempt the upgrade again after the rollback.

### Review Limitations

The rollback procedure has the following limitations.
* HDFS – If you have finalized the HDFS upgrade, you cannot roll back your cluster.
* Configuration changes, including the addition of new services or roles after the upgrade are not retained after rolling back Ambari. Cloudera recommends that you not make configuration changes or add new services and roles until you have finalized the HDFS upgrade and no longer require the option to roll back your upgrade.
* HBase – If your cluster is configured to use HBase replication, data written to HBase after the upgrade might not be replicated to peers when you start your rollback. This topic does not describe how to determine which, if any, peers have the replicated data and how to roll back that data. For more information about HBase replication, see HBase Replication.
* Kafka – Once the Kafka log format and protocol version configurations (the _inter.broker.protocol.version_ and _log.message.format.version_ properties) are set to the new version (or left blank, which means to use the latest version), Kafka rollback is not possible.

You have two options for rolling back

## Automated rollback

Cloudera recommend you to rehearse the automated rollback procedure on test clusters before doing it on production clusters.

1. Go to the _am2cm-ansible_ folder:
   * If you have used docker to upgrade, create a bash session inside the container and go to the am2cm-ansible folder: 
   ```shell
    docker container exec -it <container_id> /bin/bash
    cd am2cm-ansible/
   ```
   * If you have used local installation to upgrade, activate the python virtual environment and go to the am2cm-ansible folder: 
   ```shell
    source <path/to/am2cm-3.2.0.0>/venv/bin/activate 
    cd <path/to/am2cm-3.2.0.0>/am2cm-ansible/ 
   ```
   2. Execute the rollback playbooks: Running the rollback playbooks require you to specify an inventory and extra-vars file. You can review the previous upgrade steps to identify the files specific to your environment. 
      * Rollback Cloudera Manager to Ambari and restore /etc configuration directories 
      ```shell
      ansible-playbook -i <path/to/the/inventory.ini> playbooks/rollback/site.yml --extra-vars "@<path/to/the/vars.json>" --tags ambari-rollback,etc-config-rollback
      ```
      * Rollback Kerberos 
      ```shell
      ansible-playbook -i <path/to/the/inventory.ini> playbooks/rollback/site.yml --extra-vars "@<path/to/the/vars.json>" --tags kerberos-rollback
      ```
      * Rollback HDP Services:
       Run the following command for all HDP services installed in the cluster in 
      ```shell
      ansible-playbook -i <path/to/the/inventory.ini> playbooks/rollback/site.yml --extra-vars "@<path/to/the/vars.json>" --tags <service-rollback-tag>
      ```
The <service-rollback-tag> defaults to <service>-rollback, where <service> is replaced by the name of the HDP service to be rolled back.

For Ambari Infra Solr, the <service-rollback-tag> tag must be infra-solr-rollback.

You can skip some of the services that your cluster may not require. However, some services are dependent on each other. 
Rollback in the order listed below:
* zookeeper-rollback
* infra-solr-rollback
* ranger-rollback
* ranger-kms-rollback
* hdfs-rollback
* yarn-rollback
* kafka-rollback
* hbase-rollback
* atlas-rollback
* hive-rollback
* oozie-rollback

## Manual rollback

While automated rollback is faster, you can have full control on the rollback process using __Manual rollback__ of 
the two stage upgrade :
[HDP2](https://docs.cloudera.com/cdp-private-cloud-upgrade/latest/upgrade-hdp/topics/rollback-717sp1-to-717.html)
[HDP3](https://docs.cloudera.com/cdp-private-cloud-upgrade/latest/upgrade-hdp3-one-stage/topics/amb3-one-stage-manual-rollback.html)

