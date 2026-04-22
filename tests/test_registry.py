"""Tests for the connector registry."""
import pytest
from src.data_sources.registry import ConnectorRegistry, _CONNECTOR_TYPES
from tests.conftest import MockStructuredConnector, MockStorageConnector


def test_registry_load_from_config():
    """Test loading connectors from config entries."""
    # Register mock types
    _CONNECTOR_TYPES["mock_sql"] = MockStructuredConnector
    _CONNECTOR_TYPES["mock_storage"] = MockStorageConnector

    config = [
        {"name": "db1", "type": "mock_sql", "enabled": True, "connection": {}},
        {"name": "store1", "type": "mock_storage", "enabled": True, "connection": {}},
        {"name": "disabled", "type": "mock_sql", "enabled": False, "connection": {}},
    ]

    reg = ConnectorRegistry()
    reg.load_from_config(config)

    assert "db1" in reg.get_all()
    assert "store1" in reg.get_all()
    assert "disabled" not in reg.get_all()

    # Clean up
    _CONNECTOR_TYPES.pop("mock_sql", None)
    _CONNECTOR_TYPES.pop("mock_storage", None)


def test_registry_get_by_category(mock_registry):
    """Test getting connectors by category."""
    structured = mock_registry.get_structured()
    storage = mock_registry.get_storage()

    assert "mock_db" in structured
    assert "mock_store" in storage
    assert "mock_db" not in storage
    assert "mock_store" not in structured


def test_registry_list_sources(mock_registry):
    """Test listing all registered sources."""
    sources = mock_registry.list_sources()
    assert len(sources) == 2
    names = [s["name"] for s in sources]
    assert "mock_db" in names
    assert "mock_store" in names


def test_registry_get_nonexistent(mock_registry):
    """Test getting a non-existent connector."""
    assert mock_registry.get("nonexistent") is None


def test_registry_unknown_type():
    """Test loading config with unknown connector type."""
    config = [
        {"name": "bad", "type": "nonexistent_type", "enabled": True, "connection": {}},
    ]
    reg = ConnectorRegistry()
    reg.load_from_config(config)
    assert len(reg.get_all()) == 0
