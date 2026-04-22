"""Azure SQL Database connector."""
import asyncio
from typing import Any, Dict, List, Optional

import pyodbc

from ..models.schemas import TableSchema
from .base import StructuredConnector
from .registry import register


@register("azure_sql")
class AzureSQLConnector(StructuredConnector):
    """Connector for Azure SQL Database."""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.connection = None

    def _build_connection_string(self) -> str:
        server = self.config["server"]
        database = self.config["database"]
        username = self.config["username"]
        password = self.config["password"]
        driver = self.config.get("driver", "{ODBC Driver 18 for SQL Server}")
        return (
            f"DRIVER={driver};"
            f"SERVER={server};"
            f"DATABASE={database};"
            f"UID={username};"
            f"PWD={password};"
            "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
        )

    async def connect(self) -> None:
        """Establish connection to Azure SQL."""
        loop = asyncio.get_event_loop()
        conn_str = self._build_connection_string()
        self.connection = await loop.run_in_executor(
            None, pyodbc.connect, conn_str
        )

    async def disconnect(self) -> None:
        """Close Azure SQL connection."""
        if self.connection:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.connection.close)
            self.connection = None

    async def execute_query(
        self, query: str, params: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """Execute a SQL query with optional parameters."""
        if not self.connection:
            await self.connect()

        loop = asyncio.get_event_loop()

        def _execute():
            cursor = self.connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            if cursor.description:
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
            return []

        return await loop.run_in_executor(None, _execute)

    async def get_table_schema(self, table_name: str) -> TableSchema:
        """Get schema information for a table."""
        if not await self.validate_table_name(table_name):
            raise ValueError(f"Table '{table_name}' does not exist")

        columns = await self.execute_query(
            """
            SELECT COLUMN_NAME as column_name,
                   DATA_TYPE as data_type,
                   IS_NULLABLE as is_nullable,
                   COLUMN_DEFAULT as column_default
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = ?
            ORDER BY ORDINAL_POSITION
            """,
            (table_name,),
        )

        # Primary keys
        pk_rows = await self.execute_query(
            """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE OBJECTPROPERTY(OBJECT_ID(CONSTRAINT_NAME), 'IsPrimaryKey') = 1
              AND TABLE_NAME = ?
            """,
            (table_name,),
        )
        primary_keys = [r["COLUMN_NAME"] for r in pk_rows]

        # Foreign keys
        fk_rows = await self.execute_query(
            """
            SELECT
                kcu.COLUMN_NAME as column_name,
                ccu.TABLE_NAME as foreign_table_name,
                ccu.COLUMN_NAME as foreign_column_name
            FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                ON rc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
            JOIN INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE ccu
                ON rc.UNIQUE_CONSTRAINT_NAME = ccu.CONSTRAINT_NAME
            WHERE kcu.TABLE_NAME = ?
            """,
            (table_name,),
        )

        return TableSchema(
            source=self.name,
            table_name=table_name,
            columns=columns,
            primary_keys=primary_keys,
            foreign_keys=fk_rows,
        )

    async def list_tables(self) -> List[str]:
        """List all available tables."""
        results = await self.execute_query(
            """
            SELECT TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME
            """
        )
        return [row["TABLE_NAME"] for row in results]

    async def get_sample_data(
        self, table_name: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get sample data from a table (validates table name)."""
        if not await self.validate_table_name(table_name):
            raise ValueError(f"Table '{table_name}' does not exist")

        # T-SQL uses TOP instead of LIMIT
        # table_name is validated above, safe to interpolate
        return await self.execute_query(
            f"SELECT TOP {int(limit)} * FROM [{table_name}]"
        )
