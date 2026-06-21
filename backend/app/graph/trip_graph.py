"""LangGraph workflow for trip planning."""

from datetime import datetime, timedelta
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from app.graph.prompts import REPAIR_SYSTEM_PROMPT, TRIP_PLAN_SYSTEM_PROMPT
from app.graph.state import TripGraphState
from app.core.logging_utils import log_section, preview
from app.models.schemas import Attraction, Budget, DayPlan, Location, Meal, TripPlan, TripRequest, WeatherInfo
from app.services.llm import get_llm
from app.services.mcp_client import call_amap_tool
from app.utils.date_utils import validate_trip_dates
from app.utils.json_utils import extract_json, stringify


def _append_error(state: TripGraphState, message: str) -> List[str]:
    return [*state.get("errors", []), message]


async def validate_request(state: TripGraphState) -> Dict[str, Any]:
    request = state["request"]
    log_section("🚀 开始旅行规划流程")
    print(f"目的地: {request.city}")
    print(f"日期: {request.start_date} 至 {request.end_date}")
    print(f"天数: {request.travel_days}天")
    print(f"偏好: {', '.join(request.preferences) if request.preferences else '无'}")
    validate_trip_dates(request.start_date, request.end_date, request.travel_days)
    print("✅ 请求参数校验通过")
    return {"errors": state.get("errors", [])}


async def search_attractions_llm(state: TripGraphState) -> Dict[str, Any]:
    request = state["request"]
    keyword = request.preferences[0] if request.preferences else "景点"
    print(f"\n📍 步骤1: 搜索景点... 关键词: {keyword}")
    try:
        raw = await call_amap_tool(
            "maps_text_search",
            {"keywords": keyword, "city": request.city, "citylimit": "true"},
        )
        print(f"✅ 景点搜索完成: {preview(raw)}")
        return {"attractions_raw": raw}
    except Exception as exc:
        print(f"❌ 景点 MCP 调用失败: {exc}")
        return {"attractions_raw": "", "errors": _append_error(state, f"景点 MCP 调用失败: {exc}")}


async def search_weather_llm(state: TripGraphState) -> Dict[str, Any]:
    request = state["request"]
    print("\n🌤️ 步骤2: 查询天气...")
    try:
        raw = await call_amap_tool("maps_weather", {"city": request.city})
        print(f"✅ 天气查询完成: {preview(raw)}")
        return {"weather_raw": raw}
    except Exception as exc:
        print(f"❌ 天气 MCP 调用失败: {exc}")
        return {"weather_raw": "", "errors": _append_error(state, f"天气 MCP 调用失败: {exc}")}


async def search_hotels_llm(state: TripGraphState) -> Dict[str, Any]:
    request = state["request"]
    print("\n🏨 步骤3: 搜索酒店...")
    try:
        raw = await call_amap_tool(
            "maps_text_search",
            {"keywords": f"{request.accommodation} 酒店", "city": request.city, "citylimit": "true"},
        )
        print(f"✅ 酒店搜索完成: {preview(raw)}")
        return {"hotels_raw": raw}
    except Exception as exc:
        print(f"❌ 酒店 MCP 调用失败: {exc}")
        return {"hotels_raw": "", "errors": _append_error(state, f"酒店 MCP 调用失败: {exc}")}


def _planner_payload(state: TripGraphState) -> str:
    request = state["request"]
    return stringify(
        {
            "request": request.model_dump(),
            "attractions_raw": state.get("attractions_raw", ""),
            "weather_raw": state.get("weather_raw", ""),
            "hotels_raw": state.get("hotels_raw", ""),
            "schema_hint": TripPlan.model_json_schema(),
        }
    )


async def compose_plan_llm(state: TripGraphState) -> Dict[str, Any]:
    print("\n📋 步骤4: 生成行程计划...")
    llm = get_llm()
    response = await llm.ainvoke(
        [
            SystemMessage(content=TRIP_PLAN_SYSTEM_PROMPT),
            HumanMessage(content=_planner_payload(state)),
        ]
    )
    print(f"✅ 行程规划结果: {preview(response.content)}")
    return {"draft_plan": response.content}


async def validate_trip_plan(state: TripGraphState) -> Dict[str, Any]:
    request = state["request"]
    draft = state.get("draft_plan", "")
    try:
        plan = TripPlan.model_validate(extract_json(str(draft)))
        print("✅ 行程 JSON 校验通过")
        return {"trip_plan": normalize_trip_plan(plan, request)}
    except Exception as first_exc:
        print(f"⚠️ 行程 JSON 首次校验失败, 尝试修复: {first_exc}")
        try:
            llm = get_llm()
            repaired = await llm.ainvoke(
                [
                    SystemMessage(content=REPAIR_SYSTEM_PROMPT),
                    HumanMessage(
                        content=stringify(
                            {
                                "request": request.model_dump(),
                                "validation_error": str(first_exc),
                                "draft": draft,
                                "schema": TripPlan.model_json_schema(),
                            }
                        )
                    ),
                ]
            )
            plan = TripPlan.model_validate(extract_json(str(repaired.content)))
            print("✅ 行程 JSON 修复并校验通过")
            return {"trip_plan": normalize_trip_plan(plan, request)}
        except Exception as second_exc:
            print(f"❌ 行程 JSON 修复失败, 使用备用行程: {second_exc}")
            return {
                "trip_plan": create_fallback_plan(request),
                "errors": _append_error(
                    state,
                    f"Pydantic 校验失败, 已使用备用行程: {first_exc}; repair failed: {second_exc}",
                ),
            }


async def finalize_response(state: TripGraphState) -> Dict[str, Any]:
    plan = state.get("trip_plan")
    if plan:
        log_section("✅ 旅行计划生成完成!")
        print(f"城市: {plan.city}")
        print(f"日期: {plan.start_date} 至 {plan.end_date}")
        print(f"行程天数: {len(plan.days)}")
    return {"trip_plan": state.get("trip_plan")}


def normalize_trip_plan(plan: TripPlan, request: TripRequest) -> TripPlan:
    start = datetime.strptime(request.start_date, "%Y-%m-%d")
    for index, day in enumerate(plan.days):
        day.day_index = index
        day.date = (start + timedelta(days=index)).strftime("%Y-%m-%d")
    return plan


def create_fallback_plan(request: TripRequest) -> TripPlan:
    start = datetime.strptime(request.start_date, "%Y-%m-%d")
    days: List[DayPlan] = []
    weather: List[WeatherInfo] = []

    for index in range(request.travel_days):
        current = start + timedelta(days=index)
        date = current.strftime("%Y-%m-%d")
        weather.append(WeatherInfo(date=date))
        attractions = [
            Attraction(
                name=f"{request.city}推荐景点 {item + 1}",
                address=f"{request.city}市",
                location=Location(longitude=116.397128 + index * 0.01 + item * 0.005, latitude=39.916527 + index * 0.01),
                visit_duration=120,
                description=f"根据您的偏好为第 {index + 1} 天安排的{request.city}景点。",
                category=request.preferences[0] if request.preferences else "景点",
                ticket_price=0,
            )
            for item in range(2)
        ]
        meals = [
            Meal(type="breakfast", name="当地早餐", description="选择酒店或附近早餐店", estimated_cost=30),
            Meal(type="lunch", name="午餐推荐", description="安排在景点附近用餐", estimated_cost=60),
            Meal(type="dinner", name="晚餐推荐", description="体验当地特色餐饮", estimated_cost=90),
        ]
        days.append(
            DayPlan(
                date=date,
                day_index=index,
                description=f"第 {index + 1} 天游览安排",
                transportation=request.transportation,
                accommodation=request.accommodation,
                attractions=attractions,
                meals=meals,
            )
        )

    meal_total = request.travel_days * 180
    return TripPlan(
        city=request.city,
        start_date=request.start_date,
        end_date=request.end_date,
        days=days,
        weather_info=weather,
        overall_suggestions="当前外部服务或模型输出不可用, 已生成可编辑的备用行程。建议出发前核对景点开放时间和交通情况。",
        budget=Budget(
            total_attractions=0,
            total_hotels=0,
            total_meals=meal_total,
            total_transportation=0,
            total=meal_total,
        ),
    )


def build_trip_graph():
    graph = StateGraph(TripGraphState)
    graph.add_node("validate_request", validate_request)
    graph.add_node("search_attractions_llm", search_attractions_llm)
    graph.add_node("search_weather_llm", search_weather_llm)
    graph.add_node("search_hotels_llm", search_hotels_llm)
    graph.add_node("compose_plan_llm", compose_plan_llm)
    graph.add_node("validate_trip_plan", validate_trip_plan)
    graph.add_node("finalize_response", finalize_response)

    graph.set_entry_point("validate_request")
    graph.add_edge("validate_request", "search_attractions_llm")
    graph.add_edge("search_attractions_llm", "search_weather_llm")
    graph.add_edge("search_weather_llm", "search_hotels_llm")
    graph.add_edge("search_hotels_llm", "compose_plan_llm")
    graph.add_edge("compose_plan_llm", "validate_trip_plan")
    graph.add_edge("validate_trip_plan", "finalize_response")
    graph.add_edge("finalize_response", END)
    return graph.compile()


trip_graph = build_trip_graph()
