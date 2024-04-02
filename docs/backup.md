# Backup HDP services from CDP 7.1.x

You should always take a backup of a production HDP cluster before rolling back from CDP to HDP.

# Automated Backup

The CMA Server takes the backup of everything except Ambari 
as it is not affected by the upgrade process. If you still want to back up Ambari see either  [HDP3 Back Up Ambari documentation](http://docs-dev.cloudera.com.s3.amazonaws.com/cdp-private-cloud-upgrade/latest/upgrade-hdp3/topics/amb3_backup_ambari_hdp3.html) 
or  [HDP2 Back Up Ambari documentation](https://docs-dev.cloudera.com/cdp-private-cloud-upgrade/latest/upgrade-hdp/topics/amb_backup_ambari.html).
The backup handles HDP services in HDP services. If you have mpacks or other application level services you need add those to the transition or do it separately.

# Manual Backup
In case you skipped the Automated backup steps in CMA, then you can manually perform the following steps:
* Backing up [HDP2](https://docs-dev.cloudera.com/cdp-private-cloud-upgrade/latest/upgrade-hdp/topics/amb_backup_hdp2_services.html)/[HDP3](https://docs-dev.cloudera.com/cdp-private-cloud-upgrade/latest/upgrade-hdp3/topics/amb3_backup_hdp3_services.html) cluster 
* Backup /etc config symlinks for all HDP services on all hosts by running the following command:
```shell
cp -d /etc/_\<service\>_/conf /etc/_\<service\>_/conf.hdp.bak
```
* Backup _/etc/krb5.conf_ by running the following command: 
```shell
cp /etc/krb5.conf /etc/krb5.conf.bak
```
