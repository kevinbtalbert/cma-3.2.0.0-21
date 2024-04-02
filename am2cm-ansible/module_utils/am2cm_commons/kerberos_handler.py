import argparse
import logging
import sys

from ansible.module_utils.am2cm_commons.cdp_cluster import CDPCluster

LOG = logging.getLogger(__name__)


class KerberosHandler:
    def __init__(self, cluster: CDPCluster, use_ad: bool, kdc_host: str, realm_name: str, ad_domain: str,
                 kerberos_admin_user: str, kerberos_admin_password: str, os_type: str):
        self.cluster = cluster
        self.use_ad = use_ad
        self.kdc_host = kdc_host
        self.realm_name = realm_name
        self.ad_domain = ad_domain
        self.kerberos_admin_user = kerberos_admin_user
        self.kerberos_admin_password = kerberos_admin_password
        self.os_type = os_type

    def set_kerberos_configurations(self):
        kdc_type = 'Active Directory' if self.use_ad else 'MIT KDC'
        cm_kerberos_configs = {"MAX_RENEW_LIFE": "0",
                               "KDC_TYPE": kdc_type,
                               "KDC_HOST": self.kdc_host,
                               "SECURITY_REALM": self.realm_name,
                               "KRB_MANAGE_KRB5_CONF": "true"
                               }
        if self.use_ad:
            ad_configs = {
                "KDC_ADMIN_HOST": self.kdc_host,
                "AD_KDC_DOMAIN": self.ad_domain,
                "AD_DELETE_ON_REGENERATE": "true"
            }
            cm_kerberos_configs.update(ad_configs)
            if self.os_type.lower().startswith('suse'):
                ad_configs["KRB_LIBDEFAULTS_SAFETY_VALVE"] = "default_ccache_name = FILE:/tmp/krb5cc_%{uid}"
            cm_kerberos_configs.update(ad_configs)

        return self.cluster.update_cm_config(cm_kerberos_configs)

    def configure_cm_for_kerberos(self):
        if self.use_ad:
            LOG.info("Importing Kerberos Admin Credentials for AD...")
            res, output = self.cluster.import_kerberos_admin_credentials(
                f"{self.kerberos_admin_user}@{self.realm_name}",
                self.kerberos_admin_password)
            if not res:
                return res, output

        LOG.info("Configuring CM for Kerberos...")
        res, output = self.cluster.configure_cluster_for_kerberos()
        LOG.info(output)
        if not res:
            return res, output

        LOG.info("Stopping CM Management Service...")
        res, output = self.cluster.stop_cm_management_service()
        LOG.info(output)
        if not res:
            return res, output

        LOG.info("Deleting existing credentials...")
        res, output = self.cluster.delete_kerberos_credentials()
        LOG.info(output)
        if not res:
            return res, output

        LOG.info("Generating Kerberos credentials...")
        res, output = self.cluster.generate_missing_kerberos_credentials()
        LOG.info(output)
        if not res:
            return res, output

        LOG.info("Deploy kerberos client configuration to cluster...")
        res, output = self.cluster.deploy_cluster_client_config()
        LOG.info(output)
        if not res:
            return res, output

        LOG.info("Starting CM Management service...")
        return self.cluster.start_cm_management_service()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hostname", dest="hostname", action="store", required=True)
    parser.add_argument("--port", dest="port", type=int, action="store", required=True)
    parser.add_argument("--username", default="admin", dest="username", action="store")
    parser.add_argument("--password", default="admin", dest="password", action="store")
    parser.add_argument("--cluster-name", dest="cluster_name", action="store", required=True)
    parser.add_argument("--https-enabled", dest="is_https", action="store_true", required=False)
    parser.add_argument("--verify-ssl", dest="verify_ssl", action="store_true")
    parser.add_argument("--use-ad", dest="use_ad", action="store_true")
    parser.add_argument("--kdc-host", dest="kdc_host", action="store", required=True)
    parser.add_argument("--realm-name", dest="realm_name", action="store", required=True)
    parser.add_argument("--ad-domain", dest="ad_domain", action="store", required=False)
    parser.add_argument("--kerberos-admin-user", dest="kerberos_admin_user", action="store", required=True)
    parser.add_argument("--kerberos-admin-password", dest="kerberos_admin_password", action="store", required=True)
    parser.add_argument("--os-type", dest="os_type", action="store", required=True)

    args = parser.parse_args()

    cluster = CDPCluster(args.hostname, args.port, args.is_https, args.verify_ssl,
                         args.username, args.port, args.cluster_name)

    kerberos_handler = KerberosHandler(cluster, args.use_ad, args.kdc_host, args.realm_name, args.ad_domain,
                                       args.kerberos_admin_user, args.kerberos_admin_password, args.os_type)

    res, out = kerberos_handler.set_kerberos_configurations()
    if not res:
        LOG.error(out)
        sys.exit(1)

    LOG.warning(
        "Prerequisite: CM keytab and CM principal file has to be already in place at /etc/cloudera-scm-server/!")
    res, out = kerberos_handler.configure_cm_for_kerberos()
    if not res:
        LOG.error(out)
        sys.exit(2)

    sys.exit(0)


if __name__ == '__main__':
    sys.exit(main())
