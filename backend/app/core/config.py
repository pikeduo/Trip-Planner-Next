"""Application settings."""

from functools import lru_cache
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"

load_dotenv(ENV_FILE)


class Settings(BaseSettings):
    app_name: str = "Trip Planner Next"
    app_version: str = "1.0.0"
    debug: bool = False

    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = (
        "http://localhost:5173,http://localhost:3000,"
        "http://127.0.0.1:5173,http://127.0.0.1:3000"
    )
    log_level: str = "INFO"

    amap_api_key: str = ""
    amap_maps_api_key: str = ""
    unsplash_access_key: str = ""
    unsplash_secret_key: str = ""

    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model_id: str = "gpt-4o-mini"
    llm_timeout: int = 120

    class Config:
        env_file = str(ENV_FILE)
        case_sensitive = False
        extra = "ignore"

    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def validate_config() -> None:
    settings = get_settings()
    missing = []
    if not settings.amap_maps_api_key:
        missing.append("AMAP_MAPS_API_KEY")
    if not settings.llm_api_key:
        missing.append("LLM_API_KEY")
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
