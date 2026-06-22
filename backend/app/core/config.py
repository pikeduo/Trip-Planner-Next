"""Application settings.

Centralized configuration for the backend service.
This module reads environment variables, provides default values,
and exposes a cached Settings instance for the rest of the application.
"""

from functools import lru_cache
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Locate the backend directory based on this file's position:
# backend/app/core/config.py -> backend
BACKEND_DIR = Path(__file__).resolve().parents[2]

# The backend .env file is expected to be placed directly under backend/.
ENV_FILE = BACKEND_DIR / ".env"

# Load variables from backend/.env into the process environment before
# Pydantic Settings reads them.
load_dotenv(ENV_FILE)


class Settings(BaseSettings):
    """Typed application settings loaded from environment variables.

    Each field can be overridden by an environment variable with the same name
    because case_sensitive is disabled in the Config class below.
    """

    # Basic application metadata.
    app_name: str = "Trip Planner Next"
    app_version: str = "1.0.0"
    debug: bool = False

    # Server and frontend access configuration.
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = (
        "http://localhost:5173,http://localhost:3000,"
        "http://127.0.0.1:5173,http://127.0.0.1:3000"
    )
    log_level: str = "INFO"

    # Third-party API keys used by map and image-related features.
    amap_api_key: str = ""
    amap_maps_api_key: str = ""
    unsplash_access_key: str = ""
    unsplash_secret_key: str = ""

    # LLM provider configuration. Defaults target the OpenAI-compatible API format.
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model_id: str = "gpt-4o-mini"
    llm_timeout: int = 120

    class Config:
        # Tell pydantic-settings where to read environment variables from.
        env_file = str(ENV_FILE)

        # Allow variables like APP_NAME and app_name to map to the same field.
        case_sensitive = False

        # Ignore unrelated variables in .env instead of raising validation errors.
        extra = "ignore"

    def cors_origins_list(self) -> List[str]:
        """Convert the comma-separated CORS origin string into a clean list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a singleton-like Settings object.

    Caching avoids rebuilding Settings every time another module needs config.
    """
    return Settings()


def validate_config() -> None:
    """Validate required runtime configuration.

    Raises:
        ValueError: If required environment variables are missing.
    """
    settings = get_settings()
    missing = []

    # The frontend map SDK/API requires a map-specific AMap key.
    if not settings.amap_maps_api_key:
        missing.append("AMAP_MAPS_API_KEY")

    # LLM features cannot run without a model provider API key.
    if not settings.llm_api_key:
        missing.append("LLM_API_KEY")

    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
