"""Config validation + env expansion."""
import os

import pytest

from src.config import ConfigError, SourcesConfig, _expand_env_vars, load_sources_config


def test_expand_env_vars_success(monkeypatch):
    monkeypatch.setenv("FOO", "bar")
    missing: set[str] = set()
    result = _expand_env_vars({"host": "${FOO}.example.com"}, missing)
    assert result == {"host": "bar.example.com"}
    assert not missing


def test_expand_env_vars_missing():
    missing: set[str] = set()
    _expand_env_vars("${UNSET_AT_ALL}", missing)
    assert "UNSET_AT_ALL" in missing


def test_sources_config_validates():
    SourcesConfig.model_validate(
        {"sources": [{"name": "x", "type": "postgresql", "enabled": False}]}
    )


def test_load_sources_missing_vars_in_enabled(tmp_path, monkeypatch):
    cfg = tmp_path / "sources.yaml"
    cfg.write_text(
        "sources:\n"
        "  - name: pg\n"
        "    type: postgresql\n"
        "    enabled: true\n"
        "    connection:\n"
        "      host: ${DEFINITELY_NOT_SET_XYZ}\n"
    )
    monkeypatch.delenv("DEFINITELY_NOT_SET_XYZ", raising=False)
    with pytest.raises(ConfigError):
        load_sources_config(str(cfg))


def test_load_sources_ignores_missing_in_disabled(tmp_path, monkeypatch):
    cfg = tmp_path / "sources.yaml"
    cfg.write_text(
        "sources:\n"
        "  - name: pg\n"
        "    type: postgresql\n"
        "    enabled: false\n"
        "    connection:\n"
        "      host: ${NOT_SET_ABC}\n"
    )
    monkeypatch.delenv("NOT_SET_ABC", raising=False)
    result = load_sources_config(str(cfg))
    assert len(result) == 1
    assert result[0]["enabled"] is False
