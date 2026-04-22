"""Connector registry — plugin-style system for data source connectors."""
import logging
from typing import Any, Dict, List, Optional, Type

from .base import BaseConnector

log = logging.getLogger(__name__)


# Global type registry: maps source type string -> connector class
_CONNECTOR_TYPES: Dict[str, Type[BaseConnector]] = {}


def register(source_type: str):
    """Class decorator to register a connector type.

    Usage:
        @register("postgresql")
        class PostgresConnector(StructuredConnector):
            ...
    """
    def decorator(cls: Type[BaseConnector]):
        cls.source_type = source_type
        _CONNECTOR_TYPES[source_type] = cls
        return cls
    return decorator


class ConnectorRegistry:
    """Creates and manages connector instances from configuration."""

    def __init__(self):
        self._connectors: Dict[str, BaseConnector] = {}

    def load_from_config(self, sources: List[Dict[str, Any]]) -> None:
        """Instantiate connectors from sources.yaml config entries."""
        for source_cfg in sources:
            name = source_cfg.get("name", "")
            source_type = source_cfg.get("type", "")
            enabled = source_cfg.get("enabled", False)
            connection = source_cfg.get("connection", {})

            if not enabled:
                continue

            cls = _CONNECTOR_TYPES.get(source_type)
            if cls is None:
                log.warning(
                    "No connector registered for type '%s' (source '%s'). Skipping.",
                    source_type, name,
                )
                continue

            self._connectors[name] = cls(name=name, config=connection)

    def get(self, name: str) -> Optional[BaseConnector]:
        """Get a connector by its configured name."""
        return self._connectors.get(name)

    def get_by_type(self, source_type: str) -> List[BaseConnector]:
        """Get all connectors of a given type."""
        return [c for c in self._connectors.values() if c.source_type == source_type]

    def get_all(self) -> Dict[str, BaseConnector]:
        """Get all enabled connectors."""
        return dict(self._connectors)

    def get_structured(self) -> Dict[str, BaseConnector]:
        """Get all StructuredConnector instances."""
        from .base import StructuredConnector
        return {
            n: c for n, c in self._connectors.items()
            if isinstance(c, StructuredConnector)
        }

    def get_storage(self) -> Dict[str, BaseConnector]:
        """Get all StorageConnector instances."""
        from .base import StorageConnector
        return {
            n: c for n, c in self._connectors.items()
            if isinstance(c, StorageConnector)
        }

    def get_document(self) -> Dict[str, BaseConnector]:
        """Get all DocumentConnector instances."""
        from .base import DocumentConnector
        return {
            n: c for n, c in self._connectors.items()
            if isinstance(c, DocumentConnector)
        }

    def list_sources(self) -> List[Dict[str, str]]:
        """Return a summary of all registered connectors."""
        return [
            {
                "name": name,
                "type": conn.source_type,
                "connector_class": type(conn).__name__,
            }
            for name, conn in self._connectors.items()
        ]

    async def connect_all(self) -> Dict[str, bool]:
        """Connect all registered connectors. Returns name -> success. Fail-soft."""
        results: Dict[str, bool] = {}
        for name, conn in self._connectors.items():
            try:
                await conn.connect()
                results[name] = True
            except Exception:
                log.exception("Failed to connect source '%s'", name)
                results[name] = False
        return results

    async def disconnect_all(self) -> None:
        """Disconnect all connectors. Logs per-connector failures, never raises."""
        for name, conn in self._connectors.items():
            try:
                await conn.disconnect()
            except Exception:
                log.exception("Failed to disconnect source '%s'", name)

    async def health_check_all(self) -> Dict[str, bool]:
        """Run ``health_check()`` on every connector. Returns name -> healthy."""
        results: Dict[str, bool] = {}
        for name, conn in self._connectors.items():
            try:
                results[name] = bool(await conn.health_check())
            except Exception:
                log.exception("Health check failed for '%s'", name)
                results[name] = False
        return results
