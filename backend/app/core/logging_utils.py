"""Console logging helpers for runtime diagnostics."""

from typing import Any
from urllib.parse import urlparse


SEPARATOR = "=" * 60


def log_section(title: str) -> None:
    print(f"\n{SEPARATOR}")
    print(title)
    print(SEPARATOR)


def configured(value: str | None) -> str:
    return "已配置" if value else "未配置"


def llm_provider(base_url: str) -> str:
    host = urlparse(base_url).netloc or base_url
    if "deepseek" in host:
        return "deepseek"
    if "openai" in host:
        return "openai"
    return host or "unknown"


def preview(value: Any, limit: int = 500) -> str:
    text = str(value).replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."
