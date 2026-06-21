"""Map service API routes."""

import httpx
from fastapi import APIRouter, HTTPException, Query, Response

from app.core.config import get_settings
from app.core.logging_utils import configured
from app.models.schemas import POISearchResponse, RouteRequest, RouteResponse, WeatherResponse
from app.services import mcp_client

router = APIRouter(prefix="/map", tags=["地图服务"])


@router.get("/poi", response_model=POISearchResponse, summary="搜索POI")
async def search_poi(
    keywords: str = Query(..., description="搜索关键词"),
    city: str = Query(..., description="城市"),
    citylimit: bool = Query(True, description="是否限制在城市范围内"),
):
    try:
        pois = await mcp_client.search_poi(keywords, city, citylimit)
        return POISearchResponse(success=True, message="POI搜索成功", data=pois)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"POI搜索失败: {exc}") from exc


@router.get("/weather", response_model=WeatherResponse, summary="查询天气")
async def get_weather(city: str = Query(..., description="城市名称")):
    try:
        weather = await mcp_client.get_weather(city)
        return WeatherResponse(success=True, message="天气查询成功", data=weather)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"天气查询失败: {exc}") from exc


@router.post("/route", response_model=RouteResponse, summary="规划路线")
async def plan_route(request: RouteRequest):
    try:
        route = await mcp_client.plan_route(
            origin_address=request.origin_address,
            destination_address=request.destination_address,
            origin_city=request.origin_city,
            destination_city=request.destination_city,
            route_type=request.route_type,
        )
        return RouteResponse(
            success=route is not None,
            message="路线规划成功" if route else "路线规划未返回可解析结果",
            data=route,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"路线规划失败: {exc}") from exc


@router.get("/static", summary="获取高德静态地图")
async def static_map(
    location: str = Query(..., description="地图中心点, 格式: longitude,latitude"),
    zoom: int = Query(12, ge=3, le=18, description="地图缩放级别"),
    size: str = Query("1000*560", description="静态图尺寸"),
    scale: int = Query(2, ge=1, le=2, description="像素倍率"),
    markers: str = Query("", description="高德静态地图 markers 参数"),
    paths: str = Query("", description="高德静态地图 paths 参数"),
):
    settings = get_settings()
    amap_key = settings.amap_api_key or settings.amap_maps_api_key
    print("\n🗺️ 收到静态地图请求:")
    print(f"   location: {location}")
    print(f"   zoom: {zoom}")
    print(f"   size: {size}")
    print(f"   markers: {'已提供' if markers else '未提供'}")
    print(f"   paths: {'已提供' if paths else '未提供'}")
    print(f"   高德 Key: {configured(amap_key)}")
    if not amap_key:
        raise HTTPException(status_code=500, detail="未配置高德地图静态图 Key")

    params = {
        "key": amap_key,
        "location": location,
        "zoom": zoom,
        "size": size,
        "scale": scale,
    }
    if markers:
        params["markers"] = markers
    if paths:
        params["paths"] = paths

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get("https://restapi.amap.com/v3/staticmap", params=params)
            print(f"   高德静态地图响应: HTTP {response.status_code}")
            response.raise_for_status()
    except Exception as exc:
        print(f"❌ 静态地图获取失败: {exc}")
        raise HTTPException(status_code=502, detail=f"静态地图获取失败: {exc}") from exc

    print(f"✅ 静态地图获取成功: {len(response.content)} bytes")
    return Response(
        content=response.content,
        media_type=response.headers.get("content-type", "image/png"),
        headers={"Cache-Control": "no-store"},
    )


@router.get("/health", summary="地图服务健康检查")
async def health_check():
    mcp = await mcp_client.mcp_health()
    return {
        "status": "healthy" if mcp.get("available") else "degraded",
        "service": "map-service",
        "mcp": mcp,
    }
