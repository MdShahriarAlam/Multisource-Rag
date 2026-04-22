"""Configuration management for the application."""
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Populate os.environ from .env so _expand_env_vars can resolve ${VAR} references
load_dotenv(override=True)


class Settings(BaseSettings):
    """Global application settings (not source-specific)."""

    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-4-turbo-preview"
    openai_embedding_model: str = "text-embedding-3-small"

    # Application
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # MCP Server
    mcp_server_host: str = "localhost"
    mcp_server_port: int = 8001

    # Sources config
    sources_config_path: str = "sources.yaml"

    # ChromaDB
    chroma_persist_dir: str = "./chroma_data"

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


def _expand_env_vars(value: Any) -> Any:
    """Recursively expand ${ENV_VAR} references in config values."""
    if isinstance(value, str):
        pattern = re.compile(r"\$\{([^}]+)\}")
        def replacer(match):
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))
        return pattern.sub(replacer, value)
    elif isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_expand_env_vars(item) for item in value]
    return value


def load_sources_config(config_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Load data source configurations from YAML file.

    Each source entry has: name, type, enabled, connection (dict of params).
    Environment variable references (${VAR}) are expanded from os.environ.
    """
    if config_path is None:
        config_path = settings.sources_config_path

    path = Path(config_path)
    if not path.exists():
        print(f"Warning: Sources config file not found at {config_path}")
        return []

    with open(path, "r") as f:
        raw = yaml.safe_load(f)

    if not raw or "sources" not in raw:
        return []

    sources = _expand_env_vars(raw["sources"])
    return [s for s in sources if isinstance(s, dict)]


settings = Settings()
