"""地图服务相关 API 路由。

这个模块负责对外提供地图相关接口，包括：
1. POI 搜索；
2. 天气查询；
3. 路线规划；
4. 高德静态地图获取；
5. 地图服务健康检查。

路由层只负责接收请求、调用服务层、封装响应；
真正的高德 MCP / REST API 调用逻辑放在 app.services.mcp_client 中。
"""

import httpx
from fastapi import APIRouter, HTTPException, Query, Response

from app.core.config import get_settings
from app.core.logging_utils import configured
from app.models.schemas import POISearchResponse, RouteRequest, RouteResponse, WeatherResponse
from app.services import mcp_client

# 创建地图服务路由器。
# 该 router 会在 app/api/main.py 中统一挂载到 /api，最终路径前缀是 /api/map。
router = APIRouter(prefix="/map", tags=["地图服务"])


@router.get("/poi", response_model=POISearchResponse, summary="搜索POI")
async def search_poi(
    keywords: str = Query(..., description="搜索关键词"),
    city: str = Query(..., description="城市"),
    citylimit: bool = Query(True, description="是否限制在城市范围内"),
):
    """搜索 POI 兴趣点。

    POI 是 Point of Interest 的缩写，可以理解为地图上的兴趣点，
    例如景点、餐厅、酒店、商场等。
    """
    try:
        # 具体搜索逻辑交给服务层处理；服务层会优先调用高德 MCP，失败时尝试 REST 兜底。
        pois = await mcp_client.search_poi(keywords, city, citylimit)
        return POISearchResponse(success=True, message="POI搜索成功", data=pois)
    except Exception as exc:
        # 路由层统一把异常转换成 HTTPException，方便前端获得明确的错误响应。
        raise HTTPException(status_code=500, detail=f"POI搜索失败: {exc}") from exc


@router.get("/weather", response_model=WeatherResponse, summary="查询天气")
async def get_weather(city: str = Query(..., description="城市名称")):
    """查询指定城市的天气信息。"""
    try:
        # 服务层会把高德返回的原始天气数据转换成 WeatherInfo 列表。
        weather = await mcp_client.get_weather(city)
        return WeatherResponse(success=True, message="天气查询成功", data=weather)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"天气查询失败: {exc}") from exc


@router.post("/route", response_model=RouteResponse, summary="规划路线")
async def plan_route(request: RouteRequest):
    """根据起点、终点和交通方式规划路线。

    request 中包含起点地址、终点地址、起点城市、终点城市和路线类型。
    route_type 通常支持 walking、driving、transit。
    """
    try:
        # 把请求模型中的字段拆出来传给服务层，服务层负责选择对应的高德路线工具。
        route = await mcp_client.plan_route(
            origin_address=request.origin_address,
            destination_address=request.destination_address,
            origin_city=request.origin_city,
            destination_city=request.destination_city,
            route_type=request.route_type,
        )
        return RouteResponse(
            # route 为 None 表示调用成功，但没有解析出可用路线。
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
    """获取高德静态地图图片。

    静态地图接口返回的是图片二进制内容，不是普通 JSON。
    前端可以用这个接口展示路线概览、景点标记或地图截图。
    """
    settings = get_settings()

    # 静态地图优先使用 AMAP_API_KEY；如果没有，则使用 AMAP_MAPS_API_KEY。
    amap_key = settings.amap_api_key or settings.amap_maps_api_key

    print("\n🗺️ 收到静态地图请求:")
    print(f"   location: {location}")
    print(f"   zoom: {zoom}")
    print(f"   size: {size}")
    print(f"   markers: {'已提供' if markers else '未提供'}")
    print(f"   paths: {'已提供' if paths else '未提供'}")
    # configured() 只显示 Key 是否配置，避免在日志里泄露真实密钥。
    print(f"   高德 Key: {configured(amap_key)}")

    if not amap_key:
        raise HTTPException(status_code=500, detail="未配置高德地图静态图 Key")

    # 构造高德静态地图接口参数。
    params = {
        "key": amap_key,
        "location": location,
        "zoom": zoom,
        "size": size,
        "scale": scale,
    }
    # markers 和 paths 是可选参数，只有前端传入时才添加，避免发送空参数。
    if markers:
        params["markers"] = markers
    if paths:
        params["paths"] = paths

    try:
        # 使用异步 HTTP 客户端请求高德静态地图接口。
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get("https://restapi.amap.com/v3/staticmap", params=params)
            print(f"   高德静态地图响应: HTTP {response.status_code}")
            response.raise_for_status()
    except Exception as exc:
        print(f"❌ 静态地图获取失败: {exc}")
        # 502 表示后端作为网关调用外部高德服务失败。
        raise HTTPException(status_code=502, detail=f"静态地图获取失败: {exc}") from exc

    print(f"✅ 静态地图获取成功: {len(response.content)} bytes")
    return Response(
        content=response.content,
        media_type=response.headers.get("content-type", "image/png"),
        # 静态地图可能受参数影响较大，这里禁用缓存，避免前端拿到旧图。
        headers={"Cache-Control": "no-store"},
    )


@router.get("/health", summary="地图服务健康检查")
async def health_check():
    """地图服务健康检查接口。

    该接口会检查 MCP / 高德地图能力是否可用，供前端或监控系统判断地图服务状态。
    """
    mcp = await mcp_client.mcp_health()
    return {
        "status": "healthy" if mcp.get("available") else "degraded",
        "service": "map-service",
        "mcp": mcp,
    }
