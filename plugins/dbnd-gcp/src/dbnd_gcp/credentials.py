import logging

from google.auth import default

from cachetools import cached
from dbnd._core.plugin.dbnd_plugins import use_airflow_connections


logger = logging.getLogger(__name__)


@cached(cache={})
def get_gc_credentials():
    if use_airflow_connections():
        from dbnd_airflow_contrib.credentials_helper_gcp import GSCredentials

        gcp_credentials = GSCredentials()
        logger.debug(
            "getting gcp credentials from airflow connection '%s'"
            % gcp_credentials.gcp_conn_id
        )
        return gcp_credentials.get_credentials()
    else:
        logger.debug(
            "getting gcp credentials from environment using google.auth.default()"
        )
        credentials, _ = default()
        return credentials
