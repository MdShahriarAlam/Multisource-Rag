"""Google BigQuery data source connector."""
from typing import Any, Dict, List, Optional

from google.cloud import bigquery
from google.oauth2 import service_account

from ..models.schemas import TableSchema
from .base import StructuredConnector
from .registry import register


@register("bigquery")
class BigQueryConnector(StructuredConnector):
    """Connector for Google BigQuery."""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.client = None
        self.project_id = config["project_id"]
        self.dataset_id = config["dataset"]
        self._tables_cache: Optional[List[str]] = None

    async def connect(self) -> None:
        """Establish connection to BigQuery."""
        credentials = service_account.Credentials.from_service_account_file(
            self.config["credentials_file"]
        )
        self.client = bigquery.Client(
            credentials=credentials, project=self.project_id
        )

    async def disconnect(self) -> None:
        """Close BigQuery connection."""
        if self.client:
            self.client.close()
            self.client = None
        self._tables_cache = None

    async def execute_query(
        self, query: str, params: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """Execute a SQL query and return results."""
        if not self.client:
            await self.connect()

        job_config = None
        if params:
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter(None, "STRING", p)
                    for p in params
                ]
            )

        query_job = self.client.query(query, job_config=job_config)
        results = query_job.result()
        return [dict(row) for row in results]

    async def get_table_schema(self, table_name: str) -> TableSchema:
        """Get schema information for a table."""
        if not await self.validate_table_name(table_name):
            raise ValueError(f"Table '{table_name}' does not exist")

        if not self.client:
            await self.connect()

        table_ref = f"{self.project_id}.{self.dataset_id}.{table_name}"
        table = self.client.get_table(table_ref)

        columns = []
        for field in table.schema:
            columns.append(
                {
                    "column_name": field.name,
                    "data_type": field.field_type,
                    "is_nullable": "YES" if field.mode == "NULLABLE" else "NO",
                    "description": field.description or "",
                }
            )

        return TableSchema(
            source=self.name,
            table_name=table_name,
            columns=columns,
            primary_keys=[],
            foreign_keys=[],
        )

    async def list_tables(self) -> List[str]:
        """List all available tables."""
        if self._tables_cache is not None:
            return self._tables_cache

        if not self.client:
            await self.connect()

        dataset_ref = f"{self.project_id}.{self.dataset_id}"
        tables = self.client.list_tables(dataset_ref)
        self._tables_cache = [table.table_id for table in tables]
        return self._tables_cache

    async def get_sample_data(
        self, table_name: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get sample data from a table (validates table name first)."""
        if not await self.validate_table_name(table_name):
            raise ValueError(f"Table '{table_name}' does not exist")

        query = (
            f"SELECT * FROM "
            f"`{self.project_id}.{self.dataset_id}.{table_name}` "
            f"LIMIT {int(limit)}"
        )
        return await self.execute_query(query)
