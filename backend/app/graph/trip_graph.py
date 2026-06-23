"""旅行规划 LangGraph 工作流。

这个模块是 AI 行程生成的核心流程编排层，负责把一次旅行规划请求拆成多个节点执行：
1. 校验用户请求；
2. 调用高德地图能力搜索景点、天气、酒店；
3. 将外部数据和用户需求交给 LLM 生成结构化行程；
4. 校验并修复 LLM 返回的 JSON；
5. 在外部服务或模型失败时生成备用行程；
6. 使用 LangGraph 将这些步骤串成完整工作流。
"""

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
    """向图状态中的错误列表追加一条错误信息。

    LangGraph 的节点通常返回局部状态更新，所以这里不直接修改原 state，
    而是基于已有 errors 创建一个新列表返回，避免共享状态被意外污染。
    """
    return [*state.get("errors", []), message]


async def validate_request(state: TripGraphState) -> Dict[str, Any]:
    """校验用户提交的旅行规划请求。

    这是整个图的入口节点，主要确认日期范围和旅行天数是否一致。
    如果这里校验失败，后续搜索和 LLM 生成就没有继续执行的意义。
    """
    request = state["request"]
    log_section("🚀 开始旅行规划流程")
    print(f"目的地: {request.city}")
    print(f"日期: {request.start_date} 至 {request.end_date}")
    print(f"天数: {request.travel_days}天")
    print(f"偏好: {', '.join(request.preferences) if request.preferences else '无'}")

    # 校验开始日期、结束日期和旅行天数是否匹配，例如 7 月 1 日到 7 月 3 日应为 3 天。
    validate_trip_dates(request.start_date, request.end_date, request.travel_days)
    print("✅ 请求参数校验通过")
    return {"errors": state.get("errors", [])}


async def search_attractions_llm(state: TripGraphState) -> Dict[str, Any]:
    """搜索景点相关原始数据。

    这里根据用户偏好选择搜索关键词；如果用户没有偏好，就默认搜索“景点”。
    搜索结果暂时保存为原始数据，后续由 LLM 结合天气、酒店等信息统一规划。
    """
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
        # 景点搜索失败时不中断整个图，而是记录错误并让后续 LLM 或备用行程继续兜底。
        print(f"❌ 景点 MCP 调用失败: {exc}")
        return {"attractions_raw": "", "errors": _append_error(state, f"景点 MCP 调用失败: {exc}")}


async def search_weather_llm(state: TripGraphState) -> Dict[str, Any]:
    """查询目的地天气原始数据。

    天气会作为 LLM 生成行程时的重要参考，例如雨天减少户外景点、炎热天气降低步行强度。
    """
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
    """搜索酒店相关原始数据。

    酒店搜索关键词由用户住宿偏好和“酒店”组合而成，
    例如“经济型 酒店”“舒适型 酒店”，用于给 LLM 提供住宿候选参考。
    """
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
    """构造发送给 LLM 的规划输入。

    这里会把用户请求、景点原始数据、天气原始数据、酒店原始数据，
    以及 TripPlan 的 JSON Schema 一起传给模型，帮助模型按后端期望的结构输出。
    """
    request = state["request"]
    return stringify(
        {
            "request": request.model_dump(),
            "attractions_raw": state.get("attractions_raw", ""),
            "weather_raw": state.get("weather_raw", ""),
            "hotels_raw": state.get("hotels_raw", ""),
            # schema_hint 告诉 LLM 最终必须生成什么结构，降低输出格式不匹配的概率。
            "schema_hint": TripPlan.model_json_schema(),
        }
    )


async def compose_plan_llm(state: TripGraphState) -> Dict[str, Any]:
    """调用 LLM 生成初版旅行计划。

    该节点只负责生成草稿，不在这里做最终可信校验。
    后续 validate_trip_plan 节点会负责 JSON 提取、Pydantic 校验和必要的修复。
    """
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
    """校验、修复或兜底生成旅行计划。

    LLM 输出可能不是严格 JSON，或者字段不符合 TripPlan 模型。
    因此这里采用三层保护：
    1. 首次提取 JSON 并用 Pydantic 校验；
    2. 失败后让 LLM 根据错误信息修复；
    3. 修复仍失败时生成本地备用行程，保证接口有可返回结果。
    """
    request = state["request"]
    draft = state.get("draft_plan", "")
    try:
        # extract_json 负责从 LLM 文本中提取 JSON；TripPlan.model_validate 负责结构校验。
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
    """输出最终日志并返回图的最终结果。"""
    plan = state.get("trip_plan")
    if plan:
        log_section("✅ 旅行计划生成完成!")
        print(f"城市: {plan.city}")
        print(f"日期: {plan.start_date} 至 {plan.end_date}")
        print(f"行程天数: {len(plan.days)}")
    return {"trip_plan": state.get("trip_plan")}


def normalize_trip_plan(plan: TripPlan, request: TripRequest) -> TripPlan:
    """统一修正行程中的日期和天数索引。

    即使 LLM 返回了 day_index 或 date，也以用户请求的开始日期为准重新计算，
    避免模型生成的日期和用户输入不一致。
    """
    start = datetime.strptime(request.start_date, "%Y-%m-%d")
    for index, day in enumerate(plan.days):
        day.day_index = index
        day.date = (start + timedelta(days=index)).strftime("%Y-%m-%d")
    return plan


def create_fallback_plan(request: TripRequest) -> TripPlan:
    """创建本地备用旅行计划。

    当外部地图服务不可用、LLM 输出不可解析或修复失败时，
    该函数会基于用户请求生成一个结构完整但内容较通用的备用行程，
    确保 API 不会因为 AI 输出失败而完全没有结果。
    """
    start = datetime.strptime(request.start_date, "%Y-%m-%d")
    days: List[DayPlan] = []
    weather: List[WeatherInfo] = []

    for index in range(request.travel_days):
        current = start + timedelta(days=index)
        date = current.strftime("%Y-%m-%d")
        weather.append(WeatherInfo(date=date))

        # 备用景点使用虚拟推荐名称和近似坐标，保证前端仍然能展示基本行程结构。
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

        # 餐饮部分使用固定早中晚结构，让备用行程也能满足前端展示要求。
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
    """构建并编译旅行规划 LangGraph。

    每个 add_node 都注册一个处理节点；每条 add_edge 都表示节点之间的执行顺序。
    当前流程是线性的：校验请求 -> 搜索外部数据 -> LLM 生成 -> 校验修复 -> 输出结果。
    """
    graph = StateGraph(TripGraphState)

    # 注册图节点。每个节点都是一个函数，接收 state 并返回需要合并进 state 的局部结果。
    graph.add_node("validate_request", validate_request)
    graph.add_node("search_attractions_llm", search_attractions_llm)
    graph.add_node("search_weather_llm", search_weather_llm)
    graph.add_node("search_hotels_llm", search_hotels_llm)
    graph.add_node("compose_plan_llm", compose_plan_llm)
    graph.add_node("validate_trip_plan", validate_trip_plan)
    graph.add_node("finalize_response", finalize_response)

    # 设置入口节点，并用边定义节点执行顺序。
    graph.set_entry_point("validate_request")
    graph.add_edge("validate_request", "search_attractions_llm")
    graph.add_edge("search_attractions_llm", "search_weather_llm")
    graph.add_edge("search_weather_llm", "search_hotels_llm")
    graph.add_edge("search_hotels_llm", "compose_plan_llm")
    graph.add_edge("compose_plan_llm", "validate_trip_plan")
    graph.add_edge("validate_trip_plan", "finalize_response")
    graph.add_edge("finalize_response", END)
    return graph.compile()


# 模块加载时直接编译图，路由层可以导入 trip_graph 后直接调用。
trip_graph = build_trip_graph()
