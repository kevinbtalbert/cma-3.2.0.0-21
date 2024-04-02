# Reviewing prerequisites before migration

Before migrating from CDH 5 or CDH 6 to CDP Public Cloud, review the list of prerequisites that are required for the migration process.

- Ensure that the CMA server is deployed as described in [Setting up CMA server](docs/cma-server-setup.md).
- The CDH 5 source cluster minimum version requirement is CDH 5.16.1 and CDH 5.16.2 in case of HBase migration.
CDH 6 source cluster minimum version requirement is CDH 6.3.3.
- For HBase migration, you need either of the following parcels procured from Cloudera Professional Services : 
    - `CLOUDERA_OPDB_REPLICATION-1.0-1.CLOUDERA_OPDB_REPLICATION5.14.4.p0.31473501-el7.parcel`
    - `CLOUDERA_OPDB_REPLICATION-1.0-1.CLOUDERA_OPDB_REPLICATION6.3.3.p0.8959316-el7.parcel`
- For data and metadata migration, you need a Data Lake cluster already created in a CDP Public Cloud environment. To create a Data Lake cluster, you can follow the process described in [Registering an AWS environment](https://docs.cloudera.com/management-console/cloud/environments/topics/mc-environment-register-aws-ui.html).
- For a Hive workload migration, you need a Data Engineering Data Hub already created in a CDP Public Cloud environment. To create a Data Engineering Data Hub cluster, you can follow the process described in [Creating a cluster on AWS](https://docs.cloudera.com/data-hub/cloud/create-cluster-aws/topics/dh-cluster-options.html).
- You must use the [Cluster Connectivity Manager](https://docs.cloudera.com/management-console/cloud/connection-to-private-subnets/topics/mc-ccm-overview.html) to manually register the source CDH cluster as a classic cluster in the CDP Control Plane, following the process described in [Adding a CDH cluster (CCMv2)](https://docs.cloudera.com/management-console/cloud/classic-clusters/topics/mc-add-a-cdh-cluster.html)
- Information to gather before you begin the migration:
    - **For the source CDH cluster**: The Cloudera Manager URL, Admin username and password, SSH user, port, and private key of source nodes
    - **For the target CDP cluster/environment**: CDP Control Plane URL, Admin username and password, SSH user, port, and private key
    - **In S3**: S3 bucket access key and S3 bucket secret key, S3 credential name. Potentially, you might also need the S3 bucket base path for HDFS files, S3 bucket path for Hive external tables (these paths should auto-fill from the selected target cluster, but can be changed if needed)
- The Cloudera Manager node of the source CDH cluster must have Python 3.8.12 or higher installed.
- Redaction needs to be off in Cloudera Manager. To disable redaction in Cloudera Manager, you can follow the process described in [Disabling Redaction of sensitive information](https://docs.cloudera.com/cdp-private-cloud-base/7.1.9/configuring-clusters/topics/cm-api-disable-redaction.html).

> Note: You can also check [Migrating Data and Workloads Cloudera documentation](https://docs.cloudera.com/cdp-public-cloud/cloud/migrating.html) that describes all migration scenarios without the use of CMA. It gives you a wider scope in services and platfrom versions.
