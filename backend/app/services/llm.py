"""大模型服务工厂模块。

这个模块负责为 LangGraph 节点创建可复用的 LLM 客户端。
项目中真正和大模型服务通信的对象，是这里返回的 ChatOpenAI 实例。

注意：虽然类名叫 ChatOpenAI，但只要服务端兼容 OpenAI Chat Completions 接口，
也可以通过 llm_base_url 接入其他兼容服务商。
"""

from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.core.config import get_settings
from app.core.logging_utils import configured, llm_provider


@lru_cache
def get_llm() -> ChatOpenAI:
    """获取全局复用的 LLM 客户端实例。

    LangGraph 中多个节点可能都会调用大模型。
    使用 lru_cache 可以确保 ChatOpenAI 只初始化一次，避免重复创建客户端对象。
    """
    # 从统一配置中心读取大模型相关配置，例如 API Key、Base URL、模型 ID 和超时时间。
    settings = get_settings()

    # 打印初始化日志，方便启动时确认当前使用的大模型服务配置。
    print("🔄 初始化 LLM 服务...")
    print(f"✅ LLM服务初始化成功")
    print(f"   提供商: {llm_provider(settings.llm_base_url)}")
    print(f"   模型: {settings.llm_model_id}")

    # configured() 只显示是否已配置，不会直接输出真实 API Key，避免密钥泄露到日志中。
    print(f"   API Key: {configured(settings.llm_api_key)}")
    print(f"   Base URL: {settings.llm_base_url}")

    # 创建 LangChain 的聊天模型客户端。
    # 后续 LangGraph 节点会通过这个对象向大模型发送对话请求。
    return ChatOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model_id,
        timeout=settings.llm_timeout,
        # temperature 越低，输出越稳定；旅行规划需要结构清晰，所以这里设置为 0.2。
        temperature=0.2,
    )


def llm_health() -> dict:
    """返回 LLM 服务的基础健康状态。

    该函数不会真正请求大模型，只检查当前配置是否具备调用大模型的基本条件。
    通常用于健康检查接口，帮助前端或运维判断 LLM 配置是否完整。
    """
    settings = get_settings()
    return {
        # 只要配置了 API Key，就认为具备调用大模型的基础条件。
        "configured": bool(settings.llm_api_key),
        "base_url": settings.llm_base_url,
        "model": settings.llm_model_id,
    }
