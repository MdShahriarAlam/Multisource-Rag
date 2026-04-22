"""MySQL data source connector."""
import asyncio
from typing import Any, Dict, List, Optional

import pymysql
import pymysql.cursors

from ..models.schemas import TableSchema
from .base import StructuredConnector
from .registry import register


@register("mysql")
class MySQLConnector(StructuredConnector):
    """Connector for MySQL databases."""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.connection = None

    async def connect(self) -> None:
        """Establish connection to MySQL."""
        loop = asyncio.get_event_loop()

        def _connect():
            return pymysql.connect(
                host=self.config["host"],
                port=int(self.config.get("port", 3306)),
                user=self.config["user"],
                password=self.config["password"],
                database=self.config["database"],
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=True,
                charset="utf8mb4",
            )

        self.connection = await loop.run_in_executor(None, _connect)

    async def disconnect(self) -> None:
        """Close MySQL connection."""
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
            try:
                with self.connection.cursor() as cursor:
                    cursor.execute(query, params)
                    if cursor.description:
                        return list(cursor.fetchall())
                    return []
            except Exception:
                self.connection.rollback()
                raise

        return await loop.run_in_executor(None, _execute)

    async def get_table_schema(self, table_name: str) -> TableSchema:
        """Get schema information for a table."""
        if not await self.validate_table_name(table_name):
            raise ValueError(f"Table '{table_name}' does not exist")

        if not self.connection:
            await self.connect()

        loop = asyncio.get_event_loop()
        database = self.config["database"]

        def _get_schema():
            try:
                with self.connection.cursor() as cursor:
                    # Columns — alias to lowercase so TableSchema stays consistent
                    cursor.execute(
                        """
                        SELECT
                            COLUMN_NAME    AS column_name,
                            DATA_TYPE      AS data_type,
                            IS_NULLABLE    AS is_nullable,
                            COLUMN_DEFAULT AS column_default
                        FROM information_schema.COLUMNS
                        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                        ORDER BY ORDINAL_POSITION
                        """,
                        (database, table_name),
                    )
                    columns = list(cursor.fetchall())

                    # Primary keys
                    cursor.execute(
                        """
                        SELECT COLUMN_NAME
                        FROM information_schema.KEY_COLUMN_USAGE
                        WHERE TABLE_SCHEMA = %s
                          AND TABLE_NAME = %s
                          AND CONSTRAINT_NAME = 'PRIMARY'
                        ORDER BY ORDINAL_POSITION
                        """,
                        (database, table_name),
                    )
                    primary_keys = [row["COLUMN_NAME"] for row in cursor.fetchall()]

                    # Foreign keys
                    cursor.execute(
                        """
                        SELECT
                            kcu.COLUMN_NAME        AS column_name,
                            kcu.REFERENCED_TABLE_NAME  AS foreign_table_name,
                            kcu.REFERENCED_COLUMN_NAME AS foreign_column_name
                        FROM information_schema.KEY_COLUMN_USAGE AS kcu
                        JOIN information_schema.REFERENTIAL_CONSTRAINTS AS rc
                            ON kcu.CONSTRAINT_NAME   = rc.CONSTRAINT_NAME
                            AND kcu.CONSTRAINT_SCHEMA = rc.CONSTRAINT_SCHEMA
                        WHERE kcu.TABLE_SCHEMA = %s AND kcu.TABLE_NAME = %s
                          AND kcu.REFERENCED_TABLE_NAME IS NOT NULL
                        """,
                        (database, table_name),
                    )
                    foreign_keys = list(cursor.fetchall())

                    return columns, primary_keys, foreign_keys
            except Exception:
                self.connection.rollback()
                raise

        columns, primary_keys, foreign_keys = await loop.run_in_executor(
            None, _get_schema
        )

        return TableSchema(
            source=self.name,
            table_name=table_name,
            columns=columns,
            primary_keys=primary_keys,
            foreign_keys=foreign_keys,
        )

    async def list_tables(self) -> List[str]:
        """List all user tables in the connected database."""
        results = await self.execute_query(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """
        )
        return [row["TABLE_NAME"] for row in results]

    async def get_sample_data(
        self, table_name: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get sample rows from a table."""
        if not await self.validate_table_name(table_name):
            raise ValueError(f"Table '{table_name}' does not exist")

        if not self.connection:
            await self.connect()

        # validate_table_name confirms the table exists via list_tables(),
        # so backtick-escaping the already-validated name is safe.
        safe_name = table_name.replace("`", "")
        query = f"SELECT * FROM `{safe_name}` LIMIT %s"

        loop = asyncio.get_event_loop()

        def _execute():
            try:
                with self.connection.cursor() as cursor:
                    cursor.execute(query, (limit,))
                    if cursor.description:
                        return list(cursor.fetchall())
                    return []
            except Exception:
                self.connection.rollback()
                raise

        return await loop.run_in_executor(None, _execute)

    async def test_connection(self) -> bool:
        """Verify the connection is alive."""
        try:
            await self.execute_query("SELECT 1")
            return True
        except Exception:
            return False
