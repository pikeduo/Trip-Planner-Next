"""高德 MCP 客户端与 REST 兜底工具。

这个模块是后端访问高德地图能力的统一入口，主要负责：
1. 启动并复用高德 MCP Server；
2. 通过 MCP 工具调用 POI 搜索、天气查询、路线规划等能力；
3. 当 MCP 不可用时，自动退回到高德 REST API；
4. 将外部服务返回的原始数据转换为项目内部统一的数据模型。
"""

import asyncio
import json
import re
import shutil
import sys
from contextlib import AsyncExitStack
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.core.config import get_settings
from app.core.logging_utils import configured, preview
from app.models.schemas import Location, POIInfo, RouteInfo, WeatherInfo


class AmapMCPUnavailableError(RuntimeError):
    """高德 MCP 服务无法启动或无法连接时抛出的异常。"""


class AmapMCPToolError(RuntimeError):
    """MCP 服务可用，但具体工具调用失败时抛出的异常。"""


def _find_amap_mcp_command() -> tuple[str, List[str]]:
    """查找可用于启动高德 MCP Server 的命令。

    优先查找当前 Python 环境中的 amap-mcp-server；
    如果没有找到，则尝试使用 uvx 临时启动 amap-mcp-server。
    """
    executable_dir = Path(sys.executable).resolve().parent
    executable_name = "amap-mcp-server.exe" if sys.platform.startswith("win") else "amap-mcp-server"

    # 先从当前虚拟环境或 Python 安装目录中查找，兼容 Windows Scripts 目录。
    local_candidates = [
        executable_dir / executable_name,
        executable_dir / "Scripts" / executable_name,
        executable_dir.parent / "Scripts" / executable_name,
    ]
    for local_server in local_candidates:
        if local_server.exists():
            return str(local_server), ["stdio"]

    # 再从系统 PATH 中查找已安装的 amap-mcp-server 命令。
    resolved_server = shutil.which("amap-mcp-server")
    if resolved_server:
        return resolved_server, ["stdio"]

    # 如果本地没有 server，则尝试通过 uvx 启动。
    resolved_uvx = shutil.which("uvx")
    if resolved_uvx:
        return resolved_uvx, ["amap-mcp-server", "stdio"]

    # 最后保留 uvx 作为默认命令；真正调用时如果不可用，会进入 REST API 兜底逻辑。
    return "uvx", ["amap-mcp-server", "stdio"]


def _command_preview(command: str, args: List[str]) -> str:
    """把命令和参数拼接成日志中易读的一行文本。"""
    return " ".join([command, *args]).strip()


def _amap_mcp_config() -> dict:
    """构造高德 MCP Server 的启动配置。"""
    settings = get_settings()
    command, args = _find_amap_mcp_command()
    command_exists = Path(command).exists() or shutil.which(command) is not None

    print("  - 创建共享 MCP 工具...")
    print(f"🔑 使用环境变量: AMAP_MAPS_API_KEY={configured(settings.amap_maps_api_key)}")
    print(f"📝 使用 Stdio 传输 (命令): {_command_preview(command, args)}")
    if not command_exists:
        print(f"⚠️ 未找到 MCP 启动命令: {command}，工具调用时将使用高德 REST API 兜底")

    # MCP Server 通过 stdio 与当前 Python 进程通信，API Key 通过环境变量传给子进程。
    return {
        "amap": {
            "transport": "stdio",
            "command": command,
            "args": args,
            "env": {"AMAP_MAPS_API_KEY": settings.amap_maps_api_key},
        }
    }


@lru_cache
def get_mcp_server_params() -> StdioServerParameters:
    """获取并缓存 MCP Server 启动参数。

    MCP 启动命令在应用运行期间通常不会变化，因此缓存起来避免重复解析。
    """
    config = _amap_mcp_config()["amap"]
    return StdioServerParameters(
        command=config["command"],
        args=config["args"],
        env=config["env"],
    )


def parse_jsonish(raw: Any) -> Any:
    """尽可能把外部服务返回值解析成 Python 对象。

    MCP 或 REST API 的返回值有时是 dict/list，有时是 JSON 字符串，
    也可能是带有说明文字的 JSON 片段。这个函数会尽量提取可解析的 JSON。
    """
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw

    text = str(raw)
    try:
        return json.loads(text)
    except Exception:
        pass

    # 如果整段文本不是合法 JSON，就尝试从文本中截取 {...} 或 [...] 片段再解析。
    match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            return {"raw": text}
    return {"raw": text}


def _decode_mcp_result(result: Any) -> Any:
    """解析 MCP 工具调用结果，并把错误统一转换成业务异常。"""
    if getattr(result, "isError", False):
        raise AmapMCPToolError(f"MCP tool returned error: {getattr(result, 'content', result)}")

    structured_content = getattr(result, "structuredContent", None)
    if structured_content:
        # 新版 MCP 工具可能直接返回结构化内容。
        value = structured_content.get("result", structured_content)
    else:
        # 兼容普通文本内容：把多段 content 合并成一个字符串。
        content = getattr(result, "content", None)
        if content:
            value = "\n".join(getattr(item, "text", str(item)) for item in content)
        else:
            value = result

    parsed = parse_jsonish(value)
    if isinstance(parsed, dict) and parsed.get("error"):
        raise AmapMCPToolError(str(parsed["error"]))
    return parsed if isinstance(parsed, (dict, list)) else value


class AmapMCPClient:
    """高德 MCP 客户端。

    该类会复用同一个 stdio MCP 会话，避免每次调用工具都重复启动 MCP Server。
    内部使用 asyncio.Lock，保证异步并发请求时连接和工具调用过程是安全的。
    """

    def __init__(self) -> None:
        # 锁用于保护 MCP 会话连接和工具调用，避免并发初始化同一个连接。
        self._lock = asyncio.Lock()
        self._exit_stack: Optional[AsyncExitStack] = None
        self._session: Optional[ClientSession] = None
        self._tools: List[Any] = []

    async def _connect_locked(self) -> None:
        """在已持有锁的情况下建立 MCP 连接。"""
        if self._session is not None:
            return

        params = get_mcp_server_params()
        print("🔗 连接到 MCP 服务器并加载工具...")
        print(f"   MCP 启动命令: {_command_preview(params.command, list(params.args or []))}")

        stack = AsyncExitStack()
        try:
            # stdio_client 会启动 MCP 子进程，并返回读写通道。
            read, write = await stack.enter_async_context(stdio_client(params))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            tools_result = await session.list_tools()
        except Exception as exc:
            await stack.aclose()
            raise AmapMCPUnavailableError(f"MCP server unavailable: {exc}") from exc

        self._exit_stack = stack
        self._session = session
        self._tools = tools_result.tools
        print(f"✅ MCP 工具加载完成: {len(self._tools)} 个")
        print(f"   工具列表: {', '.join(tool.name for tool in self._tools) if self._tools else '无'}")

    async def list_tools(self) -> List[Any]:
        """返回当前 MCP Server 提供的工具列表。"""
        async with self._lock:
            await self._connect_locked()
            return list(self._tools)

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """调用指定的 MCP 工具。"""
        async with self._lock:
            await self._connect_locked()
            assert self._session is not None

            available_tools = [tool.name for tool in self._tools]
            matched_tool = next(
                # 有些 MCP 工具名可能带命名空间前缀，因此这里同时支持精确匹配和后缀匹配。
                (name for name in available_tools if name == tool_name or name.endswith(tool_name)),
                None,
            )
            if not matched_tool:
                available = ", ".join(available_tools)
                raise AmapMCPToolError(f"MCP tool not found: {tool_name}. Available tools: {available}")

            print(f"   MCP 命中工具: {matched_tool}")
            try:
                result = await self._session.call_tool(matched_tool, arguments)
                return _decode_mcp_result(result)
            except AmapMCPToolError:
                raise
            except Exception as exc:
                # 如果底层连接异常，关闭旧会话；下一次调用会重新建立连接。
                await self.close()
                raise AmapMCPUnavailableError(f"MCP call failed: {exc}") from exc

    async def close(self) -> None:
        """关闭 MCP 会话并清空本地缓存状态。"""
        stack = self._exit_stack
        self._exit_stack = None
        self._session = None
        self._tools = []
        if stack is not None:
            await stack.aclose()


# 全局共享一个高德 MCP 客户端，避免重复启动 MCP Server。
_amap_mcp_client = AmapMCPClient()


async def get_mcp_tools():
    """获取高德 MCP 工具列表。"""
    return await _amap_mcp_client.list_tools()


async def get_amap_tool_node():
    """构建 LangGraph 可使用的 ToolNode。"""
    from langgraph.prebuilt import ToolNode

    return ToolNode(await get_mcp_tools())


async def mcp_health() -> dict:
    """返回 MCP 服务健康状态。

    如果 MCP Server 无法连接，但高德 REST API Key 可用，则将服务状态降级为 REST 兜底可用。
    """
    settings = get_settings()
    try:
        tools = await get_mcp_tools()
        return {
            "configured": bool(settings.amap_maps_api_key),
            "available": True,
            "tools_count": len(tools),
            "tools": [tool.name for tool in tools],
        }
    except Exception as exc:
        rest_available = bool(_amap_rest_key())
        return {
            "configured": bool(settings.amap_maps_api_key),
            "available": rest_available,
            "fallback": "amap_rest" if rest_available else None,
            "tools_count": 0,
            "error": str(exc),
        }


async def call_amap_tool(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """调用高德能力的统一入口。

    优先调用 MCP 工具；如果 MCP 不可用或工具返回错误，则自动尝试高德 REST API 兜底。
    """
    print(f"🛠️ 调用高德 MCP 工具: {tool_name}")
    print(f"   参数: {arguments}")
    try:
        result = await call_amap_mcp_tool(tool_name, arguments)
        print(f"✅ MCP 工具调用成功: {tool_name}")
        print(f"   结果预览: {preview(result)}")
        return result
    except AmapMCPToolError as exc:
        print(f"⚠️ MCP 工具返回业务错误，尝试高德 REST API 兜底: {exc}")
        return await call_amap_rest_fallback(tool_name, arguments)
    except AmapMCPUnavailableError as exc:
        print(f"⚠️ MCP 连接或调用不可用，尝试高德 REST API 兜底: {exc}")
        return await call_amap_rest_fallback(tool_name, arguments)
    except Exception as exc:
        print(f"⚠️ MCP 调用异常，尝试高德 REST API 兜底: {exc}")
        return await call_amap_rest_fallback(tool_name, arguments)


async def call_amap_mcp_tool(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """直接调用高德 MCP 工具，不做 REST 兜底。"""
    return await _amap_mcp_client.call_tool(tool_name, arguments)


async def close_amap_mcp_client() -> None:
    """关闭全局高德 MCP 客户端。

    FastAPI 应用关闭时会调用该函数，释放 MCP 子进程和 stdio 连接资源。
    """
    await _amap_mcp_client.close()


def _amap_rest_key() -> str:
    """获取高德 REST API 可用的 Key。"""
    settings = get_settings()
    return settings.amap_api_key or settings.amap_maps_api_key


async def _amap_rest_get(path: str, params: Dict[str, Any]) -> Any:
    """调用高德 REST API 的通用 GET 方法。"""
    key = _amap_rest_key()
    if not key:
        raise ValueError("未配置 AMAP_API_KEY 或 AMAP_MAPS_API_KEY")

    # 过滤掉 None 和空字符串，避免把无效参数传给高德接口。
    request_params = {key_: value for key_, value in params.items() if value not in (None, "")}
    request_params["key"] = key
    url = f"https://restapi.amap.com/v3/{path}"

    print(f"🌐 调用高德 REST API: {path}")
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(url, params=request_params)
        print(f"   高德 REST 响应: HTTP {response.status_code}")
        response.raise_for_status()

    data = response.json()
    if str(data.get("status", "1")) != "1":
        raise ValueError(f"高德 REST API 返回失败: {data.get('info') or data}")
    print(f"✅ 高德 REST API 调用成功: {preview(data)}")
    return data


async def _amap_text_search(arguments: Dict[str, Any]) -> Any:
    """通过高德 REST API 搜索 POI。"""
    return await _amap_rest_get(
        "place/text",
        {
            "keywords": arguments.get("keywords"),
            "city": arguments.get("city"),
            "citylimit": arguments.get("citylimit", "true"),
            "offset": arguments.get("offset", 20),
            "page": arguments.get("page", 1),
            "extensions": "all",
        },
    )


async def _amap_weather(arguments: Dict[str, Any]) -> Any:
    """通过高德 REST API 查询天气。

    高德天气接口通常需要 adcode，因此先用地理编码接口把城市名转换为 adcode。
    """
    city = arguments.get("city")
    geocode = await _amap_rest_get("geocode/geo", {"address": city, "city": city})
    geocodes = geocode.get("geocodes") or []
    adcode = geocodes[0].get("adcode") if geocodes else city
    return await _amap_rest_get("weather/weatherInfo", {"city": adcode, "extensions": "all"})


async def _amap_search_detail(arguments: Dict[str, Any]) -> Any:
    """通过高德 REST API 查询 POI 详情。"""
    return await _amap_rest_get("place/detail", {"id": arguments.get("id")})


async def call_amap_rest_fallback(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """根据 MCP 工具名选择对应的高德 REST API 兜底实现。"""
    if tool_name.endswith("maps_text_search") or tool_name == "maps_text_search":
        return await _amap_text_search(arguments)
    if tool_name.endswith("maps_weather") or tool_name == "maps_weather":
        return await _amap_weather(arguments)
    if tool_name.endswith("maps_search_detail") or tool_name == "maps_search_detail":
        return await _amap_search_detail(arguments)
    raise ValueError(f"暂无高德 REST API 兜底实现: {tool_name}")


def _first_list(data: Any, keys: List[str]) -> List[Any]:
    """从嵌套数据中查找第一个列表。

    外部服务返回结构不完全固定，列表可能出现在 pois、results、data 等字段中，
    因此这里递归查找第一个可用列表，方便后续统一归一化。
    """
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            return value
    for value in data.values():
        nested = _first_list(value, keys)
        if nested:
            return nested
    return []


def _location(value: Any) -> Optional[Location]:
    """把外部返回的坐标值转换为项目内部 Location 模型。"""
    if isinstance(value, dict):
        lng = value.get("longitude") or value.get("lng")
        lat = value.get("latitude") or value.get("lat")
    elif isinstance(value, str) and "," in value:
        # 高德常见坐标格式是 "longitude,latitude"。
        lng, lat = value.split(",", 1)
    else:
        return None
    try:
        return Location(longitude=float(lng), latitude=float(lat))
    except Exception:
        return None


def normalize_pois(raw: Any) -> List[POIInfo]:
    """将 POI 原始结果转换为项目内部统一的 POIInfo 列表。"""
    data = parse_jsonish(raw)
    items = _first_list(data, ["pois", "results", "data"])
    pois: List[POIInfo] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        location = _location(item.get("location"))
        if not location:
            continue
        pois.append(
            POIInfo(
                id=str(item.get("id") or item.get("poi_id") or item.get("name") or ""),
                name=str(item.get("name") or ""),
                type=str(item.get("type") or item.get("category") or ""),
                address=str(item.get("address") or item.get("adname") or ""),
                location=location,
                tel=item.get("tel"),
            )
        )
    return pois


def normalize_weather(raw: Any) -> List[WeatherInfo]:
    """将天气原始结果转换为 WeatherInfo 列表。"""
    data = parse_jsonish(raw)
    casts = _first_list(data, ["casts", "weather", "data", "lives"])
    weather: List[WeatherInfo] = []
    for item in casts:
        if not isinstance(item, dict):
            continue
        weather.append(
            WeatherInfo(
                date=str(item.get("date") or item.get("reporttime") or ""),
                day_weather=str(item.get("dayweather") or item.get("weather") or ""),
                night_weather=str(item.get("nightweather") or item.get("weather") or ""),
                day_temp=item.get("daytemp") or item.get("temperature") or 0,
                night_temp=item.get("nighttemp") or item.get("temperature") or 0,
                wind_direction=str(item.get("daywind") or item.get("winddirection") or ""),
                wind_power=str(item.get("daypower") or item.get("windpower") or ""),
            )
        )
    return weather


def normalize_route(raw: Any, route_type: str) -> Optional[RouteInfo]:
    """将路线规划原始结果转换为 RouteInfo。"""
    data = parse_jsonish(raw)
    if not isinstance(data, dict):
        return None

    # 驾车、步行、公交等接口返回结构可能不同，这里尽量兼容 route、paths、transits 等字段。
    route = data.get("route") if isinstance(data.get("route"), dict) else data
    paths = route.get("paths") or route.get("transits") or []
    first = paths[0] if isinstance(paths, list) and paths else route
    try:
        distance = float(first.get("distance") or route.get("distance") or 0)
        duration = int(float(first.get("duration") or route.get("duration") or 0))
    except Exception:
        distance = 0
        duration = 0

    # 如果没有结构化说明，就截取原始 JSON 作为兜底描述，便于前端或日志展示。
    description = first.get("instruction") or first.get("description") or json.dumps(data, ensure_ascii=False)[:500]
    if distance <= 0 and duration <= 0:
        return None
    return RouteInfo(distance=distance, duration=duration, route_type=route_type, description=str(description))


async def search_poi(keywords: str, city: str, citylimit: bool = True) -> List[POIInfo]:
    """搜索城市中的 POI，并返回统一格式的 POIInfo 列表。"""
    raw = await call_amap_tool(
        "maps_text_search",
        {"keywords": keywords, "city": city, "citylimit": str(citylimit).lower()},
    )
    return normalize_pois(raw)


async def get_weather(city: str) -> List[WeatherInfo]:
    """查询指定城市天气，并返回统一格式的 WeatherInfo 列表。"""
    raw = await call_amap_tool("maps_weather", {"city": city})
    return normalize_weather(raw)


async def plan_route(
    origin_address: str,
    destination_address: str,
    route_type: str,
    origin_city: Optional[str] = None,
    destination_city: Optional[str] = None,
) -> Optional[RouteInfo]:
    """规划两地之间的路线。

    route_type 支持 walking、driving、transit；未知类型默认按 walking 处理。
    """
    tool_map = {
        "walking": "maps_direction_walking_by_address",
        "driving": "maps_direction_driving_by_address",
        "transit": "maps_direction_transit_integrated_by_address",
    }
    args: Dict[str, Any] = {
        "origin_address": origin_address,
        "destination_address": destination_address,
    }
    if origin_city:
        args["origin_city"] = origin_city
    if destination_city:
        args["destination_city"] = destination_city

    raw = await call_amap_tool(tool_map.get(route_type, tool_map["walking"]), args)
    return normalize_route(raw, route_type)


async def get_poi_detail(poi_id: str) -> dict:
    """查询指定 POI 的详情信息。"""
    raw = await call_amap_tool("maps_search_detail", {"id": poi_id})
    parsed = parse_jsonish(raw)
    return parsed if isinstance(parsed, dict) else {"data": parsed}
