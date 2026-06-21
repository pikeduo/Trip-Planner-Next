"""POI API routes."""

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import POIDetailResponse, POISearchResponse
from app.services.image_service import get_photo_url
from app.services.mcp_client import get_poi_detail, search_poi

router = APIRouter(prefix="/poi", tags=["POI"])


@router.get("/detail/{poi_id}", response_model=POIDetailResponse, summary="获取POI详情")
async def poi_detail(poi_id: str):
    try:
        detail = await get_poi_detail(poi_id)
        return POIDetailResponse(success=True, message="获取POI详情成功", data=detail)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取POI详情失败: {exc}") from exc


@router.get("/search", response_model=POISearchResponse, summary="搜索POI")
async def poi_search(keywords: str = Query(...), city: str = Query("北京")):
    try:
        pois = await search_poi(keywords, city)
        return POISearchResponse(success=True, message="搜索成功", data=pois)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"搜索POI失败: {exc}") from exc


@router.get("/photo", summary="获取景点图片")
async def attraction_photo(name: str = Query(...)):
    try:
        photo_url = await get_photo_url(f"{name} China landmark") or await get_photo_url(name)
        return {
            "success": True,
            "message": "获取图片成功" if photo_url else "未配置图片服务或未找到图片",
            "data": {"name": name, "photo_url": photo_url},
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取景点图片失败: {exc}") from exc
