"""MCP client helpers for AMap tools."""

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
    """Raised when the AMap MCP server cannot be started or reached."""


class AmapMCPToolError(RuntimeError):
    """Raised when the MCP server is available but a tool returns an error."""


def _find_amap_mcp_command() -> tuple[str, List[str]]:
    executable_dir = Path(sys.executable).resolve().parent
    executable_name = "amap-mcp-server.exe" if sys.platform.startswith("win") else "amap-mcp-server"
    local_candidates = [
        executable_dir / executable_name,
        executable_dir / "Scripts" / executable_name,
        executable_dir.parent / "Scripts" / executable_name,
    ]
    for local_server in local_candidates:
        if local_server.exists():
            return str(local_server), ["stdio"]

    resolved_server = shutil.which("amap-mcp-server")
    if resolved_server:
        return resolved_server, ["stdio"]

    resolved_uvx = shutil.which("uvx")
    if resolved_uvx:
        return resolved_uvx, ["amap-mcp-server", "stdio"]

    return "uvx", ["amap-mcp-server", "stdio"]


def _command_preview(command: str, args: List[str]) -> str:
    return " ".join([command, *args]).strip()


def _amap_mcp_config() -> dict:
    settings = get_settings()
    command, args = _find_amap_mcp_command()
    command_exists = Path(command).exists() or shutil.which(command) is not None
    print("  - 创建共享 MCP 工具...")
    print(f"🔑 使用环境变量: AMAP_MAPS_API_KEY={configured(settings.amap_maps_api_key)}")
    print(f"📝 使用 Stdio 传输 (命令): {_command_preview(command, args)}")
    if not command_exists:
        print(f"⚠️ 未找到 MCP 启动命令: {command}，工具调用时将使用高德 REST API 兜底")
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
    config = _amap_mcp_config()["amap"]
    return StdioServerParameters(
        command=config["command"],
        args=config["args"],
        env=config["env"],
    )


def parse_jsonish(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    text = str(raw)
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            return {"raw": text}
    return {"raw": text}


def _decode_mcp_result(result: Any) -> Any:
    if getattr(result, "isError", False):
        raise AmapMCPToolError(f"MCP tool returned error: {getattr(result, 'content', result)}")

    structured_content = getattr(result, "structuredContent", None)
    if structured_content:
        value = structured_content.get("result", structured_content)
    else:
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
    """Reuse one stdio MCP session so calls behave like the reference MCPTool."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._exit_stack: Optional[AsyncExitStack] = None
        self._session: Optional[ClientSession] = None
        self._tools: List[Any] = []

    async def _connect_locked(self) -> None:
        if self._session is not None:
            return

        params = get_mcp_server_params()
        print("🔗 连接到 MCP 服务器并加载工具...")
        print(f"   MCP 启动命令: {_command_preview(params.command, list(params.args or []))}")

        stack = AsyncExitStack()
        try:
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
        async with self._lock:
            await self._connect_locked()
            return list(self._tools)

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        async with self._lock:
            await self._connect_locked()
            assert self._session is not None

            available_tools = [tool.name for tool in self._tools]
            matched_tool = next(
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
                await self.close()
                raise AmapMCPUnavailableError(f"MCP call failed: {exc}") from exc

    async def close(self) -> None:
        stack = self._exit_stack
        self._exit_stack = None
        self._session = None
        self._tools = []
        if stack is not None:
            await stack.aclose()


_amap_mcp_client = AmapMCPClient()


async def get_mcp_tools():
    return await _amap_mcp_client.list_tools()


async def get_amap_tool_node():
    """Build a LangGraph ToolNode with the loaded AMap MCP tools."""
    from langgraph.prebuilt import ToolNode

    return ToolNode(await get_mcp_tools())


async def mcp_health() -> dict:
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
    return await _amap_mcp_client.call_tool(tool_name, arguments)


async def close_amap_mcp_client() -> None:
    await _amap_mcp_client.close()


def _amap_rest_key() -> str:
    settings = get_settings()
    return settings.amap_api_key or settings.amap_maps_api_key


async def _amap_rest_get(path: str, params: Dict[str, Any]) -> Any:
    key = _amap_rest_key()
    if not key:
        raise ValueError("未配置 AMAP_API_KEY 或 AMAP_MAPS_API_KEY")
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
    city = arguments.get("city")
    geocode = await _amap_rest_get("geocode/geo", {"address": city, "city": city})
    geocodes = geocode.get("geocodes") or []
    adcode = geocodes[0].get("adcode") if geocodes else city
    return await _amap_rest_get("weather/weatherInfo", {"city": adcode, "extensions": "all"})


async def _amap_search_detail(arguments: Dict[str, Any]) -> Any:
    return await _amap_rest_get("place/detail", {"id": arguments.get("id")})


async def call_amap_rest_fallback(tool_name: str, arguments: Dict[str, Any]) -> Any:
    if tool_name.endswith("maps_text_search") or tool_name == "maps_text_search":
        return await _amap_text_search(arguments)
    if tool_name.endswith("maps_weather") or tool_name == "maps_weather":
        return await _amap_weather(arguments)
    if tool_name.endswith("maps_search_detail") or tool_name == "maps_search_detail":
        return await _amap_search_detail(arguments)
    raise ValueError(f"暂无高德 REST API 兜底实现: {tool_name}")


def _first_list(data: Any, keys: List[str]) -> List[Any]:
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
    if isinstance(value, dict):
        lng = value.get("longitude") or value.get("lng")
        lat = value.get("latitude") or value.get("lat")
    elif isinstance(value, str) and "," in value:
        lng, lat = value.split(",", 1)
    else:
        return None
    try:
        return Location(longitude=float(lng), latitude=float(lat))
    except Exception:
        return None


def normalize_pois(raw: Any) -> List[POIInfo]:
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
    data = parse_jsonish(raw)
    if not isinstance(data, dict):
        return None
    route = data.get("route") if isinstance(data.get("route"), dict) else data
    paths = route.get("paths") or route.get("transits") or []
    first = paths[0] if isinstance(paths, list) and paths else route
    try:
        distance = float(first.get("distance") or route.get("distance") or 0)
        duration = int(float(first.get("duration") or route.get("duration") or 0))
    except Exception:
        distance = 0
        duration = 0
    description = first.get("instruction") or first.get("description") or json.dumps(data, ensure_ascii=False)[:500]
    if distance <= 0 and duration <= 0:
        return None
    return RouteInfo(distance=distance, duration=duration, route_type=route_type, description=str(description))


async def search_poi(keywords: str, city: str, citylimit: bool = True) -> List[POIInfo]:
    raw = await call_amap_tool(
        "maps_text_search",
        {"keywords": keywords, "city": city, "citylimit": str(citylimit).lower()},
    )
    return normalize_pois(raw)


async def get_weather(city: str) -> List[WeatherInfo]:
    raw = await call_amap_tool("maps_weather", {"city": city})
    return normalize_weather(raw)


async def plan_route(
    origin_address: str,
    destination_address: str,
    route_type: str,
    origin_city: Optional[str] = None,
    destination_city: Optional[str] = None,
) -> Optional[RouteInfo]:
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
    raw = await call_amap_tool("maps_search_detail", {"id": poi_id})
    parsed = parse_jsonish(raw)
    return parsed if isinstance(parsed, dict) else {"data": parsed}
