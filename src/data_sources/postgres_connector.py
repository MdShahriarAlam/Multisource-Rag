"""PostgreSQL data source connector."""
import asyncio
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor

from ..models.schemas import TableSchema
from .base import StructuredConnector
from .registry import register


@register("postgresql")
class PostgresConnector(StructuredConnector):
    """Connector for PostgreSQL databases."""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.connection = None

    async def connect(self) -> None:
        """Establish connection to PostgreSQL."""
        loop = asyncio.get_event_loop()
        self.connection = await loop.run_in_executor(
            None,
            psycopg2.connect,
            (
                f"host={self.config['host']} "
                f"port={self.config.get('port', 5432)} "
                f"dbname={self.config['database']} "
                f"user={self.config['user']} "
                f"password={self.config['password']}"
            ),
        )

    async def disconnect(self) -> None:
        """Close PostgreSQL connection."""
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
                with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, params)
                    if cursor.description:
                        return [dict(row) for row in cursor.fetchall()]
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

        def _get_schema():
            try:
                with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Columns
                    cursor.execute(
                        """
                        SELECT column_name, data_type, is_nullable, column_default
                        FROM information_schema.columns
                        WHERE table_name = %s
                        ORDER BY ordinal_position
                        """,
                        (table_name,),
                    )
                    columns = [dict(row) for row in cursor.fetchall()]

                    # Primary keys
                    cursor.execute(
                        """
                        SELECT a.attname
                        FROM pg_index i
                        JOIN pg_attribute a
                            ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                        WHERE i.indrelid = %s::regclass AND i.indisprimary
                        """,
                        (table_name,),
                    )
                    primary_keys = [row["attname"] for row in cursor.fetchall()]

                    # Foreign keys
                    cursor.execute(
                        """
                        SELECT
                            kcu.column_name,
                            ccu.table_name AS foreign_table_name,
                            ccu.column_name AS foreign_column_name
                        FROM information_schema.table_constraints AS tc
                        JOIN information_schema.key_column_usage AS kcu
                            ON tc.constraint_name = kcu.constraint_name
                        JOIN information_schema.constraint_column_usage AS ccu
                            ON ccu.constraint_name = tc.constraint_name
                        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name = %s
                        """,
                        (table_name,),
                    )
                    foreign_keys = [dict(row) for row in cursor.fetchall()]

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
        """List all available tables."""
        results = await self.execute_query(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """
        )
        return [row["table_name"] for row in results]

    async def get_sample_data(
        self, table_name: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get sample data from a table (safe from SQL injection)."""
        if not await self.validate_table_name(table_name):
            raise ValueError(f"Table '{table_name}' does not exist")

        query = sql.SQL("SELECT * FROM {} LIMIT %s").format(
            sql.Identifier(table_name)
        )

        if not self.connection:
            await self.connect()

        loop = asyncio.get_event_loop()

        def _execute():
            try:
                with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, (limit,))
                    if cursor.description:
                        return [dict(row) for row in cursor.fetchall()]
                    return []
            except Exception:
                self.connection.rollback()
                raise

        return await loop.run_in_executor(None, _execute)
