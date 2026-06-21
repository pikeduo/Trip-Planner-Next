"""LLM factory for LangGraph nodes."""

from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.core.config import get_settings
from app.core.logging_utils import configured, llm_provider


@lru_cache
def get_llm() -> ChatOpenAI:
    settings = get_settings()
    print("🔄 初始化 LLM 服务...")
    print(f"✅ LLM服务初始化成功")
    print(f"   提供商: {llm_provider(settings.llm_base_url)}")
    print(f"   模型: {settings.llm_model_id}")
    print(f"   API Key: {configured(settings.llm_api_key)}")
    print(f"   Base URL: {settings.llm_base_url}")
    return ChatOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model_id,
        timeout=settings.llm_timeout,
        temperature=0.2,
    )


def llm_health() -> dict:
    settings = get_settings()
    return {
        "configured": bool(settings.llm_api_key),
        "base_url": settings.llm_base_url,
        "model": settings.llm_model_id,
    }
