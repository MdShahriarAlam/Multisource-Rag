"""Configuration management for the application."""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)

load_dotenv(override=True)


class ConfigError(RuntimeError):
    """Raised when configuration is invalid or incomplete."""


class Settings(BaseSettings):
    """Global application settings — driven by .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_request_timeout: float = 30.0

    # Application
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"
    env: Literal["dev", "prod", "test"] = "dev"

    # MCP Server (standalone binary; not used for in-process calls)
    mcp_server_host: str = "localhost"
    mcp_server_port: int = 8001

    # Sources config
    sources_config_path: str = "sources.yaml"

    # ChromaDB
    chroma_persist_dir: str = "./chroma_data"

    # Orchestrator guardrails
    request_timeout_seconds: int = 120
    max_message_chars: int = 5000
    max_iterations: int = 15
    max_sessions: int = 1000
    max_turns_per_session: int = 50

    # Ingestion / embedding
    max_file_bytes: int = 50 * 1024 * 1024  # 50 MB
    embedder_max_retries: int = 4
    embedder_batch_token_limit: int = 8000

    # Retrieval
    unstructured_relevance_threshold: float = 0.3

    # Upload folder
    upload_dir: str = "./uploaded_files"
    allowed_upload_extensions: str = ".pdf,.docx,.txt,.csv,.xlsx,.json"

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:8501"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_upload_extensions_set(self) -> set[str]:
        return {e.strip().lower() for e in self.allowed_upload_extensions.split(",") if e.strip()}


_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _expand_env_vars(value: Any, missing: set[str]) -> Any:
    """Recursively expand ${ENV_VAR} references. Collects unresolved names in `missing`."""
    if isinstance(value, str):
        def replacer(match: re.Match) -> str:
            var_name = match.group(1)
            val = os.environ.get(var_name)
            if val is None or val == "":
                missing.add(var_name)
                return match.group(0)
            return val
        return _ENV_PATTERN.sub(replacer, value)
    if isinstance(value, dict):
        return {k: _expand_env_vars(v, missing) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env_vars(item, missing) for item in value]
    return value


class SourceEntry(BaseModel):
    """Single source entry in sources.yaml."""

    name: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    enabled: bool = False
    connection: Dict[str, Any] = Field(default_factory=dict)


class SourcesConfig(BaseModel):
    """Root schema of sources.yaml."""

    sources: List[SourceEntry] = Field(default_factory=list)


def load_sources_config(config_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Load data source configurations from YAML file.

    - Validates structure against `SourcesConfig` schema.
    - Expands ${ENV_VAR} references; missing vars in ENABLED sources raise ConfigError.
    - Disabled sources are kept so callers can report them; caller filters.
    """
    if config_path is None:
        config_path = settings.sources_config_path

    path = Path(config_path)
    if not path.exists():
        log.warning("Sources config file not found at %s", config_path)
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in {config_path}: {e}") from e

    try:
        config = SourcesConfig.model_validate(raw)
    except ValidationError as e:
        raise ConfigError(f"Invalid sources.yaml structure: {e}") from e

    missing: set[str] = set()
    expanded = [_expand_env_vars(entry.model_dump(), missing) for entry in config.sources]

    # Only surface missing vars for enabled sources — disabled ones may be templates
    enabled_missing: set[str] = set()
    for entry in expanded:
        if not entry.get("enabled"):
            continue
        inner: set[str] = set()
        _expand_env_vars(entry.get("connection", {}), inner)
        enabled_missing.update(inner)

    if enabled_missing:
        raise ConfigError(
            f"Missing environment variables for enabled sources: {sorted(enabled_missing)}. "
            f"Populate them in .env."
        )

    return expanded


try:
    settings = Settings()  # type: ignore[call-arg]
except ValidationError as e:
    raise ConfigError(
        f"Invalid application settings — check .env (e.g. OPENAI_API_KEY): {e}"
    ) from e
