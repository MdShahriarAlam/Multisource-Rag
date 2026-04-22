"""Azure Cosmos DB connector for semi-structured data."""
import asyncio
from typing import Any, Dict, List, Optional

from azure.cosmos import CosmosClient, exceptions

from .base import DocumentConnector
from .registry import register


@register("azure_cosmos")
class CosmosConnector(DocumentConnector):
    """Connector for Azure Cosmos DB (SQL API)."""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.client = None
        self.database = None
        self.database_name = config.get("database", "")

    async def connect(self) -> None:
        """Establish connection to Cosmos DB."""
        loop = asyncio.get_event_loop()

        def _connect():
            self.client = CosmosClient(
                url=self.config["endpoint"],
                credential=self.config["key"],
            )
            self.database = self.client.get_database_client(self.database_name)

        await loop.run_in_executor(None, _connect)

    async def disconnect(self) -> None:
        """Close Cosmos DB connection."""
        # CosmosClient doesn't require explicit close
        self.client = None
        self.database = None

    async def list_collections(self) -> List[str]:
        """List all containers in the database."""
        if not self.database:
            await self.connect()

        loop = asyncio.get_event_loop()

        def _list():
            return [c["id"] for c in self.database.list_containers()]

        return await loop.run_in_executor(None, _list)

    async def query_documents(
        self,
        collection: str,
        query: str,
        parameters: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Query documents using Cosmos DB SQL API."""
        if not self.database:
            await self.connect()

        loop = asyncio.get_event_loop()
        container = self.database.get_container_client(collection)

        def _query():
            items = container.query_items(
                query=query,
                parameters=parameters or [],
                enable_cross_partition_query=True,
            )
            return [dict(item) for item in items]

        return await loop.run_in_executor(None, _query)

    async def get_document(
        self, collection: str, doc_id: str, partition_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get a single document by ID."""
        if not self.database:
            await self.connect()

        loop = asyncio.get_event_loop()
        container = self.database.get_container_client(collection)

        def _get():
            return dict(
                container.read_item(
                    item=doc_id,
                    partition_key=partition_key or doc_id,
                )
            )

        return await loop.run_in_executor(None, _get)

    async def get_collection_schema_sample(
        self, collection: str, sample_size: int = 5
    ) -> Dict[str, Any]:
        """Infer schema by sampling documents from a collection."""
        docs = await self.query_documents(
            collection,
            f"SELECT TOP {int(sample_size)} * FROM c",
        )

        # Union all keys across sampled documents
        all_keys: Dict[str, set] = {}
        for doc in docs:
            for key, value in doc.items():
                if key.startswith("_"):  # skip system fields
                    continue
                type_name = type(value).__name__
                if key not in all_keys:
                    all_keys[key] = set()
                all_keys[key].add(type_name)

        return {
            "collection": collection,
            "sample_size": len(docs),
            "fields": {k: list(v) for k, v in all_keys.items()},
        }
