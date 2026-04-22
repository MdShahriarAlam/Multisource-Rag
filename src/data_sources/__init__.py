"""Data source connectors.

Importing this module registers all built-in connector types
with the ConnectorRegistry.
"""
from .base import BaseConnector, DocumentConnector, StorageConnector, StructuredConnector
from .registry import ConnectorRegistry, register

# Import connectors to trigger @register decorators
from .postgres_connector import PostgresConnector
from .bigquery_connector import BigQueryConnector
from .azure_blob_connector import AzureBlobConnector
from .azure_sql_connector import AzureSQLConnector
from .cosmos_connector import CosmosConnector
from .gcs_connector import GCSConnector
from .mysql_connector import MySQLConnector
from .local_file_connector import LocalFileConnector

__all__ = [
    "BaseConnector",
    "StructuredConnector",
    "StorageConnector",
    "DocumentConnector",
    "ConnectorRegistry",
    "register",
    "PostgresConnector",
    "BigQueryConnector",
    "AzureBlobConnector",
    "AzureSQLConnector",
    "CosmosConnector",
    "GCSConnector",
    "MySQLConnector",
    "LocalFileConnector",
]
