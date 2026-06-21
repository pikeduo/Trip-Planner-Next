"""Image lookup service."""

from typing import Optional

import httpx

from app.core.config import get_settings


async def get_photo_url(query: str) -> Optional[str]:
    settings = get_settings()
    if not settings.unsplash_access_key:
        return None
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            "https://api.unsplash.com/search/photos",
            params={
                "query": query,
                "per_page": 1,
                "client_id": settings.unsplash_access_key,
            },
        )
        response.raise_for_status()
        results = response.json().get("results", [])
        if not results:
            return None
        return results[0].get("urls", {}).get("regular")
