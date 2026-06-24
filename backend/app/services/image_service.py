"""图片查询服务。

根据景点名或关键词查询外部图片地址，供前端结果页展示景点卡片时使用。
"""

from typing import Optional

import httpx

from app.core.config import get_settings


async def get_photo_url(query: str) -> Optional[str]:
    """根据关键词获取一张可展示的图片 URL。

    如果没有相关配置或没有搜索结果，则返回 None，调用方可以继续使用默认占位图。
    图片展示属于增强功能，不应影响核心旅行规划流程。
    """
    settings = get_settings()

    # 没有配置图片服务时直接返回空结果，避免影响主流程。
    if not settings.unsplash_access_key:
        return None

    # 使用异步 HTTP 客户端，避免在接口请求过程中阻塞事件循环。
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            "https://api.unsplash.com/search/photos",
            params={
                "query": query,
                # 结果页只需要一张代表图，因此只请求第一条搜索结果。
                "per_page": 1,
                "client_id": settings.unsplash_access_key,
            },
        )
        response.raise_for_status()

        results = response.json().get("results", [])
        if not results:
            return None

        # 选择 regular 尺寸，兼顾图片清晰度和前端加载速度。
        return results[0].get("urls", {}).get("regular")
