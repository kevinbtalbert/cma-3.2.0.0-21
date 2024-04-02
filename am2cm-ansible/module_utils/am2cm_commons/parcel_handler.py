import argparse
import logging
import sys

from ansible.module_utils.am2cm_commons.cdp_cluster import CDPCluster
from cm_client import ApiParcel, ApiParcelState

LOG = logging.getLogger(__name__)


def _extract_errors(parcel_info: ApiParcel):
    state: ApiParcelState = parcel_info.state
    return len(state.errors) if state.errors is not None else 0, state.errors


class ParcelHandler:
    def __init__(self, hostname: str, port: int, is_https: bool, verify_ssl: bool,
                 username: str, password: str, cluster_name: str):
        self.cluster = CDPCluster(
            hostname=hostname, port=port, is_https=is_https, verify_ssl=verify_ssl,
            username=username, password=password, cluster_name=cluster_name)

    def handle_parcel_distribution(self, parcel_product_name: str, parcel_version: str, parcel_repo: str):
        parcel_info: ApiParcel = self.cluster.get_parcel_info(parcel_product_name, parcel_version)

        if parcel_info is None and parcel_repo is not None:
            self.cluster.set_parcel_repo(parcel_repo)
            parcel_info: ApiParcel = self.cluster.get_parcel_info(parcel_product_name, parcel_version)

        if parcel_info is None:
            raise Exception(f'Parcel {parcel_product_name} with version {parcel_version} is missing!')

        LOG.info("PHASE: Download parcel")
        res, parcel_info = self.cluster.download_parcel(parcel_info)
        if not res:
            return False, f"Error during Parcel Download...Error was: {_extract_errors(parcel_info)[1]}"

        if parcel_info.stage == 'ACTIVATED':
            res, parcel_info = self.cluster.deactivate_parcel(parcel_info)
            if not res:
                return False, f"Error during Parcel Deactivation...Error was: {_extract_errors(parcel_info)[1]}"

        if parcel_info.stage == 'DISTRIBUTED':
            res, parcel_info = self.cluster.undistribute_parcel(parcel_info)
            if not res:
                return False, f"Error during Parcel Undistribution...Error was: {_extract_errors(parcel_info)[1]}"

        LOG.info("PHASE: Distribute parcel")
        res, parcel_info = self.cluster.distribute_parcel(parcel_info)
        if not res:
            return False, f"Error during Parcel Distribution...Error was: {_extract_errors(parcel_info)[1]}"

        err_count, errors = _extract_errors(parcel_info)
        if err_count != 0:
            return False, f"Error during parcel distribution. Error was {errors}"

        LOG.info("PHASE: Activate parcel")
        res, parcel_info = self.cluster.activate_parcel(parcel_info)
        if not res:
            return False, f"Error during Parcel Activation...Error was: {_extract_errors(parcel_info)[1]}"

        return res, f"Finished with handling {parcel_product_name}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hostname", dest="hostname", action="store", required=True)
    parser.add_argument("--port", dest="port", type=int, action="store", required=True)
    parser.add_argument("--username", default="admin", dest="username", action="store")
    parser.add_argument("--password", default="admin", dest="password", action="store")
    parser.add_argument("--cluster-name", dest="cluster_name", action="store", required=True)
    parser.add_argument("--https-enabled", dest="is_https", action="store_true", required=False)
    parser.add_argument("--verify-ssl", dest="verify_ssl", action="store_true")
    parser.add_argument("--parcel-display-name", default="Cloudera Runtime", dest="parcel_display_name", action="store")
    parser.add_argument("--parcel-version", default="7.1.7-1.cdh7.1.7.p1000.24349691", dest="parcel_version",
                        action="store")
    parser.add_argument("--parcel-repo", default="https://archive.cloudera.com/p/cdh7/7.1.7.1000/parcels/",
                        dest="parcel_repo", action="store")

    args = parser.parse_args()

    parcel_handler = ParcelHandler(args.hostname, args.port, args.is_https, args.veriy_ssl,
                                   args.username, args.password, args.cluster_name)

    parcel_handler.handle_parcel_distribution(parcel_product_name=args.parcel_display_name,
                                              parcel_version=args.parcel_version,
                                              parcel_repo=args.parcel_repo)


if __name__ == '__main__':
    sys.exit(main())
