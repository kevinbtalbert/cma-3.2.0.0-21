# Cloudera Migration Assistant

Cloudera Migration Assistant (CMA) is a user interface based extensible tool to assist Hadoop (CDH) users to easily migrate data, metadata and certain workloads to the various form factors of [Cloudera Data Platforms](https://www.cloudera.com/products/cloudera-data-platform.html).

> Important: The migration from CDH to CDP Public Cloud is in Technical Preview and not ready for production deployment. Cloudera encourages you to explore these features in non-production environments and provide feedback on your experiences through the *Cloudera Community Forums*.

## Before you begin
- Review the [Supported Platforms and Migration Paths](docs/supported-platforms.md)
- Review the [Supported Data and Workload Types](docs/supported-lift-and-shift-workloads.md)
- Complete the steps to [Set up CMA server](docs/cma-server-setup.md).

## Migrating from CDH to CDP Public Cloud

1. [Review prerequisites before migration](docs/cma-cdh-migration-prerequisites.md)
2. [Registering source clusters](docs/cma-new-source.md)
3. [Scanning the source cluster](docs/cma-scanning.md)
4. [Labeling datasets for migration](docs/cma-labeling.md)
5. [Registering target clusters](docs/cma-new-target.md)
6. [Migrating from source cluster to target cluster](docs/cma-new-migration.md)

## HDP to CDP Private Cloud Upgrade

1. [Review prerequisites](docs/hdp-prerequisites.md)
2. [Registration Ambari](docs/registering-ambari.md)
3. [Registering target clusters](docs/hdp-registering-target.md)
4. [Preparing Configurations](docs/preparing-configurations.md)
6. [Registering migration](docs/hdp-registering-migration.md)
7. [HDP-CDP PvC Base Upgrade](docs/cma-migration-execution-hdp.md)
8. [Backup](docs/backup.md) &  [Rollback](docs/rollback.md)

## Appendix
- [Troubleshooting](docs/troubleshooting.md)
